"""Message Downloader 認證 API 模組

處理所有 /api/auth/* 相關的認證功能
"""

import asyncio
import concurrent.futures
import time
from flask import Blueprint, jsonify, request, session
from loguru import logger
from ..core.error_handlers import success_response, error_response, handle_api_exception
from ..core.session_manager import get_session_manager
from module.session_storage import get_session_storage
from module.multiuser_auth import TelegramAuthManager, get_auth_manager

# 創建 Blueprint
bp = Blueprint('message_downloader_auth', __name__)

# Session 管理器
session_manager = get_session_manager()

# Global storage for auth sessions (like in web_original.py)
message_downloader_auth_sessions = {}

# Global app instance (for accessing config)
_app = None  # Will be set during initialization

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


@bp.route("/send_code", methods=["POST"])
@handle_api_exception
def send_code():
    """發送驗證碼到手機"""
    try:
        data = request.get_json()
        phone_number = data.get('phone_number', '').strip()

        if not phone_number:
            return error_response('請輸入電話號碼')

        # Get API credentials from main app config
        if not _app:
            return error_response('應用程式配置未初始化')

        api_id = _app.api_id
        api_hash = _app.api_hash

        if not api_id or not api_hash:
            return error_response('API 憑證未設定')

        # Initialize auth manager
        auth_manager = get_auth_manager()

        # Start auth process
        result = run_async_in_thread(
            auth_manager.start_auth_process(phone_number, api_id, api_hash)
        )

        if result['success']:
            # Store session info
            session_key = result['session_key']

            # Store in memory for immediate access
            message_downloader_auth_sessions[session_key] = {
                'phone_number': phone_number,
                'phone_code_hash': result['phone_code_hash'],
                'auth_manager': auth_manager
            }

            # Store in persistent storage
            session_storage = get_session_storage()
            session_storage.create_session(session_key, {
                'phone_number': phone_number,
                'phone_code_hash': result['phone_code_hash'],
                'status': 'awaiting_code',
                'user_id': None,
                'user_info': None
            })

            # Store session key in Flask session for this user
            session['message_downloader_session_key'] = session_key
            session.permanent = True  # Make session persistent

        return jsonify(result)

    except Exception as e:
        logger.error(f"Failed to send verification code: {e}")
        return error_response(f'發送驗證碼失敗: {str(e)}')


@bp.route("/verify_code", methods=["POST"])
@handle_api_exception
def verify_code():
    """驗證手機驗證碼"""
    try:
        data = request.get_json()
        verification_code = data.get('verification_code', '').strip()

        # Get session key from Flask session or request data
        session_key = data.get('session_key') or session.get('message_downloader_session_key')

        if not session_key:
            return error_response('會話已過期，請重新開始')

        # Check session in memory first, then restore from persistent storage
        if session_key not in message_downloader_auth_sessions:
            session_storage = get_session_storage()
            stored_session = session_storage.get_session(session_key)
            if not stored_session:
                return error_response('會話已過期，請重新開始')

            # Restore session to memory
            auth_manager = get_auth_manager()
            message_downloader_auth_sessions[session_key] = {
                'phone_number': stored_session['phone_number'],
                'phone_code_hash': stored_session['phone_code_hash'],
                'auth_manager': auth_manager
            }

        if not verification_code:
            return error_response('請輸入驗證碼')

        session_info = message_downloader_auth_sessions[session_key]
        auth_manager = session_info['auth_manager']
        phone_code_hash = session_info['phone_code_hash']

        # Verify code
        result = run_async_in_thread(
            auth_manager.verify_code(session_key, verification_code, phone_code_hash)
        )

        if result['success'] and not result.get('requires_password'):
            # Authentication completed successfully
            session['message_downloader_authenticated'] = True
            session['message_downloader_user_info'] = result.get('user_info', {})
            session.permanent = True  # Make session persistent

            # Determine session key - use user_id if available, otherwise keep original session_key
            final_session_key = session_key  # Default to original session_key

            if 'user_id' in result:
                user_id = result['user_id']
                session['message_downloader_user_id'] = user_id
                # Use user_id as session key for consistency with active_clients
                final_session_key = str(user_id)

            # Always set session key for consistency
            session['message_downloader_session_key'] = final_session_key

            # Move session data to new key if needed
            if session_key in message_downloader_auth_sessions and final_session_key != session_key:
                message_downloader_auth_sessions[final_session_key] = message_downloader_auth_sessions[session_key]
                del message_downloader_auth_sessions[session_key]
            elif final_session_key not in message_downloader_auth_sessions:
                # Ensure session exists in memory
                message_downloader_auth_sessions[final_session_key] = message_downloader_auth_sessions.get(session_key, {})

            # Update persistent storage with authentication success
            session_storage = get_session_storage()

            # Delete old session if it exists and is different from final key
            if session_key != final_session_key and session_storage.get_session(session_key):
                session_storage.delete_session(session_key)
                logger.debug(f"Deleted old session key: {session_key}")

            # Create or update the session with final key
            if session_storage.get_session(final_session_key):
                # Update existing session
                session_storage.update_session(final_session_key, {
                    'status': 'authenticated',
                    'user_id': result.get('user_id'),
                    'user_info': result.get('user_info', {}),
                    'authenticated_at': time.time()
                })
            else:
                # Create new session with final key
                session_info = message_downloader_auth_sessions.get(final_session_key, {})
                session_storage.create_session(final_session_key, {
                    'status': 'authenticated',
                    'user_id': result.get('user_id'),
                    'user_info': result.get('user_info', {}),
                    'phone_number': session_info.get('phone_number', ''),
                    'authenticated_at': time.time()
                })
                logger.debug(f"Created new session with key: {final_session_key}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Failed to verify code: {e}")
        return error_response(f'驗證碼驗證失敗: {str(e)}')


@bp.route("/verify_password", methods=["POST"])
@handle_api_exception
def verify_password():
    """驗證兩步驗證密碼"""
    try:
        data = request.get_json()
        password = data.get('password', '')

        # Get session key from Flask session or request data
        session_key = data.get('session_key') or session.get('message_downloader_session_key')

        if not session_key:
            return error_response('會話已過期，請重新開始')

        # Check session in memory first, then restore from persistent storage
        if session_key not in message_downloader_auth_sessions:
            session_storage = get_session_storage()
            stored_session = session_storage.get_session(session_key)
            if not stored_session:
                return error_response('會話已過期，請重新開始')

            # Restore session to memory
            auth_manager = get_auth_manager()
            message_downloader_auth_sessions[session_key] = {
                'phone_number': stored_session['phone_number'],
                'phone_code_hash': stored_session['phone_code_hash'],
                'auth_manager': auth_manager
            }

        if not password:
            return error_response('請輸入兩步驗證密碼')

        session_info = message_downloader_auth_sessions[session_key]
        auth_manager = session_info['auth_manager']

        # Verify password
        result = run_async_in_thread(
            auth_manager.verify_password(session_key, password)
        )

        if result['success']:
            # Authentication completed successfully
            session['message_downloader_authenticated'] = True
            session['message_downloader_user_info'] = result.get('user_info', {})
            session.permanent = True  # Make session persistent

            # Determine session key - use user_id if available, otherwise keep original session_key
            final_session_key = session_key  # Default to original session_key

            if 'user_id' in result:
                user_id = result['user_id']
                session['message_downloader_user_id'] = user_id
                # Use user_id as session key for consistency with active_clients
                final_session_key = str(user_id)

            # Always set session key for consistency
            session['message_downloader_session_key'] = final_session_key

            # Move session data to new key if needed
            if session_key in message_downloader_auth_sessions and final_session_key != session_key:
                message_downloader_auth_sessions[final_session_key] = message_downloader_auth_sessions[session_key]
                del message_downloader_auth_sessions[session_key]
            elif final_session_key not in message_downloader_auth_sessions:
                # Ensure session exists in memory
                message_downloader_auth_sessions[final_session_key] = message_downloader_auth_sessions.get(session_key, {})

            # Update persistent storage with authentication success
            session_storage = get_session_storage()

            # Delete old session if it exists and is different from final key
            if session_key != final_session_key and session_storage.get_session(session_key):
                session_storage.delete_session(session_key)
                logger.debug(f"Deleted old session key: {session_key}")

            # Create or update the session with final key
            if session_storage.get_session(final_session_key):
                # Update existing session
                session_storage.update_session(final_session_key, {
                    'status': 'authenticated',
                    'user_id': result.get('user_id'),
                    'user_info': result.get('user_info', {}),
                    'authenticated_at': time.time()
                })
            else:
                # Create new session with final key
                session_info = message_downloader_auth_sessions.get(final_session_key, {})
                session_storage.create_session(final_session_key, {
                    'status': 'authenticated',
                    'user_id': result.get('user_id'),
                    'user_info': result.get('user_info', {}),
                    'phone_number': session_info.get('phone_number', ''),
                    'authenticated_at': time.time()
                })
                logger.debug(f"Created new session with key: {final_session_key}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Failed to verify password: {e}")
        return error_response(f'密碼驗證失敗: {str(e)}')


@bp.route("/status", methods=["GET"])
@handle_api_exception
def get_auth_status():
    """獲取認證狀態"""
    # TODO: 從 web.py 移植功能
    authenticated = session.get('message_downloader_authenticated', False)
    user_info = session.get('message_downloader_user_info', {})

    return success_response({
        'authenticated': authenticated,
        'user_info': user_info
    })


@bp.route("/logout", methods=["POST"])
@handle_api_exception
def logout():
    """登出"""
    # Get session key BEFORE clearing session
    session_key = session.get('message_downloader_session_key')

    # Clear all session data
    session.clear()

    # Also clear from global auth sessions
    if session_key and session_key in message_downloader_auth_sessions:
        del message_downloader_auth_sessions[session_key]

    # Clear persistent storage
    try:
        session_storage = get_session_storage()
        if session_key:
            session_storage.delete_session(session_key)
    except Exception as e:
        logger.warning(f"Failed to clear persistent session: {e}")

    return success_response(message="已成功登出")


@bp.route("/force_clear_session", methods=["POST"])
@handle_api_exception
def force_clear_session():
    """強制清除所有 session 數據 (用於解決瀏覽器殘留問題)"""
    try:
        # Get all possible session keys before clearing
        session_key = session.get('message_downloader_session_key')
        user_id = session.get('message_downloader_user_id')

        # Force clear Flask session completely
        session.clear()

        # Clear all possible session keys from global auth sessions
        keys_to_remove = []
        for key in message_downloader_auth_sessions:
            keys_to_remove.append(key)

        for key in keys_to_remove:
            del message_downloader_auth_sessions[key]

        # Clear persistent storage for this user
        try:
            session_storage = get_session_storage()

            # Clear by session_key if available
            if session_key:
                session_storage.delete_session(session_key)

            # Clear by user_id if available
            if user_id:
                session_storage.delete_session(str(user_id))

            # Clear all active sessions as fallback
            active_sessions = session_storage.list_active_sessions()
            for stored_key in active_sessions.keys():
                session_storage.delete_session(stored_key)

        except Exception as e:
            logger.warning(f"Failed to clear persistent sessions: {e}")

        # Force set new session to ensure clean state
        from flask import make_response
        response = make_response(success_response(message="所有 session 數據已強制清除"))

        # Clear any possible cookies
        response.set_cookie('session', '', expires=0, httponly=True, path='/')

        return response

    except Exception as e:
        logger.error(f"Failed to force clear session: {e}")
        return error_response(f'強制清除失敗: {str(e)}')


@bp.route("/qr_login", methods=["POST"])
@handle_api_exception
def qr_login():
    """QR Code 登入"""
    try:
        # Get API credentials from main app config
        if not _app:
            return error_response('應用程式配置未初始化')

        api_id = _app.api_id
        api_hash = _app.api_hash

        if not api_id or not api_hash:
            return error_response('API 憑證未設定')

        # Initialize auth manager
        auth_manager = get_auth_manager()

        # Start QR login process
        result = run_async_in_thread(
            auth_manager.start_qr_login(api_id, api_hash)
        )

        if result['success']:
            session_key = result['session_key']

            # Store session
            message_downloader_auth_sessions[session_key] = {
                'auth_manager': auth_manager,
                'status': 'qr_pending',
                'created_at': time.time()
            }

            # Store in persistent storage
            session_storage = get_session_storage()
            session_storage.create_session(session_key, {
                'status': 'qr_pending',
                'login_type': 'qr',
                'created_at': time.time()
            })

            return jsonify({
                'success': True,
                'session_key': session_key,
                'qr_token': result['qr_token']
            })
        else:
            return error_response(result.get('error', 'QR 登入初始化失敗'))

    except Exception as e:
        logger.error(f"Failed to start QR login: {e}")
        return error_response(f'QR 登入失敗: {str(e)}')


@bp.route("/check_qr_status", methods=["POST"])
@handle_api_exception
def check_qr_status():
    """檢查 QR Code 登入狀態"""
    try:
        data = request.get_json()
        session_key = data.get('session_key')

        if not session_key or session_key not in message_downloader_auth_sessions:
            return error_response('無效的 session')

        session_info = message_downloader_auth_sessions[session_key]
        auth_manager = session_info['auth_manager']

        # Check QR login status
        result = run_async_in_thread(
            auth_manager.check_qr_status(session_key)
        )

        if result['success']:
            if result.get('authenticated'):
                # QR login successful
                session['message_downloader_authenticated'] = True
                session['message_downloader_user_info'] = result.get('user_info', {})
                session.permanent = True

                # Determine session key - use user_id if available, otherwise keep original session_key
                final_session_key = session_key  # Default to original session_key

                if 'user_id' in result:
                    user_id = result['user_id']
                    session['message_downloader_user_id'] = user_id
                    # Use user_id as session key for consistency with active_clients
                    final_session_key = str(user_id)

                # Always set session key for consistency
                session['message_downloader_session_key'] = final_session_key

                # Move session data to new key if needed
                if session_key in message_downloader_auth_sessions and final_session_key != session_key:
                    message_downloader_auth_sessions[final_session_key] = message_downloader_auth_sessions[session_key]
                    del message_downloader_auth_sessions[session_key]
                elif final_session_key not in message_downloader_auth_sessions:
                    # Ensure session exists in memory
                    message_downloader_auth_sessions[final_session_key] = message_downloader_auth_sessions.get(session_key, {})

                # Update persistent storage
                session_storage = get_session_storage()

                # Delete old session if it exists and is different from final key
                if session_key != final_session_key and session_storage.get_session(session_key):
                    session_storage.delete_session(session_key)
                    logger.debug(f"Deleted old session key: {session_key}")

                # Create or update the session with final key
                if session_storage.get_session(final_session_key):
                    # Update existing session
                    session_storage.update_session(final_session_key, {
                        'status': 'authenticated',
                        'user_id': result.get('user_id'),
                        'user_info': result.get('user_info', {}),
                        'authenticated_at': time.time()
                    })
                else:
                    # Create new session with final key
                    session_storage.create_session(final_session_key, {
                        'status': 'authenticated',
                        'user_id': result.get('user_id'),
                        'user_info': result.get('user_info', {}),
                        'authenticated_at': time.time()
                    })
                    logger.debug(f"Created new session with key: {final_session_key}")

                return jsonify({
                    'success': True,
                    'authenticated': True,
                    'user_info': result.get('user_info', {})
                })
            elif result.get('expired'):
                return jsonify({
                    'success': True,
                    'authenticated': False,
                    'expired': True
                })
            else:
                return jsonify({
                    'success': True,
                    'authenticated': False,
                    'expired': False
                })
        else:
            return error_response(result.get('error', 'QR 狀態檢查失敗'))

    except Exception as e:
        logger.error(f"Failed to check QR status: {e}")
        return error_response(f'QR 狀態檢查失敗: {str(e)}')