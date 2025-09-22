/**
 * Message Downloader - Selection Module
 * 訊息選擇和下載管理
 *
 * 處理訊息選擇邏輯、下載隊列管理和批次操作功能
 */

// ==================== 訊息選擇管理 ====================

/**
 * 更新訊息選擇狀態
 * @param {HTMLInputElement} checkbox - 選擇框元素
 * @param {number} messageId - 訊息ID
 */
function updateSelection(checkbox, messageId) {
    const chatBubble = checkbox.closest('.chat-bubble');

    if (checkbox.checked) {
        if (!selectedMessages.includes(messageId)) {
            selectedMessages.push(messageId);
        }
        chatBubble.classList.add('selected');
    } else {
        selectedMessages = selectedMessages.filter(id => id !== messageId);
        chatBubble.classList.remove('selected');
    }

    updateSelectionUI();
}

/**
 * 更新選擇相關的UI元素
 */
function updateSelectionUI() {
    const count = selectedMessages.length;
    const selectedCountElement = document.getElementById('selected-count');
    const downloadButton = document.getElementById('fast-test-download-btn');

    if (selectedCountElement) {
        selectedCountElement.textContent = count;
    }

    if (downloadButton) {
        downloadButton.disabled = count === 0;
    }
}

/**
 * 全選所有訊息
 */
function selectAllMessages() {
    const checkboxes = document.querySelectorAll('.message-select');
    selectedMessages = [];

    checkboxes.forEach(checkbox => {
        checkbox.checked = true;
        const chatBubble = checkbox.closest('.chat-bubble');
        if (chatBubble) {
            const messageId = parseInt(chatBubble.dataset.messageId);
            if (messageId && !isNaN(messageId)) {
                selectedMessages.push(messageId);
                chatBubble.classList.add('selected');
            }
        }
    });

    updateSelectionUI();
}

/**
 * 清除所有選擇
 */
function clearSelection() {
    const checkboxes = document.querySelectorAll('.message-select');
    checkboxes.forEach(checkbox => {
        checkbox.checked = false;
        const chatBubble = checkbox.closest('.chat-bubble');
        if (chatBubble) {
            chatBubble.classList.remove('selected');
        }
    });
    selectedMessages = [];
    updateSelectionUI();
}

// ==================== 下載管理 ====================

/**
 * 開始下載選中的訊息
 */
async function startDownload() {
    if (!currentChatId || selectedMessages.length === 0) {
        showNotification('warning', '注意', '請選擇要下載的訊息');
        return;
    }

    console.log('開始下載，群組ID:', currentChatId);
    console.log('選中的訊息ID:', selectedMessages);

    // Show loading state on download button
    const downloadBtn = document.getElementById('fast-test-download-btn');
    if (!downloadBtn) return;

    const originalText = downloadBtn.innerHTML;
    downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 準備中...';
    downloadBtn.disabled = true;

    // 顯示即時通知
    showDownloadStartNotification(selectedMessages.length);

    try {
        const response = await fetch('/api/fast_download/add_tasks', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                chat_id: currentChatId,
                message_ids: selectedMessages
            })
        });

        console.log('下載 API 響應狀態:', response.status);
        const data = await response.json();
        console.log('下載 API 響應數據:', data);

        if (data.success) {
            // 更新通知為成功狀態
            if (downloadNotificationId) {
                updateNotification(downloadNotificationId, {
                    title: '任務已加入隊列',
                    message: `✅ 成功加入 ${data.added_count} 個下載任務到隊列`
                });
            }

            clearSelection();

            // 顯示提示
            setTimeout(() => {
                showNotification('info', '提示', '您可以在此頁面查看下載進度，或透過 Telegram bot 接收通知', { duration: 4000 });
            }, 2000);
        } else {
            // 如果失敗，停止進度檢查並顯示錯誤
            stopProgressChecking();
            if (downloadNotificationId) {
                removeNotification(downloadNotificationId);
                downloadNotificationId = null;
            }
            showNotification('error', '下載失敗', data.error || data.message || '未知錯誤');
        }
    } catch (error) {
        console.error('下載錯誤:', error);
        // 如果出現異常，停止進度檢查並顯示錯誤
        stopProgressChecking();
        if (downloadNotificationId) {
            removeNotification(downloadNotificationId);
            downloadNotificationId = null;
        }
        showNotification('error', '連接錯誤', '下載請求時發生錯誤：' + error.message);
    } finally {
        // Restore download button
        downloadBtn.innerHTML = originalText;
        downloadBtn.disabled = selectedMessages.length === 0;
    }
}