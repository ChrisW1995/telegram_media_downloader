"""統一錯誤處理模組 (支援 Quart async)"""

from quart import jsonify
from loguru import logger
import traceback
import inspect


def success_response(data=None, message="操作成功"):
    """統一成功回應格式"""
    response = {'success': True, 'message': message}
    if data is not None:
        response['data'] = data
    return jsonify(response)


def error_response(message, error_code=400, data=None):
    """統一錯誤回應格式"""
    response = {'success': False, 'error': message}
    if data is not None:
        response['data'] = data
    return jsonify(response), error_code


def handle_api_exception(func):
    """API 異常處理裝飾器 - 支援 async 函數

    自動檢測被裝飾函數是否為 async，並相應處理。
    """
    from functools import wraps

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            # 如果原函數是 async，await 它；否則直接調用
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"API error in {func.__name__}: {e}")
            logger.error(traceback.format_exc())
            return error_response(str(e), 500)
    return wrapper


def register_error_handlers(app):
    """註冊全局錯誤處理器 (Quart async)"""

    @app.errorhandler(404)
    async def not_found_error(error):
        return error_response("資源不存在", 404)

    @app.errorhandler(500)
    async def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return error_response("伺服器內部錯誤", 500)

    @app.errorhandler(Exception)
    async def unhandled_exception(e):
        logger.error(f"Unhandled exception: {e}")
        logger.error(traceback.format_exc())
        return error_response("發生未預期的錯誤", 500)