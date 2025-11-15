/**
 * Message Downloader - Main Module
 * 應用程式初始化
 *
 * 負責應用程式的主要初始化邏輯和文檔載入後的設置
 */

// ==================== 應用程式初始化 ====================

/**
 * 文檔載入完成後的主要初始化函數
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Message Downloader 應用程式啟動');

    try {
        // 初始化頁面
        initializePage();

        console.log('✅ 應用程式初始化完成');
    } catch (error) {
        console.error('❌ 應用程式初始化失敗:', error);

        // 顯示錯誤訊息給用戶
        const errorMessage = '應用程式載入時發生錯誤，請重新整理頁面';
        if (typeof showAlert === 'function') {
            showAlert(errorMessage, 'danger');
        } else {
            // 後備方案：使用原生alert
            alert(errorMessage);
        }
    }
});

// ==================== 應用程式資訊 ====================

/**
 * 應用程式版本資訊
 */
const APP_INFO = {
    name: 'Telegram Message Downloader',
    version: '2.0',
    description: 'Telegram 訊息下載器 - 模組化版本',
    lastModified: '2025-09-23'
};

/**
 * 模組載入順序記錄
 */
const MODULE_LOAD_ORDER = [
    'core.js',      // 核心變數和工具函數
    'theme.js',     // 主題系統
    'auth.js',      // 認證系統
    'groups.js',    // 群組管理
    'messages.js',  // 訊息處理
    'selection.js', // 選擇邏輯
    'notifications.js', // 通知系統
    'ui.js',        // UI 交互
    'main.js'       // 應用初始化
];

/**
 * 輸出應用程式資訊到控制台
 */
console.log(`%c${APP_INFO.name} v${APP_INFO.version}`,
    'color: #007bff; font-weight: bold; font-size: 14px;'
);
console.log(`%c模組載入順序: ${MODULE_LOAD_ORDER.join(' → ')}`,
    'color: #28a745; font-size: 12px;'
);
console.log(`%c最後更新: ${APP_INFO.lastModified}`,
    'color: #6c757d; font-size: 11px;'
);