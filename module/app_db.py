"""Application module with database integration."""

import asyncio
import os
import time
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, List, Optional, Union, Dict, Any

from loguru import logger

from module.cloud_drive import CloudDrive, CloudDriveConfig
from module.filter import Filter
from module.language import Language, set_language
from utils.format import replace_date_time, validate_title
from utils.meta_data import MetaData

# Import database components
from database import (
    DatabaseManager,
    get_database_manager,
    AppConfigRepository,
    ChatRepository,
    DownloadHistoryRepository,
    CustomDownloadRepository,
    AuthorizedUserRepository,
    DownloadQueueRepository,
    AppStatisticsRepository
)
from database.migration import DataMigration

# Import enums and classes from original app.py
from module.app import (
    DownloadStatus,
    ForwardStatus,
    UploadStatus,
    TaskType,
    QueryHandler,
    QueryHandlerStr,
    TaskNode,
    LimitCall,
    ChatDownloadConfig,
    UploadProgressStat,
    CloudDriveUploadStat,
    get_config
)


class DatabaseApplication:
    """Application with SQLite database integration."""

    def __init__(
        self,
        config_file: str = "config.yaml",
        app_data_file: str = "data.yaml",
        application_name: str = "TGDL_Database",
        db_path: str = "tgdl.db",
        auto_migrate: bool = True
    ):
        """
        Initialize application with database support.

        Parameters
        ----------
        config_file: str
            Config file name
        app_data_file: str
            App data file (legacy, used for migration only)
        application_name: str
            Application Name
        db_path: str
            SQLite database path
        auto_migrate: bool
            Automatically migrate YAML data on first run
        """
        self.config_file: str = config_file
        self.app_data_file: str = app_data_file
        self.application_name: str = application_name
        self.db_path: str = db_path
        self.auto_migrate: bool = auto_migrate
        
        # Initialize database
        self.db_manager = get_database_manager(db_path)
        
        # Initialize repositories
        self.app_config_repo = AppConfigRepository(self.db_manager)
        self.chat_repo = ChatRepository(self.db_manager)
        self.download_history_repo = DownloadHistoryRepository(self.db_manager)
        self.custom_download_repo = CustomDownloadRepository(self.db_manager)
        self.authorized_user_repo = AuthorizedUserRepository(self.db_manager)
        self.download_queue_repo = DownloadQueueRepository(self.db_manager)
        self.statistics_repo = AppStatisticsRepository(self.db_manager)

        # Legacy compatibility
        self.download_filter = Filter()
        self.is_running = True
        self.total_download_task = 0
        self.chat_download_config: Dict[str, ChatDownloadConfig] = {}

        # Application settings (will be loaded from database)
        self.save_path = os.path.join(os.path.abspath("."), "downloads")
        self.bot_save_path = os.path.join(os.path.abspath("."), "downloads_bot")
        self.temp_save_path = os.path.join(os.path.abspath("."), "temp")
        self.api_id: str = ""
        self.api_hash: str = ""
        self.bot_token: str = ""
        self._chat_id: str = ""
        self.media_types: List[str] = []
        self.file_formats: Dict = {}
        self.proxy: Dict = {}
        self.restart_program = False

        # File naming and path settings
        self.file_path_prefix: List[str] = ["chat_title", "media_datetime"]
        self.file_name_prefix: List[str] = ["message_id", "file_name"]
        self.file_name_prefix_split: str = " - "
        
        # Directories
        self.log_file_path = os.path.join(os.path.abspath("."), "log")
        self.session_file_path = os.path.join(os.path.abspath("."), "sessions")
        
        # Other settings
        self.cloud_drive_config = CloudDriveConfig()
        self.hide_file_name = False
        self.caption_name_dict: Dict = {}
        self.caption_entities_dict: Dict = {}
        self.max_concurrent_transmissions: int = 1
        self.web_host: str = "0.0.0.0"
        self.web_port: int = 5000
        self.max_download_task: int = 5
        self.language = Language.EN
        self.after_upload_telegram_delete: bool = True
        self.web_login_secret: str = ""
        self.debug_web: bool = False
        self.log_level: str = "INFO"
        self.start_timeout: int = 60
        self.allowed_user_ids: List[str] = []
        self.date_format: str = "%Y_%m"
        self.drop_no_audio_video: bool = False
        self.enable_download_txt: bool = False

        self.forward_limit_call = LimitCall(max_limit_call_times=33)

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.executor = ThreadPoolExecutor(
            min(32, (os.cpu_count() or 0) + 4), thread_name_prefix="multi_task"
        )

        # Initialize config dict for compatibility
        self.config = {}

        # Migration check
        if self.auto_migrate:
            self._check_and_migrate()

    def _check_and_migrate(self):
        """Check if migration is needed and run it."""
        try:
            migration_completed = self.app_config_repo.get_config_value('migration_completed', False)
            
            if not migration_completed:
                logger.info("Database migration needed, starting migration...")
                
                migration = DataMigration(
                    config_file=self.config_file,
                    data_file=self.app_data_file,
                    custom_history_file="custom_download_history.yaml",
                    db_path=self.db_path
                )
                
                if migration.run_migration():
                    logger.info("Migration completed successfully")
                else:
                    logger.error("Migration failed, falling back to YAML mode")
                    # Could implement fallback to original Application class here
        except Exception as e:
            logger.error(f"Migration check failed: {e}")

    def load_config_from_database(self):
        """Load configuration from database instead of YAML files."""
        try:
            # Load basic configuration
            self.api_id = self.app_config_repo.get_config_value('api_id', '')
            self.api_hash = self.app_config_repo.get_config_value('api_hash', '')
            self.bot_token = self.app_config_repo.get_config_value('bot_token', '')
            
            self.save_path = self.app_config_repo.get_config_value('save_path', self.save_path)
            self.bot_save_path = self.app_config_repo.get_config_value('bot_save_path', self.bot_save_path)
            
            self.web_port = self.app_config_repo.get_config_value('web_port', self.web_port)
            self.media_types = self.app_config_repo.get_config_value('media_types', self.media_types)
            self.file_formats = self.app_config_repo.get_config_value('file_formats', self.file_formats)
            self.file_path_prefix = self.app_config_repo.get_config_value('file_path_prefix', self.file_path_prefix)
            self.file_name_prefix = self.app_config_repo.get_config_value('file_name_prefix', self.file_name_prefix)
            
            self.enable_download_txt = self.app_config_repo.get_config_value('enable_download_txt', self.enable_download_txt)
            self.max_download_task = self.app_config_repo.get_config_value('max_download_task', self.max_download_task)
            self.date_format = self.app_config_repo.get_config_value('date_format', self.date_format)
            
            # Load language setting
            language_str = self.app_config_repo.get_config_value('language', 'EN')
            try:
                self.language = Language[language_str.upper()]
            except KeyError:
                self.language = Language.EN
            
            # Load authorized users
            self.allowed_user_ids = self.app_config_repo.get_config_value('allowed_user_ids', [])
            
            # Load chat configurations
            self._load_chat_configs()
            
            # Set derived values
            self.max_concurrent_transmissions = self.max_download_task * 5
            
            # Build config dict for compatibility
            self._build_config_dict()
            
            logger.info("Configuration loaded from database")
            
        except Exception as e:
            logger.error(f"Failed to load config from database: {e}")

    def _load_chat_configs(self):
        """Load chat configurations from database."""
        try:
            active_chats = self.chat_repo.get_active_chats()
            
            for chat in active_chats:
                chat_id = chat['chat_id']
                
                # Create ChatDownloadConfig for compatibility
                config = ChatDownloadConfig()
                config.last_read_message_id = chat['last_read_message_id']
                config.download_filter = replace_date_time(chat.get('download_filter', ''))
                config.upload_telegram_chat_id = chat.get('upload_telegram_chat_id')
                
                # Load retry IDs from download history
                failed_ids = self.download_history_repo.get_failed_message_ids(chat_id)
                config.ids_to_retry = failed_ids
                config.ids_to_retry_dict = {msg_id: True for msg_id in failed_ids}
                
                self.chat_download_config[chat_id] = config
                
        except Exception as e:
            logger.error(f"Failed to load chat configs: {e}")

    def _build_config_dict(self):
        """Build config dictionary for compatibility with legacy code."""
        try:
            # Build custom_downloads section
            custom_downloads = {
                'enable': True,  # Assume enabled if custom downloads exist
                'group_tags': {},
                'target_ids': {}
            }
            
            # Get all custom download records
            all_custom_downloads = self.custom_download_repo.find_all({'is_enabled': True})
            
            for record in all_custom_downloads:
                chat_id = record['chat_id']
                
                # Add group tag if present
                if record.get('group_tag'):
                    custom_downloads['group_tags'][chat_id] = record['group_tag']
                
                # Add target message IDs if present
                target_ids_str = record.get('target_message_ids', '[]')
                try:
                    target_ids = json.loads(target_ids_str) if target_ids_str else []
                    if target_ids:
                        custom_downloads['target_ids'][chat_id] = target_ids
                except (json.JSONDecodeError, TypeError):
                    continue
            
            # Set enable to False if no custom downloads found
            if not custom_downloads['group_tags'] and not custom_downloads['target_ids']:
                custom_downloads['enable'] = False
            
            # Build full config dict
            self.config = {
                'custom_downloads': custom_downloads,
                'api_id': self.api_id,
                'api_hash': self.api_hash,
                'bot_token': self.bot_token,
                'save_path': self.save_path,
                'bot_save_path': self.bot_save_path,
                'web_port': self.web_port,
                'media_types': self.media_types,
                'file_formats': self.file_formats,
                'file_path_prefix': self.file_path_prefix,
                'file_name_prefix': self.file_name_prefix,
                'allowed_user_ids': self.allowed_user_ids,
                'enable_download_txt': self.enable_download_txt,
                'language': self.language.name,
                'chat': []  # Will be populated if needed
            }
            
            # Add chat configurations  
            for chat_id, config in self.chat_download_config.items():
                chat_config = {
                    'chat_id': chat_id,
                    'last_read_message_id': config.last_read_message_id,
                    'download_filter': config.download_filter
                }
                if config.upload_telegram_chat_id:
                    chat_config['upload_telegram_chat_id'] = config.upload_telegram_chat_id
                
                self.config['chat'].append(chat_config)
                
        except Exception as e:
            logger.error(f"Failed to build config dict: {e}")
            # Fallback to minimal config
            self.config = {
                'custom_downloads': {'enable': False},
                'chat': []
            }

    def save_config_to_database(self):
        """Save configuration to database instead of YAML files."""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Save basic configuration
                config_mappings = {
                    'api_id': self.api_id,
                    'api_hash': self.api_hash,
                    'bot_token': self.bot_token,
                    'save_path': self.save_path,
                    'bot_save_path': self.bot_save_path,
                    'web_port': self.web_port,
                    'media_types': self.media_types,
                    'file_formats': self.file_formats,
                    'file_path_prefix': self.file_path_prefix,
                    'file_name_prefix': self.file_name_prefix,
                    'enable_download_txt': self.enable_download_txt,
                    'max_download_task': self.max_download_task,
                    'date_format': self.date_format,
                    'language': self.language.name,
                    'allowed_user_ids': self.allowed_user_ids
                }
                
                for key, value in config_mappings.items():
                    self.app_config_repo.set_config_value(key, value)
                
                # Save chat configurations
                self._save_chat_configs()
                
                logger.debug("Configuration saved to database")
                return  # Success, exit the retry loop
                
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and retry_count < max_retries - 1:
                    retry_count += 1
                    wait_time = 2 ** retry_count  # Exponential backoff: 2, 4, 8 seconds
                    logger.warning(f"Database locked, retrying in {wait_time}s (attempt {retry_count}/{max_retries})")
                    import time
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to save config to database after {max_retries} attempts: {e}")
                    break
            except Exception as e:
                logger.error(f"Failed to save config to database: {e}")
                break

    def _save_chat_configs(self):
        """Save chat configurations to database."""
        try:
            for chat_id, config in self.chat_download_config.items():
                # Update chat record
                chat_data = {
                    'last_read_message_id': config.last_read_message_id,
                    'download_filter': config.download_filter
                }
                
                self.chat_repo.update({'chat_id': chat_id}, chat_data)
                
        except Exception as e:
            logger.error(f"Failed to save chat configs: {e}")

    def need_skip_message(
        self, download_config: ChatDownloadConfig, message_id: int
    ) -> bool:
        """Check if message should be skipped (database version)."""
        if message_id in download_config.ids_to_retry_dict:
            return True
        
        # Check if already successfully downloaded
        try:
            existing = self.download_history_repo.find_one({
                'message_id': message_id,
                'download_status': 'success'
            })
            return existing is not None
        except Exception:
            return False

    def set_download_id(
        self, node: TaskNode, message_id: int, download_status: DownloadStatus
    ):
        """Set download status (database version)."""
        try:
            if download_status is DownloadStatus.SuccessDownload:
                self.total_download_task += 1

            if node.chat_id not in self.chat_download_config:
                return

            # Update download history in database
            status_map = {
                DownloadStatus.SuccessDownload: 'success',
                DownloadStatus.FailedDownload: 'failed',
                DownloadStatus.SkipDownload: 'skipped'
            }
            
            db_status = status_map.get(download_status, 'pending')
            
            self.download_history_repo.update_download_status(
                str(node.chat_id),
                message_id,
                db_status
            )

            # Update in-memory config for compatibility
            config = self.chat_download_config[node.chat_id]
            config.finish_task += 1
            config.last_read_message_id = max(config.last_read_message_id, message_id)

        except Exception as e:
            logger.error(f"Failed to set download ID: {e}")

    def update_config(self, immediate: bool = True):
        """Update configuration (database version)."""
        if immediate:
            self.save_config_to_database()

    def is_user_authorized(self, user_id: Union[str, int]) -> bool:
        """Check if user is authorized using database."""
        try:
            return self.authorized_user_repo.is_user_authorized(str(user_id))
        except Exception:
            return str(user_id) in self.allowed_user_ids

    def add_authorized_user(self, user_id: Union[str, int], username: str = None,
                          first_name: str = None, last_name: str = None) -> bool:
        """Add authorized user to database."""
        try:
            return self.authorized_user_repo.add_authorized_user(
                str(user_id), username, first_name, last_name
            )
        except Exception as e:
            logger.error(f"Failed to add authorized user: {e}")
            return False

    def get_download_statistics(self, chat_id: str = None) -> Dict[str, Any]:
        """Get download statistics from database."""
        try:
            return self.download_history_repo.get_download_statistics(chat_id)
        except Exception as e:
            logger.error(f"Failed to get download statistics: {e}")
            return {'total': 0, 'success': 0, 'failed': 0, 'pending': 0, 'skipped': 0}

    def get_custom_download_targets(self, chat_id: str) -> List[int]:
        """Get custom download target message IDs."""
        try:
            return self.custom_download_repo.get_all_target_message_ids(chat_id)
        except Exception:
            return []

    # Keep all existing methods from original Application class for compatibility
    async def upload_file(
        self,
        local_file_path: str,
        progress_callback: Callable = None,
        progress_args: tuple = (),
    ) -> bool:
        """Upload file to cloud storage."""
        if not self.cloud_drive_config.enable_upload_file:
            return False

        ret: bool = False
        if self.cloud_drive_config.upload_adapter == "rclone":
            ret = await CloudDrive.rclone_upload_file(
                self.cloud_drive_config,
                self.save_path,
                local_file_path,
                progress_callback,
                progress_args,
            )
        elif self.cloud_drive_config.upload_adapter == "aligo":
            ret = await self.loop.run_in_executor(
                self.executor,
                CloudDrive.aligo_upload_file(
                    self.cloud_drive_config, self.save_path, local_file_path
                ),
            )

        return ret

    def get_file_save_path(
        self, media_type: str, chat_title: str, media_datetime: str, is_bot: bool = False
    ) -> str:
        """Get file save path prefix."""
        res: str = self.bot_save_path if is_bot else self.save_path
        for prefix in self.file_path_prefix:
            if prefix == "chat_title":
                res = os.path.join(res, chat_title)
            elif prefix == "media_datetime":
                res = os.path.join(res, media_datetime)
            elif prefix == "media_type":
                res = os.path.join(res, media_type)
        return res

    def get_file_name(
        self, message_id: int, file_name: Optional[str], caption: Optional[str]
    ) -> str:
        """Get file name with prefixes."""
        res: str = ""
        for prefix in self.file_name_prefix:
            if prefix == "message_id":
                if res != "":
                    res += self.file_name_prefix_split
                res += f"{message_id}"
            elif prefix == "file_name" and file_name:
                if res != "":
                    res += self.file_name_prefix_split
                res += f"{file_name}"
            elif prefix == "caption" and caption:
                if res != "":
                    res += self.file_name_prefix_split
                res += f"{caption}"
        if res == "":
            res = f"{message_id}"

        return validate_title(res)

    def exec_filter(self, download_config: ChatDownloadConfig, meta_data: MetaData):
        """Execute download filter."""
        if download_config.download_filter:
            self.download_filter.set_meta_data(meta_data)
            return self.download_filter.exec(download_config.download_filter)
        return True

    def set_language(self, language: Language):
        """Set application language."""
        self.language = language
        set_language(language)
        # Save to database
        self.app_config_repo.set_config_value('language', language.name)

    def load_config(self):
        """Load configuration from database (replaces YAML loading)."""
        self.load_config_from_database()

    def pre_run(self):
        """Initialize application before running."""
        self.cloud_drive_config.pre_run()
        if not os.path.exists(self.session_file_path):
            os.makedirs(self.session_file_path)

        # Clean up stale session files to prevent database locks
        self._cleanup_session_files()

        set_language(self.language)

    def _cleanup_session_files(self):
        """Safely clean up only temporary SQLite session files to prevent database locks."""
        # Only clean up SQLite temporary files, NOT the main .session file
        temp_session_files = [
            "media_downloader.session-journal",   # SQLite rollback journal
            "media_downloader.session-wal",       # Write-Ahead Logging file  
            "media_downloader.session-shm",       # Shared memory file
            "media_downloader_bot.session-journal",
            "media_downloader_bot.session-wal", 
            "media_downloader_bot.session-shm"
        ]
        
        cleaned_count = 0
        for filename in temp_session_files:
            filepath = os.path.join(self.session_file_path, filename)
            if os.path.exists(filepath):
                try:
                    # Test if file can be renamed (not locked by another process)
                    temp_path = filepath + '.cleanup'
                    os.rename(filepath, temp_path)
                    os.remove(temp_path)
                    cleaned_count += 1
                    logger.info(f"Cleaned up stale session temp file: {filename}")
                except OSError as e:
                    logger.warning(f"Cannot clean session temp file {filename}: {e} (may be in use)")
        
        if cleaned_count > 0:
            logger.info(f"Session cleanup completed: {cleaned_count} temporary files removed")
        else:
            logger.debug("No stale session temporary files found")

    def set_caption_name(
        self, chat_id: Union[int, str], media_group_id: Optional[str], caption: str
    ):
        """Set caption name for media group."""
        if not media_group_id:
            return

        if chat_id in self.caption_name_dict:
            self.caption_name_dict[chat_id][media_group_id] = caption
        else:
            self.caption_name_dict[chat_id] = {media_group_id: caption}

    def get_caption_name(
        self, chat_id: Union[int, str], media_group_id: Optional[str]
    ) -> Optional[str]:
        """Get caption name for media group."""
        if (
            not media_group_id
            or chat_id not in self.caption_name_dict
            or media_group_id not in self.caption_name_dict[chat_id]
        ):
            return None

        return str(self.caption_name_dict[chat_id][media_group_id])

    def set_caption_entities(
        self, chat_id: Union[int, str], media_group_id: Optional[str], caption_entities
    ):
        """Set caption entities for media group."""
        if not media_group_id:
            return

        if chat_id in self.caption_entities_dict:
            self.caption_entities_dict[chat_id][media_group_id] = caption_entities
        else:
            self.caption_entities_dict[chat_id] = {media_group_id: caption_entities}

    def get_caption_entities(
        self, chat_id: Union[int, str], media_group_id: Optional[str]
    ):
        """Get caption entities for media group."""
        if (
            not media_group_id
            or chat_id not in self.caption_entities_dict
            or media_group_id not in self.caption_entities_dict[chat_id]
        ):
            return None

        return self.caption_entities_dict[chat_id][media_group_id]


# Create alias for easy migration
Application = DatabaseApplication