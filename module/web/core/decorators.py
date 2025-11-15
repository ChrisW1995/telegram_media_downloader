"""認證裝飾器模組 (支援 Quart async)"""

from functools import wraps
from quart import jsonify, session
import inspect


def require_message_downloader_auth(f):
    """Message Downloader 認證裝飾器 - 支援新舊架構認證

    自動檢測被裝飾函數是否為 async，並相應處理。
    支援 async def 和 def 兩種函數類型。
    """
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        # 首先檢查新架構的認證狀態
        if session.get('authenticated', False):
            # 如果原函數是 async，await 它；否則直接調用
            if inspect.iscoroutinefunction(f):
                return await f(*args, **kwargs)
            else:
                return f(*args, **kwargs)

        # 如果新架構未認證，檢查舊架構的認證狀態
        try:
            from module.multiuser_auth import get_auth_manager
            auth_manager = get_auth_manager()

            # 如果舊架構有活躍的客戶端，視為已認證
            if auth_manager and hasattr(auth_manager, 'active_clients') and auth_manager.active_clients:
                if inspect.iscoroutinefunction(f):
                    return await f(*args, **kwargs)
                else:
                    return f(*args, **kwargs)
        except ImportError:
            pass

        # 如果兩個架構都未認證，返回錯誤
        return jsonify({'success': False, 'error': '需要先進行認證'}), 401
    return decorated_function


# 導出裝飾器
__all__ = ['require_message_downloader_auth']