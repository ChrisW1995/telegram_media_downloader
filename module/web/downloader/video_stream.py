"""影片串流與會話快取管理 API (Quart async)

提供影片預覽功能，使用記憶體快取（頁面刷新後自動清除）
"""

import asyncio
import tempfile
from pathlib import Path
from quart import Blueprint, send_file, session
from loguru import logger
from ..core.decorators import require_message_downloader_auth
from ..core.error_handlers import error_response

bp = Blueprint('video_stream', __name__)

# Global app instance
_app = None

def set_app_instance(app):
    """Set the global app instance for accessing config"""
    global _app
    _app = app

# 全局記憶體快取：{session_key: {message_key: video_path}}
_video_cache = {}

def get_message_key(chat_id: int, message_id: int) -> str:
    """生成訊息唯一鍵"""
    return f"{chat_id}_{message_id}"

def get_session_key() -> str:
    """獲取當前會話鍵"""
    return session.get('user_id', 'anonymous')

def cleanup_session_cache(session_key: str):
    """清理指定會話的所有快取"""
    if session_key in _video_cache:
        cache_dict = _video_cache[session_key]

        # 刪除所有臨時檔案
        for video_path in cache_dict.values():
            try:
                if video_path and Path(video_path).exists():
                    Path(video_path).unlink()
                    logger.info(f"已清理快取影片: {video_path}")
            except Exception as e:
                logger.warning(f"清理快取失敗: {e}")

        # 移除會話快取
        del _video_cache[session_key]
        logger.info(f"會話 {session_key} 的影片快取已清除")

def get_cached_video(session_key: str, message_key: str):
    """獲取快取的影片路徑"""
    if session_key in _video_cache:
        return _video_cache[session_key].get(message_key)
    return None

def cache_video(session_key: str, message_key: str, video_path: str):
    """快取影片路徑"""
    if session_key not in _video_cache:
        _video_cache[session_key] = {}
    _video_cache[session_key][message_key] = video_path
    logger.info(f"已快取影片: {message_key} -> {video_path}")

@bp.route('/<chat_id>/<int:message_id>', methods=['GET', 'HEAD'])
@require_message_downloader_auth
async def get_video_stream(chat_id: str, message_id: int):
    """獲取影片串流（會話級別快取） - Quart async"""
    from quart import Response, request

    try:
        # 轉換 chat_id 為整數（支援負數）
        chat_id = int(chat_id)

        # 記錄所有請求
        logger.info(f"📥 收到 {request.method} 請求: chat_id={chat_id}, message_id={message_id}")

        # HEAD 請求：檢查檔案大小並返回適當的狀態碼
        if request.method == 'HEAD':
            logger.info("🔍 執行 HEAD 請求檔案大小檢查...")
            # 獲取認證客戶端
            from module.multiuser_auth import get_auth_manager
            auth_manager = get_auth_manager()

            if not auth_manager or not auth_manager.active_clients:
                return error_response('沒有可用的已認證客戶端', 401)

            client_key = list(auth_manager.active_clients.keys())[0]
            client = auth_manager.active_clients[client_key]

            # 獲取訊息檢查檔案大小
            logger.info("📞 調用 get_messages...")
            result = await client.get_messages(chat_id=chat_id, message_ids=message_id)
            message = result if not isinstance(result, list) else result[0] if result else None
            logger.info(f"📬 收到訊息: {message is not None}, 有影片: {message.video is not None if message else False}")

            if not message or not message.video:
                logger.warning("❌ 訊息不包含影片")
                return error_response('訊息不包含影片', 404)

            # 檢查檔案大小
            file_size_mb = message.video.file_size / 1024 / 1024
            logger.info(f"📏 影片大小: {file_size_mb:.2f} MB")

            # 提示：對於大檔案（>200MB），建議使用 native API 端點以獲得更好的串流體驗
            # 但由於已實現 Range Request 支援，所有大小的檔案都可以播放
            if file_size_mb > 500:  # 提高限制到 500 MB
                logger.info(f"🚫 HEAD 請求：影片太大 ({file_size_mb:.2f} MB > 500 MB)，返回 413")
                return error_response(
                    f"影片太大 ({file_size_mb:.1f} MB)，超過限制 (500 MB)。請使用下載功能。",
                    413
                )

            # 檔案大小可接受，返回成功
            logger.info(f"✅ HEAD 請求：影片大小可接受 ({file_size_mb:.2f} MB)，返回 200")
            response = Response('', status=200)
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Content-Type'] = 'video/mp4'
            response.headers['Content-Length'] = str(message.video.file_size)
            return response

        session_key = get_session_key()
        message_key = get_message_key(chat_id, message_id)

        # 檢查記憶體快取
        cached_path = get_cached_video(session_key, message_key)
        if cached_path and Path(cached_path).exists():
            logger.info(f"使用快取影片: {message_key}")
            return await send_file(
                cached_path,
                mimetype='video/mp4',
                as_attachment=False,
                attachment_filename=f'video_{message_id}.mp4',
                conditional=True  # 啟用 Range Requests 支援
            )

        # 定義異步下載函數
        async def _download_video():
            # 獲取認證客戶端
            from module.multiuser_auth import get_auth_manager
            auth_manager = get_auth_manager()

            if not auth_manager or not auth_manager.active_clients:
                return None

            client_key = list(auth_manager.active_clients.keys())[0]
            client = auth_manager.active_clients[client_key]

            # 獲取訊息
            result = await client.get_messages(chat_id=chat_id, message_ids=message_id)
            message = result if not isinstance(result, list) else result[0] if result else None

            if not message or not message.video:
                return None

            # 檢查檔案大小
            file_size_mb = message.video.file_size / 1024 / 1024
            logger.info(f"影片大小: {file_size_mb:.2f} MB")

            # 檔案大小限制：超過 500MB 的影片不適合線上播放
            # 對於超大檔案，建議直接下載
            if file_size_mb > 500:
                logger.warning(f"影片太大 ({file_size_mb:.2f} MB)，超過線上播放限制（500MB）")
                return {'error': 'file_too_large', 'size_mb': file_size_mb, 'limit_mb': 500}

            # 下載影片到臨時檔案（會話結束後自動刪除）
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,  # 手動控制刪除
                suffix='.mp4',
                prefix=f'tgdl_video_{message_id}_'
            )
            temp_path = temp_file.name
            temp_file.close()

            logger.info(f"開始下載影片到臨時檔案: {temp_path}")

            downloaded_path = await client.download_media(
                message.video,
                file_name=temp_path
            )

            logger.success(f"影片下載完成: {downloaded_path}")

            # 使用 FFmpeg 優化 MP4 結構，將 moov atom 移至開頭
            # 這讓瀏覽器能夠在下載部分檔案後就開始播放（漸進式播放）
            try:
                import subprocess

                optimized_path = str(Path(downloaded_path).with_suffix('')) + '_faststart.mp4'
                logger.info(f"正在優化影片結構（faststart）...")

                result = subprocess.run(
                    [
                        'ffmpeg',
                        '-i', downloaded_path,
                        '-c', 'copy',  # 不重新編碼，只調整結構
                        '-movflags', 'faststart',  # 將 moov atom 移至開頭
                        '-y',  # 覆蓋輸出檔案
                        optimized_path
                    ],
                    capture_output=True,
                    timeout=30,
                    check=True
                )

                # 刪除原始檔案，使用優化後的檔案
                Path(downloaded_path).unlink()
                downloaded_path = optimized_path

                logger.success(f"影片已優化為漸進式播放格式: {optimized_path}")

            except subprocess.TimeoutExpired:
                logger.warning(f"FFmpeg 優化超時，使用原始檔案")
            except subprocess.CalledProcessError as e:
                stderr = e.stderr.decode('utf-8', errors='ignore') if e.stderr else ''
                logger.warning(f"FFmpeg 優化失敗，使用原始檔案: {stderr[:200]}")
            except Exception as e:
                logger.warning(f"FFmpeg 優化失敗，使用原始檔案: {e}")

            return downloaded_path

        # Quart: 直接 await，不需要 bridge pattern
        result = await _download_video()

        # 處理錯誤情況
        if not result:
            return error_response('訊息不包含影片或下載失敗', 404)

        # 檢查是否返回錯誤字典（例如檔案太大）
        if isinstance(result, dict) and 'error' in result:
            if result['error'] == 'file_too_large':
                return error_response(
                    f"影片太大 ({result['size_mb']:.1f} MB)，超過線上播放限制 ({result['limit_mb']} MB)。請使用下載功能。",
                    413  # 413 Payload Too Large
                )
            return error_response(str(result), 400)

        downloaded_path = result

        # 快取到記憶體
        cache_video(session_key, message_key, downloaded_path)

        # 返回影片（Quart: await send_file）
        return await send_file(
            downloaded_path,
            mimetype='video/mp4',
            as_attachment=False,
            attachment_filename=f'video_{message_id}.mp4',
            conditional=True  # 啟用 Range Requests 支援
        )

    except Exception as e:
        logger.error(f"獲取影片失敗: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return error_response(f'獲取影片失敗: {str(e)}', 500)

@bp.route('/stream/<chat_id>/<int:message_id>', methods=['GET', 'HEAD'])
@require_message_downloader_auth
async def stream_video_progressive(chat_id: str, message_id: int):
    """MPEG-TS 串流：使用 FFmpeg 實時轉換 - Quart async

    使用 MPEG-TS 格式進行真正的串流播放，支持大檔案邊下載邊播放
    參考：test_quart_stream.py 的實現
    """
    from quart import Response, request
    import asyncio

    try:
        # 轉換 chat_id 為整數（支援負數）
        chat_id = int(chat_id)

        # HEAD 請求：只返回 headers，不傳送實際內容
        if request.method == 'HEAD':
            response = await Response().make_response()
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Content-Type'] = 'video/mp2t'  # MPEG-TS mimetype
            response.headers['Cache-Control'] = 'no-cache'
            return response

        logger.info(f"🎬 開始 MPEG-TS 串流: chat_id={chat_id}, message_id={message_id}")

        async def async_stream_mpegts():
            """使用 FFmpeg 轉換為 MPEG-TS 並串流"""
            try:
                # 獲取認證客戶端
                from module.multiuser_auth import get_auth_manager
                auth_manager = get_auth_manager()

                if not auth_manager or not auth_manager.active_clients:
                    logger.error("❌ 沒有可用的已認證客戶端")
                    return

                client_key = list(auth_manager.active_clients.keys())[0]
                client = auth_manager.active_clients[client_key]
                logger.info(f"✅ 使用客戶端: {client_key}")

                # 獲取訊息
                result = await client.get_messages(chat_id=chat_id, message_ids=message_id)
                message = result if not isinstance(result, list) else result[0] if result else None

                if not message or not message.video:
                    logger.error(f"❌ 訊息 {message_id} 不包含影片")
                    return

                video_size_mb = message.video.file_size / 1024 / 1024
                logger.info(f"📹 影片大小: {video_size_mb:.2f} MB")

                # FFmpeg 命令：轉換為 MPEG-TS 格式（優化低延遲）
                ffmpeg_cmd = [
                    'ffmpeg',
                    '-loglevel', 'warning',       # 顯示警告和錯誤
                    '-fflags', '+genpts',         # 生成 PTS
                    '-i', 'pipe:0',               # 從 stdin 讀取

                    # 視頻編碼：使用硬體加速
                    '-c:v', 'h264_videotoolbox',  # macOS 硬體編碼器
                    '-b:v', '1.5M',               # 降低位元率
                    '-maxrate', '2M',
                    '-bufsize', '1.5M',           # 減小緩衝區
                    '-profile:v', 'baseline',     # H.264 baseline
                    '-g', '30',                   # GOP 大小（關鍵幀間隔）
                    '-realtime', '1',             # 實時編碼模式

                    # 音頻編碼
                    '-c:a', 'aac',
                    '-b:a', '96k',                # 降低音頻位元率

                    # 輸出格式：MPEG-TS（真正的串流格式）
                    '-f', 'mpegts',
                    '-muxdelay', '0.1',           # 降低 mux 延遲
                    'pipe:1'  # 輸出到 stdout
                ]

                # 啟動 FFmpeg 進程
                ffmpeg_process = await asyncio.create_subprocess_exec(
                    *ffmpeg_cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                logger.success(f"✅ FFmpeg 進程已啟動 (PID: {ffmpeg_process.pid})")

                # 異步寫入 Telegram 數據到 FFmpeg stdin
                async def write_to_ffmpeg():
                    try:
                        chunk_count = 0
                        total_bytes = 0

                        async for chunk in client.stream_media(message.video):
                            chunk_count += 1
                            total_bytes += len(chunk)

                            # 每 50 塊記錄一次
                            if chunk_count % 50 == 0:
                                mb = total_bytes / 1024 / 1024
                                logger.info(f"📥 已下載 {chunk_count} 塊 (~{mb:.1f} MB) → FFmpeg")

                            ffmpeg_process.stdin.write(chunk)
                            await ffmpeg_process.stdin.drain()

                        # 關閉 stdin 通知 FFmpeg 輸入完成
                        ffmpeg_process.stdin.close()
                        await ffmpeg_process.stdin.wait_closed()
                        logger.success(f"✅ Telegram 下載完成: {chunk_count} 塊, {total_bytes / 1024 / 1024:.2f} MB")

                    except Exception as e:
                        logger.error(f"❌ 寫入 FFmpeg 失敗: {e}")
                        if not ffmpeg_process.stdin.is_closing():
                            ffmpeg_process.stdin.close()

                # 監控 FFmpeg stderr
                async def monitor_stderr():
                    try:
                        while True:
                            line = await ffmpeg_process.stderr.readline()
                            if not line:
                                break
                            error_msg = line.decode('utf-8', errors='ignore').strip()
                            if error_msg:
                                logger.warning(f"🔴 FFmpeg: {error_msg}")
                    except Exception:
                        pass

                # 啟動任務
                write_task = asyncio.create_task(write_to_ffmpeg())
                stderr_task = asyncio.create_task(monitor_stderr())

                # 從 FFmpeg stdout 讀取並 yield
                output_count = 0
                output_bytes = 0
                try:
                    while True:
                        chunk = await ffmpeg_process.stdout.read(65536)  # 64KB
                        if not chunk:
                            break

                        output_count += 1
                        output_bytes += len(chunk)

                        # 每 50 塊記錄一次
                        if output_count % 50 == 0:
                            mb = output_bytes / 1024 / 1024
                            logger.info(f"📤 已輸出 {output_count} 塊 (~{mb:.1f} MB) → 瀏覽器")

                        yield chunk

                    logger.success(f"✅ FFmpeg 轉換完成: {output_count} 塊, {output_bytes / 1024 / 1024:.2f} MB")

                finally:
                    # 清理
                    if ffmpeg_process.returncode is None:
                        ffmpeg_process.kill()
                        await ffmpeg_process.wait()

                    for task in [write_task, stderr_task]:
                        if not task.done():
                            task.cancel()
                            try:
                                await task
                            except asyncio.CancelledError:
                                pass

            except Exception as e:
                logger.error(f"❌ MPEG-TS 串流錯誤: {e}")
                import traceback
                logger.error(traceback.format_exc())

        # Quart 原生支援 async generator
        response = Response(async_stream_mpegts(), mimetype='video/mp2t')  # MPEG-TS mimetype
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    except Exception as e:
        logger.error(f"❌ 串流失敗: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return error_response(f'串流失敗: {str(e)}', 500)

@bp.route('/cleanup', methods=['POST'])
@require_message_downloader_auth
async def cleanup_cache():
    """清理當前會話的影片快取 - Quart async"""
    try:
        session_key = get_session_key()
        cleanup_session_cache(session_key)

        from ..core.error_handlers import success_response
        return success_response("影片快取已清除")

    except Exception as e:
        logger.error(f"清理快取失敗: {e}")
        return error_response(f'清理快取失敗: {str(e)}', 500)

@bp.route('/native/<chat_id>/<int:message_id>', methods=['GET', 'HEAD'])
@require_message_downloader_auth
async def stream_video_native_api(chat_id: str, message_id: int):
    """使用 Telegram 原生 API 的真正串流播放 - moov atom 重組方案

    原理：
    1. 使用 upload.GetFile Range Requests 下載檔案末尾
    2. 提取 moov atom（MP4 元數據）
    3. 重組 MP4 結構：ftyp + moov + mdat
    4. 邊下載邊串流給瀏覽器

    優勢：
    - 真正的串流播放，不需要完整下載
    - 支援任意大小的檔案
    - 記憶體使用極低
    - 使用 Telegram 原生 MTProto API
    """
    from quart import Response, request
    from pyrogram.raw.functions import upload
    from pyrogram.raw.types import InputDocumentFileLocation
    import struct

    try:
        chat_id = int(chat_id)

        logger.info(f"🎬 開始原生 API 串流: chat_id={chat_id}, message_id={message_id}")

        # 獲取認證客戶端
        from module.multiuser_auth import get_auth_manager
        auth_manager = get_auth_manager()

        if not auth_manager or not auth_manager.active_clients:
            return error_response('沒有可用的已認證客戶端', 401)

        client_key = list(auth_manager.active_clients.keys())[0]
        client = auth_manager.active_clients[client_key]

        # 獲取訊息
        result = await client.get_messages(chat_id=chat_id, message_ids=message_id)
        message = result if not isinstance(result, list) else result[0] if result else None

        if not message or not message.video:
            return error_response('訊息不包含影片', 404)

        file_size = message.video.file_size
        file_size_mb = file_size / 1024 / 1024
        logger.info(f"📹 影片大小: {file_size_mb:.2f} MB")

        # 處理 HEAD 請求
        if request.method == 'HEAD':
            logger.info("🔍 HEAD 請求：返回檔案資訊")
            response = Response('', status=200)
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Content-Type'] = 'video/mp4'
            response.headers['Content-Length'] = str(file_size)
            response.headers['Cache-Control'] = 'no-cache'
            return response

        # 檢查是否為 Range Request
        range_header = request.headers.get('Range')
        if range_header:
            logger.info(f"📊 收到 Range 請求: {range_header}")
        else:
            logger.info("📺 收到完整檔案請求（無 Range header）")

        # 從 file_id 獲取底層參數（Pyrogram 內部方法）
        from pyrogram.file_id import FileId
        file_id_obj = FileId.decode(message.video.file_id)

        logger.info(f"📄 File ID 解析: id={file_id_obj.media_id}, access_hash={file_id_obj.access_hash}")

        # 構建檔案位置（Telegram 原生 API）
        location = InputDocumentFileLocation(
            id=file_id_obj.media_id,
            access_hash=file_id_obj.access_hash,
            file_reference=file_id_obj.file_reference,
            thumb_size=""  # 空字串表示主檔案
        )

        async def get_file_range(offset: int, limit: int) -> bytes:
            """使用 Telegram 原生 API 下載檔案範圍

            Telegram API 關鍵限制：
            1. offset 和 limit 必須是 4KB 的倍數
            2. limit 必須能整除 1048576 (1MB)
            3. 請求範圍必須在同一個 1MB 區塊內：
               offset // 1048576 == (offset + limit - 1) // 1048576

            Args:
                offset: 位元組偏移（必須是 4KB 的倍數）
                limit: 下載大小（必須是 4KB 的倍數）
            """
            # 確保對齊到 4KB
            aligned_offset = (offset // 4096) * 4096
            aligned_limit = ((limit + 4095) // 4096) * 4096

            # 關鍵修復：確保請求不跨越 1MB 邊界
            MB = 1024 * 1024
            current_mb_block = aligned_offset // MB
            next_mb_boundary = (current_mb_block + 1) * MB
            max_allowed = next_mb_boundary - aligned_offset

            # 如果 aligned_limit 會跨越邊界，限制在當前 1MB 區塊內
            if aligned_limit > max_allowed:
                original_limit = aligned_limit
                # 保持 4KB 對齊，且必須能整除 1MB
                # 有效值：4KB, 8192, 16KB, 32KB, 64KB, 128KB, 256KB, 512KB
                valid_limits = [4096, 8192, 16384, 32768, 65536, 131072, 262144, 524288]
                aligned_limit = max([l for l in valid_limits if l <= max_allowed], default=4096)
                logger.info(f"🔧 調整 limit: {original_limit} → {aligned_limit} (max_allowed={max_allowed})")

            result = await client.invoke(
                upload.GetFile(
                    location=location,
                    offset=aligned_offset,
                    limit=aligned_limit,
                    precise=True,  # 對影片很重要
                    cdn_supported=True
                )
            )

            return result.bytes

        async def stream_with_moov_reorg(start_byte=0, end_byte=None):
            """重組 MP4 結構並串流

            Args:
                start_byte: 開始位元組位置（用於 Range Request）
                end_byte: 結束位元組位置（用於 Range Request）
            """
            try:
                if end_byte is None:
                    end_byte = file_size - 1

                # 對於 hover 預覽，直接串流原始檔案以獲得最快的響應速度
                # 跳過 moov atom 搜尋（可能花費 20+ 秒），直接開始發送數據
                logger.info(f"📺 使用快速串流模式（Range: {start_byte}-{end_byte}）")

                current_offset = start_byte
                end_offset = end_byte + 1  # +1 因為 end_byte 是 inclusive
                chunk_size = 512 * 1024  # 512KB chunks
                chunks_sent = 0

                while current_offset < end_offset:
                    try:
                        remaining = end_offset - current_offset
                        this_chunk_size = min(chunk_size, remaining)

                        chunk = await get_file_range(current_offset, this_chunk_size)
                        yield chunk

                        current_offset += len(chunk)
                        chunks_sent += 1

                        # 每 10 個 chunks 記錄一次進度
                        if chunks_sent % 10 == 0:
                            range_size = end_byte - start_byte + 1
                            sent_size = current_offset - start_byte
                            progress = (sent_size / range_size) * 100
                            logger.info(f"📤 已串流: {progress:.1f}% ({sent_size}/{range_size} bytes)")
                    except Exception as e:
                        logger.error(f"❌ 串流時發生錯誤 at offset {current_offset}: {e}")
                        break

                total_sent = current_offset - start_byte
                logger.success(f"✅ 串流完成: {chunks_sent} chunks, {total_sent} bytes")
                return

                # 以下是 moov atom 重組邏輯（暫時停用以獲得更快的響應速度）
                # 如果需要啟用 moov 重組，取消下面的註釋
                """
                # 導入 MP4 工具
                from module.mp4_utils import extract_moov_atom, find_atom

                # 1. 提取 moov atom
                logger.info("📦 提取 moov atom...")
                moov_data = await extract_moov_atom(file_size, get_file_range)

                if not moov_data:
                    logger.warning("⚠️ 無法提取 moov atom")
                    return
                """

                moov_size = len(moov_data)
                logger.success(f"✅ moov atom 提取完成: {moov_size} bytes")

                # 2. 獲取 ftyp atom（通常在檔案開頭）
                logger.info("📦 獲取 ftyp atom...")
                header_data = await get_file_range(0, 4096)

                # 解析 ftyp
                ftyp_size = struct.unpack('>I', header_data[0:4])[0]
                ftyp_type = header_data[4:8]

                if ftyp_type != b'ftyp':
                    logger.warning(f"⚠️ 第一個 atom 不是 ftyp: {ftyp_type}")
                    # 嘗試搜尋 ftyp
                    from module.mp4_utils import find_atom as find_atom_func
                    ftyp_atom = find_atom_func(header_data, b'ftyp')
                    if ftyp_atom and ftyp_atom.data:
                        ftyp_data = ftyp_atom.data
                    else:
                        logger.error("❌ 找不到 ftyp atom")
                        return
                else:
                    ftyp_data = header_data[0:ftyp_size]

                logger.success(f"✅ ftyp atom: {len(ftyp_data)} bytes")

                # 3. 發送重組的開頭：ftyp + moov
                logger.info("📤 發送 ftyp + moov...")
                yield ftyp_data
                yield moov_data

                # 4. 串流發送 mdat 和其他 atoms
                # 跳過 ftyp，從下一個 atom 開始
                current_offset = ftyp_size
                chunk_size = 256 * 1024  # 256KB chunks（安全值，避免跨越 1MB 邊界）

                logger.info("📤 開始串流媒體數據...")

                chunks_sent = 0
                while current_offset < file_size:
                    # 計算本次下載大小
                    remaining = file_size - current_offset
                    limit = min(chunk_size, remaining)

                    # 下載數據塊
                    chunk = await get_file_range(current_offset, limit)
                    actual_size = len(chunk)

                    if actual_size == 0:
                        break

                    # 檢查是否是 moov atom（需要跳過，因為我們已經發送了）
                    if actual_size >= 8:
                        chunk_type = chunk[4:8]
                        if chunk_type == b'moov':
                            # 跳過原始的 moov atom
                            moov_size_in_chunk = struct.unpack('>I', chunk[0:4])[0]
                            logger.info(f"⏭️ 跳過原始 moov atom: {moov_size_in_chunk} bytes")
                            current_offset += moov_size_in_chunk
                            continue

                    # 發送數據塊
                    yield chunk

                    current_offset += actual_size
                    chunks_sent += 1

                    # 進度記錄
                    if chunks_sent % 10 == 0:
                        progress = (current_offset / file_size) * 100
                        mb_sent = current_offset / 1024 / 1024
                        logger.info(f"📊 串流進度: {progress:.1f}% ({mb_sent:.1f} MB)")

                logger.success(f"✅ 串流完成: {chunks_sent} 塊, {file_size_mb:.2f} MB")

            except Exception as e:
                logger.error(f"❌ 串流錯誤: {e}")
                import traceback
                logger.error(traceback.format_exc())

        # 處理 Range Request
        range_start = 0
        range_end = file_size - 1
        status_code = 200

        if range_header:
            # 解析 Range header：bytes=start-end 或 bytes=start-
            import re
            match = re.match(r'bytes=(\d+)-(\d*)', range_header)
            if match:
                range_start = int(match.group(1))
                range_end = int(match.group(2)) if match.group(2) else file_size - 1
                status_code = 206  # Partial Content
                logger.info(f"📊 Range 解析: {range_start}-{range_end}/{file_size}")
            else:
                logger.warning(f"⚠️ 無法解析 Range header: {range_header}")

        # 返回串流響應
        response = Response(stream_with_moov_reorg(range_start, range_end), mimetype='video/mp4', status=status_code)
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Content-Type'] = 'video/mp4'
        response.headers['X-Content-Type-Options'] = 'nosniff'

        if status_code == 206:
            # Range Request - 添加 Content-Range header
            content_length = range_end - range_start + 1
            response.headers['Content-Range'] = f'bytes {range_start}-{range_end}/{file_size}'
            response.headers['Content-Length'] = str(content_length)
            logger.info(f"📤 返回 206 Partial Content: {content_length} bytes")
        else:
            response.headers['Content-Length'] = str(file_size)

        return response

    except Exception as e:
        logger.error(f"❌ 原生 API 串流失敗: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return error_response(f'串流失敗: {str(e)}', 500)
