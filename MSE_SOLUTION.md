# 影片串流播放完整解決方案

## 問題分析

**現象**：Telegram 可以串流播放，但我們的實現失敗
**原因**：使用了錯誤的瀏覽器 API

## 技術對比

### 當前實現（失敗）
```javascript
videoElement.src = 'http://localhost:5003/test/video_stream/...';
```
- 使用標準 `<video>` 元素
- 需要完整的 MP4 結構（moov atom 在開頭）
- 瀏覽器控制下載過程
- ❌ 無法播放不完整的 MP4

### Telegram 方案（成功）
```javascript
const mediaSource = new MediaSource();
videoElement.src = URL.createObjectURL(mediaSource);
```
- 使用 Media Source Extensions (MSE) API
- 不需要完整的 MP4 結構
- JavaScript 控制下載和緩衝
- ✅ 可以邊下載邊播放

## 實施方案

### 方案 A：使用 MSE API（推薦）

**優點**：
- ✅ 真正的串流播放
- ✅ 用戶體驗最佳
- ✅ 不需要 Quart 遷移（可在 Flask 上實現）
- ✅ 支援所有瀏覽器（除 IE）

**缺點**：
- 需要重寫前端播放器邏輯
- 需要處理 MP4 分片
- 複雜度較高

**實施時間**：3-5 天

### 方案 B：使用 MP4Box.js 轉換

**優點**：
- ✅ 可以將 moov atom 移到開頭
- ✅ 不需要 MSE API
- ✅ 相對簡單

**缺點**：
- ❌ 仍需完整下載（或下載足夠多的數據）
- ❌ 額外的 CPU 開銷
- ❌ 延遲較高

**實施時間**：2-3 天

### 方案 C：檔案大小限制（臨時方案）

**優點**：
- ✅ 實施最快速
- ✅ 部分功能可用

**缺點**：
- ❌ 只支援小影片（< 30MB）
- ❌ 大影片無法預覽

**實施時間**：1 天

## 推薦方案：MSE API 實現

### 前端實現

```javascript
async function setupVideoHoverPlaybackMSE(container, message) {
    if (message.media_type !== 'video') return;

    let videoOverlay = null;
    let mediaSource = null;
    let sourceBuffer = null;

    container.addEventListener('mouseenter', async () => {
        // 創建覆蓋層
        videoOverlay = createVideoOverlay(container, message);
        const videoElement = videoOverlay.querySelector('video');

        // 創建 MediaSource
        mediaSource = new MediaSource();
        videoElement.src = URL.createObjectURL(mediaSource);

        mediaSource.addEventListener('sourceopen', async () => {
            // 創建 SourceBuffer
            sourceBuffer = mediaSource.addSourceBuffer('video/mp4; codecs="avc1.42E01E, mp4a.40.2"');

            // 開始串流下載
            const response = await fetch(
                `http://localhost:5003/test/video_stream/${currentChatId}/${message.message_id}`
            );

            const reader = response.body.getReader();

            // 逐塊讀取並添加到緩衝區
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                // 等待 sourceBuffer 準備好接收數據
                await new Promise(resolve => {
                    if (sourceBuffer.updating) {
                        sourceBuffer.addEventListener('updateend', resolve, { once: true });
                    } else {
                        resolve();
                    }
                });

                sourceBuffer.appendBuffer(value);
            }

            // 結束串流
            if (mediaSource.readyState === 'open') {
                mediaSource.endOfStream();
            }
        });

        videoOverlay.style.display = 'block';
    });

    container.addEventListener('mouseleave', () => {
        if (videoOverlay) {
            videoOverlay.style.display = 'none';
        }
        if (mediaSource && mediaSource.readyState === 'open') {
            mediaSource.endOfStream();
        }
    });
}
```

### 後端實現

**好消息**：Quart POC 已經證明後端可以正常串流！
```python
# test_quart_stream.py 已經完成
async for chunk in client.stream_media(message.video):
    yield chunk  # ✅ 已驗證可行
```

### 瀏覽器兼容性

| 瀏覽器 | MSE 支援 |
|--------|---------|
| Chrome 23+ | ✅ |
| Firefox 42+ | ✅ |
| Safari 8+ | ✅ |
| Edge 12+ | ✅ |
| IE 11 | ✅ (部分) |

## 結論

**Telegram 的串流播放並非魔法**，而是使用了標準的 Web 技術（MSE API）。

我們的 Quart POC 已經證明：
- ✅ 後端串流功能完全正常
- ✅ Quart 可以與 Pyrogram 共存
- ✅ 數據可以成功傳輸

**唯一缺失的是前端 MSE 實現**。

## 下一步

1. ✅ **已完成**：後端串流驗證（Quart POC）
2. ⏳ **待實施**：前端 MSE 播放器
3. ⏳ **待優化**：進度條、拖曳、錯誤處理

預計完整實施時間：**3-5 天**
