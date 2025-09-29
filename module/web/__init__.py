# -*- coding: utf-8 -*-
"""Web module main entry point

This is the refactored web module, maintaining backward compatibility with the original web.py
"""

from flask import Flask
from loguru import logger

# Global variables (for backward compatibility)
_flask_app = None
_app = None
_client = None
_queue = None
web_login_users = {}

# For backward compatibility, export necessary variables and functions
message_downloader_auth_sessions = {}


def init_web(app, client=None, queue=None):
    """Initialize web module (backward compatible interface)"""
    global _flask_app, _app, _client, _queue, message_downloader_auth_sessions

    # Save application instance
    _app = app
    _client = client
    _queue = queue

    # For now, use new modular structure directly to fix UI issues
    # TODO: Re-enable backward compatibility after fixing path issues
    # try:
    #     import module.web_original as old_web
    #     if hasattr(old_web, 'init_web'):
    #         logger.info("Using existing web_original.py for backward compatibility")
    #         return old_web.init_web(app, client, queue)
    # except ImportError:
    #     pass

    # If original web.py doesn't exist, use new modular structure
    from .core.app_factory import create_flask_app
    from .core.error_handlers import register_error_handlers

    # Create Flask application
    _flask_app = create_flask_app()

    # 現在設置 event loop，使用主應用程式的 loop
    if hasattr(app, 'loop') and app.loop:
        # 主應用已經有 loop，使用它
        _flask_app.loop = app.loop
        logger.info("Using main application's event loop for Flask app")
    else:
        # 主應用沒有 loop，創建我們自己的
        from .core.app_factory import ensure_event_loop
        app_loop = ensure_event_loop()
        _flask_app.loop = app_loop
        app.loop = app_loop
        logger.info("Created and assigned new event loop to both Flask and main app")

    # Register error handlers
    register_error_handlers(_flask_app)

    # Register Message Downloader modules
    from .message_downloader import register_blueprints
    register_blueprints(_flask_app, app)

    # Register global progress API for backward compatibility
    register_global_apis(_flask_app)

    # Start web server in a thread (like the original)
    import threading
    if app.web_login_secret:
        web_login_users["root"] = app.web_login_secret
    else:
        _flask_app.config["LOGIN_DISABLED"] = True

    if app.debug_web:
        threading.Thread(target=run_web_server, args=(app,)).start()
    else:
        threading.Thread(
            target=_flask_app.run, daemon=True, args=(app.web_host, app.web_port)
        ).start()

    logger.info("Web module initialized with new modular structure")
    logger.info(f"Web server started on {app.web_host}:{app.web_port}")
    return _flask_app


def run_web_server(app):
    """Run web server (backward compatible interface)"""
    # Use new structure directly for now
    # try:
    #     import module.web_original as old_web
    #     if hasattr(old_web, 'run_web_server'):
    #         return old_web.run_web_server(app)
    # except ImportError:
    #     pass

    # Use new structure
    from .core.app_factory import get_flask_app
    flask_app = get_flask_app() or init_web(app)
    flask_app.run(
        app.web_host,
        app.web_port,
        debug=app.debug_web,
        use_reloader=False
    )


def get_flask_app():
    """Get Flask app instance (backward compatible)"""
    # Use new structure directly
    # try:
    #     import module.web_original as old_web
    #     if hasattr(old_web, 'get_flask_app'):
    #         return old_web.get_flask_app()
    # except ImportError:
    #     pass

    from .core.app_factory import get_flask_app as new_get_flask_app
    return new_get_flask_app()


def register_global_apis(flask_app):
    """註冊全域進度API以提供向後相容性"""
    from .core.progress_system import get_download_progress_data

    @flask_app.route("/api/download_progress", methods=["GET"])
    def get_download_progress_api():
        """全域進度API - 用於前端浮動進度條"""
        return get_download_progress_data()


# Import and re-export progress functions for backward compatibility
from .core.progress_system import (
    update_download_progress,
    update_file_progress,
    clear_specific_file_progress,
    download_progress,
    active_download_session
)

# Export backward compatible interfaces
__all__ = [
    'init_web',
    'run_web_server',
    'get_flask_app',
    'message_downloader_auth_sessions',
    'web_login_users',
    # Progress system exports
    'update_download_progress',
    'update_file_progress',
    'clear_specific_file_progress',
    'download_progress',
    'active_download_session'
]