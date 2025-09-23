/**
 * Message Downloader - Core Module
 * 核心變數、常數和工具函數
 *
 * 提供全域變數定義、基礎常數設置和通用工具函數
 */

// ==================== 全域變數 ====================

// 訊息選擇和載入相關變數
let selectedMessages = [];
let currentChatId = null;
let allMessages = [];
let lastMessageId = 0;
let isLoading = false;
let hasMoreMessages = true;
let previousLastMessageId = 0; // 記錄上一次的 lastMessageId
let noProgressCount = 0; // 記錄沒有進展的次數

// 滾動檢測相關變數
let scrollTimeout = null;
let lastScrollTop = 0;
let userScrolled = false;
let preventAutoLoad = false;

// 群組管理和統計變數
let groupStats = JSON.parse(localStorage.getItem('groupStats') || '{}');
let favoriteGroups = JSON.parse(localStorage.getItem('favoriteGroups') || '[]');

// 通知系統變數
let notificationCount = 0;
let activeNotifications = new Map();
let downloadNotificationId = null;
let progressCheckInterval = null;

// ==================== 常數設置 ====================

const MESSAGES_PER_PAGE = 20;
const SCROLL_THRESHOLD = 50; // pixels from bottom to trigger auto-load
const MAX_NO_PROGRESS_ATTEMPTS = 3; // 最大無進展嘗試次數

// ==================== 工具函數 ====================

/**
 * 格式化日期
 * @param {string} dateString - 日期字符串
 * @returns {string} 格式化後的日期時間
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-TW') + ' ' + date.toLocaleTimeString('zh-TW', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * 格式化檔案大小
 * @param {number} bytes - 位元組數
 * @returns {string} 格式化後的檔案大小
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * HTML 轉義函數
 * @param {string} text - 需要轉義的文本
 * @returns {string} 轉義後的 HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * 顯示載入狀態
 * @param {boolean} show - 是否顯示載入
 */
function showLoading(show) {
    const spinner = document.getElementById('loading-spinner');
    if (spinner) {
        spinner.style.display = show ? 'block' : 'none';
    }
}

/**
 * 顯示提示訊息 - 使用 Toast 通知系統
 * @param {string} message - 提示訊息
 * @param {string} type - 訊息類型 (info, success, warning, danger)
 */
function showAlert(message, type) {
    // 將 Bootstrap 的 alert 類型轉換為通知系統的類型
    const typeMapping = {
        'success': 'success',
        'danger': 'error',
        'warning': 'warning',
        'info': 'info'
    };

    const notificationType = typeMapping[type] || 'info';

    // 使用現有的通知系統
    if (typeof showNotification === 'function') {
        showNotification(notificationType, getTypeTitle(notificationType), message);
    } else {
        // 降級方案：使用瀏覽器原生提示
        console.log(`${notificationType.toUpperCase()}: ${message}`);
    }
}

/**
 * 根據類型獲取標題
 * @param {string} type - 通知類型
 * @returns {string} 標題
 */
function getTypeTitle(type) {
    const titles = {
        'success': '成功',
        'error': '錯誤',
        'warning': '警告',
        'info': '提示'
    };
    return titles[type] || '通知';
}

/**
 * 獲取媒體類型圖標
 * @param {string} type - 媒體類型
 * @returns {string} 圖標 HTML
 */
function getMediaIcon(type) {
    const icons = {
        'photo': '<i class="fas fa-image"></i>',
        'video': '<i class="fas fa-video"></i>',
        'audio': '<i class="fas fa-music"></i>',
        'document': '<i class="fas fa-file"></i>',
        'voice': '<i class="fas fa-microphone"></i>',
        'animation': '<i class="fas fa-video"></i>',
        'sticker': '<i class="fas fa-sticky-note"></i>'
    };
    return icons[type] || '<i class="fas fa-file"></i>';
}

/**
 * 獲取媒體資訊
 * @param {Object} message - 訊息物件
 * @returns {Object} 媒體資訊物件
 */
function getMediaInfo(message) {
    console.log('處理訊息媒體資訊:', message);

    // Use the flattened structure returned by the backend
    let type = message.media_type || 'document';
    let filename = message.file_name || '';
    let size = message.file_size ? formatFileSize(message.file_size) : '';

    // If no filename, provide default based on media type
    if (!filename) {
        switch (type) {
            case 'photo':
                filename = 'Photo';
                break;
            case 'video':
                filename = 'Video';
                break;
            case 'audio':
                filename = 'Audio';
                break;
            case 'voice':
                filename = 'Voice Message';
                break;
            case 'animation':
                filename = 'Animation';
                break;
            case 'sticker':
                filename = 'Sticker';
                break;
            case 'document':
            default:
                filename = 'Document';
                break;
        }
    }

    // If no size info, set default
    if (!size) {
        size = 'Unknown size';
    }

    return { type, filename, size };
}