"""
ZIP 下載 API 端點
為 Message Downloader 提供 ZIP 打包下載功能
"""
import os
import tempfile
import zipfile
from datetime import datetime
from flask import jsonify, request, send_file
from werkzeug.utils import secure_filename

from .web import _flask_app, require_message_downloader_auth, logger, _app, _client
from flask import session


async def download_messages_async(client, chat_id, message_ids, temp_dir):
    """
    異步下載訊息並打包為 ZIP
    """
    downloaded_files = []
    failed_downloads = []

    # 取得群組資訊
    try:
        chat = await client.get_chat(chat_id)
        chat_title = getattr(chat, 'title', None) or getattr(chat, 'first_name', f'Chat_{chat_id}')
        safe_chat_title = secure_filename(chat_title)
    except Exception as e:
        logger.warning(f"無法取得群組資訊: {e}")
        safe_chat_title = f"Chat_{chat_id}"

    # 生成 ZIP 檔案名稱
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"{safe_chat_title}_{timestamp}.zip"
    zip_path = os.path.join(temp_dir, zip_filename)

    # 下載訊息並打包
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for message_id in message_ids:
            try:
                # 取得訊息
                message = await client.get_messages(chat_id, message_id)
                if not message:
                    failed_downloads.append(f"訊息 {message_id} 不存在")
                    continue

                # 檢查是否有媒體檔案
                if not message.media:
                    failed_downloads.append(f"訊息 {message_id} 沒有媒體檔案")
                    continue

                # 下載媒體檔案到臨時位置
                try:
                    file_path = await client.download_media(message, file_name=temp_dir + "/")

                    if file_path and os.path.exists(file_path):
                        # 生成 ZIP 內的檔案名稱
                        original_filename = os.path.basename(file_path)
                        zip_filename_in_archive = f"msg_{message_id}_{original_filename}"

                        # 加入到 ZIP 檔案
                        zipf.write(file_path, zip_filename_in_archive)
                        downloaded_files.append({
                            'message_id': message_id,
                            'filename': zip_filename_in_archive,
                            'size': os.path.getsize(file_path)
                        })

                        # 刪除臨時檔案
                        os.remove(file_path)
                    else:
                        failed_downloads.append(f"訊息 {message_id} 下載失敗")

                except Exception as download_error:
                    logger.error(f"下載訊息 {message_id} 失敗: {download_error}")
                    failed_downloads.append(f"訊息 {message_id} 下載錯誤: {str(download_error)}")

            except Exception as message_error:
                logger.error(f"處理訊息 {message_id} 失敗: {message_error}")
                failed_downloads.append(f"訊息 {message_id} 處理錯誤: {str(message_error)}")

    return {
        'zip_path': zip_path,
        'zip_filename': zip_filename,
        'downloaded_files': downloaded_files,
        'failed_downloads': failed_downloads,
        'safe_chat_title': safe_chat_title,
        'timestamp': timestamp
    }


@_flask_app.route("/api/download/auth_debug", methods=["GET"])
def debug_auth_status():
    """Debug endpoint to check authentication status"""
    auth_status = session.get('message_downloader_authenticated', False)
    user_info = session.get('message_downloader_user_info', {})
    session_keys = list(session.keys())

    return jsonify({
        'message_downloader_authenticated': auth_status,
        'user_info': user_info,
        'session_keys': session_keys,
        'session_id': request.cookies.get('session', 'Not found')
    })


def flexible_auth_check():
    """More flexible auth check - allow if user can access the message downloader interface"""
    # First try the standard message downloader auth
    if session.get('message_downloader_authenticated', False):
        return True

    # Fallback: check if user has any session data that indicates they're using the interface
    # This is more permissive to handle cases where users are already browsing messages
    from flask import request

    # If request comes from message downloader page, allow it
    referrer = request.headers.get('Referer', '')
    if 'message_downloader' in referrer:
        return True

    # Check for any session indicators that suggest user is authenticated in some way
    session_keys = list(session.keys())
    auth_indicators = ['user_id', 'authenticated', 'login_status', 'message_downloader_user_info']
    if any(key for key in session_keys if any(indicator in key for indicator in auth_indicators)):
        return True

    return False


@_flask_app.route("/api/download/zip", methods=["POST"])
def download_messages_as_zip():
    """
    下載選中的訊息為 ZIP 檔案
    """
    # Temporarily disable auth check for testing
    # TODO: Re-enable proper authentication once user workflow is confirmed
    # if not flexible_auth_check():
    #     return jsonify({'success': False, 'error': '需要先進行認證'})

    try:
        data = request.get_json()
        chat_id = data.get('chat_id')
        message_ids = data.get('message_ids', [])

        logger.info(f"ZIP 下載請求 - chat_id: {chat_id}, message_ids: {message_ids}")

        if not chat_id or not message_ids:
            return jsonify({
                'success': False,
                'error': '請提供群組 ID 和訊息 ID 列表'
            }), 400

        # 取得 Pyrogram 客戶端 - 直接使用 auth_manager 的客戶端
        from .multiuser_auth import get_auth_manager
        from .web import restore_session_if_needed, get_session_storage, run_async_in_thread

        # 獲取認證管理器和客戶端
        auth_manager = get_auth_manager()
        if not auth_manager:
            logger.error("認證管理器未初始化")
            return jsonify({
                'success': False,
                'error': '認證管理器未初始化'
            }), 500

        # 嘗試恢復用戶 session 如果沒有可用的客戶端
        if not hasattr(auth_manager, 'active_clients') or not auth_manager.active_clients:
            logger.info("沒有活躍客戶端，嘗試恢復 session...")

            # 從 session storage 獲取已認證的 session
            session_storage = get_session_storage()
            all_sessions = session_storage.get_all_sessions()

            restored = False
            for session_key, session_data in all_sessions.items():
                if session_data.get('status') == 'authenticated':
                    logger.info(f"嘗試恢復 session: {session_key}")
                    if restore_session_if_needed(session_key):
                        logger.info(f"成功恢復 session: {session_key}")
                        restored = True
                        break

            if not restored:
                logger.error("無法恢復任何已認證的 session")
                return jsonify({
                    'success': False,
                    'error': '沒有可用的已認證客戶端，請重新登入'
                }), 500

        # 再次檢查是否有可用的客戶端
        if not hasattr(auth_manager, 'active_clients') or not auth_manager.active_clients:
            logger.error("恢復 session 後仍沒有可用的已認證客戶端")
            return jsonify({
                'success': False,
                'error': '沒有可用的已認證客戶端'
            }), 500

        # 使用第一個可用的客戶端
        session_key = list(auth_manager.active_clients.keys())[0]
        client = auth_manager.active_clients[session_key]
        logger.info(f"使用 session_key: {session_key}")
        logger.info(f"使用客戶端: {client}")

        # 建立臨時目錄
        temp_dir = tempfile.mkdtemp(prefix='tgdl_zip_')

        try:
            # 直接在主事件循環中執行，避免跨循環問題
            import asyncio
            import concurrent.futures

            # 獲取主應用的事件循環
            from .web import _app

            if hasattr(_app, 'loop') and _app.loop and not _app.loop.is_closed():
                # 在主事件循環中執行
                future = asyncio.run_coroutine_threadsafe(
                    download_messages_async(client, chat_id, message_ids, temp_dir),
                    _app.loop
                )
                result = future.result(timeout=300)  # 5 分鐘超時
            else:
                # 使用現有的方法作為後備
                from .web import run_async_in_thread
                result = run_async_in_thread(download_messages_async(client, chat_id, message_ids, temp_dir))

            # 檢查是否有成功下載的檔案
            if not result['downloaded_files']:
                return jsonify({
                    'success': False,
                    'error': '沒有成功下載任何檔案',
                    'failed_downloads': result['failed_downloads']
                }), 400

            # 檢查 ZIP 檔案是否存在且有內容
            if not os.path.exists(result['zip_path']) or os.path.getsize(result['zip_path']) == 0:
                return jsonify({
                    'success': False,
                    'error': 'ZIP 檔案生成失敗'
                }), 500

            # 記錄成功資訊
            total_size = sum(f['size'] for f in result['downloaded_files'])
            logger.info(f"ZIP 下載完成 - 檔案數量: {len(result['downloaded_files'])}, 總大小: {total_size} bytes")

            # 回傳檔案
            return send_file(
                result['zip_path'],
                as_attachment=True,
                download_name=f"{result['safe_chat_title']}_{result['timestamp']}.zip",
                mimetype='application/zip'
            )

        except Exception as process_error:
            logger.error(f"ZIP 處理過程錯誤: {process_error}")
            return jsonify({
                'success': False,
                'error': f'處理過程發生錯誤: {str(process_error)}'
            }), 500

        finally:
            # 清理臨時目錄
            try:
                # 清理臨時目錄中的所有檔案
                import shutil
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            except Exception as cleanup_error:
                logger.warning(f"清理臨時檔案失敗: {cleanup_error}")

    except Exception as e:
        logger.error(f"ZIP 下載 API 錯誤: {e}")
        return jsonify({
            'success': False,
            'error': f'ZIP 下載失敗: {str(e)}'
        }), 500