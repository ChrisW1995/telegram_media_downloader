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

    // 初始化 Lightbox
    if (typeof initLightbox === 'function') {
        initLightbox();
    }

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

    // Jump to oldest message button
    const jumpToOldestBtn = document.getElementById('jump-to-oldest-btn');
    if (jumpToOldestBtn) {
        jumpToOldestBtn.addEventListener('click', jumpToOldestMessage);
    }

    // Jump to specific ID button
    const jumpToIdBtn = document.getElementById('jump-to-id-btn');
    if (jumpToIdBtn) {
        jumpToIdBtn.addEventListener('click', showJumpToIdModal);
    }

    // Jump to ID modal event listeners
    initializeJumpToIdModal();

    // Download choice modal event listeners
    initializeDownloadModal();

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

    // 初始化媒體篩選器
    if (typeof initMediaFilter === 'function') {
        initMediaFilter();
    }

    // 全部訊息選項
    const albumAllOption = document.querySelector('.album-option.album-all');
    if (albumAllOption) {
        albumAllOption.addEventListener('click', function() {
            showAllMessagesMode();
        });
    }

    // 媒體相簿卡片
    document.querySelectorAll('.album-card').forEach(card => {
        card.addEventListener('click', function() {
            const mediaType = this.dataset.mediaType;
            if (mediaType && currentChatId) {
                showMediaAlbum(currentChatId, mediaType);
            }
        });
    });

    // 相簿視圖返回按鈕
    const backToSelectorBtn = document.getElementById('back-to-selector');
    if (backToSelectorBtn) {
        backToSelectorBtn.addEventListener('click', backToSelector);
    }

    // 相簿視圖操作按鈕
    const albumSelectAllBtn = document.getElementById('album-select-all');
    if (albumSelectAllBtn) {
        albumSelectAllBtn.addEventListener('click', selectAllAlbumItems);
    }

    const albumClearSelectionBtn = document.getElementById('album-clear-selection');
    if (albumClearSelectionBtn) {
        albumClearSelectionBtn.addEventListener('click', clearAlbumSelection);
    }

    const albumDownloadBtn = document.getElementById('album-download-selected');
    if (albumDownloadBtn) {
        albumDownloadBtn.addEventListener('click', downloadSelectedAlbumItems);
    }
}

// ==================== 頁面初始化 ====================

/**
 * 頁面載入完成後的初始化函數
 */
function initializePage() {
    // 初始化事件監聽器
    initializeEventListeners();

    // 清理殘留的下載會話狀態
    cleanupStaleSession();

    // 檢查用戶認證狀態
    checkAuthStatus();
}

/**
 * 清理殘留的下載會話狀態
 * 用於頁面刷新後恢復正常狀態
 */
function cleanupStaleSession() {
    console.log('🧹 檢查並清理殘留的下載會話...');

    // 清理下載會話
    fetch('/api/downloads/cleanup', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('✅ 會話清理完成:', data.message);
            if (data.data && data.data.active) {
                console.log('📥 檢測到活躍下載,繼續監控');
                // 如果有活躍下載,啟動進度監控
                if (typeof startProgressMonitoring === 'function') {
                    startProgressMonitoring();
                }
            }
        } else {
            console.warn('⚠️ 會話清理回應異常:', data.message);
        }
    })
    .catch(error => {
        console.error('❌ 清理會話時發生錯誤:', error);
        // 即使清理失敗也繼續初始化,不影響用戶使用
    });

    // 清理影片快取（頁面刷新後自動清除）
    fetch('/api/video/stream/cleanup', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('✅ 影片快取已清除:', data.message);
        }
    })
    .catch(error => {
        console.error('❌ 清理影片快取時發生錯誤:', error);
    });
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

// ==================== 下載選擇對話框控制 ====================

/**
 * 初始化下載對話框事件監聽器
 */
function initializeDownloadModal() {
    // 關閉按鈕事件
    const closeBtn = document.getElementById('download-modal-close');
    const cancelBtn = document.getElementById('download-modal-cancel');
    const overlay = document.getElementById('download-choice-modal');

    if (closeBtn) {
        closeBtn.addEventListener('click', hideDownloadChoiceModal);
    }

    if (cancelBtn) {
        cancelBtn.addEventListener('click', hideDownloadChoiceModal);
    }

    if (overlay) {
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) {
                hideDownloadChoiceModal();
            }
        });
    }

    // 下載選項按鈕事件
    const botOption = document.getElementById('download-bot-option');
    const localOption = document.getElementById('download-local-option');
    const bothOption = document.getElementById('download-both-option');

    if (botOption) {
        botOption.addEventListener('click', function() {
            hideDownloadChoiceModal();
            startBotDownload();
        });
    }

    if (localOption) {
        localOption.addEventListener('click', function() {
            hideDownloadChoiceModal();
            startLocalDownload();
        });
    }

    if (bothOption) {
        bothOption.addEventListener('click', function() {
            hideDownloadChoiceModal();
            startBothDownload();
        });
    }

    // ESC 鍵關閉對話框
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const modal = document.getElementById('download-choice-modal');
            if (modal && modal.style.display !== 'none') {
                hideDownloadChoiceModal();
            }
        }
    });
}

/**
 * 顯示下載選擇對話框
 */
function showDownloadChoiceModal() {
    const modal = document.getElementById('download-choice-modal');
    const countElement = document.getElementById('download-modal-count');

    if (!modal) {
        console.error('找不到下載選擇對話框元素');
        return;
    }

    // 更新選中檔案數量
    if (countElement) {
        countElement.textContent = selectedMessages.length;
    }

    // 顯示對話框
    modal.style.display = 'flex';

    // 防止背景滾動
    document.body.style.overflow = 'hidden';

    // 聚焦到對話框以支援鍵盤導航
    modal.focus();
}

/**
 * 隱藏下載選擇對話框
 */
function hideDownloadChoiceModal() {
    const modal = document.getElementById('download-choice-modal');

    if (modal) {
        modal.style.display = 'none';
    }

    // 恢復背景滾動
    document.body.style.overflow = '';
}

/**
 * 檢查是否有選擇對話框正在顯示
 */
function isDownloadModalVisible() {
    const modal = document.getElementById('download-choice-modal');
    return modal && modal.style.display !== 'none';
}

// ==================== 跳轉到指定 ID 對話框 ====================

/**
 * 初始化跳轉到 ID 對話框
 */
function initializeJumpToIdModal() {
    const modal = document.getElementById('jump-to-id-modal');
    const closeBtn = document.getElementById('jump-modal-close');
    const cancelBtn = document.getElementById('jump-modal-cancel');
    const confirmBtn = document.getElementById('jump-modal-confirm');
    const input = document.getElementById('jump-message-id-input');

    if (!modal) {
        console.error('找不到跳轉對話框元素');
        return;
    }

    // 關閉按鈕
    if (closeBtn) {
        closeBtn.addEventListener('click', hideJumpToIdModal);
    }

    // 取消按鈕
    if (cancelBtn) {
        cancelBtn.addEventListener('click', hideJumpToIdModal);
    }

    // 確認按鈕
    if (confirmBtn) {
        confirmBtn.addEventListener('click', handleJumpToId);
    }

    // Enter 鍵確認
    if (input) {
        input.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                handleJumpToId();
            }
        });

        // 輸入時清除錯誤提示
        input.addEventListener('input', function() {
            const errorDiv = document.getElementById('jump-id-error');
            if (errorDiv) {
                errorDiv.style.display = 'none';
            }
        });
    }

    // 點擊背景關閉
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            hideJumpToIdModal();
        }
    });

    // ESC 鍵關閉
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            if (modal && modal.style.display !== 'none') {
                hideJumpToIdModal();
            }
        }
    });
}

/**
 * 顯示跳轉到 ID 對話框
 */
function showJumpToIdModal() {
    if (!currentChatId) {
        showNotification('請先選擇一個群組', 'warning');
        return;
    }

    const modal = document.getElementById('jump-to-id-modal');
    const input = document.getElementById('jump-message-id-input');
    const errorDiv = document.getElementById('jump-id-error');

    if (!modal) {
        console.error('找不到跳轉對話框元素');
        return;
    }

    // 清空輸入和錯誤提示
    if (input) {
        input.value = '';
        input.focus();
    }
    if (errorDiv) {
        errorDiv.style.display = 'none';
    }

    // 顯示對話框
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

/**
 * 隱藏跳轉到 ID 對話框
 */
function hideJumpToIdModal() {
    const modal = document.getElementById('jump-to-id-modal');
    if (modal) {
        modal.style.display = 'none';
    }
    document.body.style.overflow = '';
}

/**
 * 處理跳轉到指定 ID
 */
function handleJumpToId() {
    const input = document.getElementById('jump-message-id-input');
    const errorDiv = document.getElementById('jump-id-error');
    const errorText = document.getElementById('jump-id-error-text');

    if (!input) return;

    const messageId = parseInt(input.value);

    // 驗證輸入
    if (!messageId || messageId < 1) {
        if (errorDiv) {
            errorDiv.style.display = 'block';
            if (errorText) {
                errorText.textContent = '請輸入有效的訊息 ID（大於 0 的整數）';
            }
        }
        return;
    }

    // 隱藏對話框並執行跳轉
    hideJumpToIdModal();
    jumpToMessageId(messageId);
}