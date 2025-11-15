# 影片串流播放測試指南

## 功能概述

實現了基於 **Telegram 原生 MTProto API** 的真正串流播放方案，解決大檔案無法預覽的問題。

### 技術方案

**方案名稱**: moov atom 重組 + Range Requests

**核心原理**:
1. 使用 `upload.GetFile` Range Requests 從檔案末尾下載 moov atom（MP4 元數據）
2. 重組 MP4 結構：`ftyp + moov + mdat`
3. 邊下載邊串流給瀏覽器
4. 跳過原始檔案中的 moov atom（因為已經發送到前面）

**關鍵技術突破** (2025-01-05):
- 🔍 發現 Telegram API 的**隱藏限制**：請求範圍必須在同一個 1MB 區塊內
- 📐 實現動態邊界檢查：`offset / 1048576 == (offset + limit - 1) / 1048576`
- 🎯 優化 chunk size 為 256KB，大幅降低跨越邊界的機率
- ✅ 完全符合 Telegram MTProto API 規範

**優勢**:
- ✅ 真正的串流播放，無需完整下載
- ✅ 支援任意大小的檔案（無 200MB 限制）
- ✅ 記憶體使用極低（僅 256KB chunk buffer）
- ✅ 2-3 秒內即可開始播放（moov 提取時間）
- ✅ 完全合規的 API 使用（遵循官方文檔限制）

## 實現檔案

### 後端
- **`module/mp4_utils.py`** (NEW): MP4 檔案解析工具
  - `MP4Atom` class
  - `parse_atom_header()` - 解析 atom 結構
  - `find_atom()` - 搜尋特定 atom
  - `find_moov_location()` - 漸進式搜尋 moov atom (1MB → 5MB → 10MB)
  - `extract_moov_atom()` - 提取完整 moov atom

- **`module/web/message_downloader/video_stream.py`**
  - `/native/<chat_id>/<message_id>` endpoint (lines 410-604)
  - 使用 Telegram 原生 `upload.GetFile` API
  - 4KB 對齊的 Range Requests
  - MP4 結構重組串流

### 前端
- **`module/static/js/message_downloader/messages.js`**
  - 修改 `setupVideoHoverPlayback()` 函數 (lines 1730-1739)
  - 自動偵測大檔案（413 錯誤）並切換到 native API 端點

## 測試步驟

### 1. 啟動服務

```bash
./start_tgdl_dev.sh
# 或手動啟動
WEB_PORT=5002 python3 media_downloader.py --config-file config_develop.yaml
```

確認服務運行在 Port 5002：
```bash
ps aux | grep "media_downloader.py" | grep "5002"
```

### 2. 登入 Telegram 帳號

1. 打開瀏覽器訪問: http://localhost:5002/message_downloader
2. 如果未登入，會自動跳轉到登入頁面
3. 輸入手機號碼（含國碼，如 +886912345678）
4. 輸入收到的驗證碼
5. 如果有雙重驗證，輸入密碼
6. 登入成功後會跳轉到群組列表

### 3. 測試小檔案（< 200MB）

**目的**: 驗證快取下載模式仍正常運作

1. 選擇任一群組，載入訊息列表
2. 找一個影片檔案 < 200MB
3. 將滑鼠 hover 到影片縮圖上
4. **預期結果**:
   - ✅ 影片開始播放
   - ✅ 使用快取端點 `/api/message_downloader_video_stream/<chat_id>/<message_id>`
   - ✅ 完整下載後可隨意拖曳進度條

**瀏覽器 Console 日誌**:
```
🎬 開始載入影片...
  - videoUrl (cached): /api/message_downloader_video_stream/...
🎬 設置影片源...
✅ 影片元數據已載入
✅ 影片開始播放
```

### 4. 測試大檔案（> 200MB）⭐ 關鍵測試

**目的**: 驗證 native API 串流播放

1. 找一個影片檔案 > 200MB（如 300MB、500MB 甚至更大）
2. 將滑鼠 hover 到影片縮圖上
3. **預期結果**:
   - ✅ 影片在 2-3 秒內開始播放
   - ✅ 自動切換到 native 端點 `/api/message_downloader_video_stream/native/<chat_id>/<message_id>`
   - ✅ 播放流暢，無需等待完整下載
   - ✅ 可以拖曳進度條（瀏覽器會發送新的 Range Request）

**瀏覽器 Console 日誌**:
```
🎬 開始載入影片...
  - videoUrl (cached): /api/message_downloader_video_stream/...
⚠️ 檔案太大 (>200MB)，切換到 native API 串流...
  - videoUrl (native): /api/message_downloader_video_stream/native/...
🎬 設置影片源...
✅ 影片元數據已載入
✅ 影片開始播放
```

**後端日誌** (`tail -f tgdl_dev.log`):
```
🎬 開始原生 API 串流: chat_id=..., message_id=...
📹 影片大小: 349.82 MB
📦 提取 moov atom...
🔍 搜尋 moov atom: offset=..., limit=...
✅ 找到 moov atom: offset=..., size=...
✅ moov atom 提取完成: ... bytes
📦 獲取 ftyp atom...
✅ ftyp atom: ... bytes
📤 發送 ftyp + moov...
📤 開始串流媒體數據...
📊 串流進度: 10.0% (34.9 MB)
📊 串流進度: 20.0% (69.8 MB)
...
✅ 串流完成: ... 塊, 349.82 MB
```

### 5. 測試超大檔案（> 1GB）

**目的**: 驗證無檔案大小限制

1. 找一個影片檔案 > 1GB
2. 重複步驟 4 的測試
3. **預期結果**:
   - ✅ 同樣可以正常播放
   - ✅ 記憶體使用保持穩定（不會隨檔案大小增長）

## 驗證檢查點

### ✅ 功能驗證

- [ ] 小檔案（< 200MB）使用快取下載模式
- [ ] 大檔案（> 200MB）自動切換到 native 串流模式
- [ ] 影片在 2-3 秒內開始播放（大檔案）
- [ ] 播放流暢，無卡頓
- [ ] 可以拖曳進度條
- [ ] 支援超大檔案（> 1GB）
- [ ] 多個影片可以同時 hover 播放

### ✅ 技術驗證

- [ ] 後端日誌顯示 moov atom 提取成功
- [ ] 後端日誌顯示串流進度
- [ ] 瀏覽器 Console 顯示正確的端點切換
- [ ] 瀏覽器 Network 面板顯示逐步載入（而非一次性下載）
- [ ] 記憶體使用保持穩定

### ✅ 錯誤處理

- [ ] 無效的 chat_id/message_id 返回 404
- [ ] 未認證狀態返回 401
- [ ] 非影片訊息返回適當錯誤
- [ ] 網路中斷後可以恢復

## 已知限制

1. **進度條拖曳**:
   - 某些瀏覽器對串流影片的 seek 支援有限
   - 可能需要等待更多緩衝才能跳轉

2. **moov atom 搜尋**:
   - 目前搜尋範圍：檔案末尾 1MB → 5MB → 10MB
   - 極少數 MP4 檔案的 moov atom 可能超過 10MB（會失敗）

3. **瀏覽器相容性**:
   - Chrome/Edge: 完全支援 ✅
   - Firefox: 完全支援 ✅
   - Safari: 完全支援 ✅
   - 舊版 IE: 不支援 ❌

## 故障排除

### 問題: 影片無法播放（黑畫面）

**檢查**:
1. 查看後端日誌是否有錯誤
2. 檢查是否成功提取 moov atom
3. 確認影片格式為 MP4（H.264 + AAC）

**解決**:
```bash
# 查看最近 50 行日誌
tail -50 tgdl_dev.log

# 搜尋錯誤
grep -i "error\|failed\|❌" tgdl_dev.log | tail -20
```

### 問題: 仍然提示 "檔案太大"

**原因**: 前端程式碼未更新

**解決**:
1. 清除瀏覽器快取（Ctrl+Shift+R 或 Cmd+Shift+R）
2. 確認服務已重啟
3. 檢查 messages.js 是否包含 `/native/` 端點切換邏輯

### 問題: 記憶體持續增長

**原因**: 串流數據未正確釋放

**解決**:
1. 重啟服務
2. 檢查是否有殭屍進程
3. 查看日誌中的錯誤訊息

## 後續優化

1. **快取機制**:
   - 快取 moov atom 避免重複提取
   - 使用 Redis/Memcached 共享快取

2. **進度提示**:
   - 顯示 moov atom 提取進度
   - 顯示串流緩衝狀態

3. **自適應串流**:
   - 根據網路狀況調整 chunk 大小
   - 實作類似 HLS/DASH 的自適應位元率

4. **並行下載**:
   - 使用多個連線並行下載不同範圍
   - 加快大檔案的初始載入速度

## 參考文檔

- [VIDEO_STREAMING_ATTEMPTS.md](./VIDEO_STREAMING_ATTEMPTS.md) - 所有嘗試過的方案記錄
- [MSE_SOLUTION.md](./MSE_SOLUTION.md) - Media Source Extensions 方案（備選）
- [MP4 Container Format](https://en.wikipedia.org/wiki/MP4_file_format)
- [Telegram MTProto API](https://core.telegram.org/api)
