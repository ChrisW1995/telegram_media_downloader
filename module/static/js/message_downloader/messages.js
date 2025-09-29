/**
 * Message Downloader - Messages Module
 * 訊息載入、渲染和滾動處理
 *
 * 處理訊息顯示、媒體處理、分頁載入和滾動檢測邏輯
 */

// ==================== 滾動檢測和自動載入 ====================

/**
 * 設置滾動事件監聽器
 * 為訊息容器設置滾動檢測，實現自動載入更多訊息
 */
function setupScrollListener() {
    const messagesContainer = document.getElementById('messages-container');
    console.log('🔧 設置滾動監聽器', {
        element: messagesContainer,
        hasAttribute: messagesContainer ? messagesContainer.hasAttribute('data-scroll-listener') : false,
        style: messagesContainer ? messagesContainer.style.display : 'null'
    });

    if (!messagesContainer) {
        console.error('❌ messages-container 元素不存在');
        return;
    }

    if (!messagesContainer.hasAttribute('data-scroll-listener')) {
        console.log('🔧 設置新的簡化滾動檢測');

        // 容器滾動事件監聽器
        let scrollTimer = null;
        messagesContainer.addEventListener('scroll', function(e) {
            const currentScrollTop = messagesContainer.scrollTop;

            console.log('📜 容器滾動事件觸發', {
                scrollTop: currentScrollTop,
                scrollHeight: messagesContainer.scrollHeight,
                clientHeight: messagesContainer.clientHeight
            });

            // 檢測是否是用戶主動滾動（滾動位置發生變化）
            if (Math.abs(currentScrollTop - lastScrollTop) > 5) {
                userScrolled = true;
                console.log('👆 檢測到用戶滾動', {
                    from: lastScrollTop,
                    to: currentScrollTop,
                    userScrolled: true
                });
            }

            lastScrollTop = currentScrollTop;

            // 防抖：延遲執行檢查
            if (scrollTimer) {
                clearTimeout(scrollTimer);
            }
            scrollTimer = setTimeout(() => {
                checkShouldLoadMore();
            }, 100); // 100ms 防抖延遲
        });

        messagesContainer.setAttribute('data-scroll-listener', 'true');
        console.log('✅ 滾動監聽器設置完成');
    } else {
        console.log('⚠️ 滾動監聽器已經存在');
    }
}

/**
 * 檢查是否應該載入更多訊息
 * 基於用戶滾動位置和最後一個訊息氣泡的位置判斷
 */
function checkShouldLoadMore() {
    // 基本條件檢查
    if (isLoading || !hasMoreMessages) {
        console.log('🚫 跳過檢查: isLoading=' + isLoading + ', hasMoreMessages=' + hasMoreMessages);
        return;
    }

    // 如果被設置為阻止自動載入，跳過
    if (preventAutoLoad) {
        console.log('🚫 阻止自動載入標記已設置，跳過檢查');
        return;
    }

    const container = document.getElementById('messages-container');
    if (!container || container.style.display === 'none') {
        console.log('🚫 跳過檢查: 容器不存在或隱藏');
        return;
    }

    // 找到最後一個 chat-bubble
    const messagesList = document.getElementById('messages-list');
    if (!messagesList) {
        console.log('🚫 跳過檢查: messages-list 不存在');
        return;
    }

    const chatBubbles = messagesList.querySelectorAll('.chat-bubble');

    // 如果沒有訊息，允許初始載入
    if (chatBubbles.length === 0) {
        console.log('✅ 沒有訊息，允許初始載入');
        loadMessages(false);
        return;
    }

    // 如果用戶沒有主動滾動，不觸發載入
    if (!userScrolled) {
        console.log('🚫 用戶尚未滾動，跳過自動載入');
        return;
    }

    // 獲取容器的滾動信息
    const scrollTop = container.scrollTop;
    const scrollHeight = container.scrollHeight;
    const clientHeight = container.clientHeight;
    const scrollBottom = scrollHeight - scrollTop - clientHeight;

    // 計算是否接近底部
    const isNearBottom = scrollBottom <= SCROLL_THRESHOLD;

    console.log('🔍 滾動位置檢查:', {
        totalBubbles: chatBubbles.length,
        userScrolled: userScrolled,
        scrollTop: Math.round(scrollTop),
        scrollHeight: Math.round(scrollHeight),
        clientHeight: Math.round(clientHeight),
        scrollBottom: Math.round(scrollBottom),
        threshold: SCROLL_THRESHOLD,
        isNearBottom: isNearBottom,
        preventAutoLoad: preventAutoLoad,
        shouldLoad: isNearBottom && userScrolled && hasMoreMessages && !isLoading
    });

    // 只有當用戶滾動且接近底部時才觸發加載
    if (isNearBottom && userScrolled) {
        console.log('✅ 用戶滾動到底部附近，觸發載入更多訊息');
        // 重置用戶滾動標記，防止重複觸發
        userScrolled = false;
        // 設置阻止自動載入標記
        preventAutoLoad = true;
        loadMessages(false);
    }
}

// ==================== 訊息載入和渲染 ====================

/**
 * 載入訊息
 * @param {boolean} resetOffset - 是否重置分頁偏移（true: 載入新群組的訊息，false: 載入更多訊息）
 */
async function loadMessages(resetOffset = true) {
    if (!currentChatId || isLoading) return;

    if (resetOffset) {
        lastMessageId = 0;
        previousLastMessageId = 0;
        noProgressCount = 0;
        hasMoreMessages = true;
        allMessages = [];
        const container = document.getElementById('messages-list');
        if (container) container.innerHTML = '';
        hideMessages();
    }

    if (!hasMoreMessages) return;

    isLoading = true;
    showLoading(true);

    try {
        const response = await fetch('/api/groups/messages', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                chat_id: currentChatId,
                limit: MESSAGES_PER_PAGE,
                offset_id: lastMessageId,
                media_only: false
            })
        });
        const data = await response.json();

        if (data.success && data.messages) {
            const newMessages = data.messages;

            console.log('📨 載入訊息結果:', {
                newMessagesCount: newMessages.length,
                messagesPerPage: MESSAGES_PER_PAGE,
                resetOffset,
                hasMoreMessagesBefore: hasMoreMessages
            });

            // 檢查是否還有更多訊息的邏輯
            if (newMessages.length === 0) {
                hasMoreMessages = false;
                console.log('❌ 沒有更多訊息了 (返回 0 條訊息)');
            } else if (data.has_more !== undefined) {
                // 如果後端提供了 has_more 字段，使用它
                hasMoreMessages = data.has_more;
                console.log(hasMoreMessages ? '✅ 後端確認還有更多訊息' : '❌ 後端確認沒有更多訊息');
            } else if (newMessages.length < MESSAGES_PER_PAGE) {
                // 如果返回的數量少於請求數量，可能是到達了最舊的訊息
                console.log('⚠️ 返回的訊息少於請求數量，但保持 hasMoreMessages = true 以便繼續檢查');
            } else {
                // 返回了完整的一頁，很可能還有更多
                hasMoreMessages = true;
                console.log('✅ 返回完整頁面，可能還有更多訊息');
            }

            if (newMessages.length > 0) {
                allMessages = [...allMessages, ...newMessages];
                renderMessages(newMessages, !resetOffset); // append mode

                // Update lastMessageId for next pagination
                const newLastMessageId = Math.min(...newMessages.map(m => m.message_id));

                // 檢查是否有進展
                if (previousLastMessageId > 0 && newLastMessageId >= previousLastMessageId) {
                    noProgressCount++;
                    console.log(`⚠️ 沒有進展：newLastMessageId (${newLastMessageId}) >= previousLastMessageId (${previousLastMessageId}), 計數: ${noProgressCount}/${MAX_NO_PROGRESS_ATTEMPTS}`);

                    if (noProgressCount >= MAX_NO_PROGRESS_ATTEMPTS) {
                        hasMoreMessages = false;
                        console.log('❌ 達到最大無進展嘗試次數，停止載入更多訊息');
                    }
                } else {
                    noProgressCount = 0; // 重置計數
                    console.log('✅ 有進展，重置無進展計數');
                }

                previousLastMessageId = lastMessageId;
                lastMessageId = newLastMessageId;
                console.log('📍 更新 lastMessageId:', lastMessageId, '(previous:', previousLastMessageId, ')');

                if (resetOffset) {
                    showMessages();

                    // 處理初始狀態：檢查是否需要自動加載更多
                    setTimeout(() => {
                        if (hasMoreMessages && !isLoading) {
                            const messagesList = document.getElementById('messages-list');
                            const container = document.getElementById('messages-container');

                            if (messagesList && container) {
                                const chatBubbles = messagesList.querySelectorAll('.chat-bubble');

                                if (chatBubbles.length > 0) {
                                    // 檢查最後一個氣泡是否在可視區域內
                                    const lastBubble = chatBubbles[chatBubbles.length - 1];
                                    const containerRect = container.getBoundingClientRect();
                                    const bubbleRect = lastBubble.getBoundingClientRect();

                                    const bubbleBottom = bubbleRect.bottom;
                                    const containerBottom = containerRect.bottom;

                                    // 如果最後一個氣泡完全在可視區域內，自動載入更多
                                    if (bubbleBottom < containerBottom) {
                                        console.log('🔄 初始內容可視區域有空間，自動載入更多訊息');
                                        loadMessages(false); // 繼續載入，不重置
                                    }
                                }
                            }
                        }
                    }, 100); // 等待 DOM 更新
                }
            } else if (resetOffset) {
                hasMoreMessages = false;
                const container = document.getElementById('messages-list');
                if (container) {
                    container.innerHTML = '<div class="text-center text-muted p-4">沒有找到訊息</div>';
                }
                showMessages();
            }
        } else {
            showAlert('載入訊息失敗: ' + (data.error || data.message || '未知錯誤'), 'danger');
        }
    } catch (error) {
        console.error('載入訊息錯誤:', error);
        showAlert('載入訊息時發生錯誤', 'danger');
    } finally {
        isLoading = false;
        showLoading(false);

        // 載入完成後，延遲重置阻止自動載入標記，讓用戶可以繼續滾動
        setTimeout(() => {
            preventAutoLoad = false;
            console.log('🔓 重置阻止自動載入標記，可以再次檢測滾動');
        }, 1000); // 1秒後允許再次自動載入
    }
}

/**
 * 渲染訊息列表
 * @param {Array} messages - 訊息列表
 * @param {boolean} appendMode - 是否為追加模式（false: 清空重新渲染，true: 追加到現有列表）
 */
function renderMessages(messages, appendMode = false) {
    const container = document.getElementById('messages-list');
    if (!container) return;

    if (!appendMode) {
        container.innerHTML = '';
    }

    console.log('🎨 渲染訊息狀態:', {
        messagesCount: messages.length,
        appendMode,
        hasMoreMessages,
        isLoading,
        lastMessageId
    });

    if (messages.length > 0) {
        console.log('📝 第一條訊息範例:', {
            id: messages[0].message_id,
            date: messages[0].date,
            mediaType: messages[0].media_type
        });
    }

    if (!messages || messages.length === 0) {
        if (!appendMode) {
            container.innerHTML = '<div class="text-center text-muted p-4">沒有找到訊息</div>';
        }
        return;
    }

    // 渲染每條訊息
    messages.forEach((message, index) => {
        const messageElement = createMessageElement(message);
        if (appendMode) {
            // Add delay for smooth animation
            messageElement.style.animationDelay = `${index * 0.05}s`;
        }
        container.appendChild(messageElement);

        // 元素添加到DOM後，加載縮圖
        if (messageElement.dataset.needsThumbnail === 'true') {
            const messageData = JSON.parse(messageElement.dataset.messageData);
            console.log(`Scheduling thumbnail load for message ${messageData.message_id} after DOM addition`);
            // 使用 setTimeout 確保DOM完全更新
            setTimeout(() => {
                console.log(`DOM update timeout reached, attempting to load thumbnail for message ${messageData.message_id}`);
                const thumbContainer = document.getElementById(`thumb-${messageData.message_id}`);
                console.log(`Thumbnail container check:`, thumbContainer);
                if (thumbContainer) {
                    loadThumbnailFromMessage(messageData);
                } else {
                    console.warn(`Still no thumbnail container found for message ${messageData.message_id} even after timeout`);
                }
            }, 50); // 增加延遲到50ms
        }
    });

    // 如果沒有更多訊息，添加結束提示
    if (!hasMoreMessages && !container.querySelector('.end-message')) {
        const endMessage = document.createElement('div');
        endMessage.className = 'text-center p-3 end-message';
        endMessage.innerHTML = `
            <div class="text-muted" style="font-size: 12px; color: rgba(255, 255, 255, 0.5) !important;">
                <i class="fas fa-check"></i>
                已載入所有訊息
            </div>
        `;
        container.appendChild(endMessage);
    }
}

/**
 * 創建訊息元素
 * @param {Object} message - 訊息物件
 * @returns {HTMLElement} 訊息DOM元素
 */
function createMessageElement(message) {
    const div = document.createElement('div');
    div.className = 'chat-bubble';
    div.dataset.messageId = message.message_id;

    // Get media type and file info
    const mediaInfo = getMediaInfo(message);
    const mediaIcon = getMediaIcon(mediaInfo.type);

    div.innerHTML = `
        <div class="message-header">
            <div class="message-checkbox">
                <input type="checkbox" class="message-select"
                       onchange="updateSelection(this, ${message.message_id})"
                       onclick="event.stopPropagation()">
            </div>
            <div class="message-info">
                <span class="message-id">#${message.message_id}</span>
                <span class="message-date">${formatDate(message.date)}</span>
                <span class="media-badge ${mediaInfo.type}">
                    ${mediaIcon} ${mediaInfo.type.toUpperCase()}
                </span>
            </div>
        </div>

        <div class="message-content">
            ${message.caption ? `<div class="message-text">${escapeHtml(message.caption)}</div>` : ''}

            <div class="media-placeholder ${mediaInfo.type} ${mediaInfo.type === 'photo' || mediaInfo.type === 'video' ? 'with-thumbnail' : ''}" id="media-${message.message_id}">
                ${mediaInfo.type === 'photo' || mediaInfo.type === 'video' ? `
                    <div class="media-thumbnail" id="thumb-${message.message_id}">
                        <div class="loading-placeholder">
                            <i class="fas fa-image"></i>
                        </div>
                    </div>
                ` : `
                    <div class="media-icon">
                        ${mediaIcon}
                    </div>
                `}
                <div class="media-content">
                    <div class="media-info">
                        <div class="media-filename">${mediaInfo.filename || 'Unknown file'}</div>
                        <div class="media-size">${mediaInfo.size || 'Unknown size'}</div>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Add click event for row selection
    div.onclick = function(event) {
        if (event.target.type !== 'checkbox') {
            const checkbox = div.querySelector('.message-select');
            checkbox.checked = !checkbox.checked;
            updateSelection(checkbox, message.message_id);
        }
    };

    // 如果是照片或影片，標記需要加載縮圖（延遲到DOM添加後執行）
    if (mediaInfo.type === 'photo' || mediaInfo.type === 'video') {
        div.dataset.needsThumbnail = 'true';
        div.dataset.messageData = JSON.stringify(message);
    }

    return div;
}

// ==================== 縮圖載入功能 ====================

/**
 * 從消息數據載入縮圖
 * @param {Object} message - 訊息物件
 */
async function loadThumbnailFromMessage(message) {
    console.log(`Loading thumbnail for message ${message.message_id}`, message);
    console.log(`Message thumbnail_url:`, message.thumbnail_url);
    console.log(`Message thumbnail:`, message.thumbnail);

    try {
        const thumbnailContainer = document.getElementById(`thumb-${message.message_id}`);
        if (!thumbnailContainer) {
            console.log(`No thumbnail container found for message ${message.message_id}`);
            return;
        }

        // 檢查消息是否有縮圖數據
        if (!message.thumbnail) {
            console.log(`No thumbnail data found for message ${message.message_id}`);
            // 顯示默認圖標
            const mediaType = message.media_type === 'photo' ? 'image' :
                             message.media_type === 'video' ? 'video' : 'file';
            thumbnailContainer.innerHTML = `
                <div class="loading-placeholder">
                    <i class="fas fa-${mediaType}"></i>
                </div>
            `;
            return;
        }

        // 顯示加載指示器
        thumbnailContainer.innerHTML = `
            <div class="loading-placeholder">
                <i class="fas fa-spinner fa-spin"></i>
            </div>
        `;

        // 使用 Message Downloader 專用的縮圖API
        if (message.media_type === 'photo' || message.media_type === 'video') {
            console.log(`Loading thumbnail for ${message.media_type} message ${message.message_id}`);
            console.log(`Thumbnail API URL: /api/message_downloader_thumbnail/${currentChatId}/${message.message_id}`);

            try {
                const response = await fetch(`/api/message_downloader_thumbnail/${currentChatId}/${message.message_id}`);
                console.log(`Thumbnail API response status: ${response.status}`);

                if (response.ok) {
                    const data = await response.json();
                    console.log('Thumbnail API response data:', data);

                    if (data.success && data.message.thumbnail) {
                        console.log(`Thumbnail loaded successfully for message ${message.message_id}`);
                        thumbnailContainer.innerHTML = `<img src="${data.message.thumbnail}" alt="Thumbnail" />`;
                    } else {
                        throw new Error(data.error || 'API returned no thumbnail data');
                    }
                } else {
                    // 嘗試讀取錯誤響應
                    const errorText = await response.text();
                    console.error(`API error response: ${errorText}`);
                    throw new Error(`API returned ${response.status}: ${errorText}`);
                }
            } catch (error) {
                console.error(`Message Downloader thumbnail API failed for message ${message.message_id}:`, error);
                // 顯示默認圖標
                const mediaType = message.media_type === 'photo' ? 'image' :
                                 message.media_type === 'video' ? 'video' : 'file';
                thumbnailContainer.innerHTML = `
                    <div class="loading-placeholder">
                        <i class="fas fa-${mediaType}"></i>
                    </div>
                `;
            }
        } else {
            console.log(`No thumbnail needed for media type: ${message.media_type}`);
            // 顯示默認圖標
            const mediaType = message.media_type === 'photo' ? 'image' :
                             message.media_type === 'video' ? 'video' : 'file';
            thumbnailContainer.innerHTML = `
                <div class="loading-placeholder">
                    <i class="fas fa-${mediaType}"></i>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading thumbnail:', error);
        // 加載錯誤時顯示默認圖標
        const thumbnailContainer = document.getElementById(`thumb-${message.message_id}`);
        if (thumbnailContainer) {
            thumbnailContainer.innerHTML = `
                <div class="loading-placeholder">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
            `;
        }
    }
}

/**
 * 原有的縮圖載入函數（保持兼容性）
 * @param {number} messageId - 訊息ID
 * @param {number} chatId - 聊天ID
 */
async function loadThumbnail(messageId, chatId) {
    console.log(`Loading thumbnail for message ${messageId} in chat ${chatId}`);
    try {
        const mediaElement = document.getElementById(`media-${messageId}`);
        if (!mediaElement) {
            console.log(`No media element found for message ${messageId}`);
            return;
        }

        const thumbnailContainer = mediaElement.querySelector('.media-thumbnail');
        if (!thumbnailContainer) {
            console.log(`No thumbnail container found for message ${messageId}`);
            return;
        }

        // 顯示加載指示器
        thumbnailContainer.innerHTML = `
            <div class="loading-placeholder">
                <i class="fas fa-spinner fa-spin"></i>
            </div>
        `;

        // 請求縮圖
        console.log(`Making API request to: /api/thumbnail/${chatId}/${messageId}`);
        const response = await fetch(`/api/thumbnail/${chatId}/${messageId}`);
        console.log(`API response status: ${response.status}`);
        const data = await response.json();
        console.log(`API response data:`, data);

        if (data.success && data.thumbnail) {
            // 顯示縮圖
            thumbnailContainer.innerHTML = `<img src="${data.thumbnail}" alt="Thumbnail" />`;
        } else {
            // 縮圖加載失敗，顯示默認圖標
            const mediaType = mediaElement.classList.contains('photo') ? 'image' :
                             mediaElement.classList.contains('video') ? 'video' : 'file';
            thumbnailContainer.innerHTML = `
                <div class="loading-placeholder">
                    <i class="fas fa-${mediaType}"></i>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading thumbnail:', error);
        // 加載錯誤時顯示默認圖標
        const mediaElement = document.getElementById(`media-${messageId}`);
        const thumbnailContainer = mediaElement?.querySelector('.media-thumbnail');
        if (thumbnailContainer) {
            thumbnailContainer.innerHTML = `
                <div class="loading-placeholder">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
            `;
        }
    }
}

// ==================== 界面狀態管理 ====================

/**
 * 顯示訊息區域
 */
function showMessages() {
    const groupSelector = document.getElementById('group-selector');
    const messagesContent = document.getElementById('messages-content');
    const chatControls = document.getElementById('chat-controls');

    if (groupSelector) groupSelector.style.display = 'none';
    if (messagesContent) messagesContent.style.display = 'flex';
    if (chatControls) chatControls.style.display = 'block';

    // 設置滾動事件監聽器
    setupScrollListener();
}

/**
 * 隱藏訊息區域
 */
function hideMessages() {
    const messagesContent = document.getElementById('messages-content');
    const groupSelector = document.getElementById('group-selector');
    const chatControls = document.getElementById('chat-controls');

    if (messagesContent) messagesContent.style.display = 'none';
    if (groupSelector) groupSelector.style.display = 'flex';
    if (chatControls) chatControls.style.display = 'none';

    clearSelection();

    // Reset lazy loading state
    lastMessageId = 0;
    hasMoreMessages = true;
    allMessages = [];

    // Reset group indicator
    const indicator = document.getElementById('current-group-indicator');
    if (indicator) {
        indicator.style.display = 'none';
    }

    // Remove active states
    document.querySelectorAll('.group-item').forEach(item => {
        item.classList.remove('active');
    });
}