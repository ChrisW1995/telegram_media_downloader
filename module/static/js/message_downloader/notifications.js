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
    if (options.showProgress || options.showDetailedProgress) {
        progressHtml = `
            <div class="notification-progress">
                <div class="notification-progress-bar">
                    <div class="notification-progress-fill" id="${id}-progress"></div>
                </div>
                <div class="notification-progress-text" id="${id}-progress-text">0%</div>
            </div>
        `;

        // 如果需要詳細進度資訊
        if (options.showDetailedProgress) {
            progressHtml += `
                <div class="notification-details" id="${id}-details">
                    <div class="progress-stats">
                        <span class="stat-item">
                            <i class="fas fa-tachometer-alt"></i>
                            <span id="${id}-speed">計算中...</span>
                        </span>
                        <span class="stat-item">
                            <i class="fas fa-database"></i>
                            <span id="${id}-size">0 B / 0 B</span>
                        </span>
                        <span class="stat-item">
                            <i class="fas fa-clock"></i>
                            <span id="${id}-eta">--:--</span>
                        </span>
                        <span class="stat-item">
                            <i class="fas fa-file"></i>
                            <span id="${id}-files">0 / 0</span>
                        </span>
                    </div>
                </div>
            `;
        }
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
        autoClose: options.autoClose !== false,
        showDetailedProgress: options.showDetailedProgress || false,
        startTime: Date.now()
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

    // 更新詳細進度資訊
    if (notification.showDetailedProgress && updates.details) {
        updateDetailedProgress(id, updates.details, notification.startTime);
    }
}

/**
 * 更新詳細進度資訊
 * @param {string} id - 通知ID
 * @param {Object} details - 詳細資訊
 * @param {number} startTime - 開始時間
 */
function updateDetailedProgress(id, details, startTime) {
    // 更新下載速度
    if (details.downloadSpeed !== undefined) {
        const speedElement = document.getElementById(`${id}-speed`);
        if (speedElement) {
            speedElement.textContent = formatSpeed(details.downloadSpeed);
        }
    }

    // 更新文件大小資訊
    if (details.downloadedSize !== undefined && details.totalSize !== undefined) {
        const sizeElement = document.getElementById(`${id}-size`);
        if (sizeElement) {
            const downloaded = formatSize(details.downloadedSize);
            const total = formatSize(details.totalSize);
            sizeElement.textContent = `${downloaded} / ${total}`;
        }
    }

    // 更新預估剩餘時間
    if (details.downloadSpeed !== undefined && details.remainingSize !== undefined) {
        const etaElement = document.getElementById(`${id}-eta`);
        if (etaElement && details.downloadSpeed > 0) {
            const remainingSeconds = details.remainingSize / details.downloadSpeed;
            etaElement.textContent = formatETA(remainingSeconds);
        }
    }

    // 更新文件進度
    if (details.completedFiles !== undefined && details.totalFiles !== undefined) {
        const filesElement = document.getElementById(`${id}-files`);
        if (filesElement) {
            filesElement.textContent = `${details.completedFiles} / ${details.totalFiles}`;
        }
    }
}

/**
 * 格式化下載速度
 * @param {number} bytesPerSecond - 每秒字節數
 * @returns {string} 格式化的速度字符串
 */
function formatSpeed(bytesPerSecond) {
    if (bytesPerSecond < 1024) {
        return `${bytesPerSecond.toFixed(1)} B/s`;
    } else if (bytesPerSecond < 1024 * 1024) {
        return `${(bytesPerSecond / 1024).toFixed(1)} KB/s`;
    } else if (bytesPerSecond < 1024 * 1024 * 1024) {
        return `${(bytesPerSecond / (1024 * 1024)).toFixed(1)} MB/s`;
    } else {
        return `${(bytesPerSecond / (1024 * 1024 * 1024)).toFixed(1)} GB/s`;
    }
}

/**
 * 格式化文件大小
 * @param {number} bytes - 字節數
 * @returns {string} 格式化的大小字符串
 */
function formatSize(bytes) {
    if (bytes < 1024) {
        return `${bytes} B`;
    } else if (bytes < 1024 * 1024) {
        return `${(bytes / 1024).toFixed(1)} KB`;
    } else if (bytes < 1024 * 1024 * 1024) {
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    } else {
        return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
    }
}

/**
 * 格式化預估剩餘時間
 * @param {number} seconds - 剩餘秒數
 * @returns {string} 格式化的時間字符串
 */
function formatETA(seconds) {
    if (seconds < 60) {
        return `${Math.ceil(seconds)}s`;
    } else if (seconds < 3600) {
        const minutes = Math.floor(seconds / 60);
        const secs = Math.ceil(seconds % 60);
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    } else {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return `${hours}:${minutes.toString().padStart(2, '0')}:00`;
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
 * 顯示下載開始通知 - 使用常駐浮動進度條
 * @param {number} count - 下載檔案數量
 * @param {Array} files - 檔案列表（可選）
 */
function showDownloadStartNotification(count, files = null) {
    // 隱藏所有現有通知
    if (downloadNotificationId) {
        removeNotification(downloadNotificationId);
        downloadNotificationId = null;
    }

    // 如果有檔案列表，初始化個別檔案進度
    if (files && Array.isArray(files)) {
        initializeIndividualProgress(files);
    } else {
        // 如果沒有詳細檔案資訊，創建簡單的檔案項目
        const simpleFiles = Array.from({length: count}, (_, i) => ({
            id: `file_${i + 1}`,
            name: `檔案 ${i + 1}`,
            size: 0
        }));
        initializeIndividualProgress(simpleFiles);
    }

    // 顯示浮動進度條
    showFloatingProgress();

    // 初始化進度顯示
    updateFloatingProgress({
        percentage: 0,
        status: `正在準備下載 ${count} 個檔案...`,
        details: {
            downloadSpeed: 0,
            downloadedSize: 0,
            totalSize: 0,
            remainingSize: 0,
            completedFiles: 0,
            totalFiles: count
        }
    });

    // 開始檢查進度
    startProgressChecking();
}

// ZIP 下載相關函數已移除，改為使用真實進度 API

// 所有模擬進度相關程式碼已移除

/**
 * 開始檢查下載進度
 */
function startProgressChecking() {
    if (progressCheckInterval) {
        clearInterval(progressCheckInterval);
    }

    // 初始化進度跟蹤變數
    let lastDownloadedSize = 0;
    let lastUpdateTime = Date.now();

    progressCheckInterval = setInterval(async () => {
        try {
            // 根據下載類型使用不同的API端點
            // ZIP下載使用 /api/download_progress，其他使用 /api/fast_download/status
            const apiEndpoint = '/api/download_progress';
            const response = await fetch(apiEndpoint);
            const data = await response.json();

            if (data.success) {
                const progress = data.progress;

                if (progress && progress.active) {
                    const percentage = progress.total_task > 0
                        ? Math.round((progress.completed_task / progress.total_task) * 100)
                        : 0;

                    let statusText = progress.status_text || `下載中... ${progress.completed_task}/${progress.total_task}`;

                    // 計算總下載大小和速度
                    const currentTime = Date.now();

                    // 計算所有檔案的總大小和已下載大小
                    let totalDownloadedSize = 0;
                    let totalSize = 0;
                    let totalSpeed = 0;

                    if (progress.current_files) {
                        for (const fileData of Object.values(progress.current_files)) {
                            totalDownloadedSize += fileData.downloaded_bytes || 0;
                            totalSize += fileData.total_bytes || 0;
                            totalSpeed += fileData.download_speed || 0;
                        }
                    }

                    // 如果沒有檔案在下載但有總大小，可能是初始化階段
                    if (totalSize === 0 && progress.total_task > 0) {
                        console.log('進度初始化階段，等待檔案開始下載...');
                        statusText = `準備下載 ${progress.total_task} 個檔案...`;
                    }

                    const timeDiff = (currentTime - lastUpdateTime) / 1000;
                    const sizeDiff = totalDownloadedSize - lastDownloadedSize;
                    const downloadSpeed = timeDiff > 0 ? sizeDiff / timeDiff : totalSpeed;

                    // 更新浮動進度條
                    updateFloatingProgress({
                        percentage: percentage,
                        status: statusText,
                        details: {
                            downloadSpeed: downloadSpeed,
                            downloadedSize: totalDownloadedSize,
                            totalSize: totalSize,
                            remainingSize: totalSize - totalDownloadedSize,
                            completedFiles: progress.completed_task || 0,
                            totalFiles: progress.total_task || 0
                        }
                    });

                    // 更新個別檔案進度
                    updateIndividualFilesFromProgress(progress);

                    // 更新跟蹤變數
                    lastDownloadedSize = totalDownloadedSize;
                    lastUpdateTime = currentTime;

                } else if (progress && progress.completed_task > 0) {
                    // 下載完成
                    updateFloatingProgress({
                        percentage: 100,
                        status: `✅ 成功完成 ${progress.completed_task} 個檔案的下載！`,
                        details: {
                            downloadSpeed: 0,
                            downloadedSize: progress.total_size || 0,
                            totalSize: progress.total_size || 0,
                            remainingSize: 0,
                            completedFiles: progress.completed_task || 0,
                            totalFiles: progress.total_task || 0
                        }
                    });

                    // 顯示完成通知
                    showNotification('success', '下載完成', `成功完成 ${progress.completed_task} 個檔案的下載`);

                    // 3秒後自動隱藏進度條
                    setTimeout(() => {
                        hideFloatingProgress();
                    }, 3000);

                    // 停止檢查進度
                    clearInterval(progressCheckInterval);
                    progressCheckInterval = null;
                }
            }
        } catch (error) {
            console.error('檢查下載進度時發生錯誤:', error);
        }
    }, 1000); // 每秒檢查一次，提供更即時的更新
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

// ==================== 個別檔案進度管理 ====================

// 儲存個別檔案進度的資料
let individualFilesProgress = new Map();

/**
 * 初始化個別檔案進度
 * @param {Array} files - 檔案列表
 */
function initializeIndividualProgress(files) {
    individualFilesProgress.clear();

    files.forEach(file => {
        individualFilesProgress.set(file.id, {
            id: file.id,
            name: file.name || `檔案 ${file.id}`,
            size: file.size || 0,
            downloaded: 0,
            progress: 0,
            status: 'waiting', // waiting, downloading, completed, error
            speed: 0,
            eta: null
        });
    });

    renderIndividualProgress();
}

/**
 * 更新個別檔案進度
 * @param {string} fileId - 檔案ID
 * @param {Object} progressData - 進度資料
 */
function updateIndividualFileProgress(fileId, progressData) {
    const fileProgress = individualFilesProgress.get(fileId);
    if (!fileProgress) return;

    // 更新檔案進度資料
    Object.assign(fileProgress, progressData);

    // 計算進度百分比
    if (fileProgress.size > 0) {
        fileProgress.progress = Math.round((fileProgress.downloaded / fileProgress.size) * 100);
    }

    // 更新單個檔案的顯示
    updateIndividualFileDisplay(fileId);
}

/**
 * 渲染個別檔案進度列表
 */
function renderIndividualProgress() {
    const container = document.getElementById('individual-progress-list');
    if (!container) return;

    if (individualFilesProgress.size === 0) {
        container.innerHTML = `
            <div class="no-files-message">
                <i class="fas fa-hourglass-start"></i>
                <span>等待下載開始...</span>
            </div>
        `;
        return;
    }

    const html = Array.from(individualFilesProgress.values()).map(file => `
        <div class="individual-file-item" id="file-${file.id}" data-status="${file.status}">
            <div class="file-info">
                <div class="file-icon">
                    ${getFileIcon(file.name)}
                </div>
                <div class="file-details">
                    <div class="file-name" title="${file.name}">${truncateFileName(file.name, 30)}</div>
                    <div class="file-meta">
                        <span class="file-size">${formatSize(file.size)}</span>
                        <span class="file-status-text" id="file-status-${file.id}">${getStatusText(file.status)}</span>
                    </div>
                </div>
            </div>
            <div class="file-progress-section">
                <div class="file-progress-bar">
                    <div class="file-progress-fill" id="file-progress-${file.id}" style="width: ${file.progress}%"></div>
                </div>
                <div class="file-progress-text">
                    <span class="progress-percentage" id="file-percentage-${file.id}">${file.progress}%</span>
                    <span class="progress-speed" id="file-speed-${file.id}">${file.speed > 0 ? formatSpeed(file.speed) : ''}</span>
                </div>
            </div>
        </div>
    `).join('');

    container.innerHTML = html;
}

/**
 * 更新單個檔案的顯示
 * @param {string} fileId - 檔案ID
 */
function updateIndividualFileDisplay(fileId) {
    const fileProgress = individualFilesProgress.get(fileId);
    if (!fileProgress) return;

    const fileElement = document.getElementById(`file-${fileId}`);
    if (!fileElement) return;

    // 更新狀態
    fileElement.setAttribute('data-status', fileProgress.status);

    // 更新進度條
    const progressBar = document.getElementById(`file-progress-${fileId}`);
    if (progressBar) {
        progressBar.style.width = `${fileProgress.progress}%`;
    }

    // 更新百分比
    const percentageElement = document.getElementById(`file-percentage-${fileId}`);
    if (percentageElement) {
        percentageElement.textContent = `${fileProgress.progress}%`;
    }

    // 更新速度
    const speedElement = document.getElementById(`file-speed-${fileId}`);
    if (speedElement) {
        speedElement.textContent = fileProgress.speed > 0 ? formatSpeed(fileProgress.speed) : '';
    }

    // 更新狀態文字
    const statusElement = document.getElementById(`file-status-${fileId}`);
    if (statusElement) {
        statusElement.textContent = getStatusText(fileProgress.status);
    }

    // 更新檔案大小顯示
    const sizeElement = fileElement.querySelector('.file-size');
    if (sizeElement && fileProgress.size > 0) {
        sizeElement.textContent = formatSize(fileProgress.size);
    }
}

/**
 * 獲取檔案圖標
 * @param {string} fileName - 檔案名稱
 * @returns {string} 圖標HTML
 */
function getFileIcon(fileName) {
    const ext = fileName.split('.').pop().toLowerCase();
    const iconMap = {
        'mp4': '<i class="fas fa-video"></i>',
        'mp3': '<i class="fas fa-music"></i>',
        'jpg': '<i class="fas fa-image"></i>',
        'jpeg': '<i class="fas fa-image"></i>',
        'png': '<i class="fas fa-image"></i>',
        'gif': '<i class="fas fa-image"></i>',
        'pdf': '<i class="fas fa-file-pdf"></i>',
        'doc': '<i class="fas fa-file-word"></i>',
        'docx': '<i class="fas fa-file-word"></i>',
        'zip': '<i class="fas fa-file-archive"></i>',
        'rar': '<i class="fas fa-file-archive"></i>'
    };
    return iconMap[ext] || '<i class="fas fa-file"></i>';
}

/**
 * 截斷檔案名稱
 * @param {string} fileName - 檔案名稱
 * @param {number} maxLength - 最大長度
 * @returns {string} 截斷後的檔案名稱
 */
function truncateFileName(fileName, maxLength) {
    if (fileName.length <= maxLength) return fileName;

    const ext = fileName.split('.').pop();
    const name = fileName.substring(0, fileName.lastIndexOf('.'));
    const truncatedName = name.substring(0, maxLength - ext.length - 4) + '...';

    return `${truncatedName}.${ext}`;
}

/**
 * 獲取狀態文字
 * @param {string} status - 狀態
 * @returns {string} 狀態文字
 */
function getStatusText(status) {
    const statusMap = {
        'waiting': '等待中',
        'downloading': '下載中',
        'completed': '已完成',
        'error': '錯誤'
    };
    return statusMap[status] || '未知';
}

/**
 * 從後端進度資料更新個別檔案進度
 * @param {Object} progress - 後端進度資料
 */
function updateIndividualFilesFromProgress(progress) {
    if (!progress || !progress.current_files) return;

    const currentFiles = progress.current_files;
    const completedFiles = progress.completed_task || 0;
    const totalFiles = progress.total_task || 0;

    // 如果沒有初始化檔案列表，根據總檔案數創建
    if (individualFilesProgress.size === 0 && totalFiles > 0) {
        const fileList = [];

        // 先新增當前正在下載的檔案
        Object.keys(currentFiles).forEach((fileId, index) => {
            const fileData = currentFiles[fileId];
            fileList.push({
                id: fileId,
                name: fileData.name || fileData.filename || `檔案 ${index + 1}`,
                size: fileData.total_bytes || 0
            });
        });

        // 填充剩餘的檔案項目，確保總數等於 totalFiles
        for (let i = fileList.length; i < totalFiles; i++) {
            fileList.push({
                id: `file_${i + 1}`,
                name: `檔案 ${i + 1}`,
                size: 0
            });
        }

        console.log(`初始化 ${fileList.length} 個檔案進度項目`);
        initializeIndividualProgress(fileList);
    }

    // 更新當前正在下載的檔案狀態
    Object.keys(currentFiles).forEach(fileId => {
        const fileData = currentFiles[fileId];
        const progressPercentage = fileData.total_bytes > 0
            ? Math.round((fileData.downloaded_bytes / fileData.total_bytes) * 100)
            : 0;

        // 嘗試匹配已存在的檔案項目
        let existingFileId = fileId;
        const messageId = fileData.message_id;

        if (!individualFilesProgress.has(fileId) && messageId) {
            // 嘗試通過訊息ID匹配（尋找 message_XXX 格式）
            const matchingKey = Array.from(individualFilesProgress.keys()).find(key =>
                key === `message_${messageId}` || key.includes(`${messageId}_`) || key.includes(`_${messageId}`)
            );
            if (matchingKey) {
                existingFileId = matchingKey;
                console.log(`檔案 ${fileId} 匹配到現有項目: ${existingFileId}`);
            } else {
                // 如果沒找到匹配，使用原始格式
                existingFileId = `message_${messageId}`;
                console.log(`檔案 ${fileId} 使用標準格式: ${existingFileId}`);
            }
        }

        updateIndividualFileProgress(existingFileId, {
            downloaded: fileData.downloaded_bytes || 0,
            size: fileData.total_bytes || 0,
            progress: progressPercentage,
            status: fileData.completed ? 'completed' : (fileData.downloaded_bytes > 0 ? 'downloading' : 'waiting'),
            speed: fileData.download_speed || 0,
            name: fileData.filename || fileData.name || `訊息 ${fileData.message_id}`
        });
    });

    // 將已完成的檔案標記為完成狀態
    let completedCount = 0;
    for (const [fileId, fileData] of individualFilesProgress.entries()) {
        if (fileData.status === 'completed') {
            completedCount++;
        } else if (fileData.progress === 100 && fileData.status === 'downloading') {
            updateIndividualFileProgress(fileId, { status: 'completed' });
            completedCount++;
        } else if (!currentFiles[fileId] && fileData.status === 'waiting') {
            // 如果檔案不在當前下載列表中且還是等待狀態，可能需要根據總進度判斷
            if (completedCount < completedFiles) {
                updateIndividualFileProgress(fileId, {
                    status: 'completed',
                    progress: 100,
                    downloaded: fileData.size,  // 確保下載量等於檔案大小
                    speed: 0
                });
                completedCount++;
            }
        }
    }
}

/**
 * 切換個別進度顯示
 */
function toggleIndividualProgress() {
    const container = document.getElementById('individual-progress-container');
    const toggleBtn = document.getElementById('toggle-individual-progress');
    const icon = toggleBtn.querySelector('i');

    if (container.style.display === 'none') {
        container.style.display = 'block';
        icon.className = 'fas fa-chevron-up';
    } else {
        container.style.display = 'none';
        icon.className = 'fas fa-chevron-down';
    }
}

// ==================== 浮動進度條控制函數 ====================

/**
 * 顯示浮動進度條
 */
function showFloatingProgress() {
    const modal = document.getElementById('floating-progress-modal');
    const minimized = document.getElementById('minimized-progress-indicator');

    if (modal) {
        modal.style.display = 'block';
        // 確保最小化指示器被隱藏
        if (minimized) {
            minimized.style.display = 'none';
        }

        // 設置事件監聽器
        setupFloatingProgressEvents();

        // 重置個別進度顯示
        renderIndividualProgress();
    }
}

/**
 * 隱藏浮動進度條
 */
function hideFloatingProgress() {
    const modal = document.getElementById('floating-progress-modal');
    const minimized = document.getElementById('minimized-progress-indicator');

    if (modal) {
        modal.style.display = 'none';
    }
    if (minimized) {
        minimized.style.display = 'none';
    }

    // 停止進度檢查
    stopProgressChecking();
}

/**
 * 最小化浮動進度條
 */
function minimizeFloatingProgress() {
    const modal = document.getElementById('floating-progress-modal');
    const minimized = document.getElementById('minimized-progress-indicator');

    if (modal) {
        modal.style.display = 'none';
    }
    if (minimized) {
        minimized.style.display = 'block';
    }
}

/**
 * 恢復浮動進度條
 */
function restoreFloatingProgress() {
    const modal = document.getElementById('floating-progress-modal');
    const minimized = document.getElementById('minimized-progress-indicator');

    if (modal) {
        modal.style.display = 'block';
    }
    if (minimized) {
        minimized.style.display = 'none';
    }
}

/**
 * 更新浮動進度條
 * @param {Object} progressData - 進度資訊
 */
function updateFloatingProgress(progressData) {
    // 更新百分比
    if (progressData.percentage !== undefined) {
        const percentageElement = document.getElementById('progress-percentage-text');
        const barFill = document.getElementById('progress-bar-fill');
        const minimizedPercentage = document.querySelector('.minimized-percentage');
        const minimizedBarFill = document.getElementById('minimized-progress-fill');

        if (percentageElement) {
            percentageElement.textContent = `${progressData.percentage}%`;
        }
        if (barFill) {
            barFill.style.width = `${progressData.percentage}%`;
        }
        if (minimizedPercentage) {
            minimizedPercentage.textContent = `${progressData.percentage}%`;
        }
        if (minimizedBarFill) {
            minimizedBarFill.style.width = `${progressData.percentage}%`;
        }
    }

    // 更新狀態文字
    if (progressData.status) {
        const statusElement = document.getElementById('progress-status-text');
        if (statusElement) {
            statusElement.textContent = progressData.status;
        }
    }

    // 更新詳細資訊
    if (progressData.details) {
        const { downloadSpeed, downloadedSize, totalSize, remainingSize, completedFiles, totalFiles } = progressData.details;

        // 更新速度
        const speedElement = document.getElementById('progress-speed');
        if (speedElement && downloadSpeed !== undefined) {
            speedElement.textContent = formatSpeed(downloadSpeed);
        }

        // 更新大小
        const sizeElement = document.getElementById('progress-size');
        if (sizeElement && downloadedSize !== undefined && totalSize !== undefined) {
            const downloaded = formatSize(downloadedSize);
            const total = formatSize(totalSize);
            sizeElement.textContent = `${downloaded} / ${total}`;
        }

        // 更新預估剩餘時間
        const etaElement = document.getElementById('progress-eta');
        if (etaElement && downloadSpeed !== undefined && remainingSize !== undefined) {
            if (downloadSpeed > 0) {
                const remainingSeconds = remainingSize / downloadSpeed;
                etaElement.textContent = formatETA(remainingSeconds);
            } else {
                etaElement.textContent = '--:--';
            }
        }

        // 更新檔案進度
        const filesElement = document.getElementById('progress-files');
        if (filesElement && completedFiles !== undefined && totalFiles !== undefined) {
            filesElement.textContent = `${completedFiles} / ${totalFiles}`;
        }
    }
}

/**
 * 設置浮動進度條事件監聽器
 */
function setupFloatingProgressEvents() {
    // 最小化按鈕
    const minimizeBtn = document.getElementById('minimize-progress-btn');
    if (minimizeBtn) {
        minimizeBtn.removeEventListener('click', minimizeFloatingProgress);
        minimizeBtn.addEventListener('click', minimizeFloatingProgress);
    }

    // 關閉按鈕
    const closeBtn = document.getElementById('close-progress-btn');
    if (closeBtn) {
        closeBtn.removeEventListener('click', handleCloseProgress);
        closeBtn.addEventListener('click', handleCloseProgress);
    }

    // 最小化指示器點擊恢復
    const minimizedIndicator = document.getElementById('minimized-progress-indicator');
    if (minimizedIndicator) {
        minimizedIndicator.removeEventListener('click', restoreFloatingProgress);
        minimizedIndicator.addEventListener('click', restoreFloatingProgress);
    }

    // 個別進度切換按鈕
    const toggleBtn = document.getElementById('toggle-individual-progress');
    if (toggleBtn) {
        toggleBtn.removeEventListener('click', toggleIndividualProgress);
        toggleBtn.addEventListener('click', toggleIndividualProgress);
    }
}

/**
 * 處理關閉進度條
 */
function handleCloseProgress() {
    // 停止進度檢查
    stopProgressChecking();

    // 隱藏進度條
    hideFloatingProgress();

    // 顯示確認通知
    showNotification('info', '已停止', '下載進度監控已停止');
}

// ==================== 真實進度查詢 ====================

let realProgressInterval = null;

/**
 * 開始真實進度輪詢
 */
function startRealProgressPolling() {
    console.log('開始真實進度輪詢...');

    // 清除現有的定時器
    if (realProgressInterval) {
        clearInterval(realProgressInterval);
    }

    // 每秒查詢一次真實進度
    realProgressInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/download_progress');
            if (response.ok) {
                const progressData = await response.json();
                console.log('真實進度數據:', progressData);
                updateRealProgress(progressData);
            }
        } catch (error) {
            console.error('查詢真實進度失敗:', error);
        }
    }, 1000);
}

/**
 * 停止真實進度輪詢
 */
function stopRealProgressPolling() {
    console.log('停止真實進度輪詢...');

    if (realProgressInterval) {
        clearInterval(realProgressInterval);
        realProgressInterval = null;
    }
}

/**
 * 更新真實進度顯示
 * @param {Object} progressData - 後端返回的進度數據
 */
function updateRealProgress(progressData) {
    // 解析進度數據 - 數據在 progress 物件中
    const progress = progressData.progress || {};
    const { current_files = {}, active = false, total_task = 0, completed_task = 0 } = progress;

    console.log('更新真實進度:', { active, fileCount: Object.keys(current_files).length, totalTask: total_task, completedTask: completed_task, progress });

    // 如果沒有活躍下載，跳過更新
    if (!active) {
        console.log('沒有活躍下載，跳過更新');
        return;
    }

    // 計算總體進度
    let totalDownloaded = 0;
    let totalSize = 0;
    let totalSpeed = 0;

    // 使用後端提供的正確數據
    let completedFiles = completed_task;
    let totalFiles = total_task;

    // 更新個別檔案進度
    for (const [fileKey, fileData] of Object.entries(current_files)) {
        const { name, downloaded_bytes = 0, total_bytes = 0, download_speed = 0, message_id, completed = false } = fileData;

        totalDownloaded += downloaded_bytes;
        totalSize += total_bytes;
        totalSpeed += download_speed;

        if (completed || (downloaded_bytes >= total_bytes && total_bytes > 0)) {
            completedFiles++;
        }

        // 更新個別檔案進度顯示
        updateIndividualFileProgress({
            id: `real_${message_id}_${name}`,
            messageId: message_id,
            name: name,
            size: total_bytes,
            status: completed ? 'completed' : (downloaded_bytes > 0 ? 'downloading' : 'waiting')
        }, downloaded_bytes, total_bytes, download_speed);
    }

    // 計算百分比
    const percentage = totalSize > 0 ? Math.round((totalDownloaded / totalSize) * 100) : 0;

    // 計算剩餘時間
    const remainingBytes = totalSize - totalDownloaded;
    const etaSeconds = totalSpeed > 0 ? Math.round(remainingBytes / totalSpeed) : 0;
    const etaText = etaSeconds > 0 ? formatTime(etaSeconds) : '--:--';

    // 更新浮動進度條
    updateFloatingProgress({
        percentage: percentage,
        status: percentage >= 100 ? '下載完成' : `正在下載 ${completedFiles}/${totalFiles} 個檔案`,
        details: {
            downloadSpeed: totalSpeed,
            downloadedSize: totalDownloaded,
            totalSize: totalSize,
            completedFiles: completedFiles,
            totalFiles: totalFiles
        }
    });

    // 更新統計資訊
    updateProgressStats({
        speed: formatSpeed(totalSpeed),
        eta: etaText,
        size: `${formatSize(totalDownloaded)} / ${formatSize(totalSize)}`,
        files: `${completedFiles} / ${totalFiles}`
    });

    // 如果下載完成，停止輪詢
    if (percentage >= 100 && completedFiles === totalFiles) {
        setTimeout(() => {
            stopRealProgressPolling();
        }, 2000); // 2秒後停止輪詢
    }
}

/**
 * 更新進度統計資訊
 * @param {Object} stats - 統計資訊
 */
function updateProgressStats(stats) {
    // 更新速度
    const speedElement = document.getElementById('progress-speed');
    if (speedElement && stats.speed) {
        speedElement.textContent = stats.speed;
    }

    // 更新剩餘時間
    const etaElement = document.getElementById('progress-eta');
    if (etaElement && stats.eta) {
        etaElement.textContent = stats.eta;
    }

    // 更新大小
    const sizeElement = document.getElementById('progress-size');
    if (sizeElement && stats.size) {
        sizeElement.textContent = stats.size;
    }

    // 更新檔案數
    const filesElement = document.getElementById('progress-files');
    if (filesElement && stats.files) {
        filesElement.textContent = stats.files;
    }
}