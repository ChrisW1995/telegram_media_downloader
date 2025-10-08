"""Message Downloader 群組管理 API 模組

處理所有 /api/groups/* 相關的群組和訊息功能
"""

import asyncio
import concurrent.futures
from flask import Blueprint, jsonify, request, session
from loguru import logger
from ..core.decorators import require_message_downloader_auth
from ..core.error_handlers import success_response, error_response, handle_api_exception
from ..core.session_manager import get_session_manager
from module.multiuser_auth import get_auth_manager
from module.session_storage import get_session_storage

# 創建 Blueprint
bp = Blueprint('message_downloader_groups', __name__)

# Session 管理器
session_manager = get_session_manager()

# Global storage for auth sessions (like in auth.py)
message_downloader_auth_sessions = {}

# Global app instance
_app = None

def set_app_instance(app):
    """Set the global app instance for accessing config"""
    global _app
    _app = app

def run_async_in_thread(coro):
    """Run async coroutine using the app's main event loop"""
    # Always try to use the app's main event loop
    if hasattr(_app, 'loop') and _app.loop and not _app.loop.is_closed():
        try:
            # Submit coroutine to the app's event loop in a thread-safe way
            future = asyncio.run_coroutine_threadsafe(coro, _app.loop)
            return future.result(timeout=30)  # 30 second timeout
        except Exception as e:
            logger.error(f"Error running coroutine in main loop: {e}")

    # Fallback: create new event loop in thread
    def run_in_executor():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(run_in_executor)
        return future.result()

def restore_session_if_needed(session_key):
    """Restore session from persistent storage if needed"""
    if session_key not in message_downloader_auth_sessions:
        try:
            logger.debug(f"Attempting to restore session {session_key} from persistent storage")
            session_storage = get_session_storage()
            stored_session = session_storage.get_session(session_key)

            if not stored_session:
                logger.error(f"Session {session_key} not found in persistent storage")
                # Debug: List all available sessions
                try:
                    all_sessions = session_storage.list_active_sessions()
                    logger.debug(f"Available sessions in storage: {list(all_sessions.keys())}")
                except Exception as debug_e:
                    logger.debug(f"Could not list available sessions: {debug_e}")
                return False

            logger.debug(f"Found stored session {session_key} with status: {stored_session.get('status', 'unknown')}")

            # Check if session is actually authenticated
            if stored_session.get('status') != 'authenticated':
                logger.error(f"Session {session_key} is not authenticated (status: {stored_session.get('status')})")
                return False

            # Restore session to memory
            auth_manager = get_auth_manager()
            message_downloader_auth_sessions[session_key] = {
                'phone_number': stored_session.get('phone_number', ''),
                'auth_manager': auth_manager,
                'restored_from_storage': True
            }
            logger.info(f"Successfully restored session {session_key} from persistent storage")
            return True
        except Exception as e:
            logger.error(f"Failed to restore session {session_key}: {e}")
            logger.exception("Session restore exception details:")
            return False

    logger.debug(f"Session {session_key} already exists in memory")
    return True


@bp.route("/list", methods=["GET"])
@require_message_downloader_auth
@handle_api_exception
def get_groups_list():
    """獲取已加入的群組列表"""
    try:
        # Debug: Log current session state
        session_key = session.get('message_downloader_session_key')
        authenticated = session.get('message_downloader_authenticated', False)
        user_info = session.get('message_downloader_user_info', {})

        logger.debug(f"Groups API called - authenticated: {authenticated}, session_key: {session_key}, user_info keys: {list(user_info.keys())}")

        if not session_key:
            logger.error("Groups API error: session_key is None or empty")
            logger.debug(f"Current session contents: {dict(session)}")
            return error_response('Session key 缺失，請重新登入。如果剛登入請稍等片刻再試。', 401)

        # Restore session if needed
        if not restore_session_if_needed(session_key):
            logger.error(f"Groups API error: Failed to restore session for key: {session_key}")
            return error_response(f'無法恢復會話 ({session_key})，請重新登入', 401)

        if session_key not in message_downloader_auth_sessions:
            logger.error(f"Groups API error: Session key {session_key} not found in memory sessions")
            return error_response(f'會話不存在於記憶體 ({session_key})，請重新登入', 401)

        session_info = message_downloader_auth_sessions[session_key]
        if 'auth_manager' not in session_info:
            logger.error(f"Groups API error: auth_manager not found in session {session_key}")
            return error_response('會話缺少認證管理器，請重新登入', 401)

        auth_manager = session_info['auth_manager']
        logger.debug(f"Groups API: Using auth_manager for session {session_key}")

        # Get client for this user using our async helper
        groups = run_async_in_thread(
            auth_manager.get_user_groups(session_key)
        )

        logger.info(f"Groups API success: Retrieved {len(groups) if groups else 0} groups for session {session_key}")
        return success_response({'groups': groups})

    except Exception as e:
        logger.error(f"Groups API exception: {e}")
        logger.exception("Detailed traceback:")
        return error_response(f'獲取群組列表失敗: {str(e)}')


@bp.route("/messages", methods=["POST"])
@require_message_downloader_auth
@handle_api_exception
def get_group_messages():
    """獲取群組訊息"""
    try:
        data = request.get_json()
        chat_id = data.get('chat_id')
        limit = data.get('limit', 50)  # Default 50 messages
        offset_id = data.get('offset_id', 0)  # For pagination
        media_only = data.get('media_only', False)  # Filter for media messages only

        if not chat_id:
            return error_response('請提供群組 ID')

        # Get authenticated user's session
        session_key = session.get('message_downloader_session_key')

        if not session_key:
            return error_response('會話已過期，請重新登入', 401)

        # Restore session if needed
        if not restore_session_if_needed(session_key):
            return error_response('會話已過期，請重新登入', 401)

        session_info = message_downloader_auth_sessions[session_key]
        auth_manager = session_info['auth_manager']

        # Get messages for this group using our async helper
        result = run_async_in_thread(
            auth_manager.get_group_messages(
                session_key, chat_id, limit, offset_id, media_only
            )
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Failed to get group messages: {e}")
        return error_response(f'獲取群組訊息失敗: {str(e)}')


@bp.route("/load_more", methods=["POST"])
@require_message_downloader_auth
@handle_api_exception
def load_more_messages():
    """載入更多訊息"""
    try:
        data = request.get_json()
        chat_id = data.get('chat_id')
        offset_id = data.get('offset_id')
        limit = data.get('limit', 50)
        media_only = data.get('media_only', False)

        if not chat_id or not offset_id:
            return error_response('缺少必要參數')

        # Get authenticated user's session
        session_key = session.get('message_downloader_session_key')

        if not session_key:
            return error_response('會話已過期，請重新登入', 401)

        # Restore session if needed
        if not restore_session_if_needed(session_key):
            return error_response('會話已過期，請重新登入', 401)

        session_info = message_downloader_auth_sessions[session_key]
        auth_manager = session_info['auth_manager']

        # Load more messages using our async helper
        result = run_async_in_thread(
            auth_manager.get_group_messages(
                session_key, chat_id, limit, offset_id, media_only
            )
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Failed to load more messages: {e}")
        return error_response(f'載入更多訊息失敗: {str(e)}')


@bp.route("/<chat_id>/media_stats", methods=["GET"])
@require_message_downloader_auth
@handle_api_exception
def get_media_stats(chat_id):
    """獲取群組的媒體類型統計"""
    try:
        # 轉換 chat_id 為整數（支援負數）
        try:
            chat_id = int(chat_id)
        except ValueError:
            return error_response('無效的 chat_id')
        # Get authenticated user's session
        session_key = session.get('message_downloader_session_key')

        if not session_key:
            return error_response('會話已過期，請重新登入', 401)

        # Restore session if needed
        if not restore_session_if_needed(session_key):
            return error_response('會話已過期，請重新登入', 401)

        session_info = message_downloader_auth_sessions[session_key]
        auth_manager = session_info['auth_manager']

        # Get media stats using our async helper
        result = run_async_in_thread(
            auth_manager.get_media_statistics(session_key, chat_id)
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Failed to get media stats: {e}")
        return error_response(f'獲取媒體統計失敗: {str(e)}')