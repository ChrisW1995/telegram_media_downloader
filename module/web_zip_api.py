"""
ZIP 下載 API 端點
為 Message Downloader 提供 ZIP 打包下載功能
"""
import asyncio
import os
import tempfile
import time
import zipfile
from datetime import datetime
from flask import jsonify, request, send_file
from werkzeug.utils import secure_filename

from .web import _flask_app, require_message_downloader_auth, logger, _app, _client
from flask import session


class ZipDownloadManager:
    """管理使用主下載系統的 ZIP 下載任務"""

    def __init__(self, chat_id, message_ids, temp_dir):
        self.chat_id = chat_id
        self.message_ids = message_ids
        self.temp_dir = temp_dir
        self.downloaded_files = []
        self.failed_downloads = []
        self.task_node = None
        self.zip_path = None
        self.safe_chat_title = None
        self.timestamp = None

    async def prepare_download(self):
        """準備下載，設置檔案名和TaskNode"""
        # 取得群組資訊
        try:
            from .multiuser_auth import get_auth_manager
            auth_manager = get_auth_manager()
            if auth_manager and hasattr(auth_manager, 'active_clients') and auth_manager.active_clients:
                session_key = list(auth_manager.active_clients.keys())[0]
                client = auth_manager.active_clients[session_key]
                chat = await client.get_chat(self.chat_id)
                chat_title = getattr(chat, 'title', None) or getattr(chat, 'first_name', f'Chat_{self.chat_id}')
                self.safe_chat_title = secure_filename(chat_title)
            else:
                self.safe_chat_title = f"Chat_{self.chat_id}"
        except Exception as e:
            logger.warning(f"無法取得群組資訊: {e}")
            self.safe_chat_title = f"Chat_{self.chat_id}"

        # 生成 ZIP 檔案名稱
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"{self.safe_chat_title}_{self.timestamp}.zip"
        self.zip_path = os.path.join(self.temp_dir, zip_filename)

        # 創建 TaskNode 來追蹤整體進度
        from module.app import TaskNode
        self.task_node = TaskNode(chat_id=self.chat_id)
        self.task_node.total_task = len(self.message_ids)
        self.task_node.zip_download_manager = self  # 保存對管理器的引用

    async def start_downloads_via_worker_pool(self):
        """使用主下載系統的 worker pool 開始下載"""
        from .web import _queue, _client
        from module.app import DownloadStatus

        if not _queue:
            raise Exception("主下載隊列未初始化")

        logger.info(f"開始通過 worker pool 下載 {len(self.message_ids)} 個檔案")

        # 獲取所有需要下載的訊息
        messages_to_download = []
        for message_id in self.message_ids:
            try:
                # 獲取客戶端
                from .multiuser_auth import get_auth_manager
                auth_manager = get_auth_manager()
                if auth_manager and hasattr(auth_manager, 'active_clients') and auth_manager.active_clients:
                    session_key = list(auth_manager.active_clients.keys())[0]
                    client = auth_manager.active_clients[session_key]

                    message = await client.get_messages(self.chat_id, message_id)
                    if message and message.media:
                        messages_to_download.append(message)
                        logger.info(f"訊息 {message_id} 已加入下載隊列")
                    else:
                        self.failed_downloads.append(f"訊息 {message_id} 沒有媒體檔案或不存在")

            except Exception as e:
                logger.error(f"無法獲取訊息 {message_id}: {e}")
                self.failed_downloads.append(f"無法獲取訊息 {message_id}: {str(e)}")

        # 將所有訊息加入主下載隊列
        for message in messages_to_download:
            # 創建一個節點來追蹤這個特定訊息的下載
            from module.app import TaskNode
            message_node = TaskNode(chat_id=self.chat_id)
            message_node.download_status[message.id] = DownloadStatus.Downloading
            message_node.zip_download_manager = self  # 關聯到 ZIP 管理器
            message_node.zip_message_id = message.id  # 標記這是 ZIP 下載的一部分

            # 加入下載隊列，讓 worker 處理
            await _queue.put((message, message_node))
            logger.info(f"訊息 {message.id} 已加入主下載隊列")

    def on_file_downloaded(self, message_id, file_path, file_size):
        """當檔案下載完成時的回調"""
        logger.info(f"檔案下載完成: 訊息 {message_id}, 路徑: {file_path}")
        self.downloaded_files.append({
            'message_id': message_id,
            'file_path': file_path,
            'size': file_size
        })

        # 檢查是否所有檔案都已下載完成
        total_expected = len(self.message_ids) - len(self.failed_downloads)
        if len(self.downloaded_files) >= total_expected:
            logger.info("所有檔案下載完成，開始打包 ZIP")
            # 在事件循環中安排 ZIP 打包
            import asyncio
            asyncio.create_task(self.create_zip_file())

    def on_file_failed(self, message_id, error_message):
        """當檔案下載失敗時的回調"""
        logger.error(f"檔案下載失敗: 訊息 {message_id}, 錯誤: {error_message}")
        self.failed_downloads.append(f"訊息 {message_id}: {error_message}")

        # 檢查是否所有檔案都已處理完成
        total_processed = len(self.downloaded_files) + len(self.failed_downloads)
        if total_processed >= len(self.message_ids):
            logger.info("所有檔案處理完成，開始打包 ZIP")
            # 在事件循環中安排 ZIP 打包
            import asyncio
            asyncio.create_task(self.create_zip_file())

    async def create_zip_file(self):
        """創建 ZIP 檔案"""
        logger.info(f"開始創建 ZIP 檔案: {self.zip_path}")

        try:
            with zipfile.ZipFile(self.zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_info in self.downloaded_files:
                    try:
                        # 生成 ZIP 內的檔案名稱
                        original_filename = os.path.basename(file_info['file_path'])
                        zip_filename_in_archive = f"msg_{file_info['message_id']}_{original_filename}"

                        # 加入到 ZIP 檔案
                        zipf.write(file_info['file_path'], zip_filename_in_archive)
                        logger.info(f"檔案 {original_filename} 已加入 ZIP")

                        # 刪除臨時檔案
                        os.remove(file_info['file_path'])
                    except Exception as zip_error:
                        logger.error(f"打包檔案 {file_info['message_id']} 失敗: {zip_error}")
                        self.failed_downloads.append(f"打包檔案 {file_info['message_id']} 失敗: {str(zip_error)}")

            logger.success(f"ZIP 檔案創建完成: {self.zip_path}")

            # 設置完成標誌
            self.zip_ready = True

        except Exception as e:
            logger.error(f"創建 ZIP 檔案失敗: {e}")
            raise e


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


# 全局變數儲存活躍的 ZIP 下載管理器
active_zip_managers = {}

@_flask_app.route("/api/download/zip", methods=["POST"])
def download_messages_as_zip():
    """
    下載選中的訊息為 ZIP 檔案 - 使用主下載系統的 worker pool
    """
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

        # 檢查客戶端可用性
        from .multiuser_auth import get_auth_manager
        from .web import restore_session_if_needed, get_session_storage, run_async_in_thread

        auth_manager = get_auth_manager()
        if not auth_manager:
            logger.error("認證管理器未初始化")
            return jsonify({
                'success': False,
                'error': '認證管理器未初始化'
            }), 500

        # 嘗試恢復 session 如果需要
        if not hasattr(auth_manager, 'active_clients') or not auth_manager.active_clients:
            logger.info("沒有活躍客戶端，嘗試恢復 session...")
            session_storage = get_session_storage()
            all_sessions = session_storage.list_active_sessions()

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

        # 再次檢查客戶端可用性
        if not hasattr(auth_manager, 'active_clients') or not auth_manager.active_clients:
            logger.error("恢復 session 後仍沒有可用的已認證客戶端")
            return jsonify({
                'success': False,
                'error': '沒有可用的已認證客戶端'
            }), 500

        # 建立臨時目錄
        temp_dir = tempfile.mkdtemp(prefix='tgdl_zip_')

        # 創建 ZIP 下載管理器
        zip_manager = ZipDownloadManager(chat_id, message_ids, temp_dir)

        # 使用唯一ID儲存管理器
        manager_id = f"{chat_id}_{int(time.time() * 1000)}"
        active_zip_managers[manager_id] = zip_manager

        try:
            # 獲取主應用的事件循環並執行下載準備和啟動
            from .web import _app, run_async_in_thread

            async def prepare_and_start_download():
                await zip_manager.prepare_download()
                await zip_manager.start_downloads_via_worker_pool()
                return {
                    'manager_id': manager_id,
                    'zip_path': zip_manager.zip_path,
                    'safe_chat_title': zip_manager.safe_chat_title,
                    'timestamp': zip_manager.timestamp
                }

            if hasattr(_app, 'loop') and _app.loop and not _app.loop.is_closed():
                # 在主事件循環中執行
                future = asyncio.run_coroutine_threadsafe(
                    prepare_and_start_download(),
                    _app.loop
                )
                result = future.result(timeout=30)  # 30 秒超時用於準備階段
            else:
                # 使用現有的方法作為後備
                result = run_async_in_thread(prepare_and_start_download())

            logger.info(f"ZIP 下載已啟動，管理器ID: {manager_id}")

            # 激活進度追蹤
            from .web import download_progress
            download_progress['active'] = True
            download_progress['status_text'] = 'ZIP 下載進行中...'
            download_progress['total_count'] = len(message_ids)
            download_progress['completed_count'] = 0

            # 回傳成功響應，前端需要輪詢檢查完成狀態
            return jsonify({
                'success': True,
                'message': f'ZIP 下載已啟動，正在通過 {len(message_ids)} 個 worker 併發下載',
                'manager_id': manager_id,
                'expected_zip_filename': f"{result['safe_chat_title']}_{result['timestamp']}.zip"
            })

        except Exception as process_error:
            logger.error(f"ZIP 下載啟動過程錯誤: {process_error}")
            # 清理失敗的管理器
            if manager_id in active_zip_managers:
                del active_zip_managers[manager_id]

            # 清理臨時目錄
            try:
                import shutil
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            except Exception as cleanup_error:
                logger.warning(f"清理臨時檔案失敗: {cleanup_error}")

            return jsonify({
                'success': False,
                'error': f'ZIP 下載啟動失敗: {str(process_error)}'
            }), 500

    except Exception as e:
        logger.error(f"ZIP 下載 API 錯誤: {e}")
        return jsonify({
            'success': False,
            'error': f'ZIP 下載失敗: {str(e)}'
        }), 500


@_flask_app.route("/api/download/zip/status/<manager_id>", methods=["GET"])
def check_zip_download_status(manager_id):
    """檢查 ZIP 下載狀態"""
    try:
        if manager_id not in active_zip_managers:
            return jsonify({
                'success': False,
                'error': '下載任務不存在或已過期'
            }), 404

        zip_manager = active_zip_managers[manager_id]

        total_files = len(zip_manager.message_ids)
        downloaded_files = len(zip_manager.downloaded_files)
        failed_files = len(zip_manager.failed_downloads)

        # 檢查是否完成
        is_completed = hasattr(zip_manager, 'zip_ready') and zip_manager.zip_ready

        if is_completed:
            # 檢查 ZIP 檔案是否存在
            if os.path.exists(zip_manager.zip_path) and os.path.getsize(zip_manager.zip_path) > 0:
                # 準備檔案傳送
                zip_filename = f"{zip_manager.safe_chat_title}_{zip_manager.timestamp}.zip"

                # 清理管理器
                del active_zip_managers[manager_id]

                return send_file(
                    zip_manager.zip_path,
                    as_attachment=True,
                    download_name=zip_filename,
                    mimetype='application/zip'
                )
            else:
                return jsonify({
                    'success': False,
                    'error': 'ZIP 檔案不存在或為空'
                }), 500
        else:
            # 回傳進度狀態
            return jsonify({
                'success': True,
                'completed': False,
                'progress': {
                    'total_files': total_files,
                    'downloaded_files': downloaded_files,
                    'failed_files': failed_files,
                    'percentage': round((downloaded_files + failed_files) / total_files * 100, 2) if total_files > 0 else 0
                }
            })

    except Exception as e:
        logger.error(f"檢查 ZIP 下載狀態錯誤: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500