/**
 * Message Downloader - UI Module
 * UI 交互邏輯和事件處理
 *
 * 處理界面交互、事件綁定和用戶操作回應功能
 */

// ==================== 事件監聽器初始化 ====================

/**
 * 初始化所有事件監聽器
 */
function initializeEventListeners() {
    // 初始化主題
    initializeTheme();

    // 主題切換按鈕事件
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }

    // Refresh messages button - 應該載入更多訊息，不是重置
    const refreshBtn = document.getElementById('refresh-messages-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            console.log('🔄 手動重新整理 - 載入更多訊息');
            loadMessages(false); // false = 追加模式，不重置
        });
    }

    // Select all button
    const selectAllBtn = document.getElementById('select-all-btn');
    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', selectAllMessages);
    }

    // Clear selection button
    const clearSelectionBtn = document.getElementById('clear-selection-btn');
    if (clearSelectionBtn) {
        clearSelectionBtn.addEventListener('click', clearSelection);
    }

    // Download button
    const downloadBtn = document.getElementById('fast-test-download-btn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', startDownload);
    }

    // Header logout button
    const headerLogoutBtn = document.getElementById('header-logout-btn');
    if (headerLogoutBtn) {
        headerLogoutBtn.addEventListener('click', logout);
    }

    // Chat menu toggle (animated popup)
    const chatMenuToggle = document.querySelector('.chat-menu-toggle');
    if (chatMenuToggle) {
        chatMenuToggle.addEventListener('click', function() {
            chatMenuToggle.classList.toggle('active');
        });
    }
}

// ==================== 頁面初始化 ====================

/**
 * 頁面載入完成後的初始化函數
 */
function initializePage() {
    // 初始化事件監聽器
    initializeEventListeners();

    // 檢查用戶認證狀態
    checkAuthStatus();
}

// ==================== DOM 工具函數 ====================

/**
 * 安全獲取DOM元素
 * @param {string} id - 元素ID
 * @returns {HTMLElement|null} DOM元素或null
 */
function safeGetElement(id) {
    const element = document.getElementById(id);
    if (!element) {
        console.warn(`元素 ${id} 不存在`);
    }
    return element;
}

/**
 * 安全設置元素顯示狀態
 * @param {string} id - 元素ID
 * @param {boolean} show - 是否顯示
 */
function safeSetDisplay(id, show) {
    const element = safeGetElement(id);
    if (element) {
        element.style.display = show ? 'block' : 'none';
    }
}

/**
 * 安全設置元素文字內容
 * @param {string} id - 元素ID
 * @param {string} text - 文字內容
 */
function safeSetText(id, text) {
    const element = safeGetElement(id);
    if (element) {
        element.textContent = text;
    }
}

/**
 * 安全設置元素HTML內容
 * @param {string} id - 元素ID
 * @param {string} html - HTML內容
 */
function safeSetHTML(id, html) {
    const element = safeGetElement(id);
    if (element) {
        element.innerHTML = html;
    }
}

// ==================== 訊息顯示控制函數 ====================

/**
 * 顯示或隱藏載入動畫
 * @param {boolean} show - 是否顯示載入動畫
 */
function showLoading(show) {
    const spinner = document.getElementById('loading-spinner');
    if (spinner) {
        spinner.style.display = show ? 'block' : 'none';
    }
}

/**
 * 顯示訊息內容區域
 */
function showMessages() {
    // 隱藏覆蓋層，顯示訊息列表
    const overlay = document.getElementById('messages-overlay');
    const messagesList = document.getElementById('messages-list');
    const chatControls = document.getElementById('chat-controls');

    if (overlay) overlay.style.display = 'none';
    if (messagesList) messagesList.style.display = 'block';
    if (chatControls) chatControls.style.display = 'block';

    // 設置滾動事件監聽器
    if (typeof setupScrollListener === 'function') {
        setupScrollListener();
    }
}

/**
 * 隱藏訊息內容，顯示默認覆蓋層
 */
function hideMessages() {
    // 顯示覆蓋層，隱藏訊息列表
    const overlay = document.getElementById('messages-overlay');
    const messagesList = document.getElementById('messages-list');
    const chatControls = document.getElementById('chat-controls');

    if (overlay) overlay.style.display = 'flex';
    if (messagesList) messagesList.style.display = 'none';
    if (chatControls) chatControls.style.display = 'none';

    // 清除選擇
    if (typeof clearSelection === 'function') {
        clearSelection();
    }

    // 重置載入狀態
    if (typeof lastMessageId !== 'undefined') lastMessageId = 0;
    if (typeof hasMoreMessages !== 'undefined') hasMoreMessages = true;
    if (typeof allMessages !== 'undefined') allMessages.length = 0;
}