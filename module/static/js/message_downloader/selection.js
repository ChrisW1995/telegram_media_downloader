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
 * 開始下載選中的訊息 - 顯示下載選擇對話框
 */
function startDownload() {
    if (!currentChatId || selectedMessages.length === 0) {
        showNotification('warning', '注意', '請選擇要下載的訊息');
        return;
    }

    // 顯示下載選擇對話框
    showDownloadChoiceModal();
}

/**
 * 執行 Bot 內下載
 */
async function startBotDownload() {
    console.log('開始 Bot 下載，群組ID:', currentChatId);
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

/**
 * 執行本地 ZIP 下載
 */
async function startLocalDownload() {
    console.log('開始本地 ZIP 下載，群組ID:', currentChatId);
    console.log('選中的訊息ID:', selectedMessages);

    // 顯示下載進度通知
    const zipNotificationId = showNotification('info', 'ZIP 下載', `正在準備 ${selectedMessages.length} 個檔案...`, {
        duration: 0, // 不自動消失
        progress: true // 顯示進度條
    });

    try {
        // 更新通知狀態為下載中
        updateNotification(zipNotificationId, {
            title: 'ZIP 下載',
            message: '正在從 Telegram 下載檔案並打包...',
            progress: 30
        });

        const response = await fetch('/api/download/zip', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                chat_id: currentChatId,
                message_ids: selectedMessages
            })
        });

        if (response.ok) {
            // 更新進度
            updateNotification(zipNotificationId, {
                title: 'ZIP 下載',
                message: '正在下載 ZIP 檔案到您的電腦...',
                progress: 80
            });

            // 取得檔案名稱從回應標頭
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = 'download.zip';
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename=["']?([^"';]+)["']?/);
                if (filenameMatch) {
                    filename = filenameMatch[1];
                }
            }

            // 下載檔案
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            // 更新為完成狀態
            updateNotification(zipNotificationId, {
                title: '下載完成',
                message: `✅ ${filename} 已下載到您的電腦`,
                progress: 100
            });

            // 3秒後移除通知
            setTimeout(() => {
                removeNotification(zipNotificationId);
            }, 3000);

            clearSelection();
        } else {
            const data = await response.json();

            // 顯示錯誤
            updateNotification(zipNotificationId, {
                title: '下載失敗',
                message: `❌ ${data.error || data.message || '未知錯誤'}`,
                type: 'error'
            });

            // 5秒後移除通知
            setTimeout(() => {
                removeNotification(zipNotificationId);
            }, 5000);
        }
    } catch (error) {
        console.error('ZIP 下載錯誤:', error);

        // 顯示錯誤
        updateNotification(zipNotificationId, {
            title: '連接錯誤',
            message: `❌ ZIP 下載時發生錯誤：${error.message}`,
            type: 'error'
        });

        // 5秒後移除通知
        setTimeout(() => {
            removeNotification(zipNotificationId);
        }, 5000);
    }
}

/**
 * 執行兩種下載方式
 */
async function startBothDownload() {
    console.log('開始執行 Bot 和本地雙重下載');

    showNotification('info', '雙重下載', '正在同時執行 Bot 下載和本地 ZIP 下載...');

    try {
        // 同時執行兩種下載
        await Promise.all([
            startBotDownload(),
            startLocalDownload()
        ]);

        showNotification('success', '完成', '兩種下載方式都已開始執行');
    } catch (error) {
        console.error('雙重下載錯誤:', error);
        showNotification('error', '下載錯誤', '執行雙重下載時發生錯誤');
    }
}