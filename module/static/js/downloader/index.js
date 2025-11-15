/**
 * Message Downloader - Module Architecture Documentation
 * 模組架構說明文檔
 *
 * 此檔案提供 Message Downloader JavaScript 模組的詳細架構說明
 */

/**
 * ==================== 模組架構概覽 ====================
 *
 * Message Downloader 採用模組化 JavaScript 架構，將原本單一的大型檔案
 * 分解為多個專責模組，提升代碼可維護性和開發效率。
 *
 * 原始狀況：
 * - message_downloader.html: 3,693 行混合代碼
 * - JavaScript 部分：2005-3665 行（共 1660+ 行）
 *
 * 重構結果：
 * - HTML 檔案：245 行純模板
 * - JavaScript 模組：9 個專責檔案
 *
 * ==================== 模組載入順序 ====================
 *
 * 模組間的依賴關係和載入順序（從基礎到應用層）：
 *
 * 1. core.js          - 核心變數、常數和工具函數
 * 2. theme.js         - 主題切換邏輯
 * 3. auth.js          - Telegram 認證相關功能
 * 4. groups.js        - 群組管理和側邊欄渲染
 * 5. messages.js      - 訊息載入、渲染和滾動處理
 * 6. selection.js     - 訊息選擇和下載管理
 * 7. notifications.js - 通知系統和進度追蹤
 * 8. ui.js            - UI 交互邏輯和事件處理
 * 9. main.js          - 應用程式初始化
 *
 * ==================== 模組詳細說明 ====================
 */

const MODULE_DOCUMENTATION = {
    'core.js': {
        purpose: '核心變數、常數和工具函數',
        responsibilities: [
            '全域變數定義（selectedMessages, currentChatId, allMessages 等）',
            '基礎常數設置（MESSAGES_PER_PAGE, SCROLL_THRESHOLD 等）',
            '通用工具函數（formatDate, formatFileSize, escapeHtml 等）',
            '媒體資訊處理（getMediaInfo, getMediaIcon）',
            '基礎UI操作（showLoading, showAlert）'
        ],
        exports: [
            '全域變數（供其他模組使用）',
            '工具函數（格式化、媒體處理等）',
            '常數定義（分頁大小、滾動閾值等）'
        ],
        lineCount: '約 200 行',
        functionCount: 8
    },

    'theme.js': {
        purpose: '主題切換邏輯',
        responsibilities: [
            '主題狀態管理（明亮/黑暗模式）',
            '主題切換動畫效果',
            '主題UI更新（按鈕圖標和文字）',
            'localStorage 主題偏好保存'
        ],
        exports: [
            'initializeTheme()',
            'toggleTheme()',
            'updateThemeUI()'
        ],
        lineCount: '約 70 行',
        functionCount: 3
    },

    'auth.js': {
        purpose: 'Telegram 認證相關功能',
        responsibilities: [
            '用戶認證狀態檢查',
            'Telegram 登入流程（電話號碼、驗證碼、密碼）',
            '認證界面切換',
            '登入狀態指示器管理',
            '認證事件監聽器設置',
            '用戶登出功能'
        ],
        exports: [
            'checkAuthStatus()',
            'showAuthForm()',
            'showAuthSuccess()',
            'sendVerificationCode()',
            'verifyCode()',
            'verifyPassword()',
            'logout()'
        ],
        lineCount: '約 250 行',
        functionCount: 12
    },

    'groups.js': {
        purpose: '群組管理和側邊欄渲染',
        responsibilities: [
            '群組列表載入和API通信',
            '群組側邊欄渲染和分類顯示',
            '群組項目創建和事件綁定',
            '群組收藏功能（pin/unpin）',
            '群組選擇和統計更新',
            '群組搜尋功能'
        ],
        exports: [
            'loadGroups()',
            'renderGroupSidebar()',
            'selectGroup()',
            'toggleGroupPin()',
            'setupGroupSearch()'
        ],
        lineCount: '約 300 行',
        functionCount: 8
    },

    'messages.js': {
        purpose: '訊息載入、渲染和滾動處理',
        responsibilities: [
            '訊息分頁載入和API通信',
            '訊息列表渲染和DOM創建',
            '滾動檢測和自動載入更多',
            '縮圖載入和顯示',
            '訊息界面狀態管理',
            '無限滾動實現'
        ],
        exports: [
            'loadMessages()',
            'renderMessages()',
            'createMessageElement()',
            'setupScrollListener()',
            'loadThumbnailFromMessage()',
            'showMessages()',
            'hideMessages()'
        ],
        lineCount: '約 450 行',
        functionCount: 10
    },

    'selection.js': {
        purpose: '訊息選擇和下載管理',
        responsibilities: [
            '訊息選擇狀態管理',
            '選擇UI更新（計數器、按鈕狀態）',
            '批次選擇操作（全選、清除）',
            '下載請求處理',
            '下載API通信'
        ],
        exports: [
            'updateSelection()',
            'selectAllMessages()',
            'clearSelection()',
            'startDownload()',
            'updateSelectionUI()'
        ],
        lineCount: '約 130 行',
        functionCount: 5
    },

    'notifications.js': {
        purpose: '通知系統和進度追蹤',
        responsibilities: [
            '通知創建和顯示',
            '通知更新和移除',
            '下載進度追蹤',
            '進度條顯示',
            '自動關閉邏輯',
            '通知圖標管理'
        ],
        exports: [
            'createNotification()',
            'updateNotification()',
            'removeNotification()',
            'showDownloadStartNotification()',
            'startProgressChecking()',
            'stopProgressChecking()',
            'showNotification()'
        ],
        lineCount: '約 200 行',
        functionCount: 7
    },

    'ui.js': {
        purpose: 'UI 交互邏輯和事件處理',
        responsibilities: [
            '事件監聽器初始化和綁定',
            '頁面初始化邏輯',
            'DOM 操作工具函數',
            '用戶交互回應處理'
        ],
        exports: [
            'initializeEventListeners()',
            'initializePage()',
            'safeGetElement()',
            'safeSetDisplay()',
            'safeSetText()',
            'safeSetHTML()'
        ],
        lineCount: '約 120 行',
        functionCount: 6
    },

    'main.js': {
        purpose: '應用程式初始化',
        responsibilities: [
            'DOMContentLoaded 事件處理',
            '應用程式啟動邏輯',
            '錯誤處理和後備方案',
            '應用程式資訊和版本管理',
            '開發調試資訊輸出'
        ],
        exports: [
            '文檔載入事件監聽器',
            'APP_INFO 常數',
            'MODULE_LOAD_ORDER 常數'
        ],
        lineCount: '約 80 行',
        functionCount: 1
    }
};

/**
 * ==================== 全域變數和函數依賴關係 ====================
 *
 * 跨模組共享的全域變數：
 * - selectedMessages: 選中的訊息ID列表
 * - currentChatId: 當前選中的聊天ID
 * - allMessages: 所有載入的訊息
 * - isLoading: 載入狀態標記
 * - hasMoreMessages: 是否還有更多訊息
 * - downloadNotificationId: 下載通知ID
 * - progressCheckInterval: 進度檢查間隔器
 *
 * 主要函數調用關係：
 * main.js → ui.js → auth.js → groups.js → messages.js → selection.js → notifications.js
 *
 * ==================== 模組化優勢 ====================
 *
 * 1. **可維護性**：代碼按功能組織，便於定位和修改
 * 2. **可擴展性**：新功能可以獨立模組的形式添加
 * 3. **可重用性**：工具函數和組件可以在其他頁面中重用
 * 4. **協作效率**：多人開發時可以同時編輯不同模組
 * 5. **調試便利**：問題可以快速定位到特定模組
 * 6. **載入優化**：可以根據需要選擇性載入模組
 *
 * ==================== 開發建議 ====================
 *
 * 1. **修改代碼時**：在對應的模組中修改，避免跨模組修改
 * 2. **新增功能時**：考慮功能歸屬，選擇合適的模組或創建新模組
 * 3. **調試問題時**：根據功能分類快速定位到相關模組
 * 4. **版本控制時**：模組化便於查看變更歷史和代碼審查
 * 5. **測試時**：可以針對特定模組進行單元測試
 *
 * ==================== 載入示例 ====================
 *
 * HTML 中的模組載入順序：
 * ```html
 * <!-- 模組載入順序很重要，依賴模組必須先載入 -->
 * <script src="/static/js/message_downloader/core.js"></script>
 * <script src="/static/js/message_downloader/theme.js"></script>
 * <script src="/static/js/message_downloader/auth.js"></script>
 * <script src="/static/js/message_downloader/groups.js"></script>
 * <script src="/static/js/message_downloader/messages.js"></script>
 * <script src="/static/js/message_downloader/selection.js"></script>
 * <script src="/static/js/message_downloader/notifications.js"></script>
 * <script src="/static/js/message_downloader/ui.js"></script>
 * <script src="/static/js/message_downloader/main.js"></script>
 * ```
 */

// 輸出模組文檔到控制台（僅在開發模式）
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    console.log('%cMessage Downloader 模組架構', 'color: #dc3545; font-weight: bold; font-size: 16px;');
    console.log('%c共 9 個模組，總計約 1800+ 行代碼', 'color: #17a2b8; font-size: 12px;');
    console.log('%c詳細文檔請查看 index.js 檔案', 'color: #6c757d; font-size: 11px;');
}