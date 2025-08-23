"""Session management utilities for preventing database locks."""

import os
import glob
import asyncio
from loguru import logger
from typing import Optional
import pyrogram


class SessionManager:
    """Manages Pyrogram session files and prevents database locking issues."""
    
    def __init__(self, session_path: str, session_name: str):
        self.session_path = session_path
        self.session_name = session_name
        self.session_file = os.path.join(session_path, f"{session_name}.session")
        self.journal_file = os.path.join(session_path, f"{session_name}.session-journal")
        
    def cleanup_stale_sessions(self) -> bool:
        """Clean up stale session files that might cause database locks."""
        cleaned = False
        
        # Remove journal files which can cause locks
        if os.path.exists(self.journal_file):
            try:
                os.remove(self.journal_file)
                logger.info(f"Removed stale session journal: {self.journal_file}")
                cleaned = True
            except OSError as e:
                logger.warning(f"Failed to remove journal file {self.journal_file}: {e}")
        
        # Check for temporary SQLite files (WAL, SHM)
        temp_patterns = [
            f"{self.session_file}-wal",
            f"{self.session_file}-shm"
        ]
        
        for pattern in temp_patterns:
            if os.path.exists(pattern):
                try:
                    os.remove(pattern)
                    logger.info(f"Removed temporary session file: {pattern}")
                    cleaned = True
                except OSError as e:
                    logger.warning(f"Failed to remove temp file {pattern}: {e}")
        
        return cleaned
    
    def ensure_session_directory(self):
        """Ensure session directory exists."""
        if not os.path.exists(self.session_path):
            os.makedirs(self.session_path)
            logger.info(f"Created session directory: {self.session_path}")
    
    async def safe_client_stop(self, client: pyrogram.Client, timeout: float = 10.0) -> bool:
        """Safely stop a Pyrogram client with timeout."""
        if not client.is_connected:
            return True
            
        try:
            # Use asyncio.wait_for to add timeout protection
            await asyncio.wait_for(client.stop(), timeout=timeout)
            logger.info("Client stopped successfully")
            return True
        except asyncio.TimeoutError:
            logger.warning(f"Client stop timed out after {timeout}s")
            return False
        except ConnectionError:
            # Client already terminated
            logger.info("Client was already terminated")
            return True
        except Exception as e:
            logger.error(f"Error stopping client: {e}")
            return False
    
    def force_cleanup_on_error(self):
        """Force cleanup session files when normal shutdown fails."""
        logger.warning("Performing force cleanup of session files")
        
        # Force remove all session-related files
        patterns = [
            self.journal_file,
            f"{self.session_file}-wal",
            f"{self.session_file}-shm"
        ]
        
        for pattern in patterns:
            if os.path.exists(pattern):
                try:
                    os.remove(pattern)
                    logger.info(f"Force removed: {pattern}")
                except OSError as e:
                    logger.error(f"Failed to force remove {pattern}: {e}")


def create_session_manager(app) -> SessionManager:
    """Create a session manager for the application."""
    return SessionManager(app.session_file_path, "media_downloader")