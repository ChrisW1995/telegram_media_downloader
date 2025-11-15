/**
 * Message Downloader - Album Module
 * 相簿和媒體篩選功能
 *
 * 提供相簿入口、媒體篩選、網格視圖等功能
 */

// ==================== 媒體篩選器功能 ====================

/**
 * 初始化媒體篩選器
 */
function initMediaFilter() {
    document.querySelectorAll('.media-tab').forEach(btn => {
        btn.addEventListener('click', function() {
            const filterType = this.dataset.filter;
            toggleMediaFilter(filterType);
        });
    });
}

/**
 * 切換媒體篩選器
 * @param {string} filterType - 篩選類型
 */
function toggleMediaFilter(filterType) {
    if (filterType === 'all') {
        activeMediaFilters = ['all'];
        document.querySelectorAll('.media-tab').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector('.media-tab[data-filter="all"]').classList.add('active');
    } else {
        // 移除 'all'
        activeMediaFilters = activeMediaFilters.filter(f => f !== 'all');
        document.querySelector('.media-tab[data-filter="all"]')?.classList.remove('active');

        // 切換選中狀態
        const btn = document.querySelector(`.media-tab[data-filter="${filterType}"]`);
        if (activeMediaFilters.includes(filterType)) {
            activeMediaFilters = activeMediaFilters.filter(f => f !== filterType);
            btn.classList.remove('active');
        } else {
            activeMediaFilters.push(filterType);
            btn.classList.add('active');
        }

        // 如果都沒選，自動切回全部
        if (activeMediaFilters.length === 0) {
            activeMediaFilters = ['all'];
            document.querySelector('.media-tab[data-filter="all"]')?.classList.add('active');
        }
    }

    // 應用篩選
    applyMessageFilter();
}

/**
 * 應用篩選到訊息列表
 */
function applyMessageFilter() {
    if (activeMediaFilters.includes('all')) {
        filteredMessages = allMessages;
    } else {
        filteredMessages = allMessages.filter(msg =>
            activeMediaFilters.includes(msg.media_type)
        );
    }

    // 重新渲染
    const container = document.getElementById('messages-list');
    if (container) {
        container.innerHTML = '';
        renderMessages(filteredMessages, false);
    }

    console.log(`篩選完成: ${filteredMessages.length}/${allMessages.length} 條訊息`);
}

/**
 * 更新篩選器計數
 */
function updateFilterCounts() {
    const counts = {
        all: allMessages.length,
        photo: allMessages.filter(m => m.media_type === 'photo').length,
        video: allMessages.filter(m => m.media_type === 'video').length,
        audio: allMessages.filter(m => m.media_type === 'audio').length,
        document: allMessages.filter(m => m.media_type === 'document').length,
        voice: allMessages.filter(m => m.media_type === 'voice').length,
        animation: allMessages.filter(m => m.media_type === 'animation').length
    };

    Object.keys(counts).forEach(type => {
        const el = document.getElementById(`filter-count-${type}`);
        if (el) el.textContent = counts[type];
    });
}

// ==================== 相簿入口功能 ====================

/**
 * 顯示相簿選擇器
 * @param {number} chatId - 聊天 ID
 */
async function showAlbumSelector(chatId) {
    currentChatId = chatId;
    currentViewMode = 'album-selector';

    // 隱藏其他視圖
    document.getElementById('messages-container').style.display = 'none';
    document.getElementById('media-album-view').style.display = 'none';

    // 隱藏媒體篩選列
    const filterBar = document.getElementById('media-filter-bar');
    if (filterBar) {
        filterBar.style.display = 'none';
    }

    // 顯示相簿選擇器
    const selector = document.getElementById('album-selector');
    selector.style.display = 'flex';

    // 載入媒體統計
    await loadMediaStats(chatId);
}

/**
 * 格式化數字顯示（處理大數字）
 * @param {number} num - 數字
 * @returns {string} 格式化後的字串
 */
function formatCount(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
    }
    if (num >= 1000) {
        return (num / 1000).toFixed(1).replace(/\.0$/, '') + 'K';
    }
    return num.toString();
}

/**
 * 載入媒體統計
 * @param {number} chatId - 聊天 ID
 */
async function loadMediaStats(chatId) {
    try {
        const response = await apiFetch(`/api/groups/${chatId}/media_stats`);
        const data = await response.json();

        if (data.success && data.stats) {
            const stats = data.stats;

            // 更新相簿選擇頁面的計數
            document.getElementById('album-count-all').textContent =
                `共 ${formatCount(stats.total)} 條訊息`;
            document.getElementById('album-count-photo').textContent = formatCount(stats.photo);
            document.getElementById('album-count-video').textContent = formatCount(stats.video);
            document.getElementById('album-count-audio').textContent = formatCount(stats.audio);
            document.getElementById('album-count-document').textContent = formatCount(stats.document);
        }
    } catch (error) {
        console.error('載入媒體統計失敗:', error);
        showAlert('載入媒體統計失敗', 'danger');
    }
}

/**
 * 顯示全部訊息模式
 */
async function showAllMessagesMode() {
    currentViewMode = 'messages';

    // 隱藏相簿相關視圖
    document.getElementById('album-selector').style.display = 'none';
    document.getElementById('media-album-view').style.display = 'none';
    document.getElementById('messages-overlay').style.display = 'none';

    // 顯示訊息容器和篩選器
    document.getElementById('messages-container').style.display = 'block';
    document.getElementById('media-filter-bar').style.display = 'flex';

    // 載入訊息（直接調用 loadMessages 而不是 selectGroup 以避免循環）
    if (currentChatId && typeof loadMessages === 'function') {
        console.log('載入全部訊息模式的訊息...');
        await loadMessages(true);

        // 更新篩選器計數
        if (typeof updateFilterCounts === 'function') {
            updateFilterCounts();
        }
    }
}

// ==================== 媒體相簿網格視圖 ====================

/**
 * 顯示媒體相簿
 * @param {number} chatId - 聊天 ID
 * @param {string} mediaType - 媒體類型
 */
// 相簿分頁變數
let albumOffset = 0;
let albumHasMore = true;
let albumIsLoading = false;
const ALBUM_PAGE_SIZE = 50;

async function showMediaAlbum(chatId, mediaType) {
    currentChatId = chatId;
    currentAlbumType = mediaType;
    currentViewMode = 'album-grid';
    albumSelectedMessages = [];

    // 重置分頁變數
    albumOffset = 0;
    albumHasMore = true;
    albumIsLoading = false;

    // 隱藏其他視圖
    document.getElementById('album-selector').style.display = 'none';
    document.getElementById('messages-container').style.display = 'none';

    // 隱藏媒體篩選列
    const filterBar = document.getElementById('media-filter-bar');
    if (filterBar) {
        filterBar.style.display = 'none';
    }

    // 顯示相簿視圖
    const albumView = document.getElementById('media-album-view');
    albumView.style.display = 'flex';

    // 更新標題（使用 SVG icon）
    const titleIcons = {
        photo: `<svg width="24" height="24" viewBox="0 0 40 40" fill="none" style="vertical-align: middle; margin-right: 8px; color: #ffffff;">
                    <rect x="6" y="8" width="28" height="24" rx="3" stroke="currentColor" stroke-width="2"/>
                    <circle cx="14" cy="16" r="3" fill="currentColor"/>
                    <path d="M6 26 L14 18 L20 24 L26 18 L34 26" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>`,
        video: `<svg width="24" height="24" viewBox="0 0 40 40" fill="none" style="vertical-align: middle; margin-right: 8px; color: #ffffff;">
                    <rect x="6" y="10" width="20" height="20" rx="3" stroke="currentColor" stroke-width="2"/>
                    <path d="M26 14 L34 10 L34 30 L26 26 Z" fill="currentColor"/>
                </svg>`,
        audio: `<svg width="24" height="24" viewBox="0 0 40 40" fill="none" style="vertical-align: middle; margin-right: 8px; color: #ffffff;">
                    <rect x="11" y="16" width="3" height="8" rx="1.5" fill="currentColor"/>
                    <rect x="16" y="12" width="3" height="16" rx="1.5" fill="currentColor"/>
                    <rect x="21" y="8" width="3" height="24" rx="1.5" fill="currentColor"/>
                    <rect x="26" y="14" width="3" height="12" rx="1.5" fill="currentColor"/>
                </svg>`,
        document: `<svg width="24" height="24" viewBox="0 0 40 40" fill="none" style="vertical-align: middle; margin-right: 8px; color: #ffffff;">
                    <path d="M12 6 L24 6 L32 14 L32 34 C32 35.1 31.1 36 30 36 L12 36 C10.9 36 10 35.1 10 34 L10 8 C10 6.9 10.9 6 12 6 Z" stroke="currentColor" stroke-width="2"/>
                    <path d="M24 6 L24 14 L32 14" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
                    <line x1="16" y1="22" x2="26" y2="22" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    <line x1="16" y1="27" x2="26" y2="27" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>`,
        voice: `<svg width="24" height="24" viewBox="0 0 40 40" fill="none" style="vertical-align: middle; margin-right: 8px; color: #ffffff;">
                    <rect x="16" y="8" width="8" height="16" rx="4" stroke="currentColor" stroke-width="2"/>
                    <path d="M12 20 C12 24.4 15.6 28 20 28 C24.4 28 28 24.4 28 20" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    <line x1="20" y1="28" x2="20" y2="34" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    <line x1="16" y1="34" x2="24" y2="34" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>`,
        animation: `<svg width="24" height="24" viewBox="0 0 40 40" fill="none" style="vertical-align: middle; margin-right: 8px; color: #ffffff;">
                    <rect x="8" y="10" width="24" height="20" rx="2" stroke="currentColor" stroke-width="2"/>
                    <rect x="12" y="6" width="2" height="8" fill="currentColor"/>
                    <rect x="18" y="6" width="2" height="8" fill="currentColor"/>
                    <rect x="24" y="6" width="2" height="8" fill="currentColor"/>
                    <rect x="12" y="26" width="2" height="8" fill="currentColor"/>
                    <rect x="18" y="26" width="2" height="8" fill="currentColor"/>
                    <rect x="24" y="26" width="2" height="8" fill="currentColor"/>
                </svg>`
    };

    const titleTexts = {
        photo: '照片',
        video: '影片',
        audio: '音訊',
        document: '文件',
        voice: '語音',
        animation: '動畫'
    };

    const titleElement = document.getElementById('album-view-title');
    titleElement.innerHTML = (titleIcons[mediaType] || '') + (titleTexts[mediaType] || '媒體相簿');

    // 清空容器並載入第一頁
    const container = document.getElementById('album-grid-container');
    container.innerHTML = '';

    // 設置滾動監聽器
    setupAlbumScrollListener();

    // 載入第一頁媒體
    await loadMediaForAlbum(chatId, mediaType, true);
}

/**
 * 載入相簿媒體
 * @param {number} chatId - 聊天 ID
 * @param {string} mediaType - 媒體類型
 * @param {boolean} isFirstLoad - 是否為首次載入
 */
async function loadMediaForAlbum(chatId, mediaType, isFirstLoad = false) {
    if (albumIsLoading || !albumHasMore) {
        return;
    }

    albumIsLoading = true;
    if (isFirstLoad) {
        showLoading(true);
    }

    try {
        const response = await apiFetch('/api/groups/messages', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chat_id: chatId,
                limit: ALBUM_PAGE_SIZE,
                offset_id: albumOffset,
                media_only: true
            })
        });

        const data = await response.json();

        if (data.success && data.messages) {
            console.log(`🔍 收到 ${data.messages.length} 則訊息`);

            // 記錄前3則訊息的詳細信息
            data.messages.slice(0, 3).forEach((msg, idx) => {
                console.log(`訊息 ${idx}: ID=${msg.message_id}, type=${msg.media_type}, thumbnail_url=${msg.thumbnail_url || 'NONE'}`);
            });

            // 過濾符合類型的訊息
            const filteredMessages = data.messages.filter(msg => msg.media_type === mediaType);

            if (filteredMessages.length > 0) {
                console.log(`✅ 過濾後: ${filteredMessages.length} 則 ${mediaType} 類型訊息`);
                renderAlbumGrid(filteredMessages, !isFirstLoad);

                // 更新 offset 為最後一則訊息的 ID
                albumOffset = data.messages[data.messages.length - 1].message_id;
            } else {
                console.log(`⚠️ 沒有符合 ${mediaType} 類型的訊息`);
            }

            // 檢查是否還有更多
            albumHasMore = data.has_more !== undefined ? data.has_more : (data.messages.length >= ALBUM_PAGE_SIZE);

            console.log(`相簿載入: ${filteredMessages.length} 則 ${mediaType}，offset: ${albumOffset}，hasMore: ${albumHasMore}`);
        } else {
            console.error('❌ API 返回失敗或沒有訊息');
            albumHasMore = false;
        }
    } catch (error) {
        console.error('載入相簿失敗:', error);
        showAlert('載入媒體相簿失敗', 'danger');
        albumHasMore = false;
    } finally {
        albumIsLoading = false;
        if (isFirstLoad) {
            showLoading(false);
        }
    }
}

/**
 * 渲染網格
 * @param {Array} messages - 訊息陣列
 * @param {boolean} append - 是否為 append 模式
 */
function renderAlbumGrid(messages, append = false) {
    const container = document.getElementById('album-grid-container');

    if (!append) {
        container.innerHTML = '';
    }

    messages.forEach(message => {
        const item = document.createElement('div');
        item.className = 'album-grid-item';
        item.dataset.messageId = message.message_id;

        // 使用 loading placeholder
        const placeholderSvg = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="200" height="200"%3E%3Crect fill="%23444" width="200" height="200"/%3E%3Ctext fill="%23999" x="50%25" y="50%25" text-anchor="middle" dy=".3em" font-size="14"%3ELoading...%3C/text%3E%3C/svg%3E';

        item.innerHTML = `
            <img src="${placeholderSvg}"
                 alt="Message ${message.message_id}"
                 loading="eager"
                 class="album-grid-img"
                 style="display: block; width: 100%; height: 100%; object-fit: cover;">
            <div class="album-grid-item-overlay">
                <span>#${message.message_id}</span>
                <span>${typeof formatFileSize === 'function' ? formatFileSize(message.file_size || 0) : ''}</span>
            </div>
            <div class="album-grid-item-checkbox">
                <input type="checkbox"
                       onchange="toggleAlbumItemSelection(${message.message_id})"
                       onclick="event.stopPropagation()">
            </div>
        `;

        // 點擊放大（如果有 Lightbox 功能）
        item.addEventListener('click', function(e) {
            if (e.target.type !== 'checkbox') {
                if (typeof openLightbox === 'function') {
                    openLightbox(message.message_id);
                }
            }
        });

        container.appendChild(item);

        // 異步載入縮圖
        if (message.thumbnail_url) {
            loadAlbumThumbnail(message.message_id);
        }

        console.log(`📸 渲染 #${message.message_id}, 類型: ${message.media_type}, 開始載入縮圖: ${message.thumbnail_url ? 'YES' : 'NO'}`);
    });
}

/**
 * 設置相簿滾動監聽器
 */
function setupAlbumScrollListener() {
    const container = document.getElementById('album-grid-container');
    if (!container) return;

    // 移除舊的監聽器（如果存在）
    if (container.hasAttribute('data-album-scroll-listener')) {
        return;
    }

    container.addEventListener('scroll', function() {
        const scrollTop = container.scrollTop;
        const scrollHeight = container.scrollHeight;
        const clientHeight = container.clientHeight;

        // 當滾動到底部 200px 時載入更多
        if (scrollHeight - scrollTop - clientHeight < 200) {
            if (!albumIsLoading && albumHasMore) {
                loadMediaForAlbum(currentChatId, currentAlbumType, false);
            }
        }
    });

    container.setAttribute('data-album-scroll-listener', 'true');
    console.log('✅ 相簿滾動監聽器設置完成');
}

/**
 * 載入相簿項目縮圖
 * @param {number} messageId - 訊息 ID
 */
async function loadAlbumThumbnail(messageId) {
    try {
        const response = await apiFetch(
            `/api/thumbnails/${currentChatId}/${messageId}`
        );

        if (!response.ok) {
            console.warn(`縮圖 API 返回錯誤狀態: ${response.status} for message ${messageId}`);
            return;
        }

        const data = await response.json();

        if (data.success && data.data && data.data.thumbnail) {
            const img = document.querySelector(
                `.album-grid-item[data-message-id="${messageId}"] .album-grid-img`
            );
            if (img) {
                img.src = data.data.thumbnail;
                console.log(`✅ 縮圖載入成功: message ${messageId}`);
            }
        } else {
            console.warn(`縮圖 API 沒有返回有效數據: message ${messageId}`, data);
            // 設置為錯誤 placeholder
            const img = document.querySelector(
                `.album-grid-item[data-message-id="${messageId}"] .album-grid-img`
            );
            if (img) {
                img.src = 'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%22200%22%3E%3Crect fill=%22%23333%22 width=%22200%22 height=%22200%22/%3E%3Ctext fill=%22%23666%22 x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 dy=%22.3em%22 font-size=%2214%22%3ENo Image%3C/text%3E%3C/svg%3E';
            }
        }
    } catch (error) {
        console.error(`載入縮圖失敗 (message ${messageId}):`, error);
        // 設置為錯誤 placeholder
        const img = document.querySelector(
            `.album-grid-item[data-message-id="${messageId}"] .album-grid-img`
        );
        if (img) {
            img.src = 'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%22200%22%3E%3Crect fill=%22%23333%22 width=%22200%22 height=%22200%22/%3E%3Ctext fill=%22%23666%22 x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 dy=%22.3em%22 font-size=%2214%22%3EError%3C/text%3E%3C/svg%3E';
        }
    }
}

/**
 * 切換相簿項目選擇
 * @param {number} messageId - 訊息 ID
 */
function toggleAlbumItemSelection(messageId) {
    const item = document.querySelector(`.album-grid-item[data-message-id="${messageId}"]`);
    const checkbox = item.querySelector('input[type="checkbox"]');

    if (checkbox.checked) {
        item.classList.add('selected');
        if (!albumSelectedMessages.includes(messageId)) {
            albumSelectedMessages.push(messageId);
        }
    } else {
        item.classList.remove('selected');
        albumSelectedMessages = albumSelectedMessages.filter(id => id !== messageId);
    }

    updateAlbumSelectionUI();
}

/**
 * 更新相簿選擇 UI
 */
function updateAlbumSelectionUI() {
    document.getElementById('album-selected-count').textContent = albumSelectedMessages.length;
    document.getElementById('album-download-selected').disabled = albumSelectedMessages.length === 0;
}

/**
 * 全選相簿項目
 */
function selectAllAlbumItems() {
    const checkboxes = document.querySelectorAll('.album-grid-item input[type="checkbox"]');
    checkboxes.forEach(checkbox => {
        if (!checkbox.checked) {
            checkbox.checked = true;
            const messageId = parseInt(checkbox.closest('.album-grid-item').dataset.messageId);
            if (!albumSelectedMessages.includes(messageId)) {
                albumSelectedMessages.push(messageId);
            }
            checkbox.closest('.album-grid-item').classList.add('selected');
        }
    });
    updateAlbumSelectionUI();
}

/**
 * 清除相簿選擇
 */
function clearAlbumSelection() {
    const checkboxes = document.querySelectorAll('.album-grid-item input[type="checkbox"]');
    checkboxes.forEach(checkbox => {
        checkbox.checked = false;
        checkbox.closest('.album-grid-item').classList.remove('selected');
    });
    albumSelectedMessages = [];
    updateAlbumSelectionUI();
}

/**
 * 下載選中的相簿項目
 */
async function downloadSelectedAlbumItems() {
    if (albumSelectedMessages.length === 0) {
        showAlert('請先選擇要下載的項目', 'warning');
        return;
    }

    console.log('下載選中項目:', albumSelectedMessages);

    // 使用現有的快速下載功能
    if (typeof queueMultipleDownloads === 'function') {
        await queueMultipleDownloads(currentChatId, albumSelectedMessages);
    } else {
        showAlert('下載功能尚未實作', 'info');
    }
}

// ==================== 導航控制 ====================

/**
 * 返回相簿選擇器
 */
function backToSelector() {
    if (currentChatId) {
        showAlbumSelector(currentChatId);
    }
}

/**
 * 返回相簿選擇器（別名，供 HTML onclick 使用）
 */
function backToAlbumSelector() {
    backToSelector();
}

console.log('✅ Album module loaded');
