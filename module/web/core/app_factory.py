"""Quart 應用工廠模組 (原生異步支援)"""

import os
from datetime import timedelta
from quart import Quart
from loguru import logger

# Quart 應用實例
_quart_app = None


class CustomQuart(Quart):
    """自定義 Quart 類，解決配置初始化問題"""

    def make_config(self, instance_relative=False):
        """Override make_config to set default PROVIDE_AUTOMATIC_OPTIONS"""
        config = super().make_config(instance_relative)
        # 設置 Flask/Quart 兼容性配置
        config.setdefault('PROVIDE_AUTOMATIC_OPTIONS', True)
        return config


class User:
    """Web Login User (簡化版本，不需要繼承 UserMixin)"""

    def __init__(self):
        self.sid = "root"

    @property
    def id(self):
        """ID"""
        return self.sid


def create_quart_app():
    """創建並配置 Quart 應用實例

    Quart 原生支援 asyncio，不需要額外的 event loop 管理。
    所有路由處理器都可以是 async def 函數，直接 await Pyrogram API。
    """
    global _quart_app

    if _quart_app is not None:
        return _quart_app

    # 獲取專案根目錄
    current_dir = os.path.dirname(__file__)  # core/
    project_root = os.path.abspath(os.path.join(current_dir, '../../..'))  # TGDL/
    template_folder = os.path.join(project_root, 'module', 'templates')
    static_folder = os.path.join(project_root, 'module', 'static')

    # 使用自定義 Quart 類創建應用
    _quart_app = CustomQuart(__name__,
                             template_folder=template_folder,
                             static_folder=static_folder)

    # 其他配置
    _quart_app.secret_key = "tdl"
    _quart_app.permanent_session_lifetime = timedelta(days=30)

    # Quart 使用原生 asyncio，不需要自定義 event loop 屬性
    # 如果其他模組需要訪問 loop，可以用 asyncio.get_running_loop()

    logger.info("Quart application created successfully (native async support)")
    return _quart_app


def get_quart_app():
    """獲取 Quart 應用實例"""
    global _quart_app
    if _quart_app is None:
        _quart_app = create_quart_app()
    return _quart_app


# 向後相容的別名（過渡期使用，最終應該全部改用 Quart）
create_flask_app = create_quart_app
get_flask_app = get_quart_app