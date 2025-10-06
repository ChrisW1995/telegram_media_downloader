"""Download Stat"""
import asyncio
import time
from enum import Enum

from loguru import logger
from pyrogram import Client

from module.app import TaskNode


class DownloadState(Enum):
    """Download state"""

    Idle = 0
    Downloading = 1
    StopDownload = 2
    Cancelled = 3
    Completed = 4


_download_result: dict = {}
_total_download_speed: int = 0
_total_download_size: int = 0
_last_download_time: float = time.time()
_download_state: DownloadState = DownloadState.Idle


def get_download_result() -> dict:
    """get global download result"""
    return _download_result


def get_total_download_speed() -> int:
    """get total download speed"""
    return _total_download_speed


def get_download_state() -> DownloadState:
    """get download state"""
    return _download_state


# pylint: disable = W0603
def set_download_state(state: DownloadState):
    """set download state"""
    global _download_state
    _download_state = state


async def update_download_status(
    down_byte: int,
    total_size: int,
    message_id: int,
    file_name: str,
    start_time: float,
    node: TaskNode,
    client: Client,
):
    """update_download_status"""
    cur_time = time.time()
    # pylint: disable = W0603
    global _total_download_speed
    global _total_download_size
    global _last_download_time

    if node.is_stop_transmission:
        client.stop_transmission()

    chat_id = node.chat_id

    # ⚠️ 檢查此下載是否已被新的下載任務取代（針對 Message Downloader）
    is_message_downloader = (hasattr(node, 'is_custom_download') and node.is_custom_download) or \
                           (hasattr(node, 'zip_download_manager') and node.zip_download_manager)

    if is_message_downloader and hasattr(node, 'zip_download_manager') and node.zip_download_manager:
        from module.pyrogram_extension import _active_message_downloads
        manager_id = getattr(node.zip_download_manager, 'manager_id', None)
        message_key = (chat_id, message_id)

        # 如果註冊表中的 manager_id 與當前任務不同，表示已被新任務取代
        current_manager = _active_message_downloads.get(message_key)
        if current_manager is not None and current_manager != manager_id:
            logger.warning(f"下載任務已被取代 - 停止舊任務: chat_id={chat_id}, message_id={message_id}, "
                         f"舊 manager={manager_id}, 新 manager={current_manager}")
            node.is_stop_transmission = True
            client.stop_transmission()
            return

    # Check for cancelled state first
    if get_download_state() == DownloadState.Cancelled:
        node.is_stop_transmission = True
        client.stop_transmission()
        return
    
    # Handle pause state
    while get_download_state() == DownloadState.StopDownload:
        # Check if cancelled while paused
        if get_download_state() == DownloadState.Cancelled:
            node.is_stop_transmission = True
            client.stop_transmission()
            return
        if node.is_stop_transmission:
            client.stop_transmission()
        await asyncio.sleep(1)

    if not _download_result.get(chat_id):
        _download_result[chat_id] = {}

    if _download_result[chat_id].get(message_id):
        last_download_byte = _download_result[chat_id][message_id]["down_byte"]
        last_time = _download_result[chat_id][message_id]["end_time"]
        download_speed = _download_result[chat_id][message_id]["download_speed"]
        each_second_total_download = _download_result[chat_id][message_id][
            "each_second_total_download"
        ]
        end_time = _download_result[chat_id][message_id]["end_time"]

        _total_download_size += down_byte - last_download_byte
        each_second_total_download += down_byte - last_download_byte

        if cur_time - last_time >= 1.0:
            download_speed = int(each_second_total_download / (cur_time - last_time))
            end_time = cur_time
            each_second_total_download = 0

        download_speed = max(download_speed, 0)

        _download_result[chat_id][message_id]["down_byte"] = down_byte
        _download_result[chat_id][message_id]["end_time"] = end_time
        _download_result[chat_id][message_id]["download_speed"] = download_speed
        _download_result[chat_id][message_id][
            "each_second_total_download"
        ] = each_second_total_download
    else:
        each_second_total_download = down_byte
        _download_result[chat_id][message_id] = {
            "down_byte": down_byte,
            "total_size": total_size,
            "file_name": file_name,
            "start_time": start_time,
            "end_time": cur_time,
            "download_speed": down_byte / (cur_time - start_time),
            "each_second_total_download": each_second_total_download,
            "task_id": node.task_id,
        }
        _total_download_size += down_byte

    if cur_time - _last_download_time >= 1.0:
        # update speed
        _total_download_speed = int(
            _total_download_size / (cur_time - _last_download_time)
        )
        _total_download_speed = max(_total_download_speed, 0)
        _total_download_size = 0
        _last_download_time = cur_time

    # Update web UI file progress
    try:
        from module.web import update_file_progress
        import os
        
        # Get the current download speed for this file
        current_speed = 0
        if _download_result[chat_id].get(message_id):
            current_speed = _download_result[chat_id][message_id]["download_speed"]
        
        update_file_progress(
            file_name=os.path.basename(file_name),
            downloaded_bytes=down_byte,
            total_bytes=total_size,
            download_speed=current_speed,
            message_id=message_id
        )
        
        # Mark file as completed (但不立即清除,保留供進度統計使用)
        # 檔案會在所有下載完成或新會話開始時統一清除
    except Exception as e:
        # Don't let web update errors break downloads
        pass
