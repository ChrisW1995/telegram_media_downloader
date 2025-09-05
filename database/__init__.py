"""Database module for TGDL application."""

from .database_manager import DatabaseManager, get_database_manager, close_database
from .repositories import (
    ChatRepository,
    DownloadHistoryRepository,
    CustomDownloadRepository,
    AuthorizedUserRepository,
    DownloadQueueRepository,
    AppConfigRepository,
    AppStatisticsRepository
)

__all__ = [
    'DatabaseManager',
    'get_database_manager',
    'close_database',
    'ChatRepository',
    'DownloadHistoryRepository', 
    'CustomDownloadRepository',
    'AuthorizedUserRepository',
    'DownloadQueueRepository',
    'AppConfigRepository',
    'AppStatisticsRepository'
]