/**
 * Message Downloader - Groups Module
 * 群組管理和側邊欄渲染功能
 */

// ==================== 群組載入和管理 ====================

/**
 * 載入群組列表
 */
async function loadGroups() {
    // 如果在登入頁面,不要載入群組(避免無限跳轉)
    if (window.location.pathname.includes('/login')) {
        console.log('⏭️  在登入頁面,跳過載入群組');
        return;
    }

    try {
        console.log('🔍 開始載入群組...');

        // 先檢查認證狀態，避免在未認證時發送請求
        console.log('🔒 檢查認證狀態...');
        const authResponse = await fetch('/api/auth/status');
        const authData = await authResponse.json();

        if (!authData.success || !authData.data || !authData.data.authenticated) {
            console.log('❌ 用戶未認證，無法載入群組');
            if (typeof showAuthForm === 'function') {
                console.log('🔄 顯示認證表單...');
                showAuthForm();
            }
            return;
        }

        console.log('✅ 認證狀態確認，開始載入群組');
        const response = await fetch('/api/groups/list');
        console.log('API 回應狀態:', response.status);

        const data = await response.json();
        console.log('API 回應數據:', data);

        // 檢查是否為 401 認證錯誤
        if (response.status === 401) {
            console.log('認證錯誤，需要重新登入');
            if (data.error && (data.error.includes('認證') || data.error.includes('需要'))) {
                if (typeof showAuthForm === 'function') {
                    showAuthForm();
                }
            }
            return;
        }

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        if (data.success) {
            // 獲取群組數據，考慮 API 回應格式
            const groups = data.data ? data.data.groups : data.groups;
            console.log('群組載入成功，數量:', groups ? groups.length : 0);

            // 從本地存儲獲取釘選群組列表
            const favoriteGroups = JSON.parse(localStorage.getItem('favoriteGroups') || '[]');

            // 更新群組數據的 is_favorite 狀態
            if (groups) {
                groups.forEach(group => {
                    group.is_favorite = favoriteGroups.includes(group.id.toString());
                });
            }

            renderGroupSidebar(groups);
            window.originalGroups = groups;
        } else {
            const errorMsg = data.error || data.message || '未知錯誤';
            console.error('載入群組失敗:', errorMsg);
            // 如果是認證錯誤，顯示認證表單
            if (errorMsg.includes('認證') || errorMsg.includes('需要') || errorMsg.includes('會話')) {
                if (typeof showAuthForm === 'function') {
                    showAuthForm();
                }
            }
        }
    } catch (error) {
        console.error('載入群組網絡錯誤:', error);
        console.error('錯誤詳情:', error.message);
        // 檢查是否是網絡連接問題
        if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
            console.error('網絡連接失敗，請檢查應用程式是否運行');
        }
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

    // 防禦性檢查：確保 groups 是陣列
    if (!Array.isArray(groups)) {
        console.error('群組資料無效，應為陣列:', groups);
        groups = []; // 提供預設空陣列
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
    console.log('🎯 群組選擇:', { groupId, groupTitle });

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
    if (typeof selectedMessages !== 'undefined') {
        selectedMessages.length = 0;
        console.log('✅ 重置 selectedMessages');
    }
    if (typeof currentChatId !== 'undefined') {
        currentChatId = groupId;
        console.log('✅ 設置 currentChatId:', currentChatId);
    }
    if (typeof allMessages !== 'undefined') {
        allMessages.length = 0;
        console.log('✅ 重置 allMessages');
    }
    if (typeof lastMessageId !== 'undefined') {
        lastMessageId = 0;
        console.log('✅ 重置 lastMessageId');
    }
    if (typeof hasMoreMessages !== 'undefined') {
        hasMoreMessages = true;
        console.log('✅ 重置 hasMoreMessages');
    }

    // 更新選擇計數器
    if (typeof updateSelectionUI === 'function') {
        updateSelectionUI();
        console.log('✅ 更新選擇UI');
    }

    // 載入訊息
    console.log('📨 準備載入訊息...');
    if (typeof loadMessages === 'function') {
        try {
            await loadMessages(true);
            console.log('✅ 訊息載入完成');
        } catch (error) {
            console.error('❌ 訊息載入失敗:', error);
        }
    } else {
        console.error('❌ loadMessages 函數不存在');
    }

    // 顯示聊天控制
    const chatControls = document.getElementById('chat-controls');
    if (chatControls) {
        chatControls.style.display = 'block';
        console.log('✅ 顯示聊天控制');
    } else {
        console.warn('⚠️  chat-controls 元素不存在');
    }
}

/**
 * 切換群組釘選狀態
 * @param {string|number} groupId - 群組ID
 */
async function toggleFavorite(groupId) {
    try {
        const groupIdStr = groupId.toString();

        // 從本地存儲獲取當前釘選群組列表
        let favoriteGroups = JSON.parse(localStorage.getItem('favoriteGroups') || '[]');

        // 切換釘選狀態
        const index = favoriteGroups.indexOf(groupIdStr);
        if (index > -1) {
            // 取消釘選
            favoriteGroups.splice(index, 1);
        } else {
            // 添加釘選
            favoriteGroups.push(groupIdStr);
        }

        // 保存到本地存儲
        localStorage.setItem('favoriteGroups', JSON.stringify(favoriteGroups));

        // 更新全域變數
        if (typeof favoriteGroups !== 'undefined') {
            // 更新 core.js 中的全域變數
            window.favoriteGroups = favoriteGroups;
        }

        // 更新群組數據中的 is_favorite 狀態
        if (window.originalGroups) {
            window.originalGroups.forEach(group => {
                if (group.id.toString() === groupIdStr) {
                    group.is_favorite = favoriteGroups.includes(groupIdStr);
                }
            });

            // 重新渲染群組列表以反映變更
            renderGroupSidebar(window.originalGroups);
        }
    } catch (error) {
        console.error('切換釘選狀態失敗:', error);
    }
}