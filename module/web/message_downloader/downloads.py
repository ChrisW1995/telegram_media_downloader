"""Message Downloader 下載管理 API 模組

處理所有 /api/fast_download/* 和 /api/download/* 相關的下載功能
"""

import asyncio
import os
import tempfile
import time
import zipfile
from datetime import datetime
from flask import Blueprint, jsonify, request, session, send_file
from werkzeug.utils import secure_filename
from loguru import logger
from ..core.decorators import require_message_downloader_auth
from ..core.error_handlers import success_response, error_response, handle_api_exception
from ..core.session_manager import get_session_manager
from ..core.progress_system import (
    get_download_progress_data, calculate_detailed_progress,
    update_download_progress, initialize_download_session,
    download_progress, active_download_session
)
# update_download_status 和 TaskNode 現在在函數內部動態導入

# 創建 Blueprint
bp = Blueprint('message_downloader_downloads', __name__)

# Session 管理器
session_manager = get_session_manager()

# Global app instance
_app = None

def set_app_instance(app):
    """Set the global app instance for accessing config"""
    global _app
    _app = app


@bp.route("/add_tasks", methods=["POST"])
@require_message_downloader_auth
@handle_api_exception
def add_download_tasks():
    """添加下載任務"""
    try:
        data = request.get_json()
        chat_id = data.get('chat_id')
        message_ids = data.get('message_ids', [])

        logger.info(f"Fast Test API called with chat_id: {chat_id}, message_ids: {message_ids}")

        if not chat_id or not message_ids:
            logger.error(f"Missing data - chat_id: {chat_id}, message_ids: {message_ids}")
            return error_response('請提供群組 ID 和訊息 ID 列表')

        # Add to existing custom download system
        from collections import OrderedDict

        # Update target_ids in config
        # Ensure _app.config is properly initialized
        if not hasattr(_app, 'config') or _app.config is None:
            logger.error("_app.config is not initialized")
            return error_response('應用配置未初始化')

        # Ensure custom_downloads section exists
        if 'custom_downloads' not in _app.config:
            _app.config['custom_downloads'] = {'enable': True, 'target_ids': {}, 'group_tags': {}}

        # Ensure target_ids exists
        custom_downloads = _app.config['custom_downloads']
        if 'target_ids' not in custom_downloads:
            custom_downloads['target_ids'] = OrderedDict()

        # Add message IDs to target chat
        target_ids = custom_downloads['target_ids']
        if chat_id not in target_ids:
            target_ids[chat_id] = []

        # Add new message IDs (avoid duplicates)
        existing_ids = set(target_ids[chat_id])
        new_ids = [msg_id for msg_id in message_ids if msg_id not in existing_ids]

        if new_ids:
            target_ids[chat_id].extend(new_ids)
            logger.info(f"Added {len(new_ids)} new message IDs: {new_ids}")

            # Update config file
            try:
                _app.update_config()
                logger.info("Configuration updated successfully")
            except Exception as update_error:
                logger.error(f"Failed to update config: {update_error}")
                # Don't fail the request if config update fails
                pass

            # 自動觸發下載
            download_triggered = False
            # 使用舊架構的認證管理器獲取客戶端
            try:
                from module.multiuser_auth import get_auth_manager
                auth_manager = get_auth_manager()

                if not auth_manager or not hasattr(auth_manager, 'active_clients') or not auth_manager.active_clients:
                    logger.error("No active clients found")
                    return error_response('沒有可用的已認證客戶端', 401)

                # 獲取第一個可用的客戶端
                client_key = list(auth_manager.active_clients.keys())[0]
                client = auth_manager.active_clients[client_key]
            except ImportError as e:
                logger.error(f"無法導入認證管理器: {e}")
                return error_response('認證系統不可用', 500)

            if client and hasattr(_app, 'loop') and _app.loop:
                try:
                    from module.custom_download import run_custom_download
                    from module.download_stat import set_download_state, DownloadState

                    # 設置下載狀態為下載中
                    set_download_state(DownloadState.Downloading)

                    # 初始化進度系統
                    initialize_download_session(len(new_ids))

                    # 為 message_downloader 創建 TaskNode，支援 bot 通知
                    user_id = session.get('message_downloader_user_id')

                    # 創建 TaskNode 來支持進度通知
                    if user_id and hasattr(_app, 'download_bot') and _app.download_bot:
                            try:
                                import time

                                # 構建初始通知訊息
                                chat_id_str = str(chat_id)
                                start_message = f"""🚀 **Message Downloader 下載開始**

**群組 ID**: `{chat_id_str}`
**訊息數量**: {len(new_ids)}
**開始時間**: {time.strftime('%Y-%m-%d %H:%M:%S')}

⏳ 正在準備下載..."""

                                # 創建 TaskNode with bot notification support (先創建，後發送訊息)
                                from module.download_stat import TaskNode
                                task_node = TaskNode(
                                    chat_id=chat_id_str,
                                    bot=_app.download_bot,
                                    reply_message_id=None  # 暫時設為 None，稍後更新
                                )
                                task_node.is_running = True

                                logger.info(f"Created TaskNode with task_id: {task_node.task_id}")

                                # 異步函數來處理訊息發送和下載
                                async def send_notification_and_download():
                                    try:
                                        # 發送初始通知給用戶
                                        reply_message_obj = await _app.download_bot.send_message(
                                            user_id, start_message, parse_mode='markdown'
                                        )
                                        reply_message_id = reply_message_obj.id

                                        # 更新 TaskNode 的 reply_message_id
                                        task_node.reply_message_id = reply_message_id

                                        logger.info(f"Sent start notification to user {user_id}, reply_message_id: {reply_message_id}")

                                        # 觸發下載
                                        await run_custom_download(_app, client, task_node=task_node)

                                    except Exception as e:
                                        logger.error(f"Error in notification and download: {e}")

                                # 創建異步任務
                                download_task = _app.loop.create_task(send_notification_and_download())
                                download_triggered = True
                                logger.info("Download task triggered with bot notification support")

                            except Exception as task_error:
                                logger.error(f"Failed to create TaskNode with bot support: {task_error}")
                                # 回退到無 bot 通知的下載
                                download_task = _app.loop.create_task(
                                    run_custom_download(_app, client)
                                )
                                download_triggered = True
                                logger.info("Download task triggered without bot notification")
                    else:
                        # 普通下載（無 bot 通知）
                        download_task = _app.loop.create_task(
                            run_custom_download(_app, client)
                        )
                        download_triggered = True
                        logger.info("Download task triggered (normal mode)")

                except Exception as download_error:
                    logger.error(f"Failed to trigger download: {download_error}")

            response_message = f"成功添加 {len(new_ids)} 個新的下載任務"
            if download_triggered:
                response_message += "，下載已自動開始"
            else:
                response_message += "，請手動觸發下載"

            return success_response(response_message, {
                'added_count': len(new_ids),
                'total_count': len(target_ids[chat_id]),
                'download_triggered': download_triggered
            })
        else:
            logger.info("No new message IDs to add")
            return success_response("所有訊息 ID 已存在於下載列表中", {
                'added_count': 0,
                'total_count': len(target_ids[chat_id]),
                'download_triggered': False
            })

    except Exception as e:
        logger.error(f"Error adding download tasks: {e}")
        return error_response(f"添加下載任務失敗: {str(e)}")


@bp.route("/status", methods=["GET"])
@require_message_downloader_auth
@handle_api_exception
def get_download_status():
    """獲取下載狀態"""
    try:
        # 使用新的進度系統
        from module.download_stat import get_download_state

        # 計算詳細統計
        detailed_progress = calculate_detailed_progress()

        # 創建增強的進度數據
        enhanced_progress = {
            'active': download_progress.get('active', False),
            'total_task': download_progress.get('total_count', 0),
            'completed_task': download_progress.get('completed_count', 0),
            'status_text': download_progress.get('status_text', ''),
            # 詳細進度信息
            'downloaded_size': detailed_progress.get('downloaded_size', 0),
            'total_size': detailed_progress.get('total_size', 0),
            'download_speed': detailed_progress.get('download_speed', 0),
            'remaining_files': detailed_progress.get('remaining_files', 0),
            'current_files': detailed_progress.get('current_files', []),
            'eta_seconds': detailed_progress.get('eta_seconds', 0)
        }

        return success_response("下載狀態獲取成功", {
            'progress': enhanced_progress,
            'session': active_download_session,
            'download_state': get_download_state().name
        })

    except Exception as e:
        logger.error(f"Error getting download status: {e}")
        # 返回默認狀態以防止錯誤
        return success_response("下載狀態獲取成功", {
            'progress': {
                'active': False,
                'total_task': 0,
                'completed_task': 0,
                'status_text': '未知狀態',
                'downloaded_size': 0,
                'total_size': 0,
                'download_speed': 0,
                'remaining_files': 0,
                'current_files': [],
                'eta_seconds': 0
            },
            'session': None,
            'download_state': 'IDLE'
        })


# ============================================================================
# ZIP 下載功能
# ============================================================================

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
        self.zip_ready = False

        # 初始化進度系統
        initialize_download_session(len(message_ids))

    async def prepare_download(self):
        """準備下載，設置檔案名和TaskNode"""
        # 取得群組資訊 - 使用舊架構認證管理器
        try:
            from module.multiuser_auth import get_auth_manager
            auth_manager = get_auth_manager()

            if auth_manager and hasattr(auth_manager, 'active_clients') and auth_manager.active_clients:
                # 獲取第一個可用的客戶端
                client_key = list(auth_manager.active_clients.keys())[0]
                client = auth_manager.active_clients[client_key]
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

    async def start_downloads_via_worker_pool(self):
        """使用現有的asyncio Queue + Worker Pool系統開始下載"""
        logger.info(f"開始使用Worker Pool下載 {len(self.message_ids)} 個檔案")

        try:
            from module.multiuser_auth import get_auth_manager
            auth_manager = get_auth_manager()

            if not auth_manager or not hasattr(auth_manager, 'active_clients') or not auth_manager.active_clients:
                raise Exception("沒有可用的活躍客戶端")

            client_key = list(auth_manager.active_clients.keys())[0]
            client = auth_manager.active_clients[client_key]
            logger.info(f"-- Using client {client_key} for ZIP downloads")

        except ImportError:
            raise Exception("無法導入認證管理器")

        # 使用現有的Worker Pool系統，而非序列下載
        try:
            # 導入必要的模組
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

            # 直接使用全域queue系統
            logger.info("使用全域Worker Pool隊列系統進行下載")

            # 獲取全域queue - 從 web module 獲取
            from module.web import _queue
            from module.app import TaskNode, DownloadStatus

            if not _queue:
                raise Exception("Worker Pool 隊列未初始化")

            # 獲取所有訊息並直接加入全域Worker Pool隊列
            for message_id in self.message_ids:
                try:
                    message = await client.get_messages(self.chat_id, message_id)
                    if message and message.media:
                        # 為每個訊息創建TaskNode並設置ZIP管理器引用
                        node = TaskNode(chat_id=self.chat_id)
                        node.is_custom_download = True
                        node.zip_download_manager = self
                        node.zip_message_id = message_id  # 用於ZIP管理器回調
                        node.download_status[message.id] = DownloadStatus.Downloading
                        node.total_task += 1

                        # 直接將任務加入隊列
                        await _queue.put((message, node))
                        success = True
                        if success:
                            logger.info(f"訊息 {message_id} 已加入Worker Pool隊列")
                        else:
                            self.failed_downloads.append(f"訊息 {message_id} 無法加入下載隊列")
                    else:
                        self.failed_downloads.append(f"訊息 {message_id} 沒有媒體檔案或不存在")
                        logger.warning(f"訊息 {message_id} 沒有媒體檔案")
                except Exception as e:
                    logger.error(f"無法處理訊息 {message_id}: {e}")
                    self.failed_downloads.append(f"訊息 {message_id}: {str(e)}")

            logger.info(f"所有 {len(self.message_ids)} 個訊息已提交到Worker Pool隊列系統")

        except Exception as e:
            logger.error(f"使用Worker Pool下載時發生錯誤: {e}")
            raise


    def on_file_downloaded(self, message_id, file_path, file_size):
        """當檔案下載完成時的回調"""
        logger.info(f"檔案下載完成: 訊息 {message_id}, 路徑: {file_path}")
        self.downloaded_files.append({
            'message_id': message_id,
            'file_path': file_path,
            'size': file_size
        })

        # 更新進度系統
        completed_count = len(self.downloaded_files)
        total_count = len(self.message_ids)
        status_text = f"ZIP 下載中... ({completed_count}/{total_count})"
        update_download_progress(completed_count, total_count, status_text)

        # 檢查是否所有檔案都已下載完成
        total_expected = len(self.message_ids) - len(self.failed_downloads)
        if len(self.downloaded_files) >= total_expected:
            logger.info("所有檔案下載完成，開始打包 ZIP")
            # 更新進度為打包階段
            update_download_progress(total_count, total_count, "正在打包 ZIP 檔案...")
            # 在事件循環中安排 ZIP 打包
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

            # 更新進度系統 - 完成
            total_count = len(self.message_ids)
            update_download_progress(total_count, total_count, f"✅ ZIP 檔案創建完成！({len(self.downloaded_files)} 個檔案)")

        except Exception as e:
            logger.error(f"創建 ZIP 檔案失敗: {e}")
            # 更新進度系統 - 錯誤
            update_download_progress(0, len(self.message_ids), f"❌ ZIP 創建失敗: {str(e)}")
            raise e


# 全局變數儲存活躍的 ZIP 下載管理器
active_zip_managers = {}


@bp.route("/zip", methods=["POST"])
@require_message_downloader_auth
@handle_api_exception
def download_messages_as_zip():
    """下載選中的訊息為 ZIP 檔案"""
    logger.info("========== ZIP 下載 API 被調用了！ ==========")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request path: {request.path}")
    logger.info(f"Request URL: {request.url}")
    try:
        data = request.get_json()
        chat_id = data.get('chat_id')
        message_ids = data.get('message_ids', [])

        logger.info(f"ZIP 下載請求 - chat_id: {chat_id}, message_ids: {message_ids}")

        if not chat_id or not message_ids:
            return error_response('請提供群組 ID 和訊息 ID 列表')

        # 檢查認證狀態 - 使用舊架構的認證管理器
        try:
            from module.multiuser_auth import get_auth_manager
            auth_manager = get_auth_manager()

            if not auth_manager or not hasattr(auth_manager, 'active_clients') or not auth_manager.active_clients:
                return error_response('沒有可用的已認證客戶端，請重新登入', 500)

        except ImportError as e:
            logger.error(f"無法導入舊架構認證管理器: {e}")
            return error_response('認證系統不可用', 500)

        # 建立臨時目錄
        temp_dir = tempfile.mkdtemp(prefix='tgdl_zip_')

        # 創建 ZIP 下載管理器
        zip_manager = ZipDownloadManager(chat_id, message_ids, temp_dir)

        # 使用唯一ID儲存管理器
        manager_id = f"{chat_id}_{int(time.time() * 1000)}"
        zip_manager.manager_id = manager_id  # 設置 manager_id 屬性供 TaskNode 使用
        active_zip_managers[manager_id] = zip_manager

        try:
            # 異步準備和啟動下載 - 完全非阻塞模式
            async def prepare_and_start_download():
                try:
                    await zip_manager.prepare_download()
                    logger.info(f"ZIP 管理器準備完成: {zip_manager.safe_chat_title}")

                    # 在後台啟動下載任務，不等待完成
                    asyncio.create_task(zip_manager.start_downloads_via_worker_pool())

                    return {
                        'manager_id': manager_id,
                        'zip_path': zip_manager.zip_path,
                        'safe_chat_title': zip_manager.safe_chat_title,
                        'timestamp': zip_manager.timestamp
                    }
                except Exception as e:
                    logger.error(f"準備ZIP下載時發生錯誤: {e}")
                    raise

            # 檢查是否有可用的事件循環
            if hasattr(_app, 'loop') and _app.loop and not _app.loop.is_closed():
                # 在主事件循環中執行準備工作，但不等待下載完成
                future = asyncio.run_coroutine_threadsafe(
                    prepare_and_start_download(),
                    _app.loop
                )
                # 只等待準備工作完成，不等待實際下載 - 5秒足夠準備工作
                result = future.result(timeout=5)
            else:
                # 如果沒有主循環，創建新的事件循環進行準備工作
                try:
                    # 嘗試獲取當前循環
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 如果循環正在運行，使用執行緒執行準備工作
                        import concurrent.futures

                        def run_preparation_in_thread():
                            return asyncio.run(prepare_and_start_download())

                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(run_preparation_in_thread)
                            result = future.result(timeout=5)  # 只需等待準備工作
                    else:
                        result = loop.run_until_complete(prepare_and_start_download())
                except RuntimeError:
                    # 沒有事件循環，創建新的進行準備
                    result = asyncio.run(prepare_and_start_download())

            logger.info(f"ZIP 下載已啟動，管理器ID: {manager_id}，下載將在後台進行")

            return success_response(f'ZIP 下載已啟動，正在後台下載 {len(message_ids)} 個檔案', {
                'manager_id': manager_id,
                'expected_zip_filename': f"{result['safe_chat_title']}_{result['timestamp']}.zip",
                'status': 'started',
                'message': '下載已在後台啟動，請使用狀態API追蹤進度'
            })

        except Exception as process_error:
            logger.error(f"ZIP 下載啟動過程錯誤: {process_error}")
            import traceback
            logger.error(f"ZIP 下載錯誤堆疊: {traceback.format_exc()}")
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

            return error_response(f'ZIP 下載啟動失敗: {str(process_error)}', 500)

    except Exception as e:
        logger.error(f"ZIP 下載 API 錯誤: {e}")
        return error_response(f'ZIP 下載失敗: {str(e)}', 500)


@bp.route("/zip/status/<manager_id>", methods=["GET"])
@require_message_downloader_auth
@handle_api_exception
def check_zip_download_status(manager_id):
    """檢查 ZIP 下載狀態"""
    try:
        if manager_id not in active_zip_managers:
            return error_response('下載任務不存在或已過期', 404)

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
                return error_response('ZIP 檔案不存在或為空', 500)
        else:
            # 回傳進度狀態
            percentage = round((downloaded_files + failed_files) / total_files * 100, 2) if total_files > 0 else 0
            return success_response("下載進行中", {
                'completed': False,
                'progress': {
                    'total_files': total_files,
                    'downloaded_files': downloaded_files,
                    'failed_files': failed_files,
                    'percentage': percentage
                }
            })

    except Exception as e:
        logger.error(f"檢查 ZIP 下載狀態錯誤: {e}")
        return error_response(str(e), 500)


# ============================================================================
# 進度 API 端點 - 用於兼容性
# ============================================================================

@bp.route("/progress", methods=["GET"])
def get_download_progress_api():
    """新架構的進度API - 完全使用新的進度系統"""
    try:
        # 使用新的進度系統
        detailed_progress = calculate_detailed_progress()

        # 創建增強的進度數據
        enhanced_progress = {
            'active': download_progress.get('active', False),
            'total_task': download_progress.get('total_count', 0),
            'completed_task': download_progress.get('completed_count', 0),
            'status_text': download_progress.get('status_text', ''),
            'current_file': download_progress.get('current_file', {
                'name': '',
                'downloaded_bytes': 0,
                'total_bytes': 0,
                'download_speed': 0
            }),
            'current_files': download_progress.get('current_files', {}),
            'concurrent_downloads': len(download_progress.get('current_files', {})),
            'total_download_speed': f"{detailed_progress.get('download_speed', 0)} B/s",
            'session': {
                'active': active_download_session.get('active', False),
                'session_id': active_download_session.get('session_id'),
                'start_time': active_download_session.get('start_time'),
                'total_tasks': active_download_session.get('total_tasks', 0)
            }
        }

        return success_response("獲取進度成功", {
            'progress': enhanced_progress
        })

    except Exception as e:
        logger.error(f"獲取下載進度錯誤: {e}")
        return error_response(f'獲取進度失敗: {str(e)}', 500)