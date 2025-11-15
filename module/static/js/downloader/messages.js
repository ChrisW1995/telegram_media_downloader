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

                // 套用篩選器（如果有活躍的篩選）
                if (typeof applyMessageFilter === 'function' && typeof activeMediaFilters !== 'undefined' && !activeMediaFilters.includes('all')) {
                    // 有篩選器活躍時，使用篩選函數重新渲染所有訊息
                    applyMessageFilter();
                } else {
                    // 沒有篩選器時，正常渲染新訊息
                    renderMessages(newMessages, !resetOffset); // append mode
                }

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
            mediaType: messages[0].media_type,
            mediaGroupId: messages[0].media_group_id
        });
    }

    if (!messages || messages.length === 0) {
        if (!appendMode) {
            container.innerHTML = '<div class="text-center text-muted p-4">沒有找到訊息</div>';
        }
        return;
    }

    // 對訊息進行分組處理
    const groupedMessages = groupMessagesByMediaGroup(messages);

    // 渲染每個訊息或訊息組
    groupedMessages.forEach((item, index) => {
        let messageElement;

        if (item.isGroup) {
            // 渲染媒體組
            messageElement = createMediaGroupElement(item.messages);
        } else {
            // 渲染單個訊息
            messageElement = createMessageElement(item.message);

            // 元素添加到DOM後，加載縮圖
            if (messageElement.dataset.needsThumbnail === 'true') {
                const messageData = JSON.parse(messageElement.dataset.messageData);
                setTimeout(() => {
                    const thumbContainer = document.getElementById(`thumb-${messageData.message_id}`);
                    if (thumbContainer) {
                        loadThumbnailFromMessage(messageData);
                    }
                }, 50);
            }
        }

        if (appendMode) {
            messageElement.style.animationDelay = `${index * 0.05}s`;
        }
        container.appendChild(messageElement);
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
 * 將訊息按媒體組分組
 * @param {Array} messages - 訊息列表
 * @returns {Array} 分組後的訊息結構
 */
function groupMessagesByMediaGroup(messages) {
    const grouped = [];
    const mediaGroups = new Map();

    messages.forEach(message => {
        if (message.media_group_id && (message.media_type === 'photo' || message.media_type === 'video')) {
            // 有 media_group_id 的圖片/影片訊息
            if (!mediaGroups.has(message.media_group_id)) {
                mediaGroups.set(message.media_group_id, []);
            }
            mediaGroups.get(message.media_group_id).push(message);
        } else {
            // 沒有 media_group_id 或非圖片/影片的訊息
            grouped.push({ isGroup: false, message });
        }
    });

    // 將媒體組插入到正確的位置
    const result = [];
    const processedGroups = new Set();

    messages.forEach(message => {
        if (message.media_group_id && (message.media_type === 'photo' || message.media_type === 'video')) {
            if (!processedGroups.has(message.media_group_id)) {
                const groupMessages = mediaGroups.get(message.media_group_id);
                result.push({ isGroup: true, messages: groupMessages });
                processedGroups.add(message.media_group_id);
            }
        } else {
            result.push({ isGroup: false, message });
        }
    });

    return result;
}

/**
 * 創建媒體組元素
 * @param {Array} messages - 媒體組中的訊息列表
 * @returns {HTMLElement} 媒體組DOM元素
 */
function createMediaGroupElement(messages) {
    const div = document.createElement('div');
    div.className = 'chat-bubble media-group-bubble';

    // 使用第一個訊息的資訊作為代表
    const firstMessage = messages[0];
    const mediaGroupId = firstMessage.media_group_id;

    // 決定網格佈局類型 - 根據圖片比例智能調整（仿 Telegram）
    const count = messages.length;
    let gridClass = 'grid-1';

    // 檢測圖片方向和比例
    const analyzeOrientation = (msg) => {
        if (!msg.width || !msg.height) return null;
        const ratio = msg.height / msg.width;
        if (ratio > 1.2) return 'portrait';  // 豎圖 (如 9:16)
        if (ratio < 0.8) return 'landscape'; // 橫圖 (如 16:9)
        return 'square';  // 方圖
    };

    // 針對 2 張圖片的智能排列（仿 Telegram）
    if (count === 2) {
        const orientations = messages.map(analyzeOrientation);

        // 如果兩張都是豎圖 (height > width)，使用左右排列
        if (orientations.every(o => o === 'portrait')) {
            gridClass = 'grid-2';
        }
        // 如果兩張都是橫圖 (width > height)，使用上下排列
        else if (orientations.every(o => o === 'landscape')) {
            gridClass = 'grid-2-vertical';
        }
        // 混合比例，使用左右排列
        else {
            gridClass = 'grid-2';
        }
    }
    else if (count === 1) gridClass = 'grid-1';
    else if (count === 3) gridClass = 'grid-3';
    else if (count === 4) gridClass = 'grid-4';
    else if (count === 5) gridClass = 'grid-5';
    else if (count === 6) gridClass = 'grid-6';
    else if (count === 7) gridClass = 'grid-7';
    else if (count === 8) gridClass = 'grid-8';
    else if (count === 9) gridClass = 'grid-9';
    else if (count >= 10) gridClass = 'grid-many';

    // Telegram 最多支援 10 張圖片的 album
    const maxDisplay = 10;
    const displayMessages = messages.slice(0, maxDisplay);
    const remainingCount = Math.max(0, count - maxDisplay);

    div.innerHTML = `
        <div class="message-header">
            <div class="message-checkbox">
                <input type="checkbox" class="media-group-select"
                       onchange="updateMediaGroupSelection(this, '${mediaGroupId}')"
                       onclick="event.stopPropagation()">
            </div>
            <div class="message-info">
                <span class="message-id">#${firstMessage.message_id}</span>
                <span class="message-date">${formatDate(firstMessage.date)}</span>
                <span class="media-badge album" style="background: rgba(147, 51, 234, 0.9); color: white;">
                    <i class="fas fa-images"></i> ALBUM
                </span>
                <span class="media-group-count">${count} ${count === 1 ? 'item' : 'items'}</span>
            </div>
        </div>

        <div class="message-content">
            ${(() => {
                // 收集所有有 caption 的訊息
                const captionMessages = messages.filter(msg => msg.caption);
                if (captionMessages.length === 0) return '';

                // 如果只有一個 caption，直接顯示
                if (captionMessages.length === 1) {
                    return `<div class="message-text">${escapeHtml(captionMessages[0].caption)}</div>`;
                }

                // 如果多個圖片有不同的 caption，顯示第一個並標註還有其他
                const firstCaption = captionMessages[0].caption;
                const allSame = captionMessages.every(msg => msg.caption === firstCaption);

                if (allSame) {
                    return `<div class="message-text">${escapeHtml(firstCaption)}</div>`;
                } else {
                    return `<div class="message-text">${escapeHtml(firstCaption)} <span style="opacity: 0.6; font-size: 0.9em;">(+${captionMessages.length - 1} more captions)</span></div>`;
                }
            })()}

            <div class="media-group-grid ${gridClass}">
                ${displayMessages.map((msg, idx) => {
                    const mediaIcon = msg.media_type === 'video' ? '<i class="fas fa-video"></i>' : '<i class="fas fa-image"></i>';
                    return `
                    <div class="media-group-item"
                         data-message-id="${msg.message_id}"
                         data-media-group-id="${mediaGroupId}">
                        <div class="media-group-item-checkbox">
                            <input type="checkbox" class="media-item-select"
                                   data-message-id="${msg.message_id}"
                                   data-media-group-id="${mediaGroupId}"
                                   onchange="updateMediaItemSelection(this, ${msg.message_id}, '${mediaGroupId}')"
                                   onclick="event.stopPropagation()">
                        </div>
                        <div class="media-group-item-type ${msg.media_type}">
                            ${mediaIcon} ${msg.media_type.toUpperCase()}
                        </div>
                        <div class="loading-placeholder" id="thumb-${msg.message_id}">
                            <i class="fas fa-image"></i>
                        </div>
                        ${idx === maxDisplay - 1 && remainingCount > 0 ? `
                            <div class="media-group-more">+${remainingCount}</div>
                        ` : ''}
                    </div>
                `;
                }).join('')}
            </div>
        </div>
    `;

    // 標記需要載入縮圖
    div.dataset.needsGroupThumbnails = 'true';
    div.dataset.mediaGroupId = mediaGroupId;
    div.dataset.groupMessages = JSON.stringify(messages);

    // 載入所有縮圖並添加點擊事件
    setTimeout(() => {
        displayMessages.forEach(msg => {
            loadThumbnailFromMessage(msg);

            // 為每個媒體項目添加點擊事件（打開 Lightbox）
            const mediaItem = div.querySelector(`.media-group-item[data-message-id="${msg.message_id}"]`);
            if (mediaItem) {
                // 為整個媒體項目添加點擊事件
                mediaItem.style.cursor = 'pointer';

                mediaItem.addEventListener('click', function(e) {
                    // 如果點擊的是選擇框或其容器，不打開 Lightbox
                    if (e.target.type === 'checkbox' ||
                        e.target.closest('.media-group-item-checkbox') ||
                        e.target.classList.contains('media-group-item-checkbox')) {
                        e.stopPropagation();
                        return;
                    }

                    // 其他區域點擊打開 Lightbox
                    e.stopPropagation();
                    openLightbox(msg.message_id);
                });

                // 確保選擇框區域的點擊不會冒泡
                const checkbox = mediaItem.querySelector('.media-group-item-checkbox');
                if (checkbox) {
                    checkbox.addEventListener('click', function(e) {
                        e.stopPropagation();
                    });
                }
            }
        });
    }, 50);

    // 點擊卡片選擇整組
    div.onclick = function(event) {
        if (event.target.type !== 'checkbox' && !event.target.closest('.media-group-item')) {
            const checkbox = div.querySelector('.media-group-select');
            checkbox.checked = !checkbox.checked;
            updateMediaGroupSelection(checkbox, mediaGroupId);
        }
    };

    return div;
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
                ${message.media_group_id ? '<span class="media-badge album" style="background: rgba(147, 51, 234, 0.9); color: white;" title="媒體組 ID: ' + message.media_group_id + '"><i class="fas fa-images"></i> ALBUM</span>' : ''}
            </div>
        </div>

        <div class="message-content">
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
                    ${message.caption ? `<div class="message-caption">${escapeHtml(message.caption)}</div>` : ''}
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
        // 只為有縮圖數據的照片或影片載入縮圖
        if ((message.media_type === 'photo' || message.media_type === 'video') && message.thumbnail && message.thumbnail_url) {
            console.log(`Loading thumbnail for ${message.media_type} message ${message.message_id}`);
            console.log(`Thumbnail API URL: /api/thumbnails/${currentChatId}/${message.message_id}`);

            try {
                const response = await fetch(`/api/thumbnails/${currentChatId}/${message.message_id}`);
                console.log(`Thumbnail API response status: ${response.status}`);

                if (response.ok) {
                    const data = await response.json();
                    console.log('Thumbnail API response data:', data);
                    console.log('  - success:', data.success);
                    console.log('  - data:', data.data);
                    console.log('  - has thumbnail:', data.data && data.data.thumbnail ? 'YES' : 'NO');

                    if (data.success && data.data && data.data.thumbnail) {
                        console.log(`Thumbnail loaded successfully for message ${message.message_id}`);

                        // 檢查是否在媒體組網格中
                        const isInMediaGroup = thumbnailContainer.closest('.media-group-item');

                        if (isInMediaGroup) {
                            // 媒體組網格項目 - 設置縮圖並添加影片預覽效果
                            const imgElement = `<img src="${data.data.thumbnail}" alt="Thumbnail" style="width: 100%; height: 100%; object-fit: cover;" />`;

                            if (message.media_type === 'video') {
                                console.log(`🎬 設置相簿影片預覽效果 for message ${message.message_id}`);
                                thumbnailContainer.innerHTML = imgElement + `
                                    <div class="video-preview-progress">
                                        <div class="video-preview-bar"></div>
                                    </div>
                                `;
                                console.log(`✅ 相簿影片縮圖和進度條已添加`);

                                // 啟用影片 hover 播放效果
                                setupVideoHoverPlayback(thumbnailContainer, message);
                            } else {
                                // 照片不需要進度條
                                thumbnailContainer.innerHTML = imgElement;
                            }
                        } else {
                            // 單一訊息縮圖 - 構建完整的 HTML 結構
                            const imgElement = `<img src="${data.data.thumbnail}" alt="Thumbnail" class="thumbnail-image" />`;

                            // 如果是影片，添加進度條
                            if (message.media_type === 'video') {
                                console.log(`🎬 設置影片預覽效果 for message ${message.message_id}`);
                                thumbnailContainer.innerHTML = imgElement + `
                                    <div class="video-preview-progress">
                                        <div class="video-preview-bar"></div>
                                    </div>
                                `;
                                console.log(`✅ 影片縮圖和進度條已添加`);

                                // 啟用影片 hover 播放效果
                                setupVideoHoverPlayback(thumbnailContainer, message);
                            } else {
                                // 照片不需要進度條
                                thumbnailContainer.innerHTML = imgElement;
                            }

                            // 添加點擊事件打開 Lightbox
                            thumbnailContainer.style.cursor = 'pointer';
                            thumbnailContainer.addEventListener('click', function(e) {
                                // 檢查是否剛完成拖曳（500ms 內）
                                const now = Date.now();
                                const lastDragTime = window._lastProgressDragTime || 0;
                                const timeSinceDrag = now - lastDragTime;

                                console.log('👆 Click 事件觸發:', {
                                    now: now,
                                    lastDragTime: lastDragTime,
                                    timeSinceDrag: timeSinceDrag + 'ms',
                                    willBlock: timeSinceDrag < 500
                                });

                                if (timeSinceDrag < 500) {
                                    console.log('🎯 剛完成拖曳（' + timeSinceDrag + 'ms 前），忽略點擊事件');
                                    e.stopPropagation();
                                    return; // 不開啟 lightbox
                                }

                                // 檢查是否點擊在影片控制元素上（進度條等）
                                const isVideoControl = e.target.closest('.video-hover-controls, .video-hover-progress, .video-hover-time');
                                if (isVideoControl) {
                                    console.log('🎯 點擊在影片控制元素上，不開啟 lightbox');
                                    e.stopPropagation();
                                    return; // 不開啟 lightbox
                                }

                                console.log('✅ 通過所有檢查，開啟 lightbox');
                                e.stopPropagation(); // 防止觸發訊息氣泡的點擊事件
                                openLightbox(message.message_id);
                            });
                        }
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

// ==================== Lightbox 圖片放大預覽功能 ====================

// Lightbox 狀態管理
let lightboxImages = [];
let currentLightboxIndex = 0;

/**
 * 初始化 Lightbox 事件監聽器
 */
function initLightbox() {
    // 關閉按鈕
    const closeBtn = document.getElementById('lightbox-close-btn');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeLightbox);
    }

    // 上一張按鈕
    const prevBtn = document.getElementById('lightbox-prev-btn');
    if (prevBtn) {
        prevBtn.addEventListener('click', showPrevLightbox);
    }

    // 下一張按鈕
    const nextBtn = document.getElementById('lightbox-next-btn');
    if (nextBtn) {
        nextBtn.addEventListener('click', showNextLightbox);
    }

    // 點擊背景關閉
    const lightboxOverlay = document.getElementById('lightbox-modal');
    if (lightboxOverlay) {
        lightboxOverlay.addEventListener('click', function(e) {
            if (e.target === lightboxOverlay) {
                closeLightbox();
            }
        });
    }

    // 鍵盤導航
    document.addEventListener('keydown', handleLightboxKeyboard);

    console.log('✅ Lightbox 初始化完成');
}

/**
 * 處理鍵盤事件
 */
function handleLightboxKeyboard(e) {
    const modal = document.getElementById('lightbox-modal');
    if (!modal || modal.style.display === 'none') return;

    switch(e.key) {
        case 'Escape':
            closeLightbox();
            break;
        case 'ArrowLeft':
            showPrevLightbox();
            break;
        case 'ArrowRight':
            showNextLightbox();
            break;
    }
}

/**
 * 打開 Lightbox 預覽
 * @param {number} messageId - 訊息 ID
 */
function openLightbox(messageId) {
    console.log(`🖼️ 打開 Lightbox，訊息 ID: ${messageId}`);

    // 收集當前顯示的所有圖片和影片訊息
    lightboxImages = allMessages.filter(m =>
        (m.media_type === 'photo' || m.media_type === 'video') &&
        document.querySelector(`[data-message-id="${m.message_id}"]`)
    );

    console.log(`📸 找到 ${lightboxImages.length} 個媒體項目`);

    if (lightboxImages.length === 0) {
        console.warn('❌ 沒有找到可預覽的媒體');
        return;
    }

    // 找到當前訊息的索引
    currentLightboxIndex = lightboxImages.findIndex(m => m.message_id === messageId);

    if (currentLightboxIndex === -1) {
        console.warn(`❌ 找不到訊息 ${messageId} 在 lightboxImages 中`);
        currentLightboxIndex = 0;
    }

    // 顯示圖片
    showLightboxImage(currentLightboxIndex);

    // 顯示 Lightbox
    const modal = document.getElementById('lightbox-modal');
    if (modal) {
        modal.style.display = 'flex';
        // 防止背景滾動
        document.body.style.overflow = 'hidden';
    }
}

/**
 * 顯示 Lightbox 中的圖片
 * @param {number} index - 圖片索引
 */
async function showLightboxImage(index) {
    if (index < 0 || index >= lightboxImages.length) {
        console.warn(`⚠️ 索引 ${index} 超出範圍 (0-${lightboxImages.length - 1})`);
        return;
    }

    const message = lightboxImages[index];
    console.log(`🔄 顯示 Lightbox 圖片 ${index + 1}/${lightboxImages.length}`, message);

    // 更新計數器
    document.getElementById('lightbox-current').textContent = index + 1;
    document.getElementById('lightbox-total').textContent = lightboxImages.length;

    // 更新檔案資訊
    document.getElementById('lightbox-filename').textContent = message.file_name || 'Image';
    document.getElementById('lightbox-message-id').textContent = `#${message.message_id}`;

    // 更新 caption（如果有的話）
    const captionElement = document.getElementById('lightbox-caption');
    if (message.caption) {
        captionElement.textContent = message.caption;
        captionElement.style.display = 'block';
    } else {
        captionElement.style.display = 'none';
    }

    // 更新導航按鈕狀態
    const prevBtn = document.getElementById('lightbox-prev-btn');
    const nextBtn = document.getElementById('lightbox-next-btn');
    if (prevBtn) prevBtn.disabled = (index === 0);
    if (nextBtn) nextBtn.disabled = (index === lightboxImages.length - 1);

    // 顯示載入指示器
    const loading = document.getElementById('lightbox-loading');
    const img = document.getElementById('lightbox-image');
    if (loading) loading.style.display = 'flex';
    if (img) img.style.display = 'none';

    try {
        // 使用現有的縮圖 API 載入完整圖片
        const response = await fetch(`/api/thumbnails/${currentChatId}/${message.message_id}`);

        if (!response.ok) {
            throw new Error(`API 返回錯誤: ${response.status}`);
        }

        const data = await response.json();

        if (data.success && data.data && data.data.thumbnail) {
            // 載入圖片
            img.src = data.data.thumbnail;

            // 圖片載入完成後隱藏載入指示器
            img.onload = function() {
                if (loading) loading.style.display = 'none';
                if (img) img.style.display = 'block';
                console.log('✅ Lightbox 圖片載入完成');
            };

            img.onerror = function() {
                console.error('❌ Lightbox 圖片載入失敗');
                if (loading) {
                    loading.innerHTML = `
                        <i class="fas fa-exclamation-triangle"></i>
                        <span>圖片載入失敗</span>
                    `;
                }
            };
        } else {
            throw new Error(data.error || '無法取得圖片');
        }
    } catch (error) {
        console.error('❌ 載入 Lightbox 圖片失敗:', error);
        if (loading) {
            loading.innerHTML = `
                <i class="fas fa-exclamation-triangle"></i>
                <span>載入失敗</span>
            `;
        }
    }
}

/**
 * 顯示上一張圖片
 */
function showPrevLightbox() {
    if (currentLightboxIndex > 0) {
        currentLightboxIndex--;
        showLightboxImage(currentLightboxIndex);
        console.log(`⬅️ 上一張: ${currentLightboxIndex + 1}/${lightboxImages.length}`);
    }
}

/**
 * 顯示下一張圖片
 */
function showNextLightbox() {
    if (currentLightboxIndex < lightboxImages.length - 1) {
        currentLightboxIndex++;
        showLightboxImage(currentLightboxIndex);
        console.log(`➡️ 下一張: ${currentLightboxIndex + 1}/${lightboxImages.length}`);
    }
}

/**
 * 關閉 Lightbox
 */
function closeLightbox() {
    const modal = document.getElementById('lightbox-modal');
    if (modal) {
        modal.style.display = 'none';
        // 恢復背景滾動
        document.body.style.overflow = '';
    }
    console.log('❌ 關閉 Lightbox');
}

// ==================== 訊息快速跳轉功能 ====================

/**
 * 跳轉到最舊訊息
 * 載入群組中的最舊訊息並滾動到該位置
 */
async function jumpToOldestMessage() {
    if (!currentChatId) {
        showNotification('請先選擇一個群組', 'warning');
        return;
    }

    console.log('🚀 開始跳轉到最舊訊息');

    // 顯示載入指示器
    showJumpLoadingIndicator('正在載入最舊訊息...');

    try {
        // 策略：從 ID 1 開始載入，Telegram API 會自動找到最舊的訊息
        // 重置載入狀態
        previousLastMessageId = 0;
        noProgressCount = 0;
        hasMoreMessages = true;
        allMessages = [];

        // 清空現有訊息
        const container = document.getElementById('messages-list');
        if (container) container.innerHTML = '';

        // 載入最舊的訊息（使用 offset_id = 1）
        const response = await fetch('/api/groups/messages', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                chat_id: currentChatId,
                limit: MESSAGES_PER_PAGE,
                offset_id: 1, // Telegram 會從最接近的訊息開始
                media_only: false
            })
        });

        const data = await response.json();

        if (data.success && data.messages && data.messages.length > 0) {
            // Telegram API 會返回最舊的訊息
            allMessages = data.messages;

            // 找到最舊的訊息 ID（數字最小的）
            const oldestId = Math.min(...data.messages.map(m => m.message_id));

            renderMessages(data.messages, false);
            showMessages();

            // 更新 lastMessageId 為最舊的那個（用於繼續載入更新的訊息）
            lastMessageId = oldestId;

            // 滾動到頂部（最舊訊息）
            const messagesContainer = document.getElementById('messages-container');
            if (messagesContainer) {
                messagesContainer.scrollTop = 0;
            }

            hideJumpLoadingIndicator();
            showNotification(`已跳轉到最舊訊息 (ID: ${oldestId})`, 'success');
            console.log('✅ 跳轉到最舊訊息成功, 最舊 ID:', oldestId);
        } else {
            hideJumpLoadingIndicator();
            showNotification('無法載入最舊訊息', 'error');
            console.error('❌ 跳轉失敗:', data);
        }
    } catch (error) {
        hideJumpLoadingIndicator();
        showNotification('載入失敗: ' + error.message, 'error');
        console.error('❌ 跳轉錯誤:', error);
    }
}

/**
 * 跳轉到指定訊息 ID
 * @param {number} targetMessageId - 目標訊息 ID
 */
async function jumpToMessageId(targetMessageId) {
    if (!currentChatId) {
        showNotification('請先選擇一個群組', 'warning');
        return;
    }

    if (!targetMessageId || targetMessageId < 1) {
        showNotification('請輸入有效的訊息 ID', 'warning');
        return;
    }

    console.log('🚀 開始跳轉到訊息 ID:', targetMessageId);

    // 顯示載入指示器
    showJumpLoadingIndicator(`正在載入訊息 #${targetMessageId}...`);

    try {
        // 重置載入狀態
        previousLastMessageId = 0;
        noProgressCount = 0;
        hasMoreMessages = true;
        allMessages = [];

        // 清空現有訊息
        const container = document.getElementById('messages-list');
        if (container) container.innerHTML = '';

        // 從目標 ID 開始載入訊息
        const response = await fetch('/api/groups/messages', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                chat_id: currentChatId,
                limit: MESSAGES_PER_PAGE,
                offset_id: targetMessageId,
                media_only: false
            })
        });

        const data = await response.json();

        if (data.success && data.messages && data.messages.length > 0) {
            allMessages = data.messages;
            renderMessages(data.messages, false);
            showMessages();

            // 更新 lastMessageId
            lastMessageId = Math.min(...data.messages.map(m => m.message_id));

            // 檢查目標訊息是否在載入的訊息中
            const targetMessage = data.messages.find(m => m.message_id === targetMessageId);

            if (targetMessage) {
                // 滾動到目標訊息
                setTimeout(() => {
                    const targetElement = document.querySelector(`[data-message-id="${targetMessageId}"]`);
                    if (targetElement) {
                        targetElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        // 高亮顯示目標訊息
                        targetElement.style.animation = 'highlight-pulse 2s ease-in-out';
                    }
                }, 300);

                hideJumpLoadingIndicator();
                showNotification(`已跳轉到訊息 #${targetMessageId}`, 'success');
                console.log('✅ 跳轉到訊息成功');
            } else {
                // 目標訊息不在返回結果中，可能不存在
                hideJumpLoadingIndicator();
                showNotification(`訊息 #${targetMessageId} 可能不存在或已被刪除`, 'warning');
                console.warn('⚠️ 目標訊息不在返回結果中');
            }
        } else {
            hideJumpLoadingIndicator();
            showNotification('無法載入指定訊息', 'error');
            console.error('❌ 跳轉失敗:', data);
        }
    } catch (error) {
        hideJumpLoadingIndicator();
        showNotification('載入失敗: ' + error.message, 'error');
        console.error('❌ 跳轉錯誤:', error);
    }
}

/**
 * 顯示跳轉載入指示器
 * @param {string} statusText - 狀態文字
 */
function showJumpLoadingIndicator(statusText = '載入中...') {
    const indicator = document.getElementById('jump-loading-indicator');
    const statusElement = document.getElementById('jump-loading-status');
    if (indicator) {
        indicator.style.display = 'flex';
        if (statusElement) {
            statusElement.textContent = statusText;
        }
    }
}

/**
 * 隱藏跳轉載入指示器
 */
function hideJumpLoadingIndicator() {
    const indicator = document.getElementById('jump-loading-indicator');
    if (indicator) {
        indicator.style.display = 'none';
    }
}

// ==================== 影片 Hover 預覽效果 ====================
// 注意：真實的預覽功能實現在後面的 "真實影片幀預覽系統" 區塊中

// ==================== IndexedDB 影片幀快取系統 ====================

/**
 * 初始化 IndexedDB
 */
let videoFramesDB = null;

async function initVideoFramesDB() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open('VideoFramesCache', 1);

        request.onerror = () => reject(request.error);
        request.onsuccess = () => {
            videoFramesDB = request.result;
            resolve(videoFramesDB);
        };

        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains('frames')) {
                const objectStore = db.createObjectStore('frames', { keyPath: 'key' });
                objectStore.createIndex('timestamp', 'timestamp', { unique: false });
            }
        };
    });
}

/**
 * 從 IndexedDB 獲取快取的幀數據
 */
async function getCachedFrames(chatId, messageId) {
    if (!videoFramesDB) await initVideoFramesDB();

    return new Promise((resolve, reject) => {
        const transaction = videoFramesDB.transaction(['frames'], 'readonly');
        const objectStore = transaction.objectStore('frames');
        const key = `${chatId}_${messageId}`;
        const request = objectStore.get(key);

        request.onsuccess = () => {
            const result = request.result;
            // 檢查快取是否過期（7天）
            if (result && (Date.now() - result.timestamp) < 7 * 24 * 60 * 60 * 1000) {
                resolve(result.frames);
            } else {
                resolve(null);
            }
        };

        request.onerror = () => resolve(null);
    });
}

/**
 * 將幀數據存入 IndexedDB
 */
async function cacheFrames(chatId, messageId, frames) {
    if (!videoFramesDB) await initVideoFramesDB();

    return new Promise((resolve, reject) => {
        const transaction = videoFramesDB.transaction(['frames'], 'readwrite');
        const objectStore = transaction.objectStore('frames');
        const key = `${chatId}_${messageId}`;

        const data = {
            key: key,
            chatId: chatId,
            messageId: messageId,
            frames: frames,
            timestamp: Date.now()
        };

        const request = objectStore.put(data);
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
    });
}

/**
 * 從後端 API 獲取影片幀
 */
async function fetchVideoFrames(chatId, messageId) {
    try {
        console.log(`🎬 正在獲取影片幀: chat_id=${chatId}, message_id=${messageId}`);

        const response = await fetch(`/api/video/frames/${chatId}/${messageId}`);

        if (!response.ok) {
            throw new Error(`API 返回錯誤: ${response.status}`);
        }

        const data = await response.json();

        if (data.success && data.data && data.data.frames) {
            console.log(`✅ 成功獲取 ${data.data.frames.length} 個影片幀`);
            return data.data.frames;
        } else {
            throw new Error(data.error || '無法獲取影片幀');
        }
    } catch (error) {
        console.error(`❌ 獲取影片幀失敗:`, error);
        return null;
    }
}

/**
 * 獲取影片幀（先從快取，再從 API）
 */
async function getVideoFrames(chatId, messageId) {
    // 先檢查快取
    let frames = await getCachedFrames(chatId, messageId);

    if (frames) {
        console.log(`✅ 使用快取的影片幀`);
        return frames;
    }

    // 從 API 獲取
    frames = await fetchVideoFrames(chatId, messageId);

    if (frames) {
        // 快取到 IndexedDB
        await cacheFrames(chatId, messageId, frames);
    }

    return frames;
}

// ==================== 真實影片幀預覽系統 ====================

/**
 * Fallback: 簡單的進度條動畫（當無法載入影片幀時使用）
 * @param {HTMLElement} progressBar - 進度條元素
 * @param {Object} message - 訊息物件
 */
function startProgressAnimation(progressBar, message) {
    const duration = message.duration || 10;
    const animationDuration = Math.min(Math.max(duration * 100, 2000), 5000);
    const startTime = performance.now();

    progressBar.classList.add('active');

    function animate(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min((elapsed / animationDuration) * 100, 100);

        progressBar.style.width = progress + '%';

        if (progress < 100) {
            requestAnimationFrame(animate);
        } else {
            setTimeout(() => {
                progressBar.style.width = '0%';
                progressBar.classList.remove('active');
            }, 300);
        }
    }

    requestAnimationFrame(animate);
}

/**
 * 設置真實影片幀預覽效果
 * @param {HTMLElement} container - 縮圖容器元素
 * @param {Object} message - 訊息物件（包含影片資訊）
 */
function setupVideoHoverPreview(container, message) {
    let hoverTimer = null;
    let frames = null;
    let isLoadingFrames = false;
    let previewOverlay = null;

    console.log(`🎥 setupVideoHoverPreview called for message ${message.message_id}`);

    const progressBar = container.querySelector('.video-preview-bar');
    if (!progressBar) {
        console.warn(`⚠️ No progress bar found in container`);
        return;
    }

    // 創建預覽覆蓋層（用於顯示幀）
    previewOverlay = document.createElement('div');
    previewOverlay.className = 'video-frame-preview-overlay';
    previewOverlay.style.display = 'none';
    container.appendChild(previewOverlay);

    // 滑鼠進入事件
    container.addEventListener('mouseenter', async function(e) {
        console.log(`🖱️ Mouse enter on video thumbnail ${message.message_id}`);

        // 防止在點擊時觸發
        if (e.buttons !== 0) return;

        // 清除之前的計時器
        if (hoverTimer) clearTimeout(hoverTimer);

        // 延遲啟動（避免快速滑過時觸發）
        hoverTimer = setTimeout(async () => {
            // 如果尚未載入幀，先載入
            if (!frames && !isLoadingFrames) {
                isLoadingFrames = true;
                console.log(`⏳ 開始載入影片幀...`);

                // 顯示載入指示器
                progressBar.innerHTML = '<div class="loading-text">載入預覽中...</div>';
                progressBar.style.display = 'flex';

                frames = await getVideoFrames(currentChatId, message.message_id);
                isLoadingFrames = false;

                if (frames && frames.length > 0) {
                    console.log(`✅ 影片幀載入完成: ${frames.length} 幀`);
                    progressBar.innerHTML = '';  // 清除載入文字
                } else {
                    console.warn(`⚠️ 無法載入影片幀，使用進度條動畫`);
                    progressBar.innerHTML = '';
                    // 回退到簡單的進度條動畫
                    startProgressAnimation(progressBar, message);
                    return;
                }
            }

            // 如果有幀數據，啟用真實幀預覽
            if (frames && frames.length > 0) {
                enableFramePreview(container, previewOverlay, frames, message);
            }
        }, 300);  // 延遲 300ms
    });

    // 滑鼠移動事件 - 更新預覽幀
    container.addEventListener('mousemove', function(e) {
        if (frames && frames.length > 0 && previewOverlay.style.display !== 'none') {
            updatePreviewFrame(container, previewOverlay, frames, e);
        }
    });

    // 滑鼠離開事件
    container.addEventListener('mouseleave', function() {
        if (hoverTimer) clearTimeout(hoverTimer);

        // 隱藏預覽
        if (previewOverlay) {
            previewOverlay.style.display = 'none';
        }

        // 重置進度條
        progressBar.style.width = '0%';
        progressBar.style.display = '';
        progressBar.innerHTML = '';
    });
}

/**
 * 啟用幀預覽模式
 */
function enableFramePreview(container, overlay, frames, message) {
    overlay.style.display = 'flex';
    // 預設顯示第一幀
    overlay.innerHTML = `<img src="${frames[0].data}" alt="Preview" />`;
    console.log(`🎬 幀預覽模式已啟用`);
}

/**
 * 根據滑鼠位置更新預覽幀
 */
function updatePreviewFrame(container, overlay, frames, event) {
    const rect = container.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const percentage = Math.max(0, Math.min(1, x / rect.width));

    // 根據百分比選擇對應的幀
    const frameIndex = Math.floor(percentage * (frames.length - 1));
    const frame = frames[frameIndex];

    if (frame) {
        overlay.innerHTML = `<img src="${frame.data}" alt="Preview" />`;

        // 更新進度條位置
        const progressBar = container.querySelector('.video-preview-bar');
        if (progressBar) {
            progressBar.style.width = (percentage * 100) + '%';
            progressBar.classList.add('active');
        }
    }
}

// 初始化 IndexedDB（頁面載入時）
initVideoFramesDB().then(() => {
    console.log('✅ IndexedDB 已初始化');
}).catch((error) => {
    console.error('❌ IndexedDB 初始化失敗:', error);
});

// ==================== 修改 createMessageElement 添加縮圖點擊事件 ====================

// 保存原始的 createMessageElement 引用（將在 main.js 初始化時重新賦值）
const originalCreateMessageElement = createMessageElement;

// 修改後的版本會在縮圖載入後添加點擊事件

// ==================== 影片 Hover 播放功能 ====================

/**
 * 設置影片 Hover 預覽播放
 * @param {HTMLElement} container - 縮圖容器
 * @param {Object} message - 訊息物件
 */
function setupVideoHoverPlayback(container, message) {
    // 只為影片類型設置
    if (message.media_type !== 'video') return;

    // 檢查 MSE 支援 - 詳細調試
    console.log('🔍 檢查 MSE 支援...');
    console.log('  - isMSESupported 函數存在?', typeof isMSESupported !== 'undefined');

    console.log('✅ 設置影片 hover 播放（使用快取下載方案）');

    let videoOverlay = null;
    let videoElement = null;
    let progressBar = null;
    let progressThumb = null;
    let isInitialized = false;
    let hoverTimer = null;

    // Mouseenter: 延遲顯示播放器
    container.addEventListener('mouseenter', async () => {
        hoverTimer = setTimeout(async () => {
            // 創建覆蓋層
            if (!videoOverlay) {
                videoOverlay = createVideoOverlay(container, message);
                videoElement = videoOverlay.querySelector('video');
                progressBar = videoOverlay.querySelector('.video-hover-progress-bar');
                progressThumb = videoOverlay.querySelector('.video-hover-progress-thumb');

                // 設置進度條拖曳
                setupProgressDrag(videoOverlay, videoElement, progressBar, progressThumb);
            }

            // 顯示播放器
            console.log('🖼️ 顯示 overlay...');
            console.log('  - overlay 存在?', !!videoOverlay);
            console.log('  - videoElement 存在?', !!videoElement);
            console.log('  - overlay display 前:', videoOverlay.style.display);
            videoOverlay.style.display = 'block';
            console.log('  - overlay display 後:', videoOverlay.style.display);
            console.log('  - overlay 位置:', videoOverlay.getBoundingClientRect());
            console.log('  - video 尺寸:', videoElement.width, 'x', videoElement.height);

            // 如果尚未初始化，開始載入影片
            if (!isInitialized) {
                try {
                    console.log('🎬 開始載入影片...');
                    console.log('  - currentChatId:', currentChatId);
                    console.log('  - message_id:', message.message_id);

                    // 預設使用快取下載端點（首次下載，後續使用快取）
                    let videoUrl = `/api/video/stream/${currentChatId}/${message.message_id}`;
                    console.log('  - videoUrl (cached):', videoUrl);

                    // 先檢查影片是否可用（處理錯誤狀態碼）
                    const response = await fetch(videoUrl, { method: 'HEAD' });

                    if (!response.ok) {
                        // 如果是 413，說明檔案太大，切換到 native API 串流
                        if (response.status === 413) {
                            console.log('⚠️ 檔案太大 (>200MB)，切換到 native API 串流...');
                            videoUrl = `/api/video/stream/native/${currentChatId}/${message.message_id}`;
                            console.log('  - videoUrl (native):', videoUrl);
                        } else {
                            throw new Error(`HTTP ${response.status}`);
                        }
                    }

                    // 使用標準瀏覽器播放器
                    console.log('🎬 設置影片源...');
                    console.log('  - setting videoElement.src =', videoUrl);

                    videoElement.src = videoUrl;

                    console.log('  - src set, calling videoElement.load()...');
                    // 載入元數據
                    await new Promise((resolve, reject) => {
                        videoElement.addEventListener('loadedmetadata', () => {
                            console.log('✅ loadedmetadata event fired');
                            resolve();
                        }, { once: true });
                        videoElement.addEventListener('error', (e) => {
                            console.error('❌ video error event:', e);
                            console.error('  - videoElement.error:', videoElement.error);
                            console.error('  - networkState:', videoElement.networkState);
                            console.error('  - readyState:', videoElement.readyState);
                            reject(e);
                        }, { once: true });
                        videoElement.load();
                    });

                    console.log('✅ 影片元數據已載入');
                    console.log('  - duration:', videoElement.duration);

                    // 開始播放
                    await videoElement.play();
                    console.log('✅ 影片開始播放');
                    console.log('  - paused after play:', videoElement.paused);

                    isInitialized = true;
                    console.log('✅ 影片播放已啟動');

                } catch (error) {
                    console.error('❌ 影片載入失敗:', error);

                    // 決定錯誤訊息
                    let errorMessage = '影片載入失敗';
                    if (error.message === 'FILE_TOO_LARGE') {
                        errorMessage = '影片太大\n請點擊查看';
                    }

                    // 顯示錯誤提示
                    if (videoOverlay) {
                        const errorDiv = document.createElement('div');
                        errorDiv.className = 'video-error-message';
                        errorDiv.innerHTML = errorMessage.replace('\n', '<br>');
                        errorDiv.style.cssText = `
                            position: absolute;
                            top: 50%;
                            left: 50%;
                            transform: translate(-50%, -50%);
                            color: #ff4444;
                            font-size: 14px;
                            padding: 8px 16px;
                            background: rgba(0,0,0,0.8);
                            border-radius: 4px;
                            text-align: center;
                            white-space: pre-line;
                        `;
                        videoOverlay.appendChild(errorDiv);
                    }
                }
            } else {
                // 已初始化，嘗試重新播放
                try {
                    if (videoElement.paused) {
                        videoElement.currentTime = 0;
                        await videoElement.play();
                    }
                } catch (error) {
                    console.error('❌ 重新播放失敗:', error);
                }
            }
        }, 300); // 300ms 延遲
    });

    // Mouseleave: 隱藏播放器並暫停/清理
    container.addEventListener('mouseleave', () => {
        clearTimeout(hoverTimer);

        if (videoOverlay) {
            videoOverlay.style.display = 'none';
        }

        if (videoElement) {
            // 如果使用 MSE 播放器，需要清理資源
            if (videoElement._msePlayer) {
                console.log('🧹 清理 MSE 播放器資源...');
                videoElement._msePlayer.cleanup();
                videoElement._msePlayer = null;
            } else if (!videoElement.paused) {
                // 標準播放器：暫停並重置
                videoElement.pause();
                videoElement.currentTime = 0;
            }
        }
    });
}

/**
 * 創建影片覆蓋層
 */
function createVideoOverlay(container, message) {
    const overlay = document.createElement('div');
    overlay.className = 'video-hover-overlay';
    overlay.style.display = 'none';

    overlay.innerHTML = `
        <video
            class="video-hover-player"
            muted
            playsinline
            preload="metadata"
            crossorigin="use-credentials"
        ></video>
        <div class="video-hover-controls">
            <div class="video-hover-progress">
                <div class="video-hover-progress-bar"></div>
                <div class="video-hover-progress-thumb"></div>
            </div>
            <div class="video-hover-time">
                <span class="current-time">0:00</span> /
                <span class="total-time">0:00</span>
            </div>
        </div>
    `;

    container.appendChild(overlay);

    const video = overlay.querySelector('video');
    const currentTimeSpan = overlay.querySelector('.current-time');
    const totalTimeSpan = overlay.querySelector('.total-time');
    const progressBarElement = overlay.querySelector('.video-hover-progress-bar');
    const progressThumbElement = overlay.querySelector('.video-hover-progress-thumb');

    // 更新時間顯示
    video.addEventListener('loadedmetadata', () => {
        totalTimeSpan.textContent = formatTime(video.duration);
    });

    video.addEventListener('timeupdate', () => {
        currentTimeSpan.textContent = formatTime(video.currentTime);
        updateProgressBar(video, progressBarElement, progressThumbElement);
    });

    return overlay;
}

/**
 * 設置進度條拖曳功能
 */
function setupProgressDrag(overlay, video, progressBar, progressThumb) {
    const progressContainer = progressBar.parentElement;
    let isDragging = false;
    let hasMoved = false; // 記錄是否有移動過（拖曳）

    // 更新進度的輔助函數
    const updateProgress = (clientX) => {
        if (!video || !isFinite(video.duration) || video.duration <= 0) {
            console.log('⚠️ 無法更新進度: video =', !!video, 'duration =', video?.duration);
            return;
        }

        const rect = progressContainer.getBoundingClientRect();
        const offsetX = clientX - rect.left;
        const percentage = Math.max(0, Math.min(1, offsetX / rect.width));
        const newTime = percentage * video.duration;

        console.log('📍 更新進度:', {
            percentage: (percentage * 100).toFixed(1) + '%',
            oldTime: video.currentTime.toFixed(2),
            newTime: newTime.toFixed(2),
            duration: video.duration.toFixed(2)
        });

        video.currentTime = newTime;

        // 手動更新進度條視覺（因為 timeupdate 事件可能不會立即觸發）
        updateProgressBar(video, progressBar, progressThumb);
        console.log('🎨 手動更新進度條視覺');
    };

    // 點擊或開始拖曳進度條
    progressContainer.addEventListener('mousedown', (e) => {
        // 檢查 duration 是否有效
        if (!video || !isFinite(video.duration) || video.duration <= 0) {
            e.stopPropagation();
            e.preventDefault();
            return;
        }

        console.log('🎬 開始拖曳進度條');
        isDragging = true;
        hasMoved = false; // 重置移動標記

        // 立即設置標記，防止 click 事件觸發 lightbox
        window._lastProgressDragTime = Date.now();
        console.log('🎯 設置拖曳標記（mousedown）:', window._lastProgressDragTime);

        // 立即更新到點擊位置
        updateProgress(e.clientX);

        e.stopPropagation(); // 防止觸發其他事件
        e.preventDefault(); // 防止默認行為
    });

    // 全域監聽滑鼠移動（這樣即使滑鼠離開進度條也能繼續拖曳）
    const handleMouseMove = (e) => {
        if (!isDragging) return;

        hasMoved = true; // 標記已移動
        updateProgress(e.clientX);

        e.stopPropagation();
        e.preventDefault();
    };
    document.addEventListener('mousemove', handleMouseMove);

    // 全域監聽滑鼠釋放
    const handleMouseUp = () => {
        if (isDragging) {
            console.log('🎬 結束拖曳進度條, hasMoved:', hasMoved);
            if (hasMoved) {
                // 設置全局標記：剛完成拖曳
                window._lastProgressDragTime = Date.now();
                console.log('🎯 設置拖曳標記:', window._lastProgressDragTime);
            }
        }
        isDragging = false;
        hasMoved = false;
    };
    document.addEventListener('mouseup', handleMouseUp);

    // ✅ 關鍵修復：直接阻止 progressContainer 上的 click 事件冒泡
    // 這樣就不會觸發 thumbnailContainer 的 click 事件（開啟 lightbox）
    progressContainer.addEventListener('click', (e) => {
        console.log('🚫 Progress container click 事件已阻止冒泡');
        e.stopPropagation(); // 阻止冒泡到 thumbnailContainer
        e.preventDefault();  // 防止默認行為
    });

    // 清理函數（當 overlay 被移除時）
    overlay._cleanupProgressDrag = () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
    };
}

/**
 * 更新進度條和拖曳把手位置
 */
function updateProgressBar(video, progressBar, progressThumb) {
    if (!video || !progressBar || !video.duration) return;
    const percentage = (video.currentTime / video.duration) * 100;

    // 更新進度條寬度
    progressBar.style.width = percentage + '%';

    // 更新拖曳把手位置
    if (progressThumb) {
        progressThumb.style.left = percentage + '%';
    }
}

/**
 * 格式化時間 (秒 → MM:SS)
 */
function formatTime(seconds) {
    if (isNaN(seconds) || !isFinite(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}