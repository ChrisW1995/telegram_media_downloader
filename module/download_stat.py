"""Download Stat"""
import asyncio
import time
from enum import Enum

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

    # Check for cancelled state first
    if get_download_state() == DownloadState.Cancelled:
        node.is_stop_transmission = True
        client.stop_transmission()
        return
    
    # Handle pause state with timeout to prevent infinite loops
    pause_timeout = 300  # 5 minutes maximum pause time
    pause_start_time = time.time()

    while get_download_state() == DownloadState.StopDownload:
        # Check if cancelled while paused
        if get_download_state() == DownloadState.Cancelled:
            node.is_stop_transmission = True
            client.stop_transmission()
            return

        # Check pause timeout to prevent infinite hanging
        if time.time() - pause_start_time > pause_timeout:
            print(f"Download pause timeout reached for message {message_id}, resuming...")
            break

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

    # Update web UI file progress and TaskNode statistics
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

        # Update TaskNode total_download_byte for bot progress display
        if node and hasattr(node, 'total_download_byte'):
            # Calculate the increment since last update
            if not hasattr(node, '_last_download_bytes'):
                node._last_download_bytes = {}

            last_bytes = node._last_download_bytes.get(message_id, 0)
            increment = down_byte - last_bytes
            if increment > 0:
                node.total_download_byte += increment
                node._last_download_bytes[message_id] = down_byte

        # Check if download is complete and clear specific file progress after a delay
        if down_byte >= total_size and total_size > 0:
            import threading
            def clear_specific_progress():
                try:
                    time.sleep(2)  # Reduced wait time from 5 to 2 seconds
                    # Only clear this specific file, not all files
                    from module.web import clear_specific_file_progress
                    clear_specific_file_progress(message_id, os.path.basename(file_name))
                except Exception as e:
                    # Log the error but don't raise it
                    print(f"Clear progress error: {e}")

            # Use daemon thread to prevent blocking
            threading.Thread(target=clear_specific_progress, daemon=True).start()
    except ImportError:
        # web module not available, skip progress update
        pass
    except Exception as e:
        # Log the error but don't raise it to prevent download interruption
        print(f"Progress update error: {e}")
