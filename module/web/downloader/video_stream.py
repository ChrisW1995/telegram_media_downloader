"""影片串流 API (Quart async)

採用 Telegram Web K 的方式：純粹 HTTP 206 Range 請求代理。
不再進行 moov atom 重組，讓瀏覽器自動處理 moov 位置。

核心策略：
1. 瀏覽器 video 元素請求影片
2. 自動發起 Range: bytes=0-1 探測檔案大小
3. 請求 bytes=0-全部 → 服務器只返回 2MB
4. 瀏覽器發現 moov 不在開頭，自動請求檔案末尾
5. 開始順序串流播放

參考：Telegram Web K (https://github.com/morethanwords/tweb)
"""

import re
from quart import Blueprint, session, Response, request
from loguru import logger
from ..core.decorators import require_message_downloader_auth
from ..core.error_handlers import error_response

bp = Blueprint('video_stream', __name__)

# Global app instance
_app = None

# 常數
ALIGN = 4096  # 4KB 對齊 (Telegram API 要求)
MB = 1024 * 1024
MAX_CHUNK_SIZE = 2 * MB  # 最大單次響應 2MB (與 Telegram Web K 一致)


def set_app_instance(app):
    """Set the global app instance for accessing config"""
    global _app
    _app = app


def get_session_key() -> str:
    """獲取當前會話鍵"""
    return session.get('user_id', 'anonymous')


def align_to_telegram_constraints(offset: int, limit: int, file_size: int) -> tuple[int, int]:
    """確保請求符合 Telegram API 限制

    Telegram API 限制：
    1. offset 和 limit 必須對齊到 4KB
    2. 請求不能跨越 1MB 邊界
    3. limit 必須是 4KB 的倍數且 <= 1MB

    Args:
        offset: 請求的起始位置
        limit: 請求的大小
        file_size: 檔案總大小

    Returns:
        (aligned_offset, aligned_limit)
    """
    # 對齊 offset 到 4KB 邊界 (向下對齊)
    aligned_offset = (offset // ALIGN) * ALIGN

    # 計算當前 1MB 區塊的結束位置
    current_mb_block = aligned_offset // MB
    next_mb_boundary = (current_mb_block + 1) * MB
    max_end = min(next_mb_boundary, file_size)

    # 計算可用的最大 limit
    max_limit = max_end - aligned_offset

    # 對齊 limit 到 4KB 邊界 (向下對齊)
    aligned_limit = min(limit, max_limit)
    aligned_limit = (aligned_limit // ALIGN) * ALIGN

    # 確保 limit 至少是 4KB
    if aligned_limit < ALIGN:
        aligned_limit = ALIGN

    # 確保不超過 1MB
    if aligned_limit > MB:
        aligned_limit = MB

    return aligned_offset, aligned_limit


# ==================== 統一串流端點 ====================

@bp.route('/<chat_id>/<int:message_id>', methods=['GET', 'HEAD'])
@require_message_downloader_auth
async def stream_video(chat_id: str, message_id: int):
    """純粹代理模式 - 支援 HTTP 206 Range 請求

    模仿 Telegram Web K 的實現方式：
    - 直接返回請求範圍的原始數據
    - 讓瀏覽器自動處理 moov atom 位置
    - 不進行 moov 重組

    流程：
    1. 瀏覽器請求 Range: bytes=0-1 探測檔案大小
    2. 瀏覽器請求 Range: bytes=0-全部，服務器返回前 2MB
    3. 瀏覽器發現 moov 不在開頭，請求檔案末尾
    4. 瀏覽器開始順序請求影片數據
    """
    from pyrogram.raw.functions import upload
    from pyrogram.raw.types import InputDocumentFileLocation

    try:
        chat_id = int(chat_id)

        logger.info(f"🎬 串流請求: chat_id={chat_id}, message_id={message_id}, method={request.method}")

        # 獲取認證客戶端
        from module.multiuser_auth import get_auth_manager
        auth_manager = get_auth_manager()

        if not auth_manager or not auth_manager.active_clients:
            logger.error("❌ 沒有可用的已認證客戶端")
            return error_response('沒有可用的已認證客戶端', 401)

        client_key = list(auth_manager.active_clients.keys())[0]
        client = auth_manager.active_clients[client_key]

        # 獲取訊息
        result = await client.get_messages(chat_id=chat_id, message_ids=message_id)
        message = result if not isinstance(result, list) else result[0] if result else None

        if not message or not message.video:
            logger.warning(f"❌ 訊息 {message_id} 不包含影片")
            return error_response('訊息不包含影片', 404)

        file_size = message.video.file_size
        file_size_mb = file_size / 1024 / 1024
        logger.info(f"📹 影片大小: {file_size_mb:.2f} MB")

        # HEAD 請求：返回檔案資訊
        if request.method == 'HEAD':
            logger.info("🔍 HEAD 請求：返回檔案資訊")
            response = Response('', status=200)
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Content-Type'] = 'video/mp4'
            response.headers['Content-Length'] = str(file_size)
            response.headers['Cache-Control'] = 'no-cache'
            return response

        # 從 file_id 獲取底層參數
        from pyrogram.file_id import FileId
        file_id_obj = FileId.decode(message.video.file_id)

        # 構建檔案位置
        location = InputDocumentFileLocation(
            id=file_id_obj.media_id,
            access_hash=file_id_obj.access_hash,
            file_reference=file_id_obj.file_reference,
            thumb_size=""
        )

        async def get_file_range(offset: int, limit: int) -> bytes:
            """使用 Telegram 原生 API 下載檔案範圍"""
            result = await client.invoke(
                upload.GetFile(
                    location=location,
                    offset=offset,
                    limit=limit,
                    precise=True,
                    cdn_supported=True
                )
            )
            return result.bytes

        # 解析 Range header
        range_header = request.headers.get('Range')
        if range_header:
            logger.info(f"📊 收到 Range 請求: {range_header}")
            match = re.match(r'bytes=(\d+)-(\d*)', range_header)
            if match:
                range_start = int(match.group(1))
                range_end = int(match.group(2)) if match.group(2) else file_size - 1

                # 確保範圍有效
                range_start = min(range_start, file_size - 1)
                range_end = min(range_end, file_size - 1)

                # 限制單次響應最大 2MB (與 Telegram Web K 一致)
                if range_end - range_start + 1 > MAX_CHUNK_SIZE:
                    range_end = range_start + MAX_CHUNK_SIZE - 1

                status_code = 206
                logger.info(f"📊 Range 解析: {range_start}-{range_end}/{file_size}")
            else:
                range_start = 0
                range_end = min(MAX_CHUNK_SIZE - 1, file_size - 1)
                status_code = 206
        else:
            # 無 Range 時也只返回 2MB，讓瀏覽器知道支援 Range
            range_start = 0
            range_end = min(MAX_CHUNK_SIZE - 1, file_size - 1)
            status_code = 206
            logger.info(f"📺 無 Range 請求，返回前 {MAX_CHUNK_SIZE // MB}MB")

        content_length = range_end - range_start + 1

        async def stream_range():
            """純粹代理：直接返回請求範圍的原始數據"""
            current = range_start
            end = range_end
            bytes_sent = 0

            logger.info(f"🎥 開始串流: {current}-{end} ({content_length} bytes)")

            while current <= end:
                remaining = end - current + 1

                # 計算對齊的請求
                aligned_offset, aligned_limit = align_to_telegram_constraints(
                    current, remaining, file_size
                )

                try:
                    # 從 Telegram 獲取數據
                    chunk = await get_file_range(aligned_offset, aligned_limit)

                    if not chunk:
                        logger.warning(f"⚠️ 收到空 chunk: offset={aligned_offset}")
                        break

                    # 計算實際需要的部分
                    chunk_start = current - aligned_offset
                    chunk_end = min(chunk_start + remaining, len(chunk))
                    actual_chunk = chunk[chunk_start:chunk_end]

                    if not actual_chunk:
                        break

                    yield actual_chunk
                    bytes_sent += len(actual_chunk)
                    current += len(actual_chunk)

                except Exception as e:
                    logger.error(f"❌ 獲取 chunk 失敗: offset={aligned_offset}, error={e}")
                    break

            logger.success(f"✅ 串流完成: 發送 {bytes_sent} bytes")

        response = Response(stream_range(), mimetype='video/mp4', status=status_code)
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Content-Range'] = f'bytes {range_start}-{range_end}/{file_size}'
        response.headers['Content-Length'] = str(content_length)
        response.headers['Content-Type'] = 'video/mp4'
        response.headers['Cache-Control'] = 'no-cache'

        return response

    except Exception as e:
        logger.error(f"❌ 串流失敗: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return error_response(f'串流失敗: {str(e)}', 500)


# ==================== 預載端點 (可選保留) ====================

@bp.route('/preload/<chat_id>/<int:message_id>', methods=['POST'])
@require_message_downloader_auth
async def preload_video(chat_id: str, message_id: int):
    """預載影片（可選）

    在新的 Range 請求模式下，這個端點不再必要，
    但可以保留作為「預熱」用途，提前獲取一小部分數據。
    """
    from ..core.error_handlers import success_response

    try:
        chat_id = int(chat_id)

        logger.info(f"🔄 預載請求: chat_id={chat_id}, message_id={message_id}")

        # 獲取認證客戶端
        from module.multiuser_auth import get_auth_manager
        auth_manager = get_auth_manager()

        if not auth_manager or not auth_manager.active_clients:
            return error_response('沒有可用的已認證客戶端', 401)

        client_key = list(auth_manager.active_clients.keys())[0]
        client = auth_manager.active_clients[client_key]

        # 獲取訊息驗證影片存在
        result = await client.get_messages(chat_id=chat_id, message_ids=message_id)
        message = result if not isinstance(result, list) else result[0] if result else None

        if not message or not message.video:
            return error_response('訊息不包含影片', 404)

        file_size = message.video.file_size
        file_size_mb = file_size / 1024 / 1024

        # 在新模式下，預載只是驗證影片可訪問
        logger.success(f"✅ 預載驗證完成: {file_size_mb:.2f} MB")

        return success_response({
            "status": "ready",
            "cached": True,  # 為了兼容舊前端
            "file_size_mb": round(file_size_mb, 2)
        })

    except Exception as e:
        logger.error(f"❌ 預載失敗: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return error_response(f'預載失敗: {str(e)}', 500)


# ==================== 緩存管理端點 (保留兼容性) ====================

@bp.route('/cache/stats', methods=['GET'])
@require_message_downloader_auth
async def get_cache_stats():
    """取得緩存統計資訊（在新模式下不再使用 moov 緩存）"""
    from ..core.error_handlers import success_response
    return success_response({
        "mode": "range_request",
        "note": "新的 Range 請求模式不需要 moov 緩存"
    })


@bp.route('/cache/clear', methods=['POST'])
@require_message_downloader_auth
async def clear_cache():
    """清除所有緩存（保留兼容性）"""
    from ..core.error_handlers import success_response
    return success_response({"status": "cleared", "note": "Range 模式無需清除緩存"})


@bp.route('/cache/clear/<int:chat_id>', methods=['POST'])
@require_message_downloader_auth
async def clear_chat_cache(chat_id: int):
    """清除指定聊天室的緩存（保留兼容性）"""
    from ..core.error_handlers import success_response
    return success_response({"status": "cleared", "chat_id": chat_id})
