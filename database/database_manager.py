"""Database connection manager for SQLite database."""

import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Optional, Generator, Any
from loguru import logger
import json


class DatabaseManager:
    """Manages SQLite database connections and operations."""
    
    def __init__(self, db_path: str = "tgdl.db", schema_path: str = "database/schema.sql"):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
            schema_path: Path to SQL schema file
        """
        self.db_path = os.path.abspath(db_path)
        self.schema_path = schema_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self._initialized = False
        
        # Ensure database directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            try:
                self._local.connection = sqlite3.connect(
                    self.db_path,
                    check_same_thread=False,
                    timeout=60.0  # Increased timeout to 60 seconds
                )
                # Enable foreign key constraints
                self._local.connection.execute("PRAGMA foreign_keys = ON")
                # Enable Write-Ahead Logging for better concurrency
                self._local.connection.execute("PRAGMA journal_mode = WAL")
                # Set busy timeout to handle locks better
                self._local.connection.execute("PRAGMA busy_timeout = 30000")  # 30 seconds
                # Set row factory to return dictionaries
                self._local.connection.row_factory = sqlite3.Row
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    logger.warning(f"Database is locked, retrying in 2 seconds: {e}")
                    import time
                    time.sleep(2)
                    # Retry once
                    self._local.connection = sqlite3.connect(
                        self.db_path,
                        check_same_thread=False,
                        timeout=60.0
                    )
                    self._local.connection.execute("PRAGMA foreign_keys = ON")
                    self._local.connection.execute("PRAGMA journal_mode = WAL") 
                    self._local.connection.execute("PRAGMA busy_timeout = 30000")
                    self._local.connection.row_factory = sqlite3.Row
                else:
                    raise
            
        return self._local.connection
    
    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for database connections.
        
        Yields:
            Database connection
        """
        conn = self._get_connection()
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            # Don't close connection here - it's thread-local and reused
            pass
    
    @contextmanager
    def get_transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for database transactions.
        
        Yields:
            Database connection with automatic transaction management
        """
        conn = self._get_connection()
        try:
            conn.execute("BEGIN")
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction failed: {e}")
            raise
    
    def initialize_database(self) -> bool:
        """
        Initialize database with schema.
        
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            if self._initialized:
                return True
                
            try:
                # Check if schema file exists
                if not os.path.exists(self.schema_path):
                    logger.error(f"Schema file not found: {self.schema_path}")
                    return False
                
                # Read and execute schema
                with open(self.schema_path, 'r', encoding='utf-8') as f:
                    schema_sql = f.read()
                
                with self.get_connection() as conn:
                    # Execute schema in chunks (split by semicolon)
                    statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
                    
                    for statement in statements:
                        try:
                            conn.execute(statement)
                        except sqlite3.Error as e:
                            logger.warning(f"Schema statement failed (possibly expected): {e}")
                            # Continue with other statements
                    
                    conn.commit()
                
                self._initialized = True
                logger.info(f"Database initialized successfully: {self.db_path}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                return False
    
    def execute_query(self, query: str, params: tuple = (), fetch: bool = True) -> Any:
        """
        Execute a database query.
        
        Args:
            query: SQL query string
            params: Query parameters
            fetch: Whether to fetch results
            
        Returns:
            Query results if fetch=True, otherwise None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(query, params)
                
                if fetch:
                    if query.strip().upper().startswith('SELECT'):
                        return cursor.fetchall()
                    else:
                        conn.commit()
                        return cursor.rowcount
                else:
                    conn.commit()
                    return None
                    
        except Exception as e:
            logger.error(f"Query execution failed: {query[:100]}... Error: {e}")
            raise
    
    def execute_many(self, query: str, params_list: list) -> int:
        """
        Execute a query with multiple parameter sets.
        
        Args:
            query: SQL query string
            params_list: List of parameter tuples
            
        Returns:
            Number of affected rows
        """
        try:
            with self.get_transaction() as conn:
                cursor = conn.executemany(query, params_list)
                return cursor.rowcount
                
        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            raise
    
    def get_table_info(self, table_name: str) -> list:
        """
        Get information about a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of column information dictionaries
        """
        query = f"PRAGMA table_info({table_name})"
        return self.execute_query(query)
    
    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists.
        
        Args:
            table_name: Name of the table to check
            
        Returns:
            True if table exists, False otherwise
        """
        query = """
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name=?
        """
        result = self.execute_query(query, (table_name,))
        return len(result) > 0
    
    def get_database_version(self) -> Optional[str]:
        """
        Get database schema version.
        
        Returns:
            Version string if exists, None otherwise
        """
        try:
            if self.table_exists('app_config'):
                query = "SELECT value FROM app_config WHERE key = 'schema_version'"
                result = self.execute_query(query)
                if result:
                    return result[0]['value']
            return None
        except Exception:
            return None
    
    def set_database_version(self, version: str) -> bool:
        """
        Set database schema version.
        
        Args:
            version: Version string to set
            
        Returns:
            True if successful, False otherwise
        """
        try:
            query = """
            INSERT OR REPLACE INTO app_config (key, value, description) 
            VALUES ('schema_version', ?, 'Database schema version')
            """
            self.execute_query(query, (version,), fetch=False)
            return True
        except Exception as e:
            logger.error(f"Failed to set database version: {e}")
            return False
    
    def backup_database(self, backup_path: str) -> bool:
        """
        Create a backup of the database.
        
        Args:
            backup_path: Path for backup file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                backup_conn = sqlite3.connect(backup_path)
                conn.backup(backup_conn)
                backup_conn.close()
            
            logger.info(f"Database backup created: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            return False
    
    def close_all_connections(self):
        """Close all thread-local connections."""
        if hasattr(self._local, 'connection') and self._local.connection:
            try:
                # Commit any pending transactions
                self._local.connection.commit()
                # Close the connection
                self._local.connection.close()
            except sqlite3.Error as e:
                logger.warning(f"Error closing connection: {e}")
            finally:
                self._local.connection = None
    
    def get_database_stats(self) -> dict:
        """
        Get database statistics.
        
        Returns:
            Dictionary with database statistics
        """
        stats = {}
        
        try:
            # Database file size
            if os.path.exists(self.db_path):
                stats['file_size_mb'] = round(os.path.getsize(self.db_path) / (1024 * 1024), 2)
            
            # Table statistics
            tables_query = """
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """
            tables = self.execute_query(tables_query)
            
            stats['tables'] = {}
            for table in tables:
                table_name = table['name']
                count_query = f"SELECT COUNT(*) as count FROM {table_name}"
                count_result = self.execute_query(count_query)
                stats['tables'][table_name] = count_result[0]['count']
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {}


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_database_manager(db_path: str = "tgdl.db", schema_path: str = "database/schema.sql") -> DatabaseManager:
    """
    Get global database manager instance.
    
    Args:
        db_path: Path to database file
        schema_path: Path to schema file
        
    Returns:
        DatabaseManager instance
    """
    global _db_manager
    
    if _db_manager is None:
        _db_manager = DatabaseManager(db_path, schema_path)
        _db_manager.initialize_database()
    
    return _db_manager


def close_database():
    """Close global database manager."""
    global _db_manager
    
    if _db_manager:
        _db_manager.close_all_connections()
        _db_manager = None