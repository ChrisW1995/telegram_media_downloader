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
    reset_download_progress,
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
        force_restart = data.get('force_restart', False)  # 允許強制重啟

        logger.info(f"Fast Test API called with chat_id: {chat_id}, message_ids: {message_ids}, force_restart: {force_restart}")

        if not chat_id or not message_ids:
            logger.error(f"Missing data - chat_id: {chat_id}, message_ids: {message_ids}")
            return error_response('請提供群組 ID 和訊息 ID 列表')

        # 檢查是否有活躍的下載會話
        if not force_restart and is_download_active():
            logger.warning("下載任務已在進行中,拒絕添加新任務")
            return error_response('已有下載任務進行中,請等待完成或取消後再試', 409)

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
                    from module.custom_download import run_custom_download_for_selected
                    from module.download_stat import set_download_state, DownloadState

                    # 設置下載狀態為下載中
                    set_download_state(DownloadState.Downloading)

                    # 初始化進度系統
                    initialize_download_session(len(new_ids))

                    # 為 message_downloader 創建 TaskNode，支援 bot 通知
                    user_id = session.get('user_id')
                    logger.info(f"Debug - user_id: {user_id}, has_download_bot: {hasattr(_app, 'download_bot') and _app.download_bot}")

                    # 創建 TaskNode 來支持進度通知（關鍵修復：使用 async 任務避免競態條件）
                    if user_id and hasattr(_app, 'download_bot') and _app.download_bot:
                            try:
                                import time
                                import pyrogram
                                from module.download_stat import TaskNode
                                from module.app import TaskType
                                from module.web import _queue

                                # 構建初始通知訊息
                                chat_id_str = str(chat_id)
                                start_message = f"""🚀 **Message Downloader 下載開始**

**群組 ID**: `{chat_id_str}`
**訊息數量**: {len(new_ids)}
**開始時間**: {time.strftime('%Y-%m-%d %H:%M:%S')}

⏳ 正在準備下載..."""

                                # 修復 1: 將 chat_id 轉換為整數
                                chat_id_int = int(chat_id) if isinstance(chat_id, str) else chat_id

                                # 異步函數：發送訊息並啟動下載（模仿 bot.py 流程）
                                async def setup_and_start_download():
                                    try:
                                        # 1. 先發送訊息（模仿 bot.py:1186-1188）
                                        reply_message_obj = await _app.download_bot.bot.send_message(
                                            user_id, start_message, parse_mode=pyrogram.enums.ParseMode.MARKDOWN
                                        )
                                        reply_message_id = reply_message_obj.id
                                        logger.info(f"Sent start notification to user {user_id}, reply_message_id: {reply_message_id}")

                                        # 2. 創建 TaskNode（模仿 bot.py:1189-1199）
                                        task_node = TaskNode(
                                            chat_id=chat_id_int,
                                            from_user_id=user_id,
                                            bot=_app.download_bot,
                                            reply_message_id=reply_message_id,  # 關鍵：已有 reply_message_id
                                            task_id=_app.download_bot.gen_task_id()
                                        )
                                        task_node.is_running = True
                                        task_node.is_custom_download = True
                                        task_node.task_type = TaskType.Download
                                        task_node.client = client
                                        task_node.total_task = len(new_ids)

                                        # 3. 添加到追蹤列表（模仿 bot.py:1201）
                                        _app.download_bot.add_task_node(task_node)
                                        logger.info(f"TaskNode {task_node.task_id} added with reply_message_id={reply_message_id}")

                                        # 4. 開始下載（模仿 bot.py:1202-1204）
                                        selected_target_ids = {chat_id: new_ids}
                                        await run_custom_download_for_selected(_app, client, queue_ref=_queue, selected_target_ids=selected_target_ids, task_node=task_node)

                                    except Exception as e:
                                        logger.error(f"Error in setup_and_start_download: {e}")

                                # 創建異步任務
                                download_task = _app.loop.create_task(setup_and_start_download())
                                download_triggered = True
                                logger.info("Download task triggered with bot notification support")

                            except Exception as task_error:
                                logger.error(f"Failed to create TaskNode with bot support: {task_error}")
                                # 回退到無 bot 通知的下載
                                selected_target_ids = {chat_id: new_ids}
                                from module.web import _queue
                                download_task = _app.loop.create_task(
                                    run_custom_download_for_selected(_app, client, queue_ref=_queue, selected_target_ids=selected_target_ids)
                                )
                                download_triggered = True
                                logger.info("Download task triggered without bot notification")
                    else:
                        # 普通下載（無 bot 通知）
                        selected_target_ids = {chat_id: new_ids}
                        from module.web import _queue
                        download_task = _app.loop.create_task(
                            run_custom_download_for_selected(_app, client, queue_ref=_queue, selected_target_ids=selected_target_ids)
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


@bp.route("/cleanup", methods=["POST"])
@require_message_downloader_auth
@handle_api_exception
def cleanup_stale_session():
    """清理殘留的下載會話狀態 - 用於頁面刷新後的狀態恢復"""
    try:
        from module.download_stat import get_download_state, set_download_state, DownloadState

        # 檢查當前下載狀態
        current_state = get_download_state()
        logger.info(f"🧹 Cleanup requested, current state: {current_state.name}")

        # 頁面刷新時,無條件清理所有狀態
        # 因為刷新表示用戶想要重新開始,不管之前的下載狀態如何

        # 重置進度系統
        reset_download_progress()
        # 強制設置狀態為 IDLE
        set_download_state(DownloadState.Idle)
        logger.info("✅ Reset download state to Idle")

        # 清除 active_zip_managers 中的殘留 manager
        global active_zip_managers
        if active_zip_managers:
            manager_count = len(active_zip_managers)
            logger.info(f"🧹 Found {manager_count} active ZIP managers to clean up")

            # 清理臨時檔案和目錄
            for manager_id, zip_manager in list(active_zip_managers.items()):
                try:
                    # 1. 取消背景任務
                    if hasattr(zip_manager, 'background_task') and zip_manager.background_task:
                        if not zip_manager.background_task.done():
                            zip_manager.background_task.cancel()
                            logger.info(f"🛑 Cancelled background task for manager {manager_id}")
                        else:
                            logger.info(f"ℹ️ Background task already completed for manager {manager_id}")

                    # 2. 清除下載緩存狀態和註冊表（將 Downloading 改為 FailedDownload）
                    if hasattr(zip_manager, 'message_ids') and hasattr(zip_manager, 'chat_id'):
                        try:
                            from module.pyrogram_extension import _download_cache, _active_message_downloads
                            from module.app import DownloadStatus

                            for message_id in zip_manager.message_ids:
                                # 清除普通緩存鍵
                                cache_key_normal = (zip_manager.chat_id, message_id)
                                # 清除專屬緩存鍵
                                cache_key_custom = (zip_manager.chat_id, message_id, f"md_{manager_id}")

                                _download_cache[cache_key_normal] = DownloadStatus.FailedDownload
                                _download_cache[cache_key_custom] = DownloadStatus.FailedDownload

                                # ⚠️ 清除全域下載任務註冊表
                                message_key = (zip_manager.chat_id, message_id)
                                registered_manager = _active_message_downloads.get(message_key)
                                if registered_manager == manager_id:
                                    _active_message_downloads.pop(message_key, None)

                            logger.info(f"🧹 Cleared download cache and registry for {len(zip_manager.message_ids)} messages")
                        except Exception as cache_error:
                            logger.warning(f"Failed to clear download cache: {cache_error}")

                    # 3. 設置取消標記
                    if hasattr(zip_manager, 'is_cancelled'):
                        zip_manager.is_cancelled = True

                    # 4. 刪除 ZIP 檔案(如果已創建)
                    if hasattr(zip_manager, 'zip_path') and os.path.exists(zip_manager.zip_path):
                        try:
                            os.remove(zip_manager.zip_path)
                            logger.info(f"🗑️ Deleted ZIP file: {zip_manager.zip_path}")
                        except Exception as zip_error:
                            logger.warning(f"Failed to delete ZIP file {zip_manager.zip_path}: {zip_error}")

                    # 4. 清理臨時目錄(包含所有下載的檔案)
                    if hasattr(zip_manager, 'temp_dir') and os.path.exists(zip_manager.temp_dir):
                        import shutil
                        shutil.rmtree(zip_manager.temp_dir)
                        logger.info(f"🗑️ Deleted temp dir: {zip_manager.temp_dir}")
                except Exception as cleanup_error:
                    logger.warning(f"❌ Failed to cleanup manager {manager_id}: {cleanup_error}")

            active_zip_managers.clear()
            logger.info(f"✅ Cleared {manager_count} active ZIP managers")
        else:
            logger.info("ℹ️ No active ZIP managers to clean up")

        # 清理所有 tgdl_zip_ 開頭的臨時目錄 (以防有遺漏)
        import tempfile
        import shutil
        temp_base_dir = tempfile.gettempdir()
        cleaned_count = 0
        try:
            for item in os.listdir(temp_base_dir):
                if item.startswith('tgdl_zip_'):
                    temp_path = os.path.join(temp_base_dir, item)
                    if os.path.isdir(temp_path):
                        try:
                            shutil.rmtree(temp_path)
                            cleaned_count += 1
                            logger.info(f"🗑️ Cleaned up orphaned temp dir: {temp_path}")
                        except Exception as e:
                            logger.warning(f"Failed to cleanup orphaned temp dir {temp_path}: {e}")
            if cleaned_count > 0:
                logger.info(f"✅ Cleaned up {cleaned_count} orphaned temp directories")
        except Exception as e:
            logger.warning(f"Failed to scan temp directory: {e}")

        logger.info("✅ Stale session cleaned up successfully")
        return success_response("已清理殘留狀態")

    except Exception as e:
        logger.error(f"❌ Error cleaning up stale session: {e}")
        return error_response(f"清理失敗: {str(e)}")


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
        self.background_task = None  # 追蹤背景任務
        self.is_cancelled = False  # 取消標記
        self.zip_path = None
        self.safe_chat_title = None
        self.timestamp = None
        self.zip_ready = False
        self.message_original_filenames = {}  # 儲存每個訊息的原始檔案名稱

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

        # 檢查是否已被取消
        if self.is_cancelled:
            logger.warning("下載任務已被取消,中止執行")
            return

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
                    # 修復：使用 message_ids 參數名，並處理返回的列表或單個訊息
                    result = await client.get_messages(chat_id=self.chat_id, message_ids=message_id)
                    # get_messages 返回單個訊息時直接是 Message 對象，返回多個時是列表
                    message = result if not isinstance(result, list) else result[0] if result else None
                    if message and message.media:
                        # 提取並保存原始檔案名稱
                        original_filename = None
                        if message.video and message.video.file_name:
                            original_filename = message.video.file_name
                        elif message.audio and message.audio.file_name:
                            original_filename = message.audio.file_name
                        elif message.document and message.document.file_name:
                            original_filename = message.document.file_name
                        elif message.animation and message.animation.file_name:
                            original_filename = message.animation.file_name
                        elif message.photo:
                            # 照片通常沒有檔案名稱，使用 message_id
                            original_filename = f"photo_{message_id}.jpg"
                        elif message.voice:
                            original_filename = f"voice_{message_id}.ogg"
                        elif message.sticker:
                            original_filename = f"sticker_{message_id}.webp"
                        else:
                            original_filename = f"file_{message_id}"

                        # 保存原始檔案名稱
                        self.message_original_filenames[message_id] = original_filename
                        logger.info(f"訊息 {message_id} 原始檔案名稱: {original_filename}")

                        # 為每個訊息創建全新的 TaskNode 並設置ZIP管理器引用
                        node = TaskNode(chat_id=self.chat_id)
                        node.is_custom_download = True
                        node.zip_download_manager = self
                        node.zip_message_id = message_id  # 用於ZIP管理器回調

                        # ⚠️ 關鍵修復：強制重置下載狀態，避免頁面刷新後狀態殘留
                        # 每次創建新的 TaskNode 時確保狀態字典是全新的
                        node.download_status = {}
                        node.total_task = 0

                        # 手動設置下載狀態並加入隊列（模擬 add_download_task 的行為）
                        if not message.empty:
                            node.download_status[message.id] = DownloadStatus.Downloading
                            await _queue.put((message, node))
                            node.total_task += 1
                            logger.info(f"訊息 {message_id} 已加入Worker Pool隊列")
                        else:
                            self.failed_downloads.append(f"訊息 {message_id} 是空訊息")
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
        # ⚠️ 檢查任務是否已被取消（例如被新任務取代或用戶刷新頁面）
        if hasattr(self, 'is_cancelled') and self.is_cancelled:
            logger.info(f"任務已被取消，跳過 ZIP 創建: {self.zip_path}")
            return

        # 檢查臨時目錄是否仍然存在
        temp_dir = os.path.dirname(self.zip_path)
        if not os.path.exists(temp_dir):
            logger.warning(f"臨時目錄已被清理，跳過 ZIP 創建: {temp_dir}")
            return

        logger.info(f"開始創建 ZIP 檔案: {self.zip_path}")

        try:
            with zipfile.ZipFile(self.zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_info in self.downloaded_files:
                    try:
                        # 使用保存的原始檔案名稱（從 API 獲取的）
                        message_id = file_info['message_id']
                        original_filename = self.message_original_filenames.get(message_id)

                        # 如果沒有保存的原始檔案名稱，從下載路徑提取作為備用
                        if not original_filename:
                            original_filename = os.path.basename(file_info['file_path'])
                            logger.warning(f"訊息 {message_id} 沒有保存原始檔案名稱，使用下載路徑提取: {original_filename}")

                        # ZIP 內直接使用原始檔案名稱，不加任何前綴
                        zip_filename_in_archive = original_filename

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

        # ⚠️ 防止重複下載：檢查是否有相同訊息的下載正在進行
        # 使用排序後的 message_ids 作為唯一標識
        sorted_message_ids = tuple(sorted(message_ids))
        duplicate_check_key = f"{chat_id}_{sorted_message_ids}"

        if active_zip_managers:
            for existing_manager_id, existing_manager in list(active_zip_managers.items()):
                # 跳過佔位符（placeholder）
                if existing_manager is None:
                    continue

                # 檢查是否有相同的 chat_id 和 message_ids
                if (hasattr(existing_manager, 'chat_id') and existing_manager.chat_id == chat_id and
                    hasattr(existing_manager, 'message_ids') and
                    set(existing_manager.message_ids) == set(message_ids)):
                    # 檢查背景任務是否還在運行
                    if (hasattr(existing_manager, 'background_task') and
                        existing_manager.background_task and
                        not existing_manager.background_task.done()):
                        logger.warning(f"ZIP 下載請求被拒絕：相同訊息的下載任務正在進行中 (manager: {existing_manager_id})")
                        return error_response('相同訊息的下載任務正在進行中，請等待完成後再試', 409)

        # 立即加入一個佔位符，防止後續的並發請求通過檢查
        temp_manager_id = f"{chat_id}_{int(time.time() * 1000000)}"  # 使用微秒確保唯一性
        active_zip_managers[temp_manager_id] = None  # 佔位符
        logger.info(f"加入下載佔位符: {temp_manager_id}")

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

        # ⚠️ 先生成唯一ID，使用微秒確保唯一性
        manager_id = f"{chat_id}_{int(time.time() * 1000000)}"

        # 創建 ZIP 下載管理器並立即設置 manager_id
        zip_manager = ZipDownloadManager(chat_id, message_ids, temp_dir)
        zip_manager.manager_id = manager_id  # ⚠️ 在創建後立即設置，確保 TaskNode 能正確獲取
        zip_manager.chat_id = chat_id  # 確保 chat_id 被設置
        zip_manager.message_ids = message_ids  # 確保 message_ids 被設置

        # 移除佔位符
        if temp_manager_id in active_zip_managers:
            del active_zip_managers[temp_manager_id]
            logger.info(f"移除下載佔位符: {temp_manager_id}")

        active_zip_managers[manager_id] = zip_manager
        logger.info(f"加入實際下載管理器: {manager_id}")

        try:
            # 異步準備和啟動下載 - 完全非阻塞模式
            async def prepare_and_start_download():
                try:
                    logger.info("開始執行 prepare_download()")
                    await zip_manager.prepare_download()
                    logger.info(f"ZIP 管理器準備完成: {zip_manager.safe_chat_title}")

                    # 在後台啟動下載任務，並追蹤 task
                    logger.info("開始創建背景下載任務")
                    zip_manager.background_task = asyncio.create_task(
                        zip_manager.start_downloads_via_worker_pool()
                    )
                    logger.info(f"背景下載任務已啟動: {zip_manager.background_task}")

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
                # 使用 asyncio.create_task 而不是 run_coroutine_threadsafe，避免跨線程問題
                asyncio.run_coroutine_threadsafe(
                    prepare_and_start_download(),
                    _app.loop
                )
                # 不等待結果，立即返回，讓下載在後台進行
                # 使用預設值作為 result
                result = {
                    'manager_id': manager_id,
                    'zip_path': zip_manager.zip_path if hasattr(zip_manager, 'zip_path') else f"{chat_id}_download.zip",
                    'safe_chat_title': f"Chat_{chat_id}",
                    'timestamp': datetime.now().strftime("%Y%m%d_%H%M%S")
                }
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
                            result = future.result(timeout=15)  # 增加到 15 秒
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
            # 清理失敗的管理器和佔位符
            if 'manager_id' in locals() and manager_id in active_zip_managers:
                del active_zip_managers[manager_id]
            if 'temp_manager_id' in locals() and temp_manager_id in active_zip_managers:
                del active_zip_managers[temp_manager_id]
                logger.info(f"清理失敗的佔位符: {temp_manager_id}")

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
        global active_zip_managers

        if manager_id not in active_zip_managers:
            logger.warning(f"❌ Manager {manager_id} not found in active_zip_managers (可能已被清理)")
            logger.info(f"Current active managers: {list(active_zip_managers.keys())}")
            return error_response('下載任務不存在或已被清理,請重新開始下載', 410)  # 410 Gone

        zip_manager = active_zip_managers[manager_id]

        total_files = len(zip_manager.message_ids)
        downloaded_files = len(zip_manager.downloaded_files)
        failed_files = len(zip_manager.failed_downloads)

        # 檢查是否完成
        is_completed = hasattr(zip_manager, 'zip_ready') and zip_manager.zip_ready

        if is_completed:
            # 檢查 ZIP 檔案是否存在
            if os.path.exists(zip_manager.zip_path) and os.path.getsize(zip_manager.zip_path) > 0:
                # 檢查是否是下載請求（帶 download 參數）
                from flask import request
                if request.args.get('download') == 'true':
                    # 這是實際下載請求

                    # 雙重檢查: 確認 manager 還在 active 列表中 (防止在請求途中被清理)
                    if manager_id not in active_zip_managers:
                        logger.warning(f"❌ Manager {manager_id} was removed during download request")
                        return error_response('下載任務已被取消', 410)

                    # 再次檢查是否被標記為取消
                    if hasattr(zip_manager, 'is_cancelled') and zip_manager.is_cancelled:
                        logger.warning(f"❌ Manager {manager_id} is marked as cancelled")
                        return error_response('下載任務已被取消', 410)

                    zip_filename = f"{zip_manager.safe_chat_title}_{zip_manager.timestamp}.zip"

                    # 清理管理器
                    del active_zip_managers[manager_id]

                    logger.info(f"📥 Sending ZIP file: {zip_filename}")
                    return send_file(
                        zip_manager.zip_path,
                        as_attachment=True,
                        download_name=zip_filename,
                        mimetype='application/zip'
                    )
                else:
                    # 這是狀態檢查請求，回傳完成狀態（不刪除 manager）
                    return success_response("ZIP 檔案已準備完成", {
                        'completed': True,
                        'ready': True,
                        'progress': {
                            'total_files': total_files,
                            'downloaded_files': downloaded_files,
                            'failed_files': failed_files,
                            'percentage': 100
                        }
                    })
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