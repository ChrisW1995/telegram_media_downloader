/**
 * Message Downloader - Groups Module
 * 群組管理和側邊欄渲染功能
 */

// ==================== 群組載入和管理 ====================

/**
 * 載入群組列表
 */
async function loadGroups() {
    try {
        const response = await fetch('/api/groups/list');
        const data = await response.json();

        if (data.status === 'success') {
            renderGroupSidebar(data.groups);
            window.originalGroups = data.groups;
        } else {
            console.error('載入群組失敗:', data.message);
        }
    } catch (error) {
        console.error('載入群組失敗:', error);
    }
}

/**
 * 渲染群組到側邊欄
 * @param {Array} groups - 群組列表
 */
function renderGroupSidebar(groups) {
    const mainContainer = document.getElementById('groups-container');

    if (!mainContainer) {
        console.error('群組容器元素不存在');
        return;
    }

    // 創建完整的群組結構
    const favorites = groups.filter(g => g.is_favorite);
    const others = groups.filter(g => !g.is_favorite);

    let html = `
        <!-- 搜尋框 -->
        <div class="sidebar-section">
            <div class="search-box">
                <i class="fas fa-search"></i>
                <input type="text" id="group-search" placeholder="搜尋群組..."
                       oninput="filterGroups(this.value)">
            </div>
        </div>
    `;

    // 我的最愛群組
    if (favorites.length > 0) {
        html += `
            <div class="sidebar-section">
                <div class="sidebar-title">我的最愛</div>
                <div class="favorite-groups" id="favorite-groups">
                    ${favorites.map(group => renderGroupItem(group)).join('')}
                </div>
            </div>
        `;
    }

    // 所有群組
    html += `
        <div class="sidebar-section">
            <div class="sidebar-title">所有群組</div>
            <div class="all-groups" id="all-groups">
                ${others.map(group => renderGroupItem(group)).join('')}
            </div>
        </div>
    `;

    // 添加操作按鈕
    html += `
        <div class="action-buttons" id="action-buttons">
            <div class="selection-counter" id="selection-counter" style="display: none;">
                已選擇 <span id="selection-count">0</span> 個訊息
            </div>
        </div>
    `;

    mainContainer.innerHTML = html;

    // 儲存原始群組數據供搜尋使用
    window.originalGroups = groups;
}

/**
 * 渲染單個群組項目
 * @param {Object} group - 群組對象
 * @returns {string} HTML 字符串
 */
function renderGroupItem(group) {
    const iconClass = group.type === 'channel' ? 'fas fa-bullhorn' : 'fas fa-users';
    return `
        <div class="group-item" data-chat-id="${group.id}" onclick="selectGroup(${group.id}, '${group.title.replace(/'/g, "\\'")}')">
            <div class="group-icon">
                <i class="${iconClass}"></i>
            </div>
            <div class="group-name">${group.title}</div>
            <div class="group-info">
                ${group.message_count ? `<span class="group-badge">${group.message_count}</span>` : ''}
                <button class="group-pin-btn ${group.is_favorite ? 'pinned' : ''}"
                        onclick="event.stopPropagation(); toggleFavorite(${group.id})"
                        title="${group.is_favorite ? '取消釘選' : '釘選'}">
                    <i class="fas fa-thumbtack"></i>
                </button>
            </div>
        </div>
    `;
}

/**
 * 群組搜尋功能
 * @param {string} searchTerm - 搜尋關鍵字
 */
function filterGroups(searchTerm) {
    if (!window.originalGroups) return;

    const filteredGroups = window.originalGroups.filter(group =>
        group.title.toLowerCase().includes(searchTerm.toLowerCase())
    );

    const favorites = filteredGroups.filter(g => g.is_favorite);
    const others = filteredGroups.filter(g => !g.is_favorite);

    // 只更新群組列表部分
    const favoriteContainer = document.querySelector('.favorite-groups');
    const allGroupsContainer = document.querySelector('.all-groups');
    const favoritesSection = favoriteContainer?.parentElement;

    if (favorites.length > 0) {
        if (favoriteContainer) {
            favoriteContainer.innerHTML = favorites.map(group => renderGroupItem(group)).join('');
            favoritesSection.style.display = 'block';
        }
    } else {
        if (favoritesSection) favoritesSection.style.display = 'none';
    }

    if (allGroupsContainer) {
        allGroupsContainer.innerHTML = others.map(group => renderGroupItem(group)).join('');
    }
}

// ==================== 群組操作函數 ====================

/**
 * 選擇群組
 * @param {string|number} groupId - 群組ID
 * @param {string} groupTitle - 群組標題
 */
async function selectGroup(groupId, groupTitle) {
    // 更新活躍狀態
    document.querySelectorAll('.group-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`[data-chat-id="${groupId}"]`)?.classList.add('active');

    // 更新當前群組指示器
    const currentGroupName = document.getElementById('current-group-name');
    const currentGroupIndicator = document.getElementById('current-group-indicator');

    if (currentGroupName) currentGroupName.textContent = groupTitle;
    if (currentGroupIndicator) currentGroupIndicator.style.display = 'block';

    // 重置訊息相關變數（這些變數在 core.js 中定義）
    if (window.selectedMessages) window.selectedMessages = [];
    if (window.currentChatId !== undefined) window.currentChatId = groupId;
    if (window.allMessages) window.allMessages = [];
    if (window.lastMessageId !== undefined) window.lastMessageId = 0;
    if (window.hasMoreMessages !== undefined) window.hasMoreMessages = true;

    // 更新選擇計數器
    if (typeof updateSelectionCounter === 'function') {
        updateSelectionCounter();
    }

    // 載入訊息
    if (typeof loadMessages === 'function') {
        await loadMessages(groupId, true);
    }

    // 顯示聊天控制
    const chatControls = document.getElementById('chat-controls');
    if (chatControls) chatControls.style.display = 'block';
}

/**
 * 切換群組釘選狀態
 * @param {string|number} groupId - 群組ID
 */
async function toggleFavorite(groupId) {
    try {
        const response = await fetch('/api/groups/toggle_favorite', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ chat_id: groupId })
        });

        const data = await response.json();

        if (data.status === 'success') {
            // 重新載入群組列表以反映變更
            await loadGroups();
        } else {
            console.error('切換釘選狀態失敗:', data.message);
        }
    } catch (error) {
        console.error('切換釘選狀態失敗:', error);
    }
}