# 影片串流方案嘗試記錄

## 背景

Message Downloader 需要實現 hover 預覽播放功能，要求：
- 支援大文件（>200MB）邊下載邊播放
- 使用 MSE (Media Source Extensions) API
- 從 Telegram 串流下載，不需要預先下載完整文件

## 方案 1：直接串流原始 MP4 ❌ 失敗

### 實現方式
```python
# video_stream.py
async for chunk in client.stream_media(message.video):
    yield chunk

# Response mimetype: 'video/mp4'
```

### 前端處理
```javascript
// messages.js
const msePlayer = createMSEPlayer(videoElement, videoUrl);
await msePlayer.initialize();  // 使用 video/mp4 codec
```

### 失敗原因
1. **MP4 格式限制**：
   - MP4 的 moov atom（元數據）通常在文件末尾
   - MSE 需要先讀取 moov atom 才能初始化 SourceBuffer
   - 串流模式下無法提前獲取元數據

2. **觀察到的現象**：
   - 瀏覽器 console 顯示數據正在接收
   - 前端 MSE 播放器成功接收數據塊
   - 但影片畫面保持黑屏，無法播放

3. **Console 輸出**：
```
📦 收到第 1 塊: 65528 bytes
📦 收到第 2 塊: 458752 bytes
📊 已接收 10 塊 (~1.1 MB)
📊 已接收 40 塊 (~3.8 MB)
```

### 結論
原始 MP4 格式不適合真正的串流播放，即使 MSE API 能接收數據。

---

## 方案 2：FFmpeg 碎片化 MP4 (-c copy) ❌ 失敗

### 實現方式
```python
ffmpeg_cmd = [
    'ffmpeg',
    '-i', 'pipe:0',
    '-c:v', 'copy',              # 不重新編碼視頻
    '-c:a', 'copy',              # 不重新編碼音頻
    '-movflags', '+frag_keyframe+empty_moov+default_base_moof',
    '-f', 'mp4',
    'pipe:1'
]

# 從 Telegram 讀取 → FFmpeg stdin → FFmpeg stdout → 瀏覽器
```

### 失敗原因
1. **MP4 碎片化的限制**：
   - `-c copy` 需要完整讀取源文件的 codec 參數
   - 從 pipe 輸入時無法獲取完整的流信息
   - FFmpeg 無法正確處理部分輸入

2. **實際日誌**：
```
📦 已傳送 350 塊到 FFmpeg (~349 MB)
✅ Telegram 下載完成: 350 塊

❌ FFmpeg: [mov,mp4,m4a,3gp,3g2,mj2] stream 0, offset 0x30: partial file
❌ FFmpeg: Could not find codec parameters for stream 0
❌ FFmpeg: Consider increasing the value for 'analyzeduration' and 'probesize'
❌ FFmpeg: [mp4] track 1: codec frame size is not set
❌ FFmpeg: Error during demuxing: Invalid data found when processing input
❌ FFmpeg: Output file is empty, nothing was encoded

📊 FFmpeg 轉換完成: 2 塊（幾乎沒有輸出）
```

3. **問題分析**：
   - FFmpeg 收到了所有 350 塊輸入
   - 但只輸出了 2 塊（幾乎為空）
   - MP4 容器無法從串流輸入正確重建

### 結論
FFmpeg 的碎片化 MP4 不適合串流輸入場景，即使使用 `-c copy` 避免重新編碼。

---

## 方案 3：MPEG-TS 格式 + FFmpeg 轉換 ❌ 失敗

### 理論基礎
1. **MPEG-TS 是真正的串流格式**：
   - 電視直播使用的容器格式
   - 不需要完整文件，可從任意位置播放
   - 每個 TS 包都是獨立的，包含完整元數據

2. **與 MP4 的對比**：
   - **MP4**：需要 moov atom（檔案頭），像一本書需要目錄
   - **MPEG-TS**：每個包獨立，像電視直播隨時可看

### 實現方式
```python
ffmpeg_cmd = [
    'ffmpeg',
    '-loglevel', 'warning',
    '-fflags', '+genpts',
    '-i', 'pipe:0',

    # 視頻編碼：使用硬體加速
    '-c:v', 'h264_videotoolbox',  # macOS 硬體編碼器
    '-b:v', '1.5M',               # 視頻位元率（優化）
    '-maxrate', '2M',
    '-bufsize', '1.5M',           # 減小緩衝區
    '-profile:v', 'baseline',     # H.264 baseline（最大兼容性）
    '-g', '30',                   # GOP 大小
    '-realtime', '1',             # 實時編碼模式

    # 音頻編碼
    '-c:a', 'aac',
    '-b:a', '96k',                # 降低音頻位元率

    # 輸出格式：MPEG-TS
    '-f', 'mpegts',
    '-muxdelay', '0.1',           # 降低 mux 延遲
    'pipe:1'
]

# 管道架構：Telegram stream → FFmpeg stdin → FFmpeg stdout → 瀏覽器
```

### 前端支援
```javascript
// video_mse.js - 自動偵測串流模式
const isStreamUrl = this.videoUrl.includes('/stream/');
if (isStreamUrl) {
    mimeCodec = 'video/mp2t; codecs="avc1.42E01E, mp4a.40.2"';  // MPEG-TS
} else {
    mimeCodec = 'video/mp4; codecs="avc1.42E01E, mp4a.40.2"';   // MP4
}
```

### 失敗原因

1. **FFmpeg 無法從串流 MP4 輸入產生輸出**：
   - FFmpeg 需要讀取完整的 MP4 元數據（moov atom）才能初始化解碼器
   - 串流輸入無法提供完整的檔案結構
   - 即使使用 MPEG-TS 輸出格式，問題仍在**輸入端**

2. **實際日誌**：
```
📥 已下載 350 塊 (~349.8 MB) → FFmpeg
✅ Telegram 下載完成: 350 塊, 349.82 MB

🔴 FFmpeg: [mov,mp4,m4a,3gp,3g2,mj2] stream 0, offset 0x30: partial file
🔴 FFmpeg: Error during demuxing: Invalid data found when processing input
🔴 FFmpeg: Cannot determine format of input 0:0 after EOF
🔴 FFmpeg: [vost#0:0/h264_videotoolbox] Could not open encoder before EOF
🔴 FFmpeg: Nothing was written into output file

✅ FFmpeg 轉換完成: 0 塊, 0.00 MB  ← 零輸出！
```

3. **前端現象**：
```
🎬 檢測到串流模式，使用 MPEG-TS
✅ 使用 codec: video/mp2t; codecs="avc1.42E01E, mp4a.40.2"
✅ SourceBuffer 創建成功
✅ 串流連接建立成功
✅ 串流讀取完成
📊 總共接收: 0.00 MB  ← 沒收到任何數據
❌ 播放失敗: NotSupportedError: Failed to load because no supported source was found
```

4. **問題分析**：
   - Telegram 成功下載並傳送了 349.82 MB 到 FFmpeg
   - FFmpeg 收到所有數據但無法解析 MP4 格式（認為是 "partial file"）
   - FFmpeg 在初始化編碼器前就失敗（EOF 錯誤）
   - 瀏覽器收到 0 bytes，MSE 播放器無法播放

### 根本原因

**串流 MP4 輸入的結構性問題**：
- MP4 格式設計為**隨機存取容器**，不是**順序串流容器**
- moov atom（metadata box）通常在檔案末尾，包含：
  - Track 信息（視頻/音頻參數）
  - Sample 表（關鍵幀位置）
  - Codec 初始化數據
- FFmpeg 從 pipe 輸入時：
  1. 無法 seek 到檔案末尾讀取 moov atom
  2. 無法緩衝整個檔案來重組結構
  3. 收到 EOF 時才發現缺少必要的元數據
  4. 此時已來不及初始化解碼器

### 結論

**所有基於 FFmpeg 轉換串流 MP4 的方案都不可行**，無論輸出格式是：
- ❌ 碎片化 MP4 (`-c copy`)
- ❌ MPEG-TS（重新編碼）
- ❌ 其他格式

問題不在輸出端，而在**輸入端** - FFmpeg 無法處理不完整的 MP4 串流輸入。

---

## 技術要點總結

### 為什麼直接串流 MP4 不行？
1. **MP4 容器設計**：為完整文件優化，不是為串流設計
2. **元數據位置**：moov atom 通常在文件末尾（除非用 faststart 優化）
3. **MSE 限制**：需要提前知道 codec 參數才能創建 SourceBuffer

### 為什麼 FFmpeg -c copy 失敗？
1. **部分文件問題**：從 pipe 輸入時 FFmpeg 認為是 "partial file"
2. **Codec 參數缺失**：無法從不完整的輸入推斷完整的 codec 參數
3. **MP4 封裝限制**：即使是碎片化 MP4 也需要完整的流信息

### 為什麼 MPEG-TS 理論上應該可行？（但實際失敗）
1. **自包含的包**：每個 TS 包都包含必要的元數據
2. **無需全局索引**：不像 MP4 需要 moov atom
3. **行業標準**：電視直播、HLS 串流都使用此格式
4. **瀏覽器支援**：MSE API 設計時就考慮了 MPEG-TS

**但是**：MPEG-TS 只能解決**輸出端**的問題，無法解決**輸入端**（串流 MP4）的問題。

### 為什麼 FFmpeg 無法處理串流 MP4 輸入？
1. **結構依賴性**：MP4 的 mdat（媒體數據）依賴 moov（元數據）解析
2. **順序限制**：FFmpeg 需要先讀取 moov 才能理解 mdat 內容
3. **pipe 輸入限制**：無法 seek、無法回頭讀取、只能順序處理
4. **EOF 問題**：收到完整數據後才發現元數據缺失，為時已晚

---

## 最終結論與建議

### 測試總結
**所有三種 FFmpeg 串流方案均失敗**：

| 方案 | 輸出格式 | 編碼方式 | 結果 | 原因 |
|------|---------|---------|------|------|
| 方案 1 | MP4 原始 | 無處理 | ❌ 黑屏 | moov atom 在末尾，MSE 無法播放 |
| 方案 2 | MP4 碎片化 | -c copy | ❌ 2 塊輸出 | 無法從 pipe 獲取完整 codec 參數 |
| 方案 3 | MPEG-TS | 硬體加速重編 | ❌ 0 塊輸出 | FFmpeg 無法解析串流 MP4 輸入 |

### 根本問題
**核心矛盾**：
- **Telegram API** 只提供 **MP4 格式** 的串流輸出
- **FFmpeg** 需要 **完整的 MP4 結構** 才能處理
- **串流模式** 無法提供 **完整結構**（moov atom 在末尾）

### 實際可行方案

#### 方案 A：保留現有實現（推薦）✅

**使用快取下載端點**（[video_stream.py:66-208](video_stream.py#L66-L208)）：
```python
@bp.route('/<chat_id>/<int:message_id>', methods=['GET'])
async def get_video_stream(chat_id: str, message_id: int):
    # 1. 下載完整影片到臨時檔案
    # 2. 使用 FFmpeg faststart 優化（moov atom 移到開頭）
    # 3. 返回優化後的 MP4
```

**優點**：
- ✅ 已實現且測試通過
- ✅ FFmpeg faststart 優化支援漸進式播放
- ✅ 檔案大小限制 200MB（合理範圍）
- ✅ 不需要真正的串流（200MB 下載速度可接受）

**缺點**：
- ⚠️ 需要完整下載才能開始播放（但 faststart 優化後延遲很小）
- ⚠️ 超過 200MB 的影片無法 hover 預覽

#### 方案 B：禁用大檔案 hover 預覽 ✅

**修改邏輯**：
```javascript
// messages.js
if (message.file_size > 200 * 1024 * 1024) {
    // 顯示提示：「檔案太大，請點擊以 lightbox 方式查看」
    return;
}
```

**優點**：
- ✅ 實施簡單
- ✅ 用戶體驗明確（知道為何無法預覽）

**缺點**：
- ⚠️ 大檔案無法 hover 預覽（但仍可點擊查看）

#### 方案 C：混合方案（不推薦）

嘗試其他串流技術（例如 WebRTC、WebTransport），但：
- ❌ 複雜度極高
- ❌ 瀏覽器支援不完整
- ❌ Telegram API 限制

### 推薦實施

**保持現狀** - 快取下載端點 + 200MB 限制：

1. **已有功能**：
   - ✅ 快取下載端點（支援 faststart 優化）
   - ✅ 檔案大小檢查（200MB 限制）
   - ✅ 會話級別快取管理

2. **移除失敗實現**：
   - 🗑️ 刪除或註釋 MPEG-TS 串流端點（`/stream/<chat_id>/<message_id>`）
   - 🗑️ 移除 FFmpeg 轉換相關代碼

3. **文檔更新**：
   - ✅ 本文件已記錄所有嘗試和失敗原因
   - ✅ 提供清晰的技術解釋

---

## 參考資料

- **MSE_SOLUTION.md**：詳細的 MSE 技術分析
- **test_quart_stream.py**：MPEG-TS 實現的參考代碼（已證實輸出端可行，但輸入端失敗）
- **video_mse.js**：已實現的 MSE 播放器（支援 MPEG-TS 檢測，但收不到數據）
- **video_stream.py**：包含快取下載端點（可用）和 MPEG-TS 串流端點（失敗）

---

## 實施檢查清單

### 已完成 ✅
- [x] 記錄所有方案（本文件）
- [x] 實現 MPEG-TS 串流（video_stream.py）
- [x] 修改 MSE 播放器支援 MPEG-TS（video_mse.js）
- [x] 測試和驗證 - **結果：失敗**

### 後續任務
- [ ] 決定是否刪除 MPEG-TS 串流端點
- [ ] 更新用戶介面提示（大檔案無法 hover 預覽的說明）
- [ ] 繼續 Quart 遷移（downloads.py 等其他模組）

---

**最後更新**: 2025-11-05
**作者**: Claude Code
**測試狀態**: 所有串流方案均失敗，推薦使用快取下載方案
