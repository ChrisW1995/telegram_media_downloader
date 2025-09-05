"""Data migration script from YAML files to SQLite database."""

import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger
from ruamel import yaml

from .database_manager import get_database_manager
from .repositories import (
    AppConfigRepository,
    ChatRepository,
    DownloadHistoryRepository,
    CustomDownloadRepository,
    AuthorizedUserRepository
)

_yaml = yaml.YAML()


class DataMigration:
    """Handles migration from YAML files to SQLite database."""
    
    def __init__(self, 
                 config_file: str = "config.yaml",
                 data_file: str = "data.yaml", 
                 custom_history_file: str = "custom_download_history.yaml",
                 db_path: str = "tgdl.db"):
        """
        Initialize migration.
        
        Args:
            config_file: Path to config.yaml
            data_file: Path to data.yaml
            custom_history_file: Path to custom_download_history.yaml
            db_path: Path to SQLite database
        """
        self.config_file = config_file
        self.data_file = data_file
        self.custom_history_file = custom_history_file
        self.db_path = db_path
        
        # Initialize database and repositories
        self.db_manager = get_database_manager(db_path)
        self.app_config_repo = AppConfigRepository(self.db_manager)
        self.chat_repo = ChatRepository(self.db_manager)
        self.download_history_repo = DownloadHistoryRepository(self.db_manager)
        self.custom_download_repo = CustomDownloadRepository(self.db_manager)
        self.authorized_user_repo = AuthorizedUserRepository(self.db_manager)
    
    def load_yaml_file(self, filepath: str) -> Optional[Dict[str, Any]]:
        """Load YAML file safely."""
        try:
            if not os.path.exists(filepath):
                logger.warning(f"File not found: {filepath}")
                return None
                
            with open(filepath, 'r', encoding='utf-8') as f:
                data = _yaml.load(f.read())
                return data if data else {}
                
        except Exception as e:
            logger.error(f"Failed to load {filepath}: {e}")
            return None
    
    def backup_yaml_files(self, backup_dir: str = "yaml_backup") -> bool:
        """Create backup of original YAML files."""
        try:
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            files_to_backup = [
                self.config_file,
                self.data_file,
                self.custom_history_file
            ]
            
            for file_path in files_to_backup:
                if os.path.exists(file_path):
                    filename = os.path.basename(file_path)
                    backup_path = os.path.join(backup_dir, f"{timestamp}_{filename}")
                    
                    # Copy file
                    with open(file_path, 'r', encoding='utf-8') as src:
                        with open(backup_path, 'w', encoding='utf-8') as dst:
                            dst.write(src.read())
                    
                    logger.info(f"Backed up {file_path} to {backup_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False
    
    def migrate_app_config(self, config_data: Dict[str, Any]) -> bool:
        """Migrate application configuration."""
        try:
            logger.info("Migrating application configuration...")
            
            # Configuration mappings
            config_mappings = {
                'api_id': ('api_id', 'str', 'Telegram API ID'),
                'api_hash': ('api_hash', 'str', 'Telegram API Hash'),
                'bot_token': ('bot_token', 'str', 'Telegram Bot Token'),
                'save_path': ('save_path', 'str', 'Default save path for downloads'),
                'bot_save_path': ('bot_save_path', 'str', 'Save path for bot downloads'),
                'web_port': ('web_port', 'int', 'Web interface port'),
                'language': ('language', 'str', 'Application language'),
                'media_types': ('media_types', 'list', 'Supported media types'),
                'file_formats': ('file_formats', 'dict', 'Supported file formats'),
                'file_path_prefix': ('file_path_prefix', 'list', 'File path prefix patterns'),
                'file_name_prefix': ('file_name_prefix', 'list', 'File name prefix patterns'),
                'allowed_user_ids': ('allowed_user_ids', 'list', 'Authorized user IDs'),
                'enable_download_txt': ('enable_download_txt', 'bool', 'Enable TXT file downloads'),
                'max_download_task': ('max_download_task', 'int', 'Maximum concurrent downloads'),
                'date_format': ('date_format', 'str', 'Date format for file paths')
            }
            
            migrated_count = 0
            
            for yaml_key, (db_key, value_type, description) in config_mappings.items():
                if yaml_key in config_data:
                    value = config_data[yaml_key]
                    
                    # Store configuration
                    success = self.app_config_repo.set_config_value(
                        db_key, value, description
                    )
                    
                    if success:
                        migrated_count += 1
                        logger.debug(f"Migrated config: {db_key}")
            
            # Set migration timestamp
            self.app_config_repo.set_config_value(
                'migration_date', 
                datetime.now().isoformat(),
                'Date when YAML data was migrated to database'
            )
            
            logger.info(f"Migrated {migrated_count} configuration values")
            return True
            
        except Exception as e:
            logger.error(f"Config migration failed: {e}")
            return False
    
    def migrate_chats(self, config_data: Dict[str, Any]) -> bool:
        """Migrate chat configurations."""
        try:
            logger.info("Migrating chat configurations...")
            
            migrated_count = 0
            
            # Handle chat configurations
            if 'chat' in config_data:
                chats = config_data['chat']
                
                for chat_config in chats:
                    if 'chat_id' not in chat_config:
                        continue
                    
                    chat_data = {
                        'chat_id': str(chat_config['chat_id']),
                        'last_read_message_id': chat_config.get('last_read_message_id', 0),
                        'download_filter': chat_config.get('download_filter', ''),
                        'upload_telegram_chat_id': chat_config.get('upload_telegram_chat_id'),
                        'is_active': True,
                        'chat_type': 'unknown'  # Will be updated when chat info is fetched
                    }
                    
                    # Try to insert chat
                    if self.chat_repo.upsert(['chat_id'], chat_data):
                        migrated_count += 1
                        logger.debug(f"Migrated chat: {chat_data['chat_id']}")
            
            # Handle legacy single chat_id format
            elif 'chat_id' in config_data:
                chat_data = {
                    'chat_id': str(config_data['chat_id']),
                    'last_read_message_id': config_data.get('last_read_message_id', 0),
                    'download_filter': '',
                    'is_active': True,
                    'chat_type': 'unknown'
                }
                
                if self.chat_repo.upsert(['chat_id'], chat_data):
                    migrated_count += 1
                    logger.debug(f"Migrated legacy chat: {chat_data['chat_id']}")
            
            logger.info(f"Migrated {migrated_count} chat configurations")
            return True
            
        except Exception as e:
            logger.error(f"Chat migration failed: {e}")
            return False
    
    def migrate_custom_downloads(self, config_data: Dict[str, Any]) -> bool:
        """Migrate custom download configurations."""
        try:
            logger.info("Migrating custom download configurations...")
            
            migrated_count = 0
            
            if 'custom_downloads' not in config_data:
                return True
            
            custom_config = config_data['custom_downloads']
            
            # Migrate group tags
            if 'group_tags' in custom_config:
                group_tags = custom_config['group_tags']
                
                for chat_id, tag in group_tags.items():
                    # Ensure chat exists first
                    if not self.chat_repo.find_one({'chat_id': str(chat_id)}):
                        # Create chat record if it doesn't exist
                        self.chat_repo.insert({
                            'chat_id': str(chat_id),
                            'chat_title': f'Chat {chat_id}',
                            'chat_type': 'unknown',
                            'is_active': True
                        })
                    
                    # Create custom download record with tag
                    data = {
                        'chat_id': str(chat_id),
                        'target_message_ids': json.dumps([]),  # Empty for now
                        'group_tag': tag,
                        'is_enabled': True
                    }
                    
                    if self.custom_download_repo.insert(data):
                        migrated_count += 1
                        logger.debug(f"Migrated group tag for chat {chat_id}: {tag}")
            
            # Migrate target IDs
            if 'target_ids' in custom_config:
                target_ids = custom_config['target_ids']
                
                for chat_id, message_ids in target_ids.items():
                    if message_ids:  # Only if there are actual message IDs
                        # Ensure chat exists first
                        if not self.chat_repo.find_one({'chat_id': str(chat_id)}):
                            # Create chat record if it doesn't exist
                            self.chat_repo.insert({
                                'chat_id': str(chat_id),
                                'chat_title': f'Chat {chat_id}',
                                'chat_type': 'unknown',
                                'is_active': True
                            })
                        
                        data = {
                            'chat_id': str(chat_id),
                            'target_message_ids': json.dumps(message_ids),
                            'group_tag': None,
                            'is_enabled': True
                        }
                        
                        if self.custom_download_repo.insert(data):
                            migrated_count += 1
                            logger.debug(f"Migrated target IDs for chat {chat_id}: {len(message_ids)} messages")
            
            logger.info(f"Migrated {migrated_count} custom download configurations")
            return True
            
        except Exception as e:
            logger.error(f"Custom download migration failed: {e}")
            return False
    
    def migrate_download_history(self, custom_history_data: Dict[str, Any]) -> bool:
        """Migrate download history from custom_download_history.yaml."""
        try:
            logger.info("Migrating download history...")
            
            if not custom_history_data:
                logger.info("No download history to migrate")
                return True
            
            migrated_count = 0
            
            # Migrate downloaded IDs
            if 'downloaded_ids' in custom_history_data:
                downloaded_ids = custom_history_data['downloaded_ids']
                
                for chat_id, message_ids in downloaded_ids.items():
                    # Ensure chat exists first
                    if not self.chat_repo.find_one({'chat_id': str(chat_id)}):
                        # Create chat record if it doesn't exist
                        self.chat_repo.insert({
                            'chat_id': str(chat_id),
                            'chat_title': f'Chat {chat_id}',
                            'chat_type': 'unknown',
                            'is_active': True
                        })
                    
                    for message_id in message_ids:
                        # Add successful download record
                        record_id = self.download_history_repo.add_download_record(
                            chat_id=str(chat_id),
                            message_id=int(message_id),
                            download_status='success',
                            file_name=None,
                            file_path=None,
                            media_type='unknown'
                        )
                        
                        if record_id:
                            migrated_count += 1
            
            # Migrate failed IDs
            if 'failed_ids' in custom_history_data:
                failed_ids = custom_history_data['failed_ids']
                
                for chat_id, message_ids in failed_ids.items():
                    # Ensure chat exists first
                    if not self.chat_repo.find_one({'chat_id': str(chat_id)}):
                        # Create chat record if it doesn't exist
                        self.chat_repo.insert({
                            'chat_id': str(chat_id),
                            'chat_title': f'Chat {chat_id}',
                            'chat_type': 'unknown',
                            'is_active': True
                        })
                    
                    for message_id in message_ids:
                        # Add failed download record
                        record_id = self.download_history_repo.add_download_record(
                            chat_id=str(chat_id),
                            message_id=int(message_id),
                            download_status='failed',
                            file_name=None,
                            file_path=None,
                            media_type='unknown'
                        )
                        
                        if record_id:
                            migrated_count += 1
            
            logger.info(f"Migrated {migrated_count} download history records")
            return True
            
        except Exception as e:
            logger.error(f"Download history migration failed: {e}")
            return False
    
    def migrate_authorized_users(self, config_data: Dict[str, Any]) -> bool:
        """Migrate authorized users."""
        try:
            logger.info("Migrating authorized users...")
            
            migrated_count = 0
            
            if 'allowed_user_ids' in config_data:
                allowed_users = config_data['allowed_user_ids']
                
                if isinstance(allowed_users, list):
                    for user_id in allowed_users:
                        if self.authorized_user_repo.add_authorized_user(str(user_id)):
                            migrated_count += 1
                            logger.debug(f"Migrated authorized user: {user_id}")
            
            logger.info(f"Migrated {migrated_count} authorized users")
            return True
            
        except Exception as e:
            logger.error(f"Authorized users migration failed: {e}")
            return False
    
    def migrate_retry_queue(self, data_file_data: Dict[str, Any]) -> bool:
        """Migrate retry queue from data.yaml."""
        try:
            logger.info("Migrating retry queue...")
            
            migrated_count = 0
            
            # Handle legacy format (single chat)
            if 'ids_to_retry' in data_file_data:
                ids = data_file_data['ids_to_retry']
                # Need to determine which chat this belongs to - skip for now
                logger.warning("Legacy retry queue format detected - manual migration needed")
            
            # Handle new format (per-chat)
            if 'chat' in data_file_data:
                chats = data_file_data['chat']
                
                for chat_config in chats:
                    chat_id = str(chat_config.get('chat_id', ''))
                    ids_to_retry = chat_config.get('ids_to_retry', [])
                    
                    if chat_id and ids_to_retry:
                        for message_id in ids_to_retry:
                            # Add to download history as failed (to be retried)
                            record_id = self.download_history_repo.add_download_record(
                                chat_id=chat_id,
                                message_id=int(message_id),
                                download_status='failed'
                            )
                            
                            if record_id:
                                migrated_count += 1
            
            logger.info(f"Migrated {migrated_count} retry queue items")
            return True
            
        except Exception as e:
            logger.error(f"Retry queue migration failed: {e}")
            return False
    
    def run_migration(self, create_backup: bool = True) -> bool:
        """
        Run complete migration from YAML to SQLite.
        
        Args:
            create_backup: Whether to create backup of YAML files
            
        Returns:
            True if migration successful, False otherwise
        """
        try:
            logger.info("Starting YAML to SQLite migration...")
            
            # Create backup if requested
            if create_backup:
                if not self.backup_yaml_files():
                    logger.warning("Backup creation failed, continuing with migration...")
            
            # Load YAML files
            config_data = self.load_yaml_file(self.config_file) or {}
            data_file_data = self.load_yaml_file(self.data_file) or {}
            custom_history_data = self.load_yaml_file(self.custom_history_file) or {}
            
            if not config_data:
                logger.error("Config file is required for migration")
                return False
            
            # Run migrations in order
            migration_steps = [
                ("App Configuration", lambda: self.migrate_app_config(config_data)),
                ("Chat Configurations", lambda: self.migrate_chats(config_data)),
                ("Custom Downloads", lambda: self.migrate_custom_downloads(config_data)),
                ("Authorized Users", lambda: self.migrate_authorized_users(config_data)),
                ("Download History", lambda: self.migrate_download_history(custom_history_data)),
                ("Retry Queue", lambda: self.migrate_retry_queue(data_file_data))
            ]
            
            success_count = 0
            
            for step_name, step_func in migration_steps:
                logger.info(f"Running migration step: {step_name}")
                
                if step_func():
                    success_count += 1
                    logger.info(f"✓ {step_name} migration completed")
                else:
                    logger.error(f"✗ {step_name} migration failed")
            
            # Set migration complete flag
            self.app_config_repo.set_config_value(
                'migration_completed',
                True,
                'Flag indicating YAML to SQLite migration is complete'
            )
            
            logger.info(f"Migration completed: {success_count}/{len(migration_steps)} steps successful")
            
            # Print database statistics
            stats = self.db_manager.get_database_stats()
            logger.info("Database statistics after migration:")
            for table, count in stats.get('tables', {}).items():
                logger.info(f"  {table}: {count} records")
            
            return success_count == len(migration_steps)
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
    
    def check_migration_status(self) -> bool:
        """Check if migration has already been completed."""
        try:
            return self.app_config_repo.get_config_value('migration_completed', False)
        except Exception:
            return False


def run_migration(config_file: str = "config.yaml",
                 data_file: str = "data.yaml",
                 custom_history_file: str = "custom_download_history.yaml",
                 db_path: str = "tgdl.db",
                 force: bool = False) -> bool:
    """
    Run migration with command line interface.
    
    Args:
        config_file: Path to config.yaml
        data_file: Path to data.yaml  
        custom_history_file: Path to custom_download_history.yaml
        db_path: Path to SQLite database
        force: Force migration even if already completed
        
    Returns:
        True if successful, False otherwise
    """
    migration = DataMigration(config_file, data_file, custom_history_file, db_path)
    
    # Check if migration already completed
    if not force and migration.check_migration_status():
        logger.info("Migration already completed. Use force=True to re-run.")
        return True
    
    return migration.run_migration()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate YAML data to SQLite database")
    parser.add_argument("--config", default="config.yaml", help="Config YAML file path")
    parser.add_argument("--data", default="data.yaml", help="Data YAML file path")
    parser.add_argument("--history", default="custom_download_history.yaml", help="History YAML file path")
    parser.add_argument("--db", default="tgdl.db", help="SQLite database path")
    parser.add_argument("--force", action="store_true", help="Force migration even if completed")
    
    args = parser.parse_args()
    
    success = run_migration(
        config_file=args.config,
        data_file=args.data,
        custom_history_file=args.history,
        db_path=args.db,
        force=args.force
    )
    
    exit(0 if success else 1)