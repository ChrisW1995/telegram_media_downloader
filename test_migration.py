#!/usr/bin/env python3
"""Test script for database migration and functionality."""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from loguru import logger

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.migration import run_migration
from database import get_database_manager
from module.app_db import DatabaseApplication


def test_migration():
    """Test the migration process."""
    logger.info("Testing migration process...")
    
    # Use current directory files
    config_file = "config.yaml"
    data_file = "data.yaml"  
    custom_history_file = "custom_download_history.yaml"
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        temp_db_path = tmp_db.name
    
    try:
        # Run migration
        logger.info(f"Running migration to temporary database: {temp_db_path}")
        success = run_migration(
            config_file=config_file,
            data_file=data_file,
            custom_history_file=custom_history_file,
            db_path=temp_db_path,
            force=True
        )
        
        if not success:
            logger.error("Migration failed!")
            return False
        
        logger.info("Migration completed successfully!")
        
        # Test database content
        db_manager = get_database_manager(temp_db_path)
        stats = db_manager.get_database_stats()
        
        logger.info("Database statistics:")
        for table, count in stats.get('tables', {}).items():
            logger.info(f"  {table}: {count} records")
        
        # Test application initialization
        logger.info("Testing DatabaseApplication initialization...")
        app = DatabaseApplication(
            config_file=config_file,
            db_path=temp_db_path,
            auto_migrate=False  # Already migrated
        )
        
        app.load_config()
        
        logger.info("Application configuration loaded:")
        logger.info(f"  API ID: {app.api_id}")
        logger.info(f"  Save path: {app.save_path}")
        logger.info(f"  Web port: {app.web_port}")
        logger.info(f"  Media types: {app.media_types}")
        logger.info(f"  Authorized users: {len(app.allowed_user_ids)}")
        logger.info(f"  Active chats: {len(app.chat_download_config)}")
        
        # Test some database operations
        logger.info("Testing database operations...")
        
        # Test statistics
        for chat_id in app.chat_download_config.keys():
            stats = app.get_download_statistics(chat_id)
            logger.info(f"  Chat {chat_id} stats: {stats}")
        
        # Test authorization
        if app.allowed_user_ids:
            user_id = app.allowed_user_ids[0]
            is_authorized = app.is_user_authorized(user_id)
            logger.info(f"  User {user_id} authorized: {is_authorized}")
        
        logger.info("All tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up temporary database
        try:
            os.unlink(temp_db_path)
            logger.info(f"Cleaned up temporary database: {temp_db_path}")
        except OSError:
            pass


def test_concurrent_access():
    """Test concurrent database access."""
    logger.info("Testing concurrent database access...")
    
    import threading
    import time
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        temp_db_path = tmp_db.name
    
    try:
        # Initialize database with some data
        success = run_migration(
            config_file="config.yaml",
            data_file="data.yaml",
            custom_history_file="custom_download_history.yaml",
            db_path=temp_db_path,
            force=True
        )
        
        if not success:
            logger.error("Migration failed for concurrent test!")
            return False
        
        results = []
        
        def worker(worker_id: int):
            """Worker thread function."""
            try:
                app = DatabaseApplication(
                    config_file="config.yaml",
                    db_path=temp_db_path,
                    auto_migrate=False
                )
                
                app.load_config()
                
                # Simulate some database operations
                for i in range(10):
                    stats = app.get_download_statistics()
                    time.sleep(0.01)  # Small delay
                
                # Test configuration updates
                app.app_config_repo.set_config_value(f'test_worker_{worker_id}', f'value_{i}')
                
                results.append(f"Worker {worker_id} completed successfully")
                
            except Exception as e:
                results.append(f"Worker {worker_id} failed: {e}")
        
        # Start multiple worker threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        logger.info("Concurrent access test results:")
        for result in results:
            logger.info(f"  {result}")
        
        success_count = sum(1 for r in results if "completed successfully" in r)
        logger.info(f"Concurrent test: {success_count}/5 workers succeeded")
        
        return success_count == 5
        
    except Exception as e:
        logger.error(f"Concurrent test failed: {e}")
        return False
        
    finally:
        # Clean up
        try:
            os.unlink(temp_db_path)
        except OSError:
            pass


def check_yaml_files():
    """Check if required YAML files exist."""
    required_files = ["config.yaml", "data.yaml", "custom_download_history.yaml"]
    
    for file_path in required_files:
        if not os.path.exists(file_path):
            logger.warning(f"Required file not found: {file_path}")
            return False
    
    return True


def main():
    """Run all tests."""
    logger.info("Starting database migration and functionality tests...")
    
    if not check_yaml_files():
        logger.error("Required YAML files not found. Please run from project root directory.")
        return 1
    
    # Test migration
    if not test_migration():
        logger.error("Migration test failed!")
        return 1
    
    # Test concurrent access
    if not test_concurrent_access():
        logger.error("Concurrent access test failed!")
        return 1
    
    logger.info("All tests completed successfully! 🎉")
    logger.info("")
    logger.info("Next steps:")
    logger.info("1. Update media_downloader.py to use DatabaseApplication")
    logger.info("2. Run the actual migration: python -m database.migration")
    logger.info("3. Test with real Telegram operations")
    
    return 0


if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    exit(main())