# -*- coding: utf-8 -*-
"""Web module main entry point (Quart async)

This is the refactored web module, migrated to Quart for native async support
"""

from quart import Quart
from loguru import logger

# Global variables (for backward compatibility)
_quart_app = None
_flask_app = None  # Alias for backward compatibility
_app = None
_client = None
_queue = None
web_login_users = {}

# For backward compatibility, export necessary variables and functions
message_downloader_auth_sessions = {}

# Telegram authentication state (for pyrogram_extension.py compatibility)
telegram_auth_state = {
    "needs_auth": False,
    "waiting_for_phone": False,
    "waiting_for_code": False,
    "waiting_for_password": False,
    "phone_number": None,
    "verification_code": None,
    "password": None,
    "auth_complete": False,
    "error_message": None
}


def init_web(app, client=None, queue=None):
    """Initialize web module (Quart async - backward compatible interface)"""
    global _quart_app, _flask_app, _app, _client, _queue, message_downloader_auth_sessions

    # Save application instance
    _app = app
    _client = client
    _queue = queue

    # Create Quart application
    from .core.app_factory import create_quart_app
    from .core.error_handlers import register_error_handlers

    _quart_app = create_quart_app()
    _flask_app = _quart_app  # Backward compatibility alias

    # Quart 使用原生 asyncio，不需要自定義 event loop 屬性
    # 主應用的 loop 會在 asyncio.run() 中統一管理
    logger.info("Quart application initialized with native async support")

    # Register error handlers
    register_error_handlers(_flask_app)

    # Register downloader modules
    from .downloader import register_blueprints
    register_blueprints(_flask_app, app)

    # Register global progress API for backward compatibility
    register_global_apis(_flask_app)

    # Configure login
    if app.web_login_secret:
        web_login_users["root"] = app.web_login_secret
    else:
        _quart_app.config["LOGIN_DISABLED"] = True

    # Store web config for later use in main loop
    _quart_app.web_host = app.web_host
    _quart_app.web_port = app.web_port
    _quart_app.debug_web = app.debug_web

    logger.info("Web module initialized with Quart (async support)")
    logger.info(f"Quart will start on {app.web_host}:{app.web_port}")

    # Return Quart app without starting server (will be started in main event loop)
    return _quart_app


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