"""Session 管理模組"""

from loguru import logger
from typing import Optional, Dict, Any


class MessageDownloaderSessionManager:
    """Message Downloader Session 管理器"""

    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def get_session(self, session_key: str) -> Optional[Dict[str, Any]]:
        """獲取 session"""
        return self.sessions.get(session_key)

    def create_session(self, session_key: str, session_data: Dict[str, Any]) -> None:
        """創建新 session"""
        self.sessions[session_key] = session_data
        logger.info(f"Created new session: {session_key}")

    def update_session(self, session_key: str, updates: Dict[str, Any]) -> bool:
        """更新 session"""
        if session_key not in self.sessions:
            return False
        self.sessions[session_key].update(updates)
        return True

    def delete_session(self, session_key: str) -> bool:
        """刪除 session"""
        if session_key in self.sessions:
            del self.sessions[session_key]
            logger.info(f"Deleted session: {session_key}")
            return True
        return False

    def session_exists(self, session_key: str) -> bool:
        """檢查 session 是否存在"""
        return session_key in self.sessions

    def get_all_session_keys(self) -> list:
        """獲取所有 session keys"""
        return list(self.sessions.keys())

    def get_auth_sessions(self) -> Dict[str, Dict[str, Any]]:
        """獲取所有認證 sessions（與原有接口兼容）"""
        return self.sessions.copy()

    def restore_session_if_needed(self, session_key: str) -> bool:
        """從持久存儲恢復 session（如果需要）"""
        if self.session_exists(session_key):
            return True

        try:
            # 這裡可以從持久存儲恢復 session
            # 暫時返回 False，等整合時再完善
            from ..multiuser_auth import get_auth_manager
            from ..session_storage import get_session_storage

            session_storage = get_session_storage()
            stored_session = session_storage.get_session(session_key)
            if not stored_session or stored_session.get('status') != 'authenticated':
                return False

            # 恢復 session 到記憶體
            auth_manager = get_auth_manager()
            self.sessions[session_key] = {
                'phone_number': stored_session['phone_number'],
                'auth_manager': auth_manager
            }

            logger.info(f"Session {session_key} restored from persistent storage")
            return True
        except ImportError:
            # 如果相關模組還未遷移，先返回 False
            return False


# 全局 session 管理器實例
_session_manager = MessageDownloaderSessionManager()


def get_session_manager() -> MessageDownloaderSessionManager:
    """獲取全局 session 管理器實例"""
    return _session_manager