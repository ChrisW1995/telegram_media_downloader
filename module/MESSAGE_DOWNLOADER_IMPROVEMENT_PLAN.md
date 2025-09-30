# Message Downloader 改進計劃
**創建日期**: 2025-09-30
**更新日期**: 2025-10-01
**版本**: v1.1
**狀態**: 部分完成

---

## 目標概述

改進 Message Downloader 的三個核心功能：
1. **圖片縮圖放大預覽** - ⏳ 規劃中
2. **訊息快速跳轉功能** - ⏳ 規劃中
3. **媒體類型篩選系統（混合方案：相簿入口 + 篩選器）** - ⏳ 規劃中

---

## ✅ 已完成的改進項目（2025-10-01）

### 1. UI/UX 設計優化

#### 1.1 浮動進度彈窗重設計 ✅
**完成日期**: 2025-10-01

**改進內容**:
- ✅ Dark theme 配色優化
- ✅ 統計格子改為 2×2 網格佈局，平均分配空間
- ✅ Icon 與標籤垂直排列，數值顯示在右側
- ✅ 1:3 比例分配（標籤:數值）
- ✅ 文字大小調整防止截斷（標籤 11.5px，數值 17px，icon 22px）
- ✅ 響應式寬度調整（540px）

**修改檔案**:
- `module/templates/message_downloader.html` (HTML 結構重構)
- `module/static/css/message_downloader/controls.css` (樣式優化)
- `module/static/js/message_downloader/notifications.js` (檔案名稱更新邏輯)

#### 1.2 訊息列表響應式網格佈局 ✅
**完成日期**: 2025-10-01

**改進內容**:
- ✅ 實作響應式 2 欄網格佈局
- ✅ 考慮左側 sidebar 寬度的智能斷點設計
- ✅ 斷點設定：
  - < 1120px: 單欄顯示
  - ≥ 1120px: 雙欄顯示
  - ≥ 1320px: 優化間距（16px）
  - ≥ 1720px: 加大間距（20px）
  - ≥ 2200px: 最大間距（24px）
- ✅ 使用 `!important` 強制覆蓋衝突樣式

**修改檔案**:
- `module/static/css/message_downloader/chat.css` (網格佈局)
- `module/static/css/message_downloader/layout.css` (容器調整)

#### 1.3 Media Group 智能排列 ✅
**完成日期**: 2025-10-01

**改進內容**:
- ✅ 根據圖片比例智能調整排列方式（仿 Telegram）
- ✅ 兩張豎圖（height > width）→ 左右排列
- ✅ 兩張橫圖（width > height）→ 上下排列
- ✅ 後端已提供 width 和 height 資訊
- ✅ 前端 `analyzeOrientation` 函數自動分析圖片方向
- ✅ 新增 `grid-2-vertical` CSS 樣式支援上下排列

**修改檔案**:
- `module/static/js/message_downloader/messages.js` (智能排列邏輯)
- `module/static/css/message_downloader/chat.css` (新增垂直排列樣式)

#### 1.4 Media Group 高度填充優化 ✅
**完成日期**: 2025-10-01

**改進內容**:
- ✅ Grid-2（左右排列）時圖片完全填滿訊息氣泡高度
- ✅ 實作完整的 Flex 佈局鏈：
  - `.chat-bubble.media-group-bubble`: flex container + min-height 450px
  - `.message-header`: flex-shrink: 0 防止壓縮
  - `.message-content`: flex: 1 佔據剩餘空間
  - `.media-group-grid.grid-2`: flex: 1 + height: 100%
  - `.media-group-grid.grid-2 .media-group-item`: height: 100%

**修改檔案**:
- `module/static/css/message_downloader/chat.css` (Flex 佈局優化)

---

---

## 功能 1: 圖片縮圖放大預覽

### 當前問題
- 縮圖尺寸僅 80x80px，無法看清內容
- 無法放大查看原圖

### 改進方案

#### 1.1 增大縮圖尺寸
- **修改檔案**: `module/static/css/message_downloader/chat.css`
- **變更**: 將 `.media-thumbnail` 尺寸從 `80x80px` 改為 `150x150px`
- **行號**: 229-230

#### 1.2 實作 Lightbox 預覽功能

**新增 HTML Modal 元素** (`module/templates/message_downloader.html`)：
```html
<!-- Lightbox Modal -->
<div id="lightbox-modal" class="lightbox-overlay" style="display: none;">
    <div class="lightbox-container">
        <button class="lightbox-close">
            <i class="fas fa-times"></i>
        </button>
        <button class="lightbox-prev">
            <i class="fas fa-chevron-left"></i>
        </button>
        <button class="lightbox-next">
            <i class="fas fa-chevron-right"></i>
        </button>
        <div class="lightbox-content">
            <img id="lightbox-image" src="" alt="Preview">
            <div class="lightbox-info">
                <span id="lightbox-filename">檔案名稱</span>
                <span id="lightbox-message-id">#1234</span>
            </div>
        </div>
        <div class="lightbox-counter">
            <span id="lightbox-current">1</span> / <span id="lightbox-total">10</span>
        </div>
    </div>
</div>
```

**新增 CSS 樣式** (`module/static/css/message_downloader/chat.css`)：
```css
/* Lightbox 樣式 */
.lightbox-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.95);
    backdrop-filter: blur(20px);
    z-index: 9999;
    display: flex;
    align-items: center;
    justify-content: center;
}

.lightbox-container {
    position: relative;
    max-width: 90vw;
    max-height: 90vh;
}

.lightbox-content img {
    max-width: 90vw;
    max-height: 85vh;
    object-fit: contain;
}

.lightbox-close {
    position: absolute;
    top: 20px;
    right: 20px;
    background: rgba(255, 255, 255, 0.2);
    border: none;
    border-radius: 50%;
    width: 48px;
    height: 48px;
    cursor: pointer;
    font-size: 24px;
    color: white;
}

.lightbox-prev, .lightbox-next {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    background: rgba(255, 255, 255, 0.2);
    border: none;
    border-radius: 50%;
    width: 56px;
    height: 56px;
    cursor: pointer;
    font-size: 28px;
    color: white;
}

.lightbox-prev { left: 40px; }
.lightbox-next { right: 40px; }
```

**JavaScript 功能** (`module/static/js/message_downloader/messages.js`)：
```javascript
// Lightbox 狀態管理
let lightboxImages = [];
let currentLightboxIndex = 0;

// 打開 Lightbox
function openLightbox(messageId) {
    const message = allMessages.find(m => m.message_id === messageId);
    if (!message) return;

    // 收集當前顯示的所有圖片/影片
    lightboxImages = allMessages.filter(m =>
        (m.media_type === 'photo' || m.media_type === 'video') &&
        document.querySelector(`[data-message-id="${m.message_id}"]`)
    );

    currentLightboxIndex = lightboxImages.findIndex(m => m.message_id === messageId);
    showLightboxImage(currentLightboxIndex);

    document.getElementById('lightbox-modal').style.display = 'flex';
}

// 顯示 Lightbox 圖片
function showLightboxImage(index) {
    const message = lightboxImages[index];
    const img = document.getElementById('lightbox-image');

    // 載入完整圖片
    img.src = `/api/message_full_image/${currentChatId}/${message.message_id}`;

    document.getElementById('lightbox-filename').textContent = message.file_name || 'Image';
    document.getElementById('lightbox-message-id').textContent = `#${message.message_id}`;
    document.getElementById('lightbox-current').textContent = index + 1;
    document.getElementById('lightbox-total').textContent = lightboxImages.length;
}

// 鍵盤導航
document.addEventListener('keydown', function(e) {
    const modal = document.getElementById('lightbox-modal');
    if (modal.style.display === 'none') return;

    if (e.key === 'Escape') closeLightbox();
    else if (e.key === 'ArrowLeft') showPrevLightbox();
    else if (e.key === 'ArrowRight') showNextLightbox();
});

function showPrevLightbox() {
    if (currentLightboxIndex > 0) {
        currentLightboxIndex--;
        showLightboxImage(currentLightboxIndex);
    }
}

function showNextLightbox() {
    if (currentLightboxIndex < lightboxImages.length - 1) {
        currentLightboxIndex++;
        showLightboxImage(currentLightboxIndex);
    }
}

function closeLightbox() {
    document.getElementById('lightbox-modal').style.display = 'none';
}
```

**修改縮圖點擊事件** (`createMessageElement` 函數)：
```javascript
// 在縮圖上添加點擊事件
if (mediaInfo.type === 'photo' || mediaInfo.type === 'video') {
    div.dataset.needsThumbnail = 'true';
    div.dataset.messageData = JSON.stringify(message);

    // 添加點擊放大功能
    setTimeout(() => {
        const thumb = document.getElementById(`thumb-${message.message_id}`);
        if (thumb) {
            thumb.style.cursor = 'pointer';
            thumb.addEventListener('click', (e) => {
                e.stopPropagation();
                openLightbox(message.message_id);
            });
        }
    }, 100);
}
```

---

## 功能 2: 訊息快速跳轉功能

### 當前問題
- Lazy loading 機制導致需要不斷滾動載入才能看到舊訊息
- 每次載入 20 條訊息（`MESSAGES_PER_PAGE = 20`）

### 改進方案

#### 2.1 添加「跳到最舊」按鈕

**HTML 變更** (`module/templates/message_downloader.html`)：
在 `chat-controls` 選單中添加新按鈕：
```html
<li style="--i:0.35s;">
    <div class="menu-item">
        <button id="jump-to-oldest-btn" title="跳到最舊訊息">
            <i class="fas fa-fast-backward"></i>
        </button>
        <span class="menu-label">最舊</span>
    </div>
</li>
```

#### 2.2 實作跳轉載入邏輯

**JavaScript 實作** (`module/static/js/message_downloader/messages.js`)：
```javascript
// 跳轉到最舊訊息
async function jumpToOldest() {
    if (!currentChatId || isLoading) return;

    // 顯示確認通知
    showNotification('info', '跳轉中', '正在載入最舊的訊息...');

    // 重置狀態
    lastMessageId = 0;
    previousLastMessageId = 0;
    hasMoreMessages = true;
    allMessages = [];

    const container = document.getElementById('messages-list');
    if (container) container.innerHTML = '';

    isLoading = true;
    showLoading(true);

    try {
        // 一次載入較多訊息（100-200 條）
        const response = await fetch('/api/groups/messages', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chat_id: currentChatId,
                limit: 150, // 載入 150 條
                offset_id: 0,
                reverse: true // 從最舊開始
            })
        });

        const data = await response.json();

        if (data.success && data.messages) {
            allMessages = data.messages;
            renderMessages(data.messages, false);

            if (data.messages.length > 0) {
                lastMessageId = Math.min(...data.messages.map(m => m.message_id));
            }

            hasMoreMessages = data.has_more || data.messages.length >= 150;
            showMessages();

            // 滾動到頂部
            const messagesContainer = document.getElementById('messages-container');
            if (messagesContainer) {
                messagesContainer.scrollTop = 0;
            }

            showNotification('success', '跳轉成功', `已載入最舊的 ${data.messages.length} 條訊息`);
        }
    } catch (error) {
        console.error('跳轉錯誤:', error);
        showAlert('跳轉到最舊訊息失敗', 'danger');
    } finally {
        isLoading = false;
        showLoading(false);
    }
}
```

**UI 事件綁定** (`module/static/js/message_downloader/ui.js`)：
```javascript
// 跳到最舊按鈕事件
document.getElementById('jump-to-oldest-btn')?.addEventListener('click', function() {
    jumpToOldest();
});
```

#### 2.3 顯示載入進度指示

**在工具列添加進度指示** (`module/templates/message_downloader.html`)：
```html
<div class="toolbar-center">
    <div class="current-group-indicator" id="current-group-indicator" style="display: none;">
        <span id="current-group-name">選擇群組</span>
        <span id="message-progress" class="message-progress" style="display: none;">
            已載入 <span id="loaded-count">0</span> 條訊息
        </span>
    </div>
</div>
```

**更新進度顯示** (`messages.js`)：
```javascript
function updateMessageProgress() {
    const progressEl = document.getElementById('loaded-count');
    if (progressEl) {
        progressEl.textContent = allMessages.length;
        document.getElementById('message-progress').style.display = 'inline';
    }
}

// 在 renderMessages 函數中調用
function renderMessages(messages, appendMode = false) {
    // ... 原有代碼 ...
    updateMessageProgress();
}
```

---

## 功能 3: 媒體類型篩選系統（混合方案）

### 架構設計

**混合方案 = 相簿入口 + 兩種瀏覽模式**

1. **相簿入口頁面**：選擇群組後顯示媒體類型統計
2. **全部訊息模式**：時間軸 + 頂部篩選器（當前實現的增強版）
3. **專用相簿模式**：網格式媒體瀏覽（新功能）

---

### 3.1 相簿入口頁面

#### HTML 結構 (`module/templates/message_downloader.html`)

在 `messages-container` 後添加新的相簿選擇器：
```html
<!-- 相簿入口頁面 -->
<div id="album-selector" class="album-selector" style="display: none;">
    <div class="album-selector-header">
        <button id="back-to-groups" class="back-button">
            <i class="fas fa-chevron-left"></i>
            返回群組列表
        </button>
        <h3 id="album-selector-title">選擇瀏覽模式</h3>
    </div>

    <div class="album-selector-content">
        <!-- 全部訊息選項 -->
        <div class="album-option album-all" data-mode="all">
            <div class="album-icon">📋</div>
            <div class="album-info">
                <h4>瀏覽全部訊息</h4>
                <p>查看完整的訊息時間軸</p>
                <span class="album-count" id="album-count-all">載入中...</span>
            </div>
        </div>

        <!-- 媒體相簿選項 -->
        <div class="album-grid">
            <div class="album-card" data-media-type="photo">
                <div class="album-card-icon">📷</div>
                <div class="album-card-title">照片</div>
                <div class="album-card-count" id="album-count-photo">0 張</div>
            </div>

            <div class="album-card" data-media-type="video">
                <div class="album-card-icon">🎬</div>
                <div class="album-card-title">影片</div>
                <div class="album-card-count" id="album-count-video">0 個</div>
            </div>

            <div class="album-card" data-media-type="audio">
                <div class="album-card-icon">🎵</div>
                <div class="album-card-title">音訊</div>
                <div class="album-card-count" id="album-count-audio">0 個</div>
            </div>

            <div class="album-card" data-media-type="document">
                <div class="album-card-icon">📄</div>
                <div class="album-card-title">文件</div>
                <div class="album-card-count" id="album-count-document">0 個</div>
            </div>

            <div class="album-card" data-media-type="voice">
                <div class="album-card-icon">🎤</div>
                <div class="album-card-title">語音</div>
                <div class="album-card-count" id="album-count-voice">0 個</div>
            </div>

            <div class="album-card" data-media-type="animation">
                <div class="album-card-icon">🎞️</div>
                <div class="album-card-title">動畫</div>
                <div class="album-card-count" id="album-count-animation">0 個</div>
            </div>
        </div>
    </div>
</div>
```

#### CSS 樣式 (`module/static/css/message_downloader/layout.css`)

```css
/* 相簿入口頁面 */
.album-selector {
    flex: 1;
    padding: 32px;
    overflow-y: auto;
    background: var(--theme-bg-primary);
}

.album-selector-header {
    margin-bottom: 32px;
}

.back-button {
    background: rgba(255, 255, 255, 0.1);
    border: 0.5px solid rgba(255, 255, 255, 0.2);
    border-radius: 12px;
    padding: 10px 16px;
    color: var(--apple-blue);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    margin-bottom: 16px;
    transition: all 0.2s ease;
}

.back-button:hover {
    background: rgba(255, 255, 255, 0.15);
    transform: translateX(-4px);
}

.album-selector-content {
    display: flex;
    flex-direction: column;
    gap: 24px;
}

/* 全部訊息選項 */
.album-option {
    background: linear-gradient(135deg,
        rgba(255, 255, 255, 0.2) 0%,
        rgba(255, 255, 255, 0.1) 100%);
    backdrop-filter: blur(40px) saturate(180%);
    border: 0.5px solid rgba(255, 255, 255, 0.25);
    border-radius: 20px;
    padding: 24px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 20px;
    transition: all 0.3s ease;
}

.album-option:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
}

.album-icon {
    font-size: 48px;
    width: 80px;
    height: 80px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.15);
    border-radius: 16px;
}

.album-info h4 {
    font-size: 20px;
    font-weight: 600;
    color: var(--apple-label-primary);
    margin-bottom: 4px;
}

.album-info p {
    font-size: 14px;
    color: var(--apple-label-secondary);
    margin-bottom: 8px;
}

.album-count {
    font-size: 16px;
    font-weight: 600;
    color: var(--apple-blue);
}

/* 媒體相簿網格 */
.album-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 16px;
}

.album-card {
    background: linear-gradient(135deg,
        rgba(255, 255, 255, 0.16) 0%,
        rgba(255, 255, 255, 0.08) 100%);
    backdrop-filter: blur(40px) saturate(180%);
    border: 0.5px solid rgba(255, 255, 255, 0.22);
    border-radius: 18px;
    padding: 20px;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    transition: all 0.3s ease;
}

.album-card:hover {
    transform: translateY(-4px) scale(1.02);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
    background: linear-gradient(135deg,
        rgba(255, 255, 255, 0.22) 0%,
        rgba(255, 255, 255, 0.12) 100%);
}

.album-card-icon {
    font-size: 36px;
}

.album-card-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--apple-label-primary);
}

.album-card-count {
    font-size: 13px;
    color: var(--apple-label-secondary);
}
```

---

### 3.2 全部訊息模式 + 頂部篩選器

#### HTML - 添加篩選器工具列 (`module/templates/message_downloader.html`)

在 `compact-toolbar` 的 `toolbar-center` 區域添加篩選按鈕：
```html
<div class="toolbar-center">
    <div class="current-group-indicator" id="current-group-indicator" style="display: none;">
        <span id="current-group-name">選擇群組</span>
    </div>

    <!-- 媒體篩選器 -->
    <div class="media-filter-bar" id="media-filter-bar" style="display: none;">
        <button class="filter-btn active" data-filter="all">
            <span class="filter-icon">📋</span>
            <span class="filter-label">全部</span>
            <span class="filter-count" id="filter-count-all">0</span>
        </button>
        <button class="filter-btn" data-filter="photo">
            <span class="filter-icon">📷</span>
            <span class="filter-label">照片</span>
            <span class="filter-count" id="filter-count-photo">0</span>
        </button>
        <button class="filter-btn" data-filter="video">
            <span class="filter-icon">🎬</span>
            <span class="filter-label">影片</span>
            <span class="filter-count" id="filter-count-video">0</span>
        </button>
        <button class="filter-btn" data-filter="document">
            <span class="filter-icon">📄</span>
            <span class="filter-label">文件</span>
            <span class="filter-count" id="filter-count-document">0</span>
        </button>
    </div>
</div>
```

#### CSS 篩選器樣式 (`module/static/css/message_downloader/controls.css`)

```css
/* 媒體篩選器 */
.media-filter-bar {
    display: flex;
    gap: 8px;
    padding: 8px 12px;
    background: rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(30px);
    border-radius: 16px;
    border: 0.5px solid rgba(255, 255, 255, 0.2);
}

.filter-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 14px;
    background: rgba(255, 255, 255, 0.08);
    border: 0.5px solid rgba(255, 255, 255, 0.15);
    border-radius: 12px;
    color: var(--apple-label-secondary);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    white-space: nowrap;
}

.filter-btn:hover {
    background: rgba(255, 255, 255, 0.15);
    transform: translateY(-1px);
}

.filter-btn.active {
    background: linear-gradient(135deg,
        rgba(0, 122, 255, 0.9) 0%,
        rgba(90, 200, 250, 0.8) 100%);
    border-color: rgba(255, 255, 255, 0.4);
    color: white;
    font-weight: 600;
}

.filter-icon {
    font-size: 16px;
}

.filter-label {
    font-size: 13px;
}

.filter-count {
    font-size: 11px;
    padding: 2px 6px;
    background: rgba(255, 255, 255, 0.2);
    border-radius: 8px;
    min-width: 20px;
    text-align: center;
}

.filter-btn.active .filter-count {
    background: rgba(255, 255, 255, 0.3);
}
```

#### JavaScript 篩選邏輯 (`module/static/js/message_downloader/messages.js`)

```javascript
// 篩選器狀態
let activeMediaFilters = ['all'];
let filteredMessages = [];

// 初始化篩選器
function initMediaFilter() {
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const filterType = this.dataset.filter;
            toggleMediaFilter(filterType);
        });
    });
}

// 切換篩選器
function toggleMediaFilter(filterType) {
    if (filterType === 'all') {
        activeMediaFilters = ['all'];
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector('[data-filter="all"]').classList.add('active');
    } else {
        // 移除 'all'
        activeMediaFilters = activeMediaFilters.filter(f => f !== 'all');
        document.querySelector('[data-filter="all"]').classList.remove('active');

        // 切換選中狀態
        const btn = document.querySelector(`[data-filter="${filterType}"]`);
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
            document.querySelector('[data-filter="all"]').classList.add('active');
        }
    }

    // 應用篩選
    applyMessageFilter();
}

// 應用篩選到訊息列表
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

// 更新篩選器計數
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
```

---

### 3.3 專用相簿模式（網格佈局）

#### HTML 結構 (`module/templates/message_downloader.html`)

```html
<!-- 媒體相簿網格視圖 -->
<div id="media-album-view" class="media-album-view" style="display: none;">
    <div class="album-view-header">
        <button id="back-to-selector" class="back-button">
            <i class="fas fa-chevron-left"></i>
            返回相簿選擇
        </button>
        <h3 id="album-view-title">📷 照片相簿</h3>
        <div class="album-view-actions">
            <button id="album-select-all" class="album-action-btn">
                <i class="fas fa-check-double"></i>
                全選
            </button>
            <button id="album-clear-selection" class="album-action-btn">
                <i class="fas fa-times"></i>
                清除
            </button>
            <button id="album-download-selected" class="album-action-btn primary" disabled>
                <i class="fas fa-download"></i>
                下載選中項目 (<span id="album-selected-count">0</span>)
            </button>
        </div>
    </div>

    <div class="album-grid-container" id="album-grid-container">
        <!-- 網格項目將動態加載 -->
    </div>
</div>
```

#### CSS 網格佈局樣式 (`module/static/css/message_downloader/chat.css`)

```css
/* 媒體相簿網格視圖 */
.media-album-view {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.album-view-header {
    padding: 20px 32px;
    background: linear-gradient(135deg,
        rgba(255, 255, 255, 0.2) 0%,
        rgba(255, 255, 255, 0.1) 100%);
    backdrop-filter: blur(40px);
    border-bottom: 0.5px solid rgba(255, 255, 255, 0.2);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.album-view-title {
    font-size: 20px;
    font-weight: 600;
    color: var(--apple-label-primary);
    margin: 0;
}

.album-view-actions {
    display: flex;
    gap: 12px;
}

.album-action-btn {
    padding: 10px 16px;
    background: rgba(255, 255, 255, 0.1);
    border: 0.5px solid rgba(255, 255, 255, 0.2);
    border-radius: 12px;
    color: var(--apple-label-primary);
    font-size: 14px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    transition: all 0.2s ease;
}

.album-action-btn:hover {
    background: rgba(255, 255, 255, 0.15);
    transform: translateY(-2px);
}

.album-action-btn.primary {
    background: linear-gradient(135deg,
        rgba(0, 122, 255, 0.9) 0%,
        rgba(90, 200, 250, 0.8) 100%);
    color: white;
    font-weight: 600;
}

.album-action-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}

/* 網格容器 */
.album-grid-container {
    flex: 1;
    overflow-y: auto;
    padding: 24px 32px;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 16px;
    align-content: start;
}

/* 網格項目 */
.album-grid-item {
    position: relative;
    aspect-ratio: 1;
    background: linear-gradient(135deg,
        rgba(255, 255, 255, 0.12) 0%,
        rgba(255, 255, 255, 0.06) 100%);
    backdrop-filter: blur(20px);
    border: 0.5px solid rgba(255, 255, 255, 0.2);
    border-radius: 16px;
    overflow: hidden;
    cursor: pointer;
    transition: all 0.3s ease;
}

.album-grid-item:hover {
    transform: translateY(-4px) scale(1.02);
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.3);
}

.album-grid-item.selected {
    border-color: var(--apple-blue);
    box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.3);
}

.album-grid-item img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.album-grid-item-overlay {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    padding: 12px;
    background: linear-gradient(to top,
        rgba(0, 0, 0, 0.7) 0%,
        transparent 100%);
    color: white;
    font-size: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.album-grid-item-checkbox {
    position: absolute;
    top: 12px;
    right: 12px;
    width: 28px;
    height: 28px;
    background: rgba(255, 255, 255, 0.9);
    backdrop-filter: blur(20px);
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0;
    transition: all 0.2s ease;
}

.album-grid-item:hover .album-grid-item-checkbox,
.album-grid-item.selected .album-grid-item-checkbox {
    opacity: 1;
}

.album-grid-item.selected .album-grid-item-checkbox {
    background: var(--apple-blue);
}

.album-grid-item-checkbox input {
    width: 20px;
    height: 20px;
    cursor: pointer;
}
```

#### JavaScript 網格視圖邏輯 (`module/static/js/message_downloader/messages.js`)

```javascript
// 媒體相簿狀態
let currentAlbumType = null;
let albumSelectedMessages = [];

// 顯示媒體相簿
async function showMediaAlbum(chatId, mediaType) {
    currentAlbumType = mediaType;
    albumSelectedMessages = [];

    // 隱藏其他視圖
    document.getElementById('album-selector').style.display = 'none';
    document.getElementById('messages-container').style.display = 'none';

    // 顯示相簿視圖
    const albumView = document.getElementById('media-album-view');
    albumView.style.display = 'flex';

    // 更新標題
    const titles = {
        photo: '📷 照片相簿',
        video: '🎬 影片相簿',
        audio: '🎵 音訊相簿',
        document: '📄 文件相簿',
        voice: '🎤 語音訊息',
        animation: '🎞️ 動畫相簿'
    };
    document.getElementById('album-view-title').textContent = titles[mediaType] || '媒體相簿';

    // 載入媒體
    await loadMediaForAlbum(chatId, mediaType);
}

// 載入相簿媒體
async function loadMediaForAlbum(chatId, mediaType) {
    showLoading(true);

    try {
        const response = await fetch('/api/groups/messages', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chat_id: chatId,
                limit: 200,
                offset_id: 0,
                media_types: [mediaType] // 只載入特定類型
            })
        });

        const data = await response.json();

        if (data.success && data.messages) {
            renderAlbumGrid(data.messages);
        }
    } catch (error) {
        console.error('載入相簿失敗:', error);
        showAlert('載入媒體相簿失敗', 'danger');
    } finally {
        showLoading(false);
    }
}

// 渲染網格
function renderAlbumGrid(messages) {
    const container = document.getElementById('album-grid-container');
    container.innerHTML = '';

    messages.forEach(message => {
        const item = document.createElement('div');
        item.className = 'album-grid-item';
        item.dataset.messageId = message.message_id;

        item.innerHTML = `
            <img src="${message.thumbnail || '/static/img/placeholder.png'}"
                 alt="Message ${message.message_id}"
                 loading="lazy">
            <div class="album-grid-item-overlay">
                <span>#${message.message_id}</span>
                <span>${formatFileSize(message.file_size || 0)}</span>
            </div>
            <div class="album-grid-item-checkbox">
                <input type="checkbox"
                       onchange="toggleAlbumItemSelection(${message.message_id})"
                       onclick="event.stopPropagation()">
            </div>
        `;

        // 點擊放大
        item.addEventListener('click', function(e) {
            if (e.target.type !== 'checkbox') {
                openLightbox(message.message_id);
            }
        });

        container.appendChild(item);

        // 載入縮圖
        if (message.media_type === 'photo' || message.media_type === 'video') {
            loadThumbnailFromMessage(message);
        }
    });
}

// 切換相簿項目選擇
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

// 更新相簿選擇 UI
function updateAlbumSelectionUI() {
    document.getElementById('album-selected-count').textContent = albumSelectedMessages.length;
    document.getElementById('album-download-selected').disabled = albumSelectedMessages.length === 0;
}
```

---

### 3.4 後端 API 擴展

#### 修改 `module/multiuser_auth.py`

添加媒體類型篩選和統計 API：

```python
# 1. 擴展現有的 /api/groups/messages 端點
@app.route('/api/groups/messages', methods=['POST'])
@require_auth
def get_group_messages():
    data = request.json
    chat_id = data.get('chat_id')
    limit = data.get('limit', 20)
    offset_id = data.get('offset_id', 0)
    media_only = data.get('media_only', False)
    media_types = data.get('media_types', None)  # 新增: 媒體類型篩選
    reverse = data.get('reverse', False)  # 新增: 是否從最舊開始

    try:
        client = get_user_client()
        messages = []

        # 獲取訊息（支援反向載入）
        async for message in client.get_chat_history(
            chat_id,
            limit=limit,
            offset_id=offset_id,
            reverse=reverse
        ):
            # 媒體類型篩選
            if media_types and len(media_types) > 0:
                media_type = get_media_type(message)
                if media_type not in media_types:
                    continue

            # 原有的 media_only 邏輯
            if media_only and not message.media:
                continue

            messages.append(format_message(message))

        return jsonify({
            'success': True,
            'messages': messages,
            'has_more': len(messages) >= limit
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# 2. 新增媒體統計 API
@app.route('/api/groups/<int:chat_id>/media_stats', methods=['GET'])
@require_auth
def get_media_stats(chat_id):
    """獲取群組的媒體類型統計"""
    try:
        client = get_user_client()

        # 統計各類型數量（僅掃描最近 1000 條訊息）
        stats = {
            'photo': 0,
            'video': 0,
            'audio': 0,
            'document': 0,
            'voice': 0,
            'animation': 0,
            'total': 0
        }

        async for message in client.get_chat_history(chat_id, limit=1000):
            stats['total'] += 1
            media_type = get_media_type(message)
            if media_type in stats:
                stats[media_type] += 1

        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# 3. 新增完整圖片載入 API（用於 Lightbox）
@app.route('/api/message_full_image/<int:chat_id>/<int:message_id>', methods=['GET'])
@require_auth
def get_message_full_image(chat_id, message_id):
    """獲取訊息的完整圖片（非縮圖）"""
    try:
        client = get_user_client()
        message = await client.get_messages(chat_id, message_id)

        if not message or not message.media:
            return jsonify({'success': False, 'error': 'No media found'}), 404

        # 下載到記憶體
        file_bytes = io.BytesIO()
        await client.download_media(message, file=file_bytes)
        file_bytes.seek(0)

        # 轉換為 base64 Data URL
        import base64
        encoded = base64.b64encode(file_bytes.read()).decode('utf-8')
        mime_type = get_mime_type(message)
        data_url = f"data:{mime_type};base64,{encoded}"

        return jsonify({
            'success': True,
            'image_url': data_url
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def get_media_type(message):
    """判斷訊息的媒體類型"""
    if message.photo:
        return 'photo'
    elif message.video:
        return 'video'
    elif message.audio:
        return 'audio'
    elif message.voice:
        return 'voice'
    elif message.animation:
        return 'animation'
    elif message.document:
        return 'document'
    else:
        return 'text'


def get_mime_type(message):
    """獲取媒體的 MIME 類型"""
    if message.photo:
        return 'image/jpeg'
    elif message.video:
        return 'video/mp4'
    elif message.document:
        mime = message.document.mime_type
        return mime if mime else 'application/octet-stream'
    return 'application/octet-stream'
```

---

## 實施順序

### Phase 1: 圖片縮圖放大（獨立功能）
1. ✅ 修改 CSS 增大縮圖尺寸
2. ✅ 添加 Lightbox HTML 結構
3. ✅ 實作 Lightbox CSS 樣式
4. ✅ 實作 JavaScript 功能（開啟、導航、鍵盤控制）
5. ✅ 添加後端完整圖片 API

**預估時間**: 2-3 小時
**測試要點**:
- 縮圖是否正確放大
- Lightbox 顯示是否正確
- 左右鍵導航是否流暢
- ESC 鍵關閉是否正常

---

### Phase 2: 媒體類型篩選（核心功能）
1. ✅ 實作相簿入口頁面（HTML + CSS）
2. ✅ 添加全部訊息模式的頂部篩選器
3. ✅ 實作前端篩選邏輯
4. ✅ 實作專用相簿網格視圖
5. ✅ 添加後端媒體統計 API
6. ✅ 擴展訊息載入 API 支援類型篩選
7. ✅ 整合導航邏輯（相簿入口 ↔ 兩種模式）

**預估時間**: 4-6 小時
**測試要點**:
- 相簿入口顯示正確統計
- 篩選器即時過濾是否正確
- 網格視圖載入和顯示
- 後端 API 正確返回篩選結果

---

### Phase 3: 訊息快速跳轉（便利功能）
1. ✅ 添加「跳到最舊」按鈕
2. ✅ 實作跳轉載入邏輯
3. ✅ 添加載入進度指示
4. ✅ 測試與篩選器的兼容性

**預估時間**: 1-2 小時
**測試要點**:
- 跳轉後是否正確載入最舊訊息
- 進度指示是否正確更新
- 與篩選器結合使用是否正常

---

## 測試清單

### 功能測試
- [ ] Lightbox 圖片放大預覽
  - [ ] 點擊縮圖打開 Lightbox
  - [ ] 左右鍵切換圖片
  - [ ] ESC 關閉 Lightbox
  - [ ] 圖片計數顯示正確

- [ ] 相簿入口頁面
  - [ ] 顯示正確的媒體統計數量
  - [ ] 點擊進入對應模式
  - [ ] 返回按鈕正常工作

- [ ] 全部訊息 + 篩選器
  - [ ] 篩選器即時過濾訊息
  - [ ] 多選篩選器正常工作
  - [ ] 計數顯示正確
  - [ ] 清除篩選恢復全部訊息

- [ ] 專用相簿網格視圖
  - [ ] 網格正確載入媒體
  - [ ] 點擊放大預覽
  - [ ] 批量選擇功能
  - [ ] 下載選中項目

- [ ] 快速跳轉功能
  - [ ] 跳到最舊訊息正確載入
  - [ ] 進度指示正確顯示
  - [ ] 與篩選器兼容

### 效能測試
- [ ] 載入 200+ 訊息時的渲染速度
- [ ] 網格視圖滾動流暢度
- [ ] 縮圖載入效能
- [ ] Lightbox 切換速度

### 兼容性測試
- [ ] 主題切換（明亮/黑暗模式）
- [ ] 響應式設計（手機/平板）
- [ ] 不同瀏覽器測試

---

## 風險與注意事項

### 潛在問題
1. **記憶體消耗**: 大量圖片可能導致瀏覽器記憶體不足
   - **解決方案**: 實作虛擬滾動（Lazy Loading）

2. **API 效能**: 頻繁請求媒體統計可能造成伸服器負載
   - **解決方案**: 添加快取機制，統計結果快取 5 分鐘

3. **後端同步 API**: Pyrogram 是異步框架，需要正確處理
   - **解決方案**: 使用 `asyncio.run()` 或 Flask-AsyncIO

4. **縮圖品質**: Telegram API 返回的縮圖可能品質不佳
   - **解決方案**: 提供「載入高清縮圖」選項

### 向後兼容
- ✅ 保持現有功能完全不變
- ✅ 新功能作為可選增強，不影響原有流程
- ✅ 如果 API 失敗，降級到原有行為

---

## 未來擴展建議

### 短期（1-2 週）
- 添加搜尋功能（依檔名、訊息內容）
- 實作日期範圍篩選器
- 添加「最近下載」歷史記錄

### 中期（1 個月）
- 實作虛擬滾動優化大量訊息渲染
- 添加訊息書籤功能
- 支援影片預覽播放

### 長期（2-3 個月）
- AI 智能標籤（自動識別圖片內容）
- 相簿分享功能
- 支援更多媒體格式（Sticker、GIF）

---

## 附錄

### 檔案清單
修改檔案：
- `module/templates/message_downloader.html` - 主要 HTML 結構
- `module/static/css/message_downloader/chat.css` - 媒體和相簿樣式
- `module/static/css/message_downloader/layout.css` - 佈局樣式
- `module/static/css/message_downloader/controls.css` - 控制元件樣式
- `module/static/js/message_downloader/core.js` - 核心變數和常數
- `module/static/js/message_downloader/messages.js` - 訊息載入和渲染邏輯
- `module/static/js/message_downloader/ui.js` - UI 交互邏輯
- `module/multiuser_auth.py` - 後端 API 擴展

### 關鍵常數
```javascript
// core.js
const MESSAGES_PER_PAGE = 20;           // 每頁訊息數
const SCROLL_THRESHOLD = 50;            // 滾動觸發閾值
const ALBUM_GRID_ITEMS_PER_PAGE = 200;  // 相簿網格每頁項目數
```

### API 端點總覽
- `POST /api/groups/messages` - 載入訊息（支援類型篩選）
- `GET /api/groups/<chat_id>/media_stats` - 獲取媒體統計
- `GET /api/message_full_image/<chat_id>/<message_id>` - 獲取完整圖片
- `GET /api/message_downloader_thumbnail/<chat_id>/<message_id>` - 獲取縮圖（現有）

---

**計劃結束** - 準備開始實施