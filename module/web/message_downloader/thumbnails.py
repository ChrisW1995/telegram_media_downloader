"""Message Downloader 縮圖 API 模組

處理 /api/message_downloader_thumbnail/* 相關的縮圖生成功能
"""

from flask import Blueprint, jsonify, session, Response
from loguru import logger
import base64
import io
from ..core.decorators import require_message_downloader_auth
from ..core.error_handlers import error_response, handle_api_exception, success_response
from ..core.session_manager import get_session_manager

# 創建 Blueprint
bp = Blueprint('message_downloader_thumbnails', __name__)

# Session 管理器
session_manager = get_session_manager()

# Global app instance
_app = None

def set_app_instance(app):
    """Set the global app instance for accessing config"""
    global _app
    _app = app


@bp.route("/<chat_id>/<int:message_id>", methods=["GET"])
@require_message_downloader_auth
@handle_api_exception
def get_thumbnail(chat_id, message_id):
    """獲取訊息縮圖"""
    try:
        # 轉換 chat_id 為整數（支援負數）
        try:
            chat_id = int(chat_id)
        except ValueError:
            return error_response('無效的 chat_id')

        logger.info(f"Thumbnail API: chat_id={chat_id}, message_id={message_id}")

        # 檢查會話
        session_key = session.get('message_downloader_session_key')
        logger.info(f"Session key: {session_key}")

        if not session_key:
            logger.warning("No session key found")
            return error_response('會話已過期，請重新登入', 401)

        # 使用與 groups API 相同的認證邏輯
        from ..message_downloader.groups import restore_session_if_needed
        from module.multiuser_auth import get_auth_manager

        # 嘗試恢復會話（如果需要）
        if not restore_session_if_needed(session_key):
            logger.error(f"Failed to restore session {session_key}")
            return error_response('會話恢復失敗，請重新登入', 401)

        # 獲取認證管理器
        auth_manager = get_auth_manager()
        logger.info(f"Auth manager: {auth_manager}")

        if not auth_manager or not hasattr(auth_manager, 'active_clients'):
            logger.error("Auth manager not available or no active_clients attribute")
            return error_response('客戶端不可用')

        # 首先嘗試用 session_key 直接查找客戶端
        client = auth_manager.active_clients.get(session_key)
        logger.info(f"Client with session_key: {client}")

        # 如果沒找到，嘗試用 user_id 查找（處理認證後 key 變化的情況）
        if not client:
            user_id = session.get('message_downloader_user_id')
            if user_id:
                client = auth_manager.active_clients.get(str(user_id))
                logger.info(f"Client with user_id {user_id}: {client}")

        # 如果還是沒找到，嘗試找第一個數字 key 的客戶端（回退機制）
        if not client:
            logger.info(f"Looking for numeric keys in active_clients: {list(auth_manager.active_clients.keys())}")
            for key in auth_manager.active_clients.keys():
                if key.isdigit():
                    client = auth_manager.active_clients[key]
                    logger.info(f"Found client with numeric key {key}: {client}")
                    break

        if not client:
            logger.error(f"No client found for session {session_key}, user_id {session.get('message_downloader_user_id')}")
            logger.error(f"Available clients: {list(auth_manager.active_clients.keys())}")
            return error_response('找不到有效的客戶端連接')

        # 異步獲取縮圖
        async def get_thumbnail():
            try:
                logger.info(f"開始獲取訊息 {message_id} from chat {chat_id}")
                # 獲取訊息 (使用命名參數，message_ids 可以是單個 ID)
                messages = await client.get_messages(chat_id=chat_id, message_ids=message_id)
                message = messages if not isinstance(messages, list) else (messages[0] if messages else None)
                if not message:
                    logger.warning(f"找不到訊息 {message_id}")
                    return None

                logger.info(f"成功獲取訊息，類型: {type(message)}")

                # 尋找縮圖
                thumb = None
                if hasattr(message, 'photo') and message.photo and hasattr(message.photo, 'thumbs'):
                    thumbs = message.photo.thumbs
                    logger.info(f"Photo thumbs 數量: {len(thumbs) if thumbs else 0}")
                    if thumbs:
                        thumb = min(thumbs, key=lambda t: (t.width or 0) * (t.height or 0))
                        logger.info(f"選擇的 photo thumb: {thumb}")
                elif hasattr(message, 'video') and message.video and hasattr(message.video, 'thumbs'):
                    thumbs = message.video.thumbs
                    logger.info(f"Video thumbs 數量: {len(thumbs) if thumbs else 0}")
                    if thumbs:
                        thumb = min(thumbs, key=lambda t: (t.width or 0) * (t.height or 0))
                        logger.info(f"選擇的 video thumb: {thumb}")
                elif hasattr(message, 'document') and message.document and hasattr(message.document, 'thumbs'):
                    thumbs = message.document.thumbs
                    logger.info(f"Document thumbs 數量: {len(thumbs) if thumbs else 0}")
                    if thumbs:
                        thumb = min(thumbs, key=lambda t: (t.width or 0) * (t.height or 0))
                        logger.info(f"選擇的 document thumb: {thumb}")
                elif hasattr(message, 'animation') and message.animation and hasattr(message.animation, 'thumbs'):
                    thumbs = message.animation.thumbs
                    logger.info(f"Animation thumbs 數量: {len(thumbs) if thumbs else 0}")
                    if thumbs:
                        thumb = min(thumbs, key=lambda t: (t.width or 0) * (t.height or 0))
                        logger.info(f"選擇的 animation thumb: {thumb}")
                else:
                    logger.info(f"訊息沒有支援的媒體類型或縮圖")

                # 下載縮圖到記憶體
                if thumb and hasattr(thumb, 'file_id'):
                    logger.info(f"開始下載縮圖, file_id: {thumb.file_id}")
                    # 使用 in_memory=True 直接下載到記憶體
                    binary_io = await client.download_media(thumb, in_memory=True)
                    if binary_io:
                        # 讀取 BinaryIO 內容
                        binary_io.seek(0)
                        data = binary_io.read()
                        logger.info(f"縮圖下載成功，大小: {len(data)} bytes")
                        return data
                    else:
                        logger.warning("縮圖下載失敗，返回空值")
                        return None
                else:
                    logger.info("訊息沒有可用的縮圖")
                    return None

            except Exception as e:
                logger.error(f"獲取縮圖錯誤: {e}")
                return None

        # 使用智能異步執行工具運行協程
        from ..core.async_utils import run_async_in_thread

        try:
            thumbnail_data = run_async_in_thread(get_thumbnail())
        except Exception as e:
            logger.error(f"執行異步縮圖獲取時發生錯誤: {e}")
            thumbnail_data = None

        if thumbnail_data:
            # 轉換為 base64 Data URL
            base64_data = base64.b64encode(thumbnail_data).decode('utf-8')
            data_url = f"data:image/jpeg;base64,{base64_data}"

            logger.info(f"縮圖處理完成，返回 data URL (length: {len(data_url)})")
            return success_response(
                data={
                    'thumbnail': data_url,
                    'size': len(thumbnail_data)
                },
                message="縮圖獲取成功"
            )
        else:
            logger.warning("無法獲取縮圖")
            return error_response('無法獲取該訊息的縮圖')

    except Exception as e:
        logger.error(f"Thumbnail API 錯誤: {e}")
        return error_response(f"獲取縮圖失敗: {str(e)}")