"""Persistent session storage for Fast Test authentication."""

import json
import os
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from loguru import logger


class SessionStorage:
    """Manages persistent storage of Fast Test authentication sessions."""
    
    def __init__(self, storage_file: str = "fast_test_sessions.json"):
        self.storage_file = storage_file
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.session_timeout = 24 * 60 * 60  # 24 hours in seconds
        self._load_sessions()
    
    def _load_sessions(self):
        """Load sessions from persistent storage."""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.sessions = data.get('sessions', {})
                    # Clean expired sessions on load
                    self._cleanup_expired_sessions()
                    logger.info(f"Loaded {len(self.sessions)} active Fast Test sessions")
        except Exception as e:
            logger.error(f"Failed to load sessions: {e}")
            self.sessions = {}
    
    def _save_sessions(self):
        """Save sessions to persistent storage."""
        try:
            data = {
                'sessions': self.sessions,
                'last_updated': datetime.now().isoformat()
            }
            # Write to temp file first, then rename for atomic operation
            temp_file = f"{self.storage_file}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.rename(temp_file, self.storage_file)
            logger.debug(f"Saved {len(self.sessions)} Fast Test sessions")
        except Exception as e:
            logger.error(f"Failed to save sessions: {e}")
    
    def _cleanup_expired_sessions(self):
        """Remove expired sessions."""
        current_time = time.time()
        expired_sessions = []
        
        for session_key, session_data in self.sessions.items():
            last_activity = session_data.get('last_activity', 0)
            if current_time - last_activity > self.session_timeout:
                expired_sessions.append(session_key)
        
        for session_key in expired_sessions:
            del self.sessions[session_key]
            logger.info(f"Removed expired session: {session_key}")
        
        if expired_sessions:
            self._save_sessions()
    
    def create_session(self, session_key: str, session_data: Dict[str, Any]) -> bool:
        """Create a new session."""
        try:
            self.sessions[session_key] = {
                **session_data,
                'created_at': time.time(),
                'last_activity': time.time()
            }
            self._save_sessions()
            logger.info(f"Created Fast Test session: {session_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to create session {session_key}: {e}")
            return False
    
    def get_session(self, session_key: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        self._cleanup_expired_sessions()
        session_data = self.sessions.get(session_key)
        
        if session_data:
            # Update last activity
            session_data['last_activity'] = time.time()
            self._save_sessions()
            
        return session_data
    
    def update_session(self, session_key: str, updates: Dict[str, Any]) -> bool:
        """Update session data."""
        try:
            if session_key in self.sessions:
                self.sessions[session_key].update(updates)
                self.sessions[session_key]['last_activity'] = time.time()
                self._save_sessions()
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to update session {session_key}: {e}")
            return False
    
    def delete_session(self, session_key: str) -> bool:
        """Delete a session."""
        try:
            if session_key in self.sessions:
                del self.sessions[session_key]
                self._save_sessions()
                logger.info(f"Deleted Fast Test session: {session_key}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete session {session_key}: {e}")
            return False
    
    def list_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get all active sessions."""
        self._cleanup_expired_sessions()
        return self.sessions.copy()
    
    def is_session_valid(self, session_key: str) -> bool:
        """Check if session is valid and not expired."""
        session_data = self.get_session(session_key)
        return session_data is not None


# Global session storage instance
_session_storage: Optional[SessionStorage] = None


def get_session_storage() -> SessionStorage:
    """Get or create global session storage instance."""
    global _session_storage
    if _session_storage is None:
        _session_storage = SessionStorage()
    return _session_storage