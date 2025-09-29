"""認證裝飾器模組"""

from functools import wraps
from flask import jsonify, session
from flask_login import login_required


def require_message_downloader_auth(f):
    """Message Downloader 認證裝飾器 - 支援新舊架構認證"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 首先檢查新架構的認證狀態
        if session.get('message_downloader_authenticated', False):
            return f(*args, **kwargs)

        # 如果新架構未認證，檢查舊架構的認證狀態
        try:
            from module.multiuser_auth import get_auth_manager
            auth_manager = get_auth_manager()

            # 如果舊架構有活躍的客戶端，視為已認證
            if auth_manager and hasattr(auth_manager, 'active_clients') and auth_manager.active_clients:
                return f(*args, **kwargs)
        except ImportError:
            pass

        # 如果兩個架構都未認證，返回錯誤
        return jsonify({'success': False, 'error': '需要先進行認證'}), 401
    return decorated_function


# 重新導出 login_required 以便統一管理
__all__ = ['require_message_downloader_auth', 'login_required']