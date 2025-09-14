"""Custom download functionality for specific message IDs from different chats."""
import asyncio
import os
import yaml
from typing import Dict, List, Set, Union
from loguru import logger
import pyrogram
from pyrogram.types import Message

from module.app_db import DatabaseApplication as Application
from module.app import TaskNode, DownloadStatus
from module.language import _t
from utils.meta_data import MetaData
from module.pyrogram_extension import set_meta_data
from utils.format import validate_title


class CustomDownloadManager:
    """Manages custom downloads by specific message IDs."""

    def __init__(self, app: Application, history_file: str = "custom_download_history.yaml"):
        self.app = app
        self.history_file = history_file
        self.downloaded_ids: Dict[str, List[int]] = {}
        self.failed_ids: Dict[str, List[int]] = {}
        self.pending_downloads: Dict[str, List[int]] = {}  # 追蹤等待下載的訊息
        self.download_nodes: List = []  # 儲存下載節點以便後續檢查狀態
        self.load_history()

    def load_history(self):
        """Load download history from file."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
                    self.downloaded_ids = data.get('downloaded_ids', {})
                    self.failed_ids = data.get('failed_ids', {})
                    # Convert string keys to proper format and ensure lists are integers
                    self.downloaded_ids = {str(k): [int(x) for x in v] for k, v in self.downloaded_ids.items()}
                    self.failed_ids = {str(k): [int(x) for x in v] for k, v in self.failed_ids.items()}
            except Exception as e:
                logger.error(f"Error loading history file: {e}")
                self.downloaded_ids = {}
                self.failed_ids = {}
        else:
            self.downloaded_ids = {}
            self.failed_ids = {}

    def save_history(self):
        """Save download history to file."""
        try:
            data = {
                'downloaded_ids': self.downloaded_ids,
                'failed_ids': self.failed_ids
            }
            with open(self.history_file, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logger.error(f"Error saving history file: {e}")

    def mark_downloaded(self, chat_id: Union[str, int], message_id: int):
        """Mark a message as successfully downloaded."""
        chat_key = str(chat_id)
        if chat_key not in self.downloaded_ids:
            self.downloaded_ids[chat_key] = []
        if message_id not in self.downloaded_ids[chat_key]:
            self.downloaded_ids[chat_key].append(message_id)
        
        # Remove from failed list if it was there
        if chat_key in self.failed_ids and message_id in self.failed_ids[chat_key]:
            self.failed_ids[chat_key].remove(message_id)
            if not self.failed_ids[chat_key]:
                del self.failed_ids[chat_key]

    def mark_failed(self, chat_id: Union[str, int], message_id: int):
        """Mark a message as failed to download."""
        chat_key = str(chat_id)
        if chat_key not in self.failed_ids:
            self.failed_ids[chat_key] = []
        if message_id not in self.failed_ids[chat_key]:
            self.failed_ids[chat_key].append(message_id)

    def is_downloaded(self, chat_id: Union[str, int], message_id: int) -> bool:
        """Check if a message has been downloaded and file exists."""
        chat_key = str(chat_id)
        # 首先檢查歷史記錄
        in_history = chat_key in self.downloaded_ids and message_id in self.downloaded_ids[chat_key]
        
        if not in_history:
            return False
        
        # 檢查實際檔案是否存在
        # 由於不知道確切的檔案名稱，我們需要檢查可能的路徑
        try:
            # 獲取群組標題
            chat_title = self.app.config.get("custom_downloads", {}).get("group_tags", {}).get(chat_key, f"chat_{chat_key}")
            chat_title = validate_title(chat_title)
            
            logger.debug(f"Checking file existence for message {message_id} in chat {chat_title} ({chat_key})")
            
            # 檢查兩種可能的保存路徑 (bot和regular)
            for is_bot in [False, True]:
                base_path = self.app.bot_save_path if is_bot else self.app.save_path
                chat_path = os.path.join(base_path, chat_title)
                path_type = "bot" if is_bot else "regular"
                
                logger.debug(f"Checking {path_type} path: {chat_path}")
                
                # 檢查聊天目錄是否存在
                if os.path.exists(chat_path):
                    def check_file_match(file_name):
                        """檢查文件名是否匹配該訊息ID，支援兩種格式:
                        1. {message_id} - {original_filename}
                        2. {message_id}..{extension}
                        """
                        return (file_name.startswith(f"{message_id} - ") or 
                                file_name.startswith(f"{message_id}.."))
                    
                    # 首先在群組根目錄中直接搜尋檔案
                    try:
                        for file_name in os.listdir(chat_path):
                            file_path = os.path.join(chat_path, file_name)
                            if os.path.isfile(file_path) and check_file_match(file_name):
                                logger.debug(f"Found matching file in root: {file_path}")
                                return True
                    except OSError:
                        pass
                    
                    # 然後搜尋所有子目錄 (包括日期目錄、web_downloads等)
                    for sub_dir in os.listdir(chat_path):
                        sub_path = os.path.join(chat_path, sub_dir)
                        if os.path.isdir(sub_path):
                            logger.debug(f"Checking subdirectory: {sub_path}")
                            try:
                                for file_name in os.listdir(sub_path):
                                    if check_file_match(file_name):
                                        file_path = os.path.join(sub_path, file_name)
                                        logger.debug(f"Found matching file in subdir: {file_path}")
                                        if os.path.isfile(file_path):
                                            logger.debug(f"File exists and is valid: {file_path}")
                                            return True
                            except OSError:
                                # 跳過無法讀取的目錄
                                continue
                else:
                    logger.debug(f"Chat path does not exist: {chat_path}")
        
        except Exception as e:
            logger.debug(f"Error checking file existence for message {message_id}: {e}")
        
        # 如果找不到檔案，從歷史記錄中移除
        if chat_key in self.downloaded_ids and message_id in self.downloaded_ids[chat_key]:
            self.downloaded_ids[chat_key].remove(message_id)
            if not self.downloaded_ids[chat_key]:  # 如果列表為空，移除整個鍵
                del self.downloaded_ids[chat_key]
            self.save_history()
            logger.info(f"Removed missing file from history: message {message_id} from chat {chat_id}")
        
        return False

    def get_pending_downloads(self, target_ids: Dict[Union[str, int], List[int]]) -> Dict[str, List[int]]:
        """Get list of message IDs that haven't been downloaded yet."""
        pending = {}
        for chat_id, message_ids in target_ids.items():
            chat_key = str(chat_id)
            pending_for_chat = []
            for msg_id in message_ids:
                if not self.is_downloaded(chat_id, msg_id):
                    pending_for_chat.append(msg_id)
            if pending_for_chat:
                pending[chat_key] = pending_for_chat
        return pending

    def add_to_target_list(self, chat_id: Union[str, int], message_ids: List[int]):
        """Add new message IDs to the target download list."""
        # This would update the config file
        # For now, we'll just log the request
        logger.info(f"Request to add message IDs {message_ids} from chat {chat_id} to download list")

    def remove_from_history(self, chat_id: Union[str, int], message_ids: List[int]):
        """Remove message IDs from download history."""
        chat_key = str(chat_id)
        if chat_key in self.downloaded_ids:
            for msg_id in message_ids:
                if msg_id in self.downloaded_ids[chat_key]:
                    self.downloaded_ids[chat_key].remove(msg_id)
            if not self.downloaded_ids[chat_key]:
                del self.downloaded_ids[chat_key]
        
        if chat_key in self.failed_ids:
            for msg_id in message_ids:
                if msg_id in self.failed_ids[chat_key]:
                    self.failed_ids[chat_key].remove(msg_id)
            if not self.failed_ids[chat_key]:
                del self.failed_ids[chat_key]

    async def download_custom_messages(self, client: pyrogram.Client, target_ids: Dict[Union[str, int], List[int]]):
        """Download specific messages from different chats."""
        logger.info(f"{_t('Starting custom download')} for {len(target_ids)} chats")
        
        # 不過濾已下載的項目，讓主下載邏輯來處理檔案存在檢查
        # 這樣可以確保即使歷史記錄有誤，實際檔案存在檢查仍然有效
        pending_downloads = {}
        for chat_id, message_ids in target_ids.items():
            if message_ids:
                pending_downloads[str(chat_id)] = message_ids
                already_downloaded_count = sum(1 for msg_id in message_ids if self.is_downloaded(chat_id, msg_id))
                logger.info(f"Chat {chat_id}: {len(message_ids)} total, {already_downloaded_count} marked as downloaded (will be checked for file existence)")
        
        if not pending_downloads:
            logger.info("No messages to download")
            return

        total_messages = sum(len(ids) for ids in pending_downloads.values())
        logger.info(f"Found {total_messages} messages to process (main download logic will skip existing files)")

        for chat_id, message_ids in pending_downloads.items():
            await self._download_chat_messages(client, chat_id, message_ids)

        self.save_history()
        logger.success("Custom download completed")

    async def _download_chat_messages(self, client: pyrogram.Client, chat_id: str, message_ids: List[int]):
        """Download specific messages from a chat."""
        logger.info(f"Downloading {len(message_ids)} messages from chat {chat_id}")
        
        # Convert string chat_id to int if needed (for consistency with original project)
        if isinstance(chat_id, str):
            try:
                numeric_chat_id = int(chat_id)
            except ValueError:
                logger.error(f"Invalid chat_id format: {chat_id}")
                return
        else:
            numeric_chat_id = chat_id
        
        try:
            # First check if we can access the chat
            try:
                chat_info = await client.get_chat(numeric_chat_id)
                logger.info(f"Successfully accessed chat {chat_id}: {chat_info.title if hasattr(chat_info, 'title') else 'Unknown'}")
            except Exception as access_error:
                logger.error(f"Cannot access chat {chat_id}: {access_error}")
                
                # Check if this is an AUTH_KEY_UNREGISTERED error
                error_str = str(access_error)
                if "AUTH_KEY_UNREGISTERED" in error_str or "401" in error_str:
                    # Notify web interface about authentication failure
                    try:
                        import requests
                        import threading
                        
                        def notify_auth_error():
                            try:
                                requests.post(
                                    "http://localhost:5001/api/telegram/report_error",
                                    json={"error_type": "AUTH_KEY_UNREGISTERED"},
                                    timeout=5
                                )
                            except Exception as notify_error:
                                logger.debug(f"Failed to notify web interface: {notify_error}")
                        
                        # Run notification in background to not block the main process
                        threading.Thread(target=notify_auth_error, daemon=True).start()
                        
                    except ImportError:
                        # requests not available, use basic notification
                        pass
                
                # Mark all messages as failed due to access issues
                for msg_id in message_ids:
                    self.mark_failed(chat_id, msg_id)
                return
            
            # Get messages in batches (Telegram API limit)
            batch_size = 100
            for i in range(0, len(message_ids), batch_size):
                batch_ids = message_ids[i:i + batch_size]
                messages = await client.get_messages(chat_id=numeric_chat_id, message_ids=batch_ids)
                
                if not isinstance(messages, list):
                    messages = [messages]

                for message in messages:
                    if message and not message.empty:
                        await self._process_message(message, numeric_chat_id, chat_id)
                    else:
                        # Message not found or empty
                        for msg_id in batch_ids:
                            if msg_id not in [m.id for m in messages if m and not m.empty]:
                                logger.warning(f"Message {msg_id} not found in chat {chat_id} - marking as not found")
                                # 不存在的訊息標記為失敗，並加入待清除列表
                                self.mark_failed(chat_id, msg_id)
                                if not hasattr(self, 'not_found_ids'):
                                    self.not_found_ids = set()
                                self.not_found_ids.add((str(chat_id), msg_id))

        except Exception as e:
            error_message = str(e)
            logger.error(f"Error downloading messages from chat {chat_id}: {e}")
            
            # Check if this is an AUTH_KEY_UNREGISTERED error
            if "AUTH_KEY_UNREGISTERED" in error_message or "401" in error_message:
                # Notify web interface about authentication failure
                try:
                    import requests
                    import threading
                    
                    def notify_auth_error():
                        try:
                            requests.post(
                                "http://localhost:5001/api/telegram/report_error",
                                json={"error_type": "AUTH_KEY_UNREGISTERED"},
                                timeout=5
                            )
                        except Exception as notify_error:
                            logger.debug(f"Failed to notify web interface: {notify_error}")
                    
                    # Run notification in background to not block the main process
                    threading.Thread(target=notify_auth_error, daemon=True).start()
                    
                except ImportError:
                    # requests not available, use basic notification
                    pass
            
            # Provide specific guidance for different error types
            if "CHANNEL_INVALID" in error_message:
                logger.error(f"Chat {chat_id} is invalid or inaccessible. Possible reasons:")
                logger.error("- Bot was removed from the group/channel")
                logger.error("- Group/channel was deleted")
                logger.error("- Bot lacks necessary permissions")
                logger.error("- Group/channel became private")
            elif "CHAT_ADMIN_REQUIRED" in error_message:
                logger.error(f"Bot needs admin rights in chat {chat_id}")
            elif "USER_BANNED_IN_CHANNEL" in error_message:
                logger.error(f"Bot is banned from chat {chat_id}")
            elif "PEER_ID_INVALID" in error_message:
                logger.error(f"Invalid peer ID for chat {chat_id}")
            
            # Mark all messages as failed
            for msg_id in message_ids:
                self.mark_failed(chat_id, msg_id)

    async def _process_message(self, message: Message, numeric_chat_id: int, original_chat_id: str):
        """Process and download a single message."""
        try:
            # Create a task node for this download
            node = TaskNode(chat_id=numeric_chat_id)
            
            # Set up metadata
            meta_data = MetaData()
            caption = message.caption
            if caption:
                caption = validate_title(caption)
            set_meta_data(meta_data, message, caption)

            # Use the direct queue reference if available
            if hasattr(self, 'queue_ref') and self.queue_ref is not None:
                # Set download status and add to queue directly
                node.download_status[message.id] = DownloadStatus.Downloading
                await self.queue_ref.put((message, node))
                node.total_task += 1
            else:
                # Fallback to import method
                import media_downloader
                await media_downloader.add_download_task(message, node)
            
            # Track this download
            if original_chat_id not in self.pending_downloads:
                self.pending_downloads[original_chat_id] = []
            self.pending_downloads[original_chat_id].append(message.id)
            self.download_nodes.append((node, original_chat_id, message.id))
            
            
        except Exception as e:
            logger.error(f"Error processing message {message.id} from chat {original_chat_id}: {e}")
            self.mark_failed(original_chat_id, message.id)

    async def update_download_status(self):
        """Update download status after processing is complete."""
        import asyncio
        from module.app import DownloadStatus
        
        # Wait for downloads to complete by checking node status
        max_wait_time = 300  # 5 minutes maximum wait
        check_interval = 2   # Check every 2 seconds
        waited_time = 0
        
        logger.info(f"Waiting for {len(self.download_nodes)} downloads to complete...")
        
        # 初始化全局下載結果，讓 bot 能顯示下載項目
        if hasattr(self, 'task_node') and self.task_node:
            try:
                import time
                from module.download_stat import get_download_result
                download_result = get_download_result()
                
                # 如果還沒有這個 chat_id，創建它
                if self.task_node.chat_id not in download_result:
                    download_result[self.task_node.chat_id] = {}
                
                # 為每個下載項目創建初始進度
                current_time = time.time()
                for node, chat_id, message_id in self.download_nodes:
                    if message_id not in download_result[self.task_node.chat_id]:
                        # 創建進行中的下載項目（0% 進度）
                        estimated_size = 50 * 1024 * 1024  # 假設 50MB 平均大小
                        download_result[self.task_node.chat_id][message_id] = {
                            "down_byte": 0,
                            "total_size": estimated_size,
                            "file_name": f"message_{message_id}.mp4",
                            "start_time": current_time,
                            "end_time": current_time,
                            "download_speed": 0,
                            "each_second_total_download": 0,
                            "task_id": self.task_node.task_id,
                        }
                        logger.debug(f"Initialized download progress for message {message_id}")
                
            except Exception as e:
                logger.debug(f"Error initializing download progress: {e}")
        
        while waited_time < max_wait_time:
            all_completed = True
            downloading_count = 0
            pending_count = 0
            completed_count = 0
            
            # 用來追蹤已處理的下載，避免重複更新 TaskNode
            if not hasattr(self, '_processed_downloads'):
                self._processed_downloads = set()
            
            for node, chat_id, message_id in self.download_nodes:
                try:
                    if hasattr(node, 'download_status') and message_id in node.download_status:
                        status = node.download_status[message_id]
                        status_key = f"{chat_id}_{message_id}"
                        
                        if status == DownloadStatus.Downloading:
                            all_completed = False
                            downloading_count += 1
                        elif status in [DownloadStatus.SuccessDownload, DownloadStatus.FailedDownload, DownloadStatus.SkipDownload]:
                            # These are completed statuses
                            completed_count += 1
                            
                            # 實時更新 TaskNode 進度（僅一次）
                            if status_key not in self._processed_downloads and hasattr(self, 'task_node') and self.task_node:
                                self._processed_downloads.add(status_key)
                                
                                # 更新全局下載結果為完成狀態
                                try:
                                    import time
                                    from module.download_stat import get_download_result
                                    download_result = get_download_result()
                                    
                                    # 更新為完成狀態（100% 進度）
                                    if (self.task_node.chat_id in download_result and 
                                        message_id in download_result[self.task_node.chat_id]):
                                        item = download_result[self.task_node.chat_id][message_id]
                                        total_size = item["total_size"]
                                        current_time = time.time()
                                        
                                        # 標記為完成
                                        item["down_byte"] = total_size  # 100% 完成
                                        item["end_time"] = current_time
                                        item["download_speed"] = total_size / max(1, current_time - item["start_time"])
                                        
                                        logger.debug(f"Updated download result for message {message_id} to completed")
                                
                                except Exception as e:
                                    logger.debug(f"Error updating global download result: {e}")
                                
                                # 更新 TaskNode 統計
                                if status == DownloadStatus.SuccessDownload:
                                    self.task_node.success_download_task += 1
                                    logger.debug(f"TaskNode real-time update: success {self.task_node.success_download_task}/{self.task_node.total_download_task}")
                                elif status == DownloadStatus.SkipDownload:
                                    self.task_node.skip_download_task += 1
                                    logger.debug(f"TaskNode real-time update: skip {self.task_node.skip_download_task}/{self.task_node.total_download_task}")
                                elif status == DownloadStatus.FailedDownload:
                                    self.task_node.failed_download_task += 1
                                    logger.debug(f"TaskNode real-time update: failed {self.task_node.failed_download_task}/{self.task_node.total_download_task}")
                        else:
                            # Other statuses, still consider as not completed
                            all_completed = False
                            pending_count += 1
                    else:
                        # If status not set yet, still waiting
                        all_completed = False
                        pending_count += 1
                except Exception as e:
                    logger.debug(f"Error checking status for message {message_id}: {e}")
                    pending_count += 1
                    all_completed = False
            
            # 更新進行中下載的模擬進度
            if hasattr(self, 'task_node') and self.task_node and downloading_count > 0:
                try:
                    from module.download_stat import get_download_result
                    download_result = get_download_result()
                    
                    if self.task_node.chat_id in download_result:
                        current_time = time.time()
                        for node, chat_id, message_id in self.download_nodes:
                            if (hasattr(node, 'download_status') and 
                                message_id in node.download_status and
                                node.download_status[message_id] == DownloadStatus.Downloading):
                                
                                # 更新進行中的下載進度（模擬漸進式進度）
                                if message_id in download_result[self.task_node.chat_id]:
                                    item = download_result[self.task_node.chat_id][message_id]
                                    elapsed = current_time - item["start_time"]
                                    
                                    # 模擬進度：根據時間計算進度百分比（最多到 90%）
                                    progress_ratio = min(0.9, elapsed / 30.0)  # 30秒內達到90%
                                    new_downloaded = int(item["total_size"] * progress_ratio)
                                    
                                    if new_downloaded > item["down_byte"]:
                                        item["down_byte"] = new_downloaded
                                        item["end_time"] = current_time
                                        if elapsed > 0:
                                            item["download_speed"] = int(new_downloaded / elapsed)
                                        
                                        logger.debug(f"Updated download progress for message {message_id}: {int(progress_ratio*100)}%")
                
                except Exception as e:
                    logger.debug(f"Error updating download progress: {e}")
            
            # 更新 web 進度
            try:
                from module.web import update_download_progress
                total_tasks = len(self.download_nodes)
                
                # 計算進度
                status_text = f"下載中... ({downloading_count} 下載中, {completed_count} 已完成)"
                
                # 確保傳遞正確的完成數量
                update_download_progress(completed_count, total_tasks, status_text)
                
                # Debug 資訊
                print(f"Progress Debug: completed={completed_count}, total={total_tasks}, downloading={downloading_count}, pending={pending_count}")
                logger.debug(f"Web progress updated: {completed_count}/{total_tasks} - {status_text}")
            except Exception as e:
                logger.debug(f"Error updating web progress: {e}")
            
            # Log current status every 10 seconds
            if waited_time % 10 == 0:
                logger.info(f"Download status: {downloading_count} downloading, {pending_count} pending, {completed_count} completed, waited {waited_time}s")
            
            if all_completed:
                logger.info("All downloads completed")
                break
                
            await asyncio.sleep(check_interval)
            waited_time += check_interval
        
        # Now check final status of all downloads
        successful_count = 0
        failed_count = 0
        
        for node, chat_id, message_id in self.download_nodes:
            try:
                if hasattr(node, 'download_status') and message_id in node.download_status:
                    status = node.download_status[message_id]
                    
                    if status == DownloadStatus.SuccessDownload:
                        self.mark_downloaded(chat_id, message_id)
                        successful_count += 1
                        logger.success(f"Successfully downloaded message {message_id} from chat {chat_id}")
                            
                    elif status == DownloadStatus.SkipDownload:
                        # SkipDownload means file already exists, count as successful
                        self.mark_downloaded(chat_id, message_id)
                        successful_count += 1
                        logger.success(f"Skipped (already exists) message {message_id} from chat {chat_id}")
                            
                    elif status == DownloadStatus.FailedDownload:
                        self.mark_failed(chat_id, message_id)
                        failed_count += 1
                        logger.warning(f"Failed to download message {message_id} from chat {chat_id}: {status}")
                            
                    else:
                        # Still in other status, consider as failed
                        self.mark_failed(chat_id, message_id)
                        failed_count += 1
                        logger.warning(f"Message {message_id} from chat {chat_id} timeout or unknown status: {status}")
                else:
                    # No status available, consider as failed
                    self.mark_failed(chat_id, message_id)
                    failed_count += 1
                    logger.warning(f"No download status available for message {message_id} from chat {chat_id}")
                        
            except Exception as e:
                logger.error(f"Error checking status for message {message_id} from chat {chat_id}: {e}")
                self.mark_failed(chat_id, message_id)
                failed_count += 1
        
        # 最終進度更新
        try:
            from module.web import update_download_progress
            total_tasks = len(self.download_nodes)
            if failed_count > 0:
                final_status = f"下載完成! {successful_count} 成功, {failed_count} 失敗"
            else:
                final_status = f"下載完成! 全部 {successful_count} 項目已完成"
            update_download_progress(total_tasks, total_tasks, final_status)
        except Exception as e:
            logger.debug(f"Error updating final web progress: {e}")
        
        # Remove successfully downloaded items and not found items from target_ids
        if successful_count > 0 or (hasattr(self, 'not_found_ids') and self.not_found_ids):
            try:
                target_ids = self.app.config.get('custom_downloads', {}).get('target_ids', {})
                updated_target_ids = {}
                removed_successful = 0
                removed_not_found = 0
                
                for chat_id, message_ids in target_ids.items():
                    chat_key = str(chat_id)
                    # Keep only messages that were not successfully downloaded and exist
                    remaining_ids = []
                    for msg_id in message_ids:
                        # 檢查是否不存在
                        if hasattr(self, 'not_found_ids') and (str(chat_id), msg_id) in self.not_found_ids:
                            logger.info(f"Removing not found message {msg_id} from target_ids for chat {chat_id}")
                            removed_not_found += 1
                        # 檢查是否已下載
                        elif self.is_downloaded(chat_id, msg_id):
                            logger.info(f"Removing successfully downloaded message {msg_id} from target_ids for chat {chat_id}")
                            removed_successful += 1
                        else:
                            remaining_ids.append(msg_id)
                    
                    if remaining_ids:
                        updated_target_ids[chat_id] = remaining_ids
                
                # Update the config
                self.app.config['custom_downloads']['target_ids'] = updated_target_ids
                self.app.update_config()
                
                if removed_successful > 0 or removed_not_found > 0:
                    logger.info(f"Updated config: removed {removed_successful} downloaded + {removed_not_found} not found items from target_ids")
                
                # 清除不存在ID的追蹤
                if hasattr(self, 'not_found_ids'):
                    delattr(self, 'not_found_ids')
                    
            except Exception as e:
                logger.error(f"Error updating target_ids in config: {e}")
        
        # 設置 TaskNode 為完成狀態並清理全局下載結果
        if hasattr(self, 'task_node') and self.task_node:
            self.task_node.is_running = False
            logger.info(f"TaskNode {self.task_node.task_id} set to finished state")
            
            # 清理全局下載結果中的項目
            try:
                from module.download_stat import get_download_result
                download_result = get_download_result()
                
                if self.task_node.chat_id in download_result:
                    # 移除這個 task_id 的下載項目
                    items_to_remove = []
                    for message_id, item in download_result[self.task_node.chat_id].items():
                        if item.get("task_id") == self.task_node.task_id:
                            items_to_remove.append(message_id)
                    
                    for message_id in items_to_remove:
                        del download_result[self.task_node.chat_id][message_id]
                        logger.debug(f"Cleaned up download result for message {message_id}")
                    
                    # 如果 chat 下沒有其他項目，刪除整個 chat
                    if not download_result[self.task_node.chat_id]:
                        del download_result[self.task_node.chat_id]
                        logger.debug(f"Cleaned up empty chat {self.task_node.chat_id} from download results")
            
            except Exception as e:
                logger.debug(f"Error cleaning up download results: {e}")

        # Log summary
        if failed_count > 0:
            logger.info(f"Download completed: {successful_count} successful (including skipped), {failed_count} failed")
        else:
            logger.success(f"Download completed: All {successful_count} items finished successfully (including skipped)")
        
        # 返回統計信息供上層函數使用
        return {
            'successful_count': successful_count,
            'failed_count': failed_count,
            'total_count': successful_count + failed_count
        }
        
        # Save updated status
        self.save_history()
        
        # Clear tracking data
        self.pending_downloads.clear()
        self.download_nodes.clear()


async def run_custom_download(app: Application, client: pyrogram.Client, queue_ref=None, task_node=None):
    """Main function to run custom download based on config."""
    import asyncio
    
    # Wait a bit to ensure worker tasks are ready
    await asyncio.sleep(1)
    
    custom_config = app.config.get('custom_downloads', {})
    
    if not custom_config.get('enable', False):
        logger.info("Custom download is disabled")
        return

    target_ids = custom_config.get('target_ids', {})
    if not target_ids:
        logger.info("No target IDs specified for custom download")
        return

    manager = CustomDownloadManager(app)
    manager.queue_ref = queue_ref  # Pass the queue reference
    manager.task_node = task_node  # Pass the TaskNode for progress tracking
    
    # 只清理失敗記錄，保留已下載記錄以避免重複下載
    logger.info("Clearing failed download records for re-download...")
    for chat_id, message_ids in target_ids.items():
        chat_key = str(chat_id)
        
        # 清理失敗記錄，讓失敗的項目可以重試
        if chat_key in manager.failed_ids:
            overlap_ids = [msg_id for msg_id in message_ids if msg_id in manager.failed_ids[chat_key]]
            for msg_id in overlap_ids:
                manager.failed_ids[chat_key].remove(msg_id)
                logger.info(f"Cleared failed status for message {msg_id} in chat {chat_id}")
            if not manager.failed_ids[chat_key]:
                del manager.failed_ids[chat_key]
        
        # 不要清理已下載記錄，避免重複下載已存在的檔案
        # 已下載的項目會被跳過，不會重複下載
    
    # 保存清理後的歷史
    manager.save_history()
    
    await manager.download_custom_messages(client, target_ids)
    
    # 等待下載完成後更新狀態
    download_stats = await manager.update_download_status()
    
    # TaskNode 系統會自動處理完成通知，不需要手動發送
    # download_stats 仍然可用於其他目的


async def run_custom_download_for_selected(app: Application, client: pyrogram.Client, queue_ref=None, selected_target_ids=None):
    """為選中的項目運行自訂下載"""
    import asyncio
    
    # Wait a bit to ensure worker tasks are ready
    await asyncio.sleep(1)
    
    if not selected_target_ids:
        logger.info("No selected target IDs specified")
        return

    logger.info(f"Starting selected download for {len(selected_target_ids)} chats")

    manager = CustomDownloadManager(app)
    manager.queue_ref = queue_ref  # Pass the queue reference
    
    # 只清理失敗記錄，保留已下載記錄以避免重複下載
    logger.info("Clearing failed download records for selected items...")
    for chat_id, message_ids in selected_target_ids.items():
        chat_key = str(chat_id)
        
        # 清理失敗記錄，讓失敗的項目可以重試
        if chat_key in manager.failed_ids:
            overlap_ids = [msg_id for msg_id in message_ids if msg_id in manager.failed_ids[chat_key]]
            for msg_id in overlap_ids:
                manager.failed_ids[chat_key].remove(msg_id)
                logger.info(f"Cleared failed status for selected message {msg_id} in chat {chat_id}")
            if not manager.failed_ids[chat_key]:
                del manager.failed_ids[chat_key]
        
        # 不要清理已下載記錄，避免重複下載已存在的檔案
        # 如果用戶真的想重新下載，他們可以手動刪除檔案
    
    # 保存清理後的歷史
    manager.save_history()
    
    await manager.download_custom_messages(client, selected_target_ids)
    
    # 等待下載完成後更新狀態
    await manager.update_download_status()