"""Async utilities for web module

智能異步執行工具，解決 asyncio event loop 衝突問題
"""

import asyncio
import concurrent.futures
from loguru import logger
from .app_factory import get_flask_app


def run_async_in_thread(coro):
    """Run async coroutine using the app's main event loop

    智能地處理異步協程執行：
    1. 首先嘗試使用應用程式的主 event loop
    2. 如果主 loop 不可用，則在新線程中創建新的 event loop
    3. 提供線程安全的協程執行機制

    Args:
        coro: 要執行的協程

    Returns:
        協程執行結果

    Raises:
        Exception: 如果協程執行失敗
    """

    # 恢復原始邏輯：首先嘗試使用主應用的 event loop
    # 嘗試從不同來源獲取主 event loop
    main_loop = None

    try:
        # 1. 嘗試從 Flask 應用獲取
        app = get_flask_app()
        if hasattr(app, 'loop') and app.loop and not app.loop.is_closed():
            main_loop = app.loop
            logger.debug(f"Found event loop from Flask app: {main_loop}")
    except Exception as e:
        logger.debug(f"Flask app loop not available: {e}")

    # 2. 嘗試從主應用實例獲取（向後相容）
    if not main_loop:
        try:
            # 避免循環匯入，直接查找模組
            import sys
            web_module = sys.modules.get('module.web')
            if web_module and hasattr(web_module, '_app'):
                _app = web_module._app
                if _app and hasattr(_app, 'loop') and _app.loop and not _app.loop.is_closed():
                    main_loop = _app.loop
                    logger.debug(f"Found event loop from main app: {main_loop}")
        except Exception as e:
            logger.debug(f"Main app loop not available: {e}")

    # 嘗試使用主 event loop
    if main_loop:
        try:
            logger.debug(f"Using main event loop: {main_loop}")
            # 在主 event loop 中以線程安全的方式提交協程
            future = asyncio.run_coroutine_threadsafe(coro, main_loop)
            result = future.result(timeout=30)  # 30 秒超時
            logger.debug("Successfully executed coroutine in main loop")
            return result
        except Exception as e:
            logger.warning(f"Failed to run coroutine in main loop: {e}")
            # 回退到創建新 loop

    # 回退機制：在新線程中創建新的 event loop
    logger.debug("Falling back to new event loop in thread")

    def run_in_new_loop():
        """在新線程中運行協程"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            logger.debug(f"Created new event loop: {loop}")
            result = loop.run_until_complete(coro)
            logger.debug("Successfully executed coroutine in new loop")
            return result
        finally:
            try:
                # 清理 loop 中的待處理任務
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()

                if pending:
                    # 等待所有任務被取消
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

                loop.close()
                logger.debug("Event loop cleaned up successfully")
            except Exception as cleanup_error:
                logger.warning(f"Error during loop cleanup: {cleanup_error}")

    # 使用線程池執行異步操作
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(run_in_new_loop)
        try:
            return future.result(timeout=60)  # 增加超時時間到 60 秒
        except concurrent.futures.TimeoutError:
            logger.error("Async operation timed out after 60 seconds")
            raise RuntimeError("Async operation timed out")
        except Exception as e:
            logger.error(f"Error in async operation: {e}")
            raise


def is_event_loop_running():
    """檢查是否有運行中的 event loop"""
    try:
        loop = asyncio.get_running_loop()
        return not loop.is_closed()
    except RuntimeError:
        return False


def get_or_create_event_loop():
    """獲取或創建 event loop"""
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        # 沒有運行中的 loop，創建新的
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def safe_run_async(coro, timeout=30):
    """安全地運行異步協程

    這是 run_async_in_thread 的簡化版本，適用於簡單的場景
    """
    return run_async_in_thread(coro)