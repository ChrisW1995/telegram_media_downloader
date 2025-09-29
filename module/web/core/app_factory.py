"""Flask 應用工廠模組"""

import os
import asyncio
import threading
from datetime import timedelta
from flask import Flask
from flask_login import LoginManager, UserMixin
from loguru import logger

# Flask 應用實例
_flask_app = None
_login_manager = None
_app_loop = None
_loop_thread = None


class User(UserMixin):
    """Web Login User"""

    def __init__(self):
        self.sid = "root"

    @property
    def id(self):
        """ID"""
        return self.sid


def _start_event_loop():
    """在後台線程中啟動 event loop"""
    global _app_loop
    _app_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_app_loop)
    try:
        logger.info("Starting application event loop in background thread")
        _app_loop.run_forever()
    except Exception as e:
        logger.error(f"Event loop error: {e}")
    finally:
        logger.info("Application event loop stopped")


def ensure_event_loop():
    """確保應用程式有一個可用的 event loop"""
    global _app_loop, _loop_thread

    # 首先嘗試使用已存在的主線程 event loop
    try:
        current_loop = asyncio.get_running_loop()
        if current_loop and not current_loop.is_closed():
            logger.info(f"Using existing main thread event loop: {current_loop}")
            _app_loop = current_loop
            return _app_loop
    except RuntimeError:
        # 沒有運行中的 loop，繼續創建新的
        pass

    if _app_loop is None or _app_loop.is_closed():
        # 創建並啟動後台 event loop
        _loop_thread = threading.Thread(target=_start_event_loop, daemon=True)
        _loop_thread.start()

        # 等待 loop 準備完成
        import time
        max_wait = 5  # 最多等待 5 秒
        wait_time = 0
        while (_app_loop is None or not _app_loop.is_running()) and wait_time < max_wait:
            time.sleep(0.1)
            wait_time += 0.1

        if _app_loop is None:
            logger.error("Failed to create application event loop")
        else:
            logger.info("Application event loop ready")

    return _app_loop


def stop_event_loop():
    """停止應用程式的 event loop"""
    global _app_loop, _loop_thread

    if _app_loop and not _app_loop.is_closed():
        logger.info("Stopping application event loop")
        _app_loop.call_soon_threadsafe(_app_loop.stop)

        # 等待線程結束
        if _loop_thread and _loop_thread.is_alive():
            _loop_thread.join(timeout=2)

        _app_loop = None
        _loop_thread = None


def create_flask_app():
    """創建並配置 Flask 應用實例"""
    global _flask_app, _login_manager

    if _flask_app is not None:
        return _flask_app

    # 獲取專案根目錄
    current_dir = os.path.dirname(__file__)  # core/
    project_root = os.path.abspath(os.path.join(current_dir, '../../..'))  # TGDL/
    template_folder = os.path.join(project_root, 'module', 'templates')
    static_folder = os.path.join(project_root, 'module', 'static')

    _flask_app = Flask(__name__,
                      template_folder=template_folder,
                      static_folder=static_folder)

    # 配置
    _flask_app.secret_key = "tdl"
    _flask_app.permanent_session_lifetime = timedelta(days=30)

    # 暫時不設置 event loop，讓主應用程式先完成初始化
    # event loop 會在後續由 init_web 設置
    _flask_app.loop = None

    # 初始化登入管理器
    _login_manager = LoginManager()
    _login_manager.login_view = "login"
    _login_manager.init_app(_flask_app)

    @_login_manager.user_loader
    def load_user(_):
        """Load a user object from the user ID."""
        return User()

    logger.info("Flask application created successfully with event loop support")
    return _flask_app


def get_flask_app():
    """獲取 Flask 應用實例"""
    global _flask_app
    if _flask_app is None:
        _flask_app = create_flask_app()
    return _flask_app