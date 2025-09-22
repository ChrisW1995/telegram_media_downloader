/**
 * Message Downloader - Notifications Module
 * 通知系統和進度追蹤
 *
 * 處理通知顯示、進度報告和用戶提示功能
 */

// ==================== 通知系統核心功能 ====================

/**
 * 創建通知
 * @param {string} type - 通知類型 (success, info, warning, error)
 * @param {string} title - 通知標題
 * @param {string} message - 通知內容
 * @param {Object} options - 選項配置
 * @returns {string} 通知ID
 */
function createNotification(type, title, message, options = {}) {
    notificationCount++;
    const id = options.id || `notification-${notificationCount}`;
    const container = document.getElementById('notification-container');

    if (!container) {
        console.error('通知容器不存在');
        return id;
    }

    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.id = id;

    let progressHtml = '';
    if (options.showProgress) {
        progressHtml = `
            <div class="notification-progress">
                <div class="notification-progress-bar">
                    <div class="notification-progress-fill" id="${id}-progress"></div>
                </div>
                <div class="notification-progress-text" id="${id}-progress-text">0%</div>
            </div>
        `;
    }

    notification.innerHTML = `
        <div class="notification-header">
            <div class="notification-title">
                ${getNotificationIcon(type)}
                <span>${title}</span>
            </div>
            <button class="notification-close" onclick="removeNotification('${id}')">
                ×
            </button>
        </div>
        <div class="notification-body" id="${id}-body">
            ${message}
        </div>
        ${progressHtml}
    `;

    container.appendChild(notification);

    // 添加動畫效果
    setTimeout(() => {
        notification.classList.add('show');
    }, 100);

    // 保存通知引用
    activeNotifications.set(id, {
        element: notification,
        type: type,
        autoClose: options.autoClose !== false
    });

    // 自動關閉
    if (options.autoClose !== false) {
        const delay = options.duration || (type === 'error' ? 8000 : 5000);
        setTimeout(() => {
            removeNotification(id);
        }, delay);
    }

    return id;
}

/**
 * 更新通知內容
 * @param {string} id - 通知ID
 * @param {Object} updates - 更新內容
 */
function updateNotification(id, updates) {
    const notification = activeNotifications.get(id);
    if (!notification) return;

    if (updates.message) {
        const body = document.getElementById(`${id}-body`);
        if (body) body.innerHTML = updates.message;
    }

    if (updates.progress !== undefined) {
        const progressFill = document.getElementById(`${id}-progress`);
        const progressText = document.getElementById(`${id}-progress-text`);
        if (progressFill) {
            progressFill.style.width = `${updates.progress}%`;
        }
        if (progressText) {
            progressText.textContent = `${updates.progress}%`;
        }
    }

    if (updates.title) {
        const titleElement = notification.element.querySelector('.notification-title span');
        if (titleElement) titleElement.textContent = updates.title;
    }
}

/**
 * 移除通知
 * @param {string} id - 通知ID
 */
function removeNotification(id) {
    const notification = activeNotifications.get(id);
    if (!notification) return;

    notification.element.classList.remove('show');

    setTimeout(() => {
        if (notification.element.parentNode) {
            notification.element.parentNode.removeChild(notification.element);
        }
        activeNotifications.delete(id);
    }, 400);
}

/**
 * 獲取通知圖標
 * @param {string} type - 通知類型
 * @returns {string} 圖標HTML
 */
function getNotificationIcon(type) {
    const icons = {
        'success': '<i class="fas fa-check-circle"></i>',
        'info': '<i class="fas fa-info-circle"></i>',
        'warning': '<i class="fas fa-exclamation-triangle"></i>',
        'error': '<i class="fas fa-times-circle"></i>'
    };
    return icons[type] || '<i class="fas fa-bell"></i>';
}

// ==================== 下載通知相關功能 ====================

/**
 * 顯示下載開始通知
 * @param {number} count - 下載檔案數量
 */
function showDownloadStartNotification(count) {
    if (downloadNotificationId) {
        removeNotification(downloadNotificationId);
    }

    downloadNotificationId = createNotification(
        'info',
        '下載開始',
        `正在準備下載 ${count} 個檔案...`,
        {
            id: 'download-progress',
            showProgress: true,
            autoClose: false
        }
    );

    // 開始檢查進度
    startProgressChecking();
}

/**
 * 開始檢查下載進度
 */
function startProgressChecking() {
    if (progressCheckInterval) {
        clearInterval(progressCheckInterval);
    }

    progressCheckInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/download_progress');
            const data = await response.json();

            if (data.success && downloadNotificationId) {
                const progress = data.progress;

                if (progress.active) {
                    const percentage = progress.total_task > 0
                        ? Math.round((progress.completed_task / progress.total_task) * 100)
                        : 0;

                    let statusText = progress.status_text || `下載中... ${progress.completed_task}/${progress.total_task}`;

                    updateNotification(downloadNotificationId, {
                        title: '下載進行中',
                        message: statusText,
                        progress: percentage
                    });
                } else if (progress.completed_task > 0) {
                    // 下載完成
                    updateNotification(downloadNotificationId, {
                        title: '下載完成',
                        message: `✅ 成功完成 ${progress.completed_task} 個檔案的下載！`,
                        progress: 100
                    });

                    // 將通知改為成功類型
                    const notificationElement = document.getElementById(downloadNotificationId);
                    if (notificationElement) {
                        notificationElement.className = 'notification success show';
                    }

                    // 5秒後自動關閉
                    setTimeout(() => {
                        removeNotification(downloadNotificationId);
                        downloadNotificationId = null;
                    }, 5000);

                    // 停止檢查進度
                    clearInterval(progressCheckInterval);
                    progressCheckInterval = null;
                }
            }
        } catch (error) {
            console.error('檢查下載進度時發生錯誤:', error);
        }
    }, 2000); // 每2秒檢查一次
}

/**
 * 停止進度檢查
 */
function stopProgressChecking() {
    if (progressCheckInterval) {
        clearInterval(progressCheckInterval);
        progressCheckInterval = null;
    }
}

// ==================== 通知便捷方法 ====================

/**
 * 顯示一般通知
 * @param {string} type - 通知類型
 * @param {string} title - 通知標題
 * @param {string} message - 通知內容
 * @param {Object} options - 選項配置
 * @returns {string} 通知ID
 */
function showNotification(type, title, message, options = {}) {
    return createNotification(type, title, message, options);
}