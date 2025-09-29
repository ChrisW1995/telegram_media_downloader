# -*- coding: utf-8 -*-
"""下載進度管理系統

從 web_original.py 完整移植的進度追蹤和管理功能，
為新架構提供向後相容的進度系統。
"""

from flask import jsonify
from loguru import logger
from module.download_stat import get_download_state, set_download_state, DownloadState

# ==================== 全域進度變數 ====================

# 下載進度追蹤
download_progress = {
    'total_count': 0,
    'completed_count': 0,
    'status_text': '準備中...',
    'active': False,
    'current_files': {},  # 改為字典，追蹤多個並發下載
    'current_file': {     # 保留兼容性
        'name': '',
        'downloaded_bytes': 0,
        'total_bytes': 0,
        'download_speed': 0
    }
}

# 全局變數來追蹤新加入的項目（會話期間）
newly_added_items = set()

# 全局變數來追蹤活躍的下載會話
active_download_session = {
    'active': False,
    'session_id': None,
    'start_time': None,
    'target_ids': {},
    'total_tasks': 0
}

# ==================== 進度數據獲取 ====================

def get_download_progress_data():
    """獲取當前下載進度（API 核心邏輯）"""
    global download_progress
    print(f"Progress API called: {download_progress}")

    # 選擇一個活躍的下載作為主要顯示（包括正在下載和剛完成的）
    all_files = [f for f in download_progress['current_files'].values() if f['total_bytes'] > 0]
    active_files = [f for f in all_files if f['downloaded_bytes'] < f['total_bytes']]

    if active_files:
        # 優先選擇正在下載的檔案
        main_file = max(active_files, key=lambda x: x['downloaded_bytes'] / max(x['total_bytes'], 1))
        download_progress['current_file'] = main_file
    elif all_files:
        # 如果沒有正在下載的，選擇最近完成的
        main_file = max(all_files, key=lambda x: x['downloaded_bytes'] / max(x['total_bytes'], 1))
        download_progress['current_file'] = main_file

    # 計算已完成檔案數（進度達到100%或已標記為完成）
    completed_files = len([f for f in download_progress['current_files'].values()
                          if f.get('completed', False) or
                          (f.get('total_bytes', 0) > 0 and f.get('downloaded_bytes', 0) >= f.get('total_bytes', 0))])

    progress_data = {
        'progress': {
            'total_task': download_progress['total_count'],  # 使用設定的總檔案數，而非動態計算
            'completed_task': completed_files,  # 使用動態計算的已完成檔案數，而非靜態計數器
            'status_text': download_progress['status_text'],
            'active': download_progress['active'],
            'current_file': download_progress['current_file'],
            'current_files': download_progress['current_files'],
            'concurrent_downloads': len(download_progress['current_files']),
            'total_download_speed': f"{sum(f.get('download_speed', 0) for f in download_progress['current_files'].values())} B/s"
        },
        'session': {
            'active': active_download_session['active'],
            'session_id': active_download_session['session_id'],
            'start_time': active_download_session['start_time'],
            'total_tasks': active_download_session['total_tasks']
        }
    }

    return jsonify(progress_data)


def calculate_detailed_progress():
    """計算詳細的下載進度資訊"""
    global download_progress

    try:
        current_files = download_progress.get('current_files', {})

        # 計算總下載大小和已下載大小
        total_size = 0
        downloaded_size = 0
        total_speed = 0

        for file_info in current_files.values():
            total_size += file_info.get('total_bytes', 0)
            downloaded_size += file_info.get('downloaded_bytes', 0)
            total_speed += file_info.get('download_speed', 0)

        # 如果沒有活動文件，使用單一文件資訊
        if not current_files and download_progress.get('current_file'):
            single_file = download_progress['current_file']
            total_size = single_file.get('total_bytes', 0)
            downloaded_size = single_file.get('downloaded_bytes', 0)
            total_speed = single_file.get('download_speed', 0)

        # 計算預估剩餘時間
        remaining_size = total_size - downloaded_size
        eta_seconds = 0
        if total_speed > 0:
            eta_seconds = remaining_size / total_speed

        return {
            'total_size': total_size,
            'downloaded_size': downloaded_size,
            'download_speed': total_speed,
            'remaining_files': download_progress.get('total_count', 0) - download_progress.get('completed_count', 0),
            'current_files': list(current_files.values()),
            'eta_seconds': eta_seconds
        }
    except Exception as e:
        logger.error(f"計算詳細進度時發生錯誤: {e}")
        return {
            'total_size': 0,
            'downloaded_size': 0,
            'download_speed': 0,
            'remaining_files': 0,
            'current_files': [],
            'eta_seconds': 0
        }

# ==================== 進度更新函數 ====================

def update_download_progress(completed, total, status_text="下載中..."):
    """更新任務總進度"""
    global download_progress, active_download_session
    download_progress['completed_count'] = completed
    download_progress['total_count'] = total
    download_progress['status_text'] = status_text
    print(f"✅ Progress updated: {completed}/{total} - {status_text}")

    # 更新會話狀態
    _update_download_session_status(completed, total)


def _update_download_session_status(completed, total):
    """更新下載會話狀態"""
    global download_progress, active_download_session
    download_progress['active'] = completed < total

    # 更新會話狀態
    if completed < total and total > 0:
        active_download_session['active'] = True
        active_download_session['total_tasks'] = total
        if not active_download_session['session_id']:
            import time
            active_download_session['session_id'] = str(int(time.time()))
            active_download_session['start_time'] = time.time()
    elif completed >= total and total > 0:
        # 下載完成，設置狀態並清除會話
        if get_download_state() != DownloadState.Cancelled:  # 只有非取消狀態才設為完成
            set_download_state(DownloadState.Completed)

        active_download_session['active'] = False
        active_download_session['session_id'] = None
        active_download_session['start_time'] = None
        active_download_session['target_ids'] = {}
        active_download_session['total_tasks'] = 0

    print(f"Task session status updated: {completed}/{total} - Active: {download_progress['active']}")


def update_file_progress(file_name="", downloaded_bytes=0, total_bytes=0, download_speed=0, message_id=None):
    """更新當前文件下載進度"""
    global download_progress

    # 如果有文件名和message_id，更新並發下載追蹤
    if file_name and message_id:
        file_key = f"{message_id}_{file_name}"
        download_progress['current_files'][file_key] = {
            'name': file_name,
            'downloaded_bytes': downloaded_bytes,
            'total_bytes': total_bytes,
            'download_speed': download_speed,
            'message_id': message_id
        }

        # 如果下載完成，標記為完成但保持顯示一會兒
        if downloaded_bytes >= total_bytes and total_bytes > 0:
            download_progress['current_files'][file_key]['completed'] = True

        print(f"File progress updated: {file_name} (ID:{message_id}) - {downloaded_bytes}/{total_bytes} bytes @ {download_speed} B/s")
    else:
        # 清空所有進度
        if not file_name:
            download_progress['current_files'].clear()

    # 兼容舊的單一文件進度更新（總是更新 current_file 以保持兼容性）
    if file_name and downloaded_bytes > 0:
        download_progress['current_file'] = {
            'name': file_name,
            'downloaded_bytes': downloaded_bytes,
            'total_bytes': total_bytes,
            'download_speed': download_speed
        }


def clear_specific_file_progress(message_id, file_name):
    """清除特定檔案的進度，而不影響其他正在下載的檔案"""
    global download_progress
    file_key = f"{message_id}_{file_name}"

    if file_key in download_progress['current_files']:
        del download_progress['current_files'][file_key]
        print(f"Cleared completed file progress: {file_name} (ID:{message_id})")


def remove_file_progress(file_key):
    """移除文件進度（通過 file_key）"""
    global download_progress
    if file_key in download_progress['current_files']:
        del download_progress['current_files'][file_key]


# ==================== 進度系統控制 ====================

def reset_download_progress():
    """重置進度系統（取消下載時使用）"""
    global download_progress, active_download_session
    download_progress['completed_count'] = 0
    download_progress['total_count'] = 0
    download_progress['active'] = False
    download_progress['current_files'] = {}
    active_download_session['active'] = False
    active_download_session['total_tasks'] = 0
    print("Download progress reset")


def initialize_download_session(total_tasks):
    """初始化下載會話"""
    global download_progress, active_download_session
    import time

    # 設置進度狀態
    download_progress['total_count'] = total_tasks
    download_progress['completed_count'] = 0
    download_progress['active'] = True
    download_progress['status_text'] = f"準備下載 {total_tasks} 個檔案..."
    download_progress['current_files'] = {}

    # 設置會話狀態
    active_download_session['active'] = True
    active_download_session['total_tasks'] = total_tasks
    active_download_session['session_id'] = str(int(time.time()))
    active_download_session['start_time'] = time.time()
    active_download_session['target_ids'] = {}

    print(f"Download session initialized: {total_tasks} tasks")


# ==================== 便捷訪問函數 ====================

def get_download_progress():
    """獲取當前進度變數"""
    return download_progress


def get_active_download_session():
    """獲取當前會話變數"""
    return active_download_session


def is_download_active():
    """檢查是否有活躍下載"""
    return download_progress.get('active', False)


# ==================== 導出模組接口 ====================

__all__ = [
    'download_progress',
    'active_download_session',
    'get_download_progress_data',
    'calculate_detailed_progress',
    'update_download_progress',
    'update_file_progress',
    'clear_specific_file_progress',
    'remove_file_progress',
    'reset_download_progress',
    'initialize_download_session',
    'get_download_progress',
    'get_active_download_session',
    'is_download_active'
]