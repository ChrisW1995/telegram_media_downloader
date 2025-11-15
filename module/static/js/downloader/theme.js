/**
 * Message Downloader - Theme Module
 * 主題切換邏輯
 *
 * 處理明亮/黑暗模式切換功能，包含主題狀態管理和UI更新
 */

// ==================== 主題管理變數 ====================

let currentTheme = localStorage.getItem('theme') || 'light';

// ==================== 主題功能函數 ====================

/**
 * 初始化主題
 * 在頁面載入時設置保存的主題並更新UI
 */
function initializeTheme() {
    // 設置初始主題
    document.documentElement.setAttribute('data-theme', currentTheme);
    updateThemeUI();
}

/**
 * 切換主題
 * 在明亮和黑暗模式之間切換
 */
function toggleTheme() {
    const toggle = document.getElementById('theme-toggle');
    if (!toggle) return;

    toggle.classList.add('switching');

    // 切換主題
    currentTheme = currentTheme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', currentTheme);
    localStorage.setItem('theme', currentTheme);

    // 更新 UI
    updateThemeUI();

    // 移除切換動畫類
    setTimeout(() => {
        toggle.classList.remove('switching');
    }, 300);
}

/**
 * 更新主題UI
 * 根據當前主題更新按鈕圖標和文字
 */
function updateThemeUI() {
    const themeIcon = document.getElementById('theme-icon');
    const themeText = document.getElementById('theme-text');

    if (!themeIcon || !themeText) return;

    if (currentTheme === 'dark') {
        themeIcon.className = 'theme-icon fas fa-moon';
        themeText.textContent = 'Dark';
    } else {
        themeIcon.className = 'theme-icon fas fa-sun';
        themeText.textContent = 'Light';
    }
}