"""過渡性輔助模組

幫助從 web.py 逐步遷移到新的模組化架構
"""

import sys
from loguru import logger


def enable_new_web_module():
    """啟用新的 web 模組架構"""
    try:
        # 嘗試導入新模組
        from module.web import init_web, run_web_server
        logger.info("New web module structure is enabled")
        return True
    except ImportError as e:
        logger.warning(f"Failed to enable new web module: {e}")
        return False


def use_legacy_web():
    """使用舊的 web.py"""
    try:
        from module.web import init_web, run_web_server
        logger.info("Using legacy web.py")
        return True
    except ImportError as e:
        logger.error(f"Failed to import legacy web.py: {e}")
        return False


def check_migration_status():
    """檢查遷移狀態"""
    status = {
        'new_module_ready': False,
        'legacy_exists': False,
        'can_migrate': False
    }

    # 檢查新模組
    try:
        from module.web.core import app_factory
        from module.web.message_downloader import register_blueprints
        status['new_module_ready'] = True
    except ImportError:
        pass

    # 檢查舊模組
    try:
        import module.web as old_web
        if hasattr(old_web, '_flask_app'):
            status['legacy_exists'] = True
    except ImportError:
        pass

    status['can_migrate'] = status['new_module_ready']

    return status


def print_migration_guide():
    """打印遷移指南"""
    print("\n" + "="*60)
    print("Web 模組重構遷移指南")
    print("="*60)
    print("\n當前狀態：")

    status = check_migration_status()
    for key, value in status.items():
        status_text = "✅" if value else "❌"
        print(f"  {status_text} {key}: {value}")

    print("\n遷移步驟：")
    print("1. 新的模組化架構已經建立在 module/web/ 目錄下")
    print("2. 原有的 web.py 仍然保持運作")
    print("3. 新架構包含以下模組：")
    print("   - core/ : 核心功能（Flask 工廠、裝飾器、錯誤處理）")
    print("   - message_downloader/ : Message Downloader 功能")
    print("   - legacy/ : 傳統功能（待實作）")
    print("\n4. 要完成遷移，需要：")
    print("   a. 將 web.py 中的功能逐步移植到新模組")
    print("   b. 測試所有功能正常運作")
    print("   c. 最後可以刪除或歸檔原有的 web.py")
    print("\n注意：目前系統仍使用原有 web.py，新架構已準備就緒")
    print("="*60 + "\n")


if __name__ == "__main__":
    print_migration_guide()