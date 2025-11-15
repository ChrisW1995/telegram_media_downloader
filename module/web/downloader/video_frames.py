"""Message Downloader 影片關鍵幀提取 API 模組 (Sprite Sheet 版本) - Quart async

處理 /api/video/frames/* 相關的影片幀提取功能
使用 Sprite Sheet 技術：只生成一張包含所有縮圖的大圖，節省帶寬和處理時間
"""

from quart import Blueprint, jsonify, session
from loguru import logger
import base64
import subprocess
import tempfile
import os
import hashlib
import json
from pathlib import Path
from ..core.decorators import require_message_downloader_auth
from ..core.error_handlers import error_response, handle_api_exception, success_response
from ..core.session_manager import get_session_manager

# 創建 Blueprint
bp = Blueprint('message_downloader_video_frames', __name__)

# Session 管理器
session_manager = get_session_manager()

# Global app instance
_app = None

def set_app_instance(app):
    """Set the global app instance for accessing config"""
    global _app
    _app = app


# 快取目錄
CACHE_DIR = Path(tempfile.gettempdir()) / 'tgdl_video_sprites_cache'
CACHE_DIR.mkdir(exist_ok=True)

# 快取過期時間（秒） - 7 天
CACHE_EXPIRY = 7 * 24 * 60 * 60

# Sprite 配置
SPRITE_GRID_SIZE = 4  # 4x4 網格 = 16 個縮圖
SPRITE_FRAMES = 16
SPRITE_THUMB_WIDTH = 160  # 每個縮圖的寬度


def get_cache_key(chat_id: int, message_id: int) -> str:
    """生成快取鍵"""
    return hashlib.md5(f"{chat_id}_{message_id}".encode()).hexdigest()


def get_cache_path(cache_key: str) -> Path:
    """獲取快取文件路徑"""
    return CACHE_DIR / f"{cache_key}.json"


def is_cache_valid(cache_path: Path) -> bool:
    """檢查快取是否有效"""
    if not cache_path.exists():
        return False

    # 檢查快取是否過期
    import time
    cache_age = time.time() - cache_path.stat().st_mtime
    return cache_age < CACHE_EXPIRY


def generate_video_sprite(video_path: str, output_path: Path) -> dict:
    """
    使用 ffmpeg 生成影片 sprite sheet

    Args:
        video_path: 影片文件路徑
        output_path: 輸出 sprite 文件路徑

    Returns:
        包含 sprite 信息的字典，失敗返回 None
    """
    try:
        # 獲取影片時長
        probe_cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]

        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            logger.error(f"ffprobe 失敗: {result.stderr}")
            return None

        try:
            duration = float(result.stdout.strip())
        except ValueError:
            logger.error(f"無法解析影片時長: {result.stdout}")
            return None

        logger.info(f"影片時長: {duration} 秒，生成 {SPRITE_FRAMES} 幀的 sprite sheet")

        # 使用 ffmpeg 的 fps 和 tile 濾鏡生成 sprite
        # fps=1/X 表示每 X 秒取一幀
        frame_interval = duration / SPRITE_FRAMES

        sprite_cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vf', f'fps=1/{frame_interval},scale={SPRITE_THUMB_WIDTH}:-1,tile={SPRITE_GRID_SIZE}x{SPRITE_GRID_SIZE}',
            '-frames:v', '1',
            '-q:v', '3',  # JPEG 品質 (2-5 為高品質)
            '-y',
            str(output_path)
        ]

        logger.debug(f"執行 ffmpeg: {' '.join(sprite_cmd)}")

        result = subprocess.run(sprite_cmd, capture_output=True, timeout=60)

        if result.returncode == 0 and output_path.exists():
            file_size = output_path.stat().st_size
            logger.info(f"✅ 成功生成 sprite sheet: {output_path} ({file_size / 1024:.1f} KB)")

            return {
                'grid_size': SPRITE_GRID_SIZE,
                'frame_count': SPRITE_FRAMES,
                'thumb_width': SPRITE_THUMB_WIDTH,
                'thumb_height': int(SPRITE_THUMB_WIDTH * 9 / 16),  # 假設 16:9
                'file_size': file_size
            }
        else:
            logger.error(f"生成 sprite sheet 失敗: {result.stderr.decode()}")
            return None

    except subprocess.TimeoutExpired:
        logger.error("ffmpeg 處理超時")
        return None
    except Exception as e:
        logger.error(f"生成 sprite sheet 時發生錯誤: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


@bp.route("/<chat_id>/<int:message_id>", methods=["GET"])
@require_message_downloader_auth
@handle_api_exception
async def get_video_frames(chat_id, message_id):
    """獲取影片的 sprite sheet (Quart async)"""
    try:
        # 轉換 chat_id 為整數
        try:
            chat_id = int(chat_id)
        except ValueError:
            return error_response('無效的 chat_id')

        logger.info(f"Video Sprite API: chat_id={chat_id}, message_id={message_id}")

        # 檢查快取
        cache_key = get_cache_key(chat_id, message_id)
        cache_path = get_cache_path(cache_key)

        if is_cache_valid(cache_path):
            logger.info(f"使用快取的 sprite: {cache_key}")
            with open(cache_path, 'r') as f:
                cached_data = json.load(f)
            return success_response(
                data=cached_data,
                message="從快取讀取 sprite"
            )

        # 檢查會話
        session_key = session.get('message_downloader_session_key')
        if not session_key:
            return error_response('會話已過期，請重新登入', 401)

        # 使用與 thumbnails API 相同的認證邏輯
        from ..downloader.groups import restore_session_if_needed
        from module.multiuser_auth import get_auth_manager

        if not restore_session_if_needed(session_key):
            return error_response('會話恢復失敗，請重新登入', 401)

        auth_manager = get_auth_manager()
        if not auth_manager or not hasattr(auth_manager, 'active_clients'):
            return error_response('客戶端不可用')

        # 查找客戶端
        client = auth_manager.active_clients.get(session_key)
        if not client:
            user_id = session.get('message_downloader_user_id')
            if user_id:
                client = auth_manager.active_clients.get(str(user_id))

        if not client:
            for key in auth_manager.active_clients.keys():
                if key.isdigit():
                    client = auth_manager.active_clients[key]
                    break

        if not client:
            return error_response('找不到有效的客戶端連接')

        # 異步處理影片
        async def process_video():
            try:
                # 獲取訊息
                messages = await client.get_messages(chat_id=chat_id, message_ids=message_id)
                message = messages if not isinstance(messages, list) else (messages[0] if messages else None)

                if not message:
                    logger.warning(f"找不到訊息 {message_id}")
                    return None

                # 確認是影片
                if not hasattr(message, 'video') or not message.video:
                    logger.warning(f"訊息 {message_id} 不是影片")
                    return None

                # 檢查影片大小
                video_size = message.video.file_size if hasattr(message.video, 'file_size') else 0
                logger.info(f"影片大小: {video_size} bytes ({video_size / 1024 / 1024:.2f} MB)")

                # 限制最大大小為 100MB
                if video_size > 100 * 1024 * 1024:
                    logger.warning(f"影片太大 ({video_size / 1024 / 1024:.2f} MB)，跳過")
                    return {
                        'error': 'video_too_large',
                        'message': f'影片太大 ({video_size / 1024 / 1024:.1f} MB)，暫不支援預覽'
                    }

                logger.info(f"開始下載影片 {message_id}")

                # 創建臨時目錄
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)

                    # 下載影片到臨時文件
                    video_file = temp_path / f"video_{message_id}.mp4"

                    logger.info(f"開始下載影片到: {video_file}")

                    try:
                        await client.download_media(
                            message.video,
                            file_name=str(video_file)
                        )
                    except Exception as e:
                        logger.error(f"下載影片時發生錯誤: {e}")
                        return None

                    if not video_file.exists():
                        logger.error("影片下載失敗 - 文件不存在")
                        return None

                    actual_size = video_file.stat().st_size
                    logger.info(f"影片已下載: {actual_size} bytes ({actual_size / 1024 / 1024:.2f} MB)")

                    # 生成 sprite sheet
                    sprite_file = temp_path / f"sprite_{message_id}.jpg"
                    sprite_info = generate_video_sprite(str(video_file), sprite_file)

                    if not sprite_info:
                        logger.error("未能生成 sprite")
                        return None

                    # 讀取 sprite 並轉換為 base64
                    with open(sprite_file, 'rb') as f:
                        sprite_bytes = f.read()
                        sprite_base64 = base64.b64encode(sprite_bytes).decode('utf-8')
                        sprite_data_url = f"data:image/jpeg;base64,{sprite_base64}"

                    logger.info(f"成功生成 sprite ({len(sprite_bytes) / 1024:.1f} KB)")

                    # 準備回傳數據
                    cache_data = {
                        'chat_id': chat_id,
                        'message_id': message_id,
                        'sprite': sprite_data_url,
                        'grid_size': sprite_info['grid_size'],
                        'frame_count': sprite_info['frame_count'],
                        'thumb_width': sprite_info['thumb_width'],
                        'thumb_height': sprite_info['thumb_height']
                    }

                    # 快取結果
                    with open(cache_path, 'w') as f:
                        json.dump(cache_data, f)

                    logger.info(f"Sprite 已快取: {cache_key}")

                    return cache_data

            except Exception as e:
                logger.error(f"處理影片時發生錯誤: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return None

        # Quart: 直接 await，不需要 bridge pattern
        try:
            result = await process_video()
        except Exception as e:
            logger.error(f"執行異步影片處理時發生錯誤: {e}")
            result = None

        if result:
            # 檢查是否是錯誤信息
            if isinstance(result, dict) and 'error' in result:
                return error_response(result['message'])

            return success_response(
                data=result,
                message="Sprite 生成成功"
            )
        else:
            return error_response('無法生成影片 sprite')

    except Exception as e:
        logger.error(f"Video Sprite API 錯誤: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return error_response(f"處理失敗: {str(e)}")
