"""Repository implementations for all database tables."""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime, date
import json

from .base_repository import BaseRepository
from .database_manager import DatabaseManager


class AppConfigRepository(BaseRepository):
    """Repository for app_config table."""
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__(db_manager, "app_config")
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        record = self.find_one({"key": key})
        if not record:
            return default
        
        value = record['value']
        value_type = record.get('value_type', 'str')
        
        # Deserialize based on type
        if value_type == 'int':
            return int(value) if value else default
        elif value_type == 'float':
            return float(value) if value else default
        elif value_type == 'bool':
            return value.lower() == 'true' if value else default
        elif value_type in ['list', 'dict']:
            try:
                return json.loads(value) if value else default
            except json.JSONDecodeError:
                return default
        else:
            return value if value else default
    
    def set_config_value(self, key: str, value: Any, description: str = None) -> bool:
        """Set configuration value."""
        # Determine value type
        if isinstance(value, bool):
            value_type = 'bool'
            value_str = 'true' if value else 'false'
        elif isinstance(value, int):
            value_type = 'int'
            value_str = str(value)
        elif isinstance(value, float):
            value_type = 'float'
            value_str = str(value)
        elif isinstance(value, (list, dict)):
            value_type = 'list' if isinstance(value, list) else 'dict'
            value_str = json.dumps(value, ensure_ascii=False)
        else:
            value_type = 'str'
            value_str = str(value)
        
        data = {
            'key': key,
            'value': value_str,
            'value_type': value_type
        }
        
        if description:
            data['description'] = description
        
        try:
            self.upsert(['key'], data)
            return True
        except Exception:
            return False


class ChatRepository(BaseRepository):
    """Repository for chats table."""
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__(db_manager, "chats")
    
    def get_active_chats(self) -> List[Dict[str, Any]]:
        """Get all active chats."""
        return self.find_all({"is_active": True})
    
    def get_chat_by_id(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """Get chat by ID."""
        return self.find_one({"chat_id": chat_id})
    
    def update_last_read_message(self, chat_id: str, message_id: int) -> bool:
        """Update last read message ID for chat."""
        try:
            count = self.update(
                {"chat_id": chat_id},
                {"last_read_message_id": message_id}
            )
            return count > 0
        except Exception:
            return False
    
    def set_chat_filter(self, chat_id: str, download_filter: str) -> bool:
        """Set download filter for chat."""
        try:
            count = self.update(
                {"chat_id": chat_id},
                {"download_filter": download_filter}
            )
            return count > 0
        except Exception:
            return False


class DownloadHistoryRepository(BaseRepository):
    """Repository for download_history table."""
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__(db_manager, "download_history")
    
    def add_download_record(self, chat_id: str, message_id: int, 
                          file_name: str = None, file_path: str = None,
                          file_size: int = None, media_type: str = None,
                          download_status: str = 'pending') -> Optional[int]:
        """Add a download record."""
        data = {
            'chat_id': chat_id,
            'message_id': message_id,
            'file_name': file_name,
            'file_path': file_path,
            'file_size': file_size,
            'media_type': media_type,
            'download_status': download_status,
            'download_date': datetime.now().isoformat()
        }
        
        return self.upsert(['chat_id', 'message_id'], data)
    
    def update_download_status(self, chat_id: str, message_id: int, 
                             status: str, error_message: str = None) -> bool:
        """Update download status."""
        try:
            data = {'download_status': status}
            if error_message:
                data['error_message'] = error_message
            
            count = self.update(
                {"chat_id": chat_id, "message_id": message_id},
                data
            )
            return count > 0
        except Exception:
            return False
    
    def get_downloaded_message_ids(self, chat_id: str) -> List[int]:
        """Get list of successfully downloaded message IDs for a chat."""
        records = self.find_all({
            "chat_id": chat_id,
            "download_status": "success"
        })
        return [record['message_id'] for record in records]
    
    def get_failed_message_ids(self, chat_id: str) -> List[int]:
        """Get list of failed download message IDs for a chat."""
        records = self.find_all({
            "chat_id": chat_id,
            "download_status": "failed"
        })
        return [record['message_id'] for record in records]
    
    def get_download_statistics(self, chat_id: str = None) -> Dict[str, Any]:
        """Get download statistics."""
        base_query = "SELECT download_status, COUNT(*) as count, SUM(COALESCE(file_size, 0)) as total_size FROM download_history"
        params = ()
        
        if chat_id:
            base_query += " WHERE chat_id = ?"
            params = (chat_id,)
        
        base_query += " GROUP BY download_status"
        
        results = self.execute_custom_query(base_query, params)
        
        stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'pending': 0,
            'skipped': 0,
            'total_size': 0
        }
        
        for result in results:
            status = result['download_status']
            count = result['count']
            size = result['total_size'] or 0
            
            stats['total'] += count
            stats['total_size'] += size
            
            if status in stats:
                stats[status] = count
        
        return stats


class CustomDownloadRepository(BaseRepository):
    """Repository for custom_downloads table."""
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__(db_manager, "custom_downloads")
    
    def add_custom_download(self, chat_id: str, target_message_ids: List[int], 
                          group_tag: str = None) -> Optional[int]:
        """Add custom download configuration."""
        data = {
            'chat_id': chat_id,
            'target_message_ids': json.dumps(target_message_ids),
            'group_tag': group_tag,
            'is_enabled': True
        }
        
        return self.insert(data)
    
    def get_custom_downloads_for_chat(self, chat_id: str) -> List[Dict[str, Any]]:
        """Get custom downloads for a specific chat."""
        records = self.find_all({"chat_id": chat_id, "is_enabled": True})
        
        # Deserialize target_message_ids
        for record in records:
            try:
                record['target_message_ids'] = json.loads(record['target_message_ids'])
            except (json.JSONDecodeError, TypeError):
                record['target_message_ids'] = []
        
        return records
    
    def get_all_target_message_ids(self, chat_id: str) -> List[int]:
        """Get all target message IDs for a chat."""
        records = self.get_custom_downloads_for_chat(chat_id)
        message_ids = []
        
        for record in records:
            message_ids.extend(record['target_message_ids'])
        
        return list(set(message_ids))  # Remove duplicates


class AuthorizedUserRepository(BaseRepository):
    """Repository for authorized_users table."""
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__(db_manager, "authorized_users")
    
    def add_authorized_user(self, user_id: str, username: str = None,
                          first_name: str = None, last_name: str = None,
                          permissions: List[str] = None) -> bool:
        """Add authorized user."""
        data = {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'permissions': json.dumps(permissions or []),
            'is_active': True
        }
        
        try:
            self.upsert(['user_id'], data)
            return True
        except Exception:
            return False
    
    def is_user_authorized(self, user_id: str) -> bool:
        """Check if user is authorized."""
        user = self.find_one({"user_id": user_id, "is_active": True})
        return user is not None
    
    def update_last_activity(self, user_id: str) -> bool:
        """Update user's last activity timestamp."""
        try:
            count = self.update(
                {"user_id": user_id},
                {"last_activity": datetime.now().isoformat()}
            )
            return count > 0
        except Exception:
            return False
    
    def get_all_authorized_users(self) -> List[str]:
        """Get list of all authorized user IDs."""
        records = self.find_all({"is_active": True})
        return [record['user_id'] for record in records]


class DownloadQueueRepository(BaseRepository):
    """Repository for download_queue table."""
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__(db_manager, "download_queue")
    
    def add_to_queue(self, chat_id: str, message_id: int, priority: int = 0,
                    max_retries: int = 3) -> Optional[int]:
        """Add message to download queue."""
        data = {
            'chat_id': chat_id,
            'message_id': message_id,
            'priority': priority,
            'max_retries': max_retries,
            'current_retries': 0,
            'status': 'pending',
            'scheduled_at': datetime.now().isoformat()
        }
        
        return self.upsert(['chat_id', 'message_id'], data)
    
    def get_pending_downloads(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get pending downloads from queue."""
        return self.find_all(
            {"status": "pending"},
            order_by="priority DESC, scheduled_at ASC",
            limit=limit
        )
    
    def mark_as_processing(self, queue_id: int) -> bool:
        """Mark queue item as processing."""
        try:
            count = self.update(
                {"id": queue_id},
                {"status": "processing", "processed_at": datetime.now().isoformat()}
            )
            return count > 0
        except Exception:
            return False
    
    def mark_as_completed(self, queue_id: int) -> bool:
        """Mark queue item as completed."""
        try:
            count = self.update(
                {"id": queue_id},
                {"status": "completed", "processed_at": datetime.now().isoformat()}
            )
            return count > 0
        except Exception:
            return False
    
    def mark_as_failed(self, queue_id: int, error_message: str = None) -> bool:
        """Mark queue item as failed and increment retry count."""
        try:
            # Get current retry count
            record = self.find_by_id(queue_id)
            if not record:
                return False
            
            current_retries = record.get('current_retries', 0) + 1
            max_retries = record.get('max_retries', 3)
            
            # Determine new status
            if current_retries >= max_retries:
                new_status = 'failed'
            else:
                new_status = 'pending'  # Allow retry
            
            count = self.update(
                {"id": queue_id},
                {
                    "status": new_status,
                    "current_retries": current_retries,
                    "error_message": error_message,
                    "processed_at": datetime.now().isoformat()
                }
            )
            return count > 0
        except Exception:
            return False
    
    def cleanup_old_completed(self, days: int = 7) -> int:
        """Remove old completed queue items."""
        cutoff_date = (datetime.now() - datetime.timedelta(days=days)).isoformat()
        
        return self.delete({
            "status": "completed",
            "processed_at": f"< '{cutoff_date}'"
        })


class AppStatisticsRepository(BaseRepository):
    """Repository for app_statistics table."""
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__(db_manager, "app_statistics")
    
    def update_daily_stats(self, chat_id: str = None, 
                          total_messages: int = 0,
                          successful_downloads: int = 0,
                          failed_downloads: int = 0,
                          skipped_downloads: int = 0,
                          total_file_size: int = 0) -> bool:
        """Update daily statistics."""
        today = date.today().isoformat()
        
        data = {
            'stat_date': today,
            'chat_id': chat_id,
            'total_messages': total_messages,
            'successful_downloads': successful_downloads,
            'failed_downloads': failed_downloads,
            'skipped_downloads': skipped_downloads,
            'total_file_size': total_file_size
        }
        
        try:
            if chat_id:
                unique_fields = ['stat_date', 'chat_id']
            else:
                unique_fields = ['stat_date']
                
            self.upsert(unique_fields, data)
            return True
        except Exception:
            return False
    
    def get_statistics_by_date_range(self, start_date: str, end_date: str, 
                                   chat_id: str = None) -> List[Dict[str, Any]]:
        """Get statistics for date range."""
        conditions = {
            "stat_date": f"BETWEEN '{start_date}' AND '{end_date}'"
        }
        
        if chat_id:
            conditions['chat_id'] = chat_id
        
        query = f"""
        SELECT stat_date, chat_id,
               SUM(total_messages) as total_messages,
               SUM(successful_downloads) as successful_downloads,
               SUM(failed_downloads) as failed_downloads,
               SUM(skipped_downloads) as skipped_downloads,
               SUM(total_file_size) as total_file_size
        FROM {self.table_name}
        WHERE stat_date BETWEEN ? AND ?
        """
        
        params = [start_date, end_date]
        
        if chat_id:
            query += " AND chat_id = ?"
            params.append(chat_id)
        
        query += " GROUP BY stat_date" + (", chat_id" if not chat_id else "")
        query += " ORDER BY stat_date DESC"
        
        return self.execute_custom_query(query, tuple(params))