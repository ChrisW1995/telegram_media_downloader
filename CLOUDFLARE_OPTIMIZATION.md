# Cloudflare Tunnel 下載速度優化指南

## 問題：透過 Cloudflare Tunnel 下載速度慢

Cloudflare Tunnel 預設配置針對網頁優化，對於大檔案下載需要額外優化。

## 優化清單

### 1. 本地配置優化 ✅

**cloudflare_tunnel_config.yml** 已包含以下優化：

```yaml
# 使用 QUIC 協議（HTTP/3）
protocol: quic

# 增加連接逾時
originRequest:
  connectTimeout: 30s
  tcpKeepAlive: 30s
```

### 2. Cloudflare Dashboard 設定優化 ⚠️

**必須在 Cloudflare Dashboard 執行以下設定**：

#### A. 停用不必要的優化功能

登入 [Cloudflare Dashboard](https://dash.cloudflare.com) → 選擇你的網域 `cw1005host.com`

**速度 (Speed) → 優化 (Optimization)**

1. **Auto Minify (自動壓縮)** - 全部關閉 ❌
   - JavaScript: OFF
   - CSS: OFF
   - HTML: OFF
   - 原因：媒體檔案不需要壓縮，反而增加處理時間

2. **Brotli** - 關閉 ❌
   - 原因：影片、圖片等媒體檔案已經壓縮，再次壓縮無益反而降速

3. **Rocket Loader** - 關閉 ❌
   - 原因：會延遲 JavaScript 載入，影響下載功能

#### B. 網路設定

**網路 (Network)**

1. **HTTP/3 (with QUIC)** - 開啟 ✅
   - 提升連接速度和穩定性

2. **WebSockets** - 開啟 ✅
   - 確保實時進度更新正常運作

3. **gRPC** - 可選
   - 如果使用 gRPC，建議開啟

#### C. 快取規則優化

**快取 (Caching) → 配置 (Configuration)**

建立 **Page Rule** 或 **Cache Rule**：

**規則 1: ZIP 下載不快取**
```
URL 匹配: cw1005host.com/api/download/*
設定:
  - Cache Level: Bypass
  - Browser Cache TTL: Bypass
```

**規則 2: 靜態資源快取**
```
URL 匹配: cw1005host.com/static/*
設定:
  - Cache Level: Standard
  - Edge Cache TTL: 1 month
  - Browser Cache TTL: 1 month
```

#### D. 防火牆規則

**安全性 (Security) → WAF**

確保以下請求不被阻擋：
```
URL 包含: /api/download/
動作: 允許
```

### 3. 應用程式層級優化

**檢查 Flask 設定** (已完成 ✅)

在 `module/web/message_downloader/downloads.py` 中：

```python
# 確保大檔案傳輸不受限制
@app.route('/download')
def download():
    return send_file(
        file_path,
        as_attachment=True,
        # 不使用快取
        cache_timeout=0,
        # 支援斷點續傳
        conditional=True
    )
```

### 4. 網路層級檢查

**檢查本地到 Cloudflare 的連接品質**

```bash
# 測試到 Cloudflare 的延遲
ping 1.1.1.1

# 測試 Cloudflare Tunnel 狀態
cloudflared tunnel info 14a68aa7-97b1-4bc2-bf66-48961589b1c7

# 檢查當前連接
cloudflared tunnel list
```

### 5. 進階優化選項

#### A. 增加 Cloudflare Tunnel 並發連接

編輯配置檔案（已包含在 config 中）：

```yaml
# 預設 4 個連接，可增加到 8-16 個（視網路狀況）
# 注意：太多連接可能適得其反
# connections: 8
```

#### B. 使用 Argo Smart Routing（付費功能）

- 優化全球路由，減少延遲
- 適合國際用戶訪問
- 費用：$5/月 + $0.1/GB

#### C. Cloudflare Stream（專為影片優化，付費）

如果主要下載影片，考慮使用 Cloudflare Stream：
- 專為影片傳輸優化
- 自動轉碼和 CDN 加速

## 診斷工具

### 測試下載速度

```bash
# 測試直接下載（不透過 Cloudflare）
curl -o /dev/null http://localhost:5001/api/download/test.zip

# 測試透過 Cloudflare 下載
curl -o /dev/null https://cw1005host.com/api/download/test.zip

# 比較兩者速度差異
```

### 檢查 Cloudflare 日誌

```bash
# 查看 Tunnel 日誌
tail -f ~/Documents/Py/TGDL/cloudflare_tunnel.log

# 查看是否有連接問題、逾時等
```

### 使用瀏覽器開發者工具

1. 開啟 Chrome DevTools (F12)
2. Network 標籤
3. 下載檔案時觀察：
   - **Waiting (TTFB)**: 如果很長，是伺服器或 Cloudflare 處理慢
   - **Content Download**: 如果很長，是頻寬問題
   - **Protocol**: 應該顯示 `h3` (HTTP/3) 或 `h2` (HTTP/2)

## 預期速度

### 理想情況下

- **本地下載**: 接近磁碟 I/O 速度（100+ MB/s）
- **透過 Cloudflare Free Plan**:
  - 台灣本地用戶: 10-50 MB/s
  - 國際用戶: 5-20 MB/s
- **透過 Cloudflare + Argo**:
  - 可提升 30-50%

### 影響因素

1. **上傳頻寬限制**: Cloudflare Tunnel 受限於你的上傳速度
2. **Cloudflare Free Plan 限制**: 可能有速率限制（未公開具體數值）
3. **用戶端網路**: 下載速度也受限於用戶的網路品質
4. **檔案大小**: 非常大的檔案（>1GB）可能觸發 Cloudflare 的速率限制

## 替代方案

如果 Cloudflare Tunnel 速度仍不理想，考慮：

### 1. 使用 Cloudflare R2 + Workers

上傳檔案到 R2，透過 Workers 提供下載：
- 全球 CDN 加速
- 無頻寬費用（egress free）
- 更適合大檔案分發

### 2. 直接使用 Cloudflare CDN

將下載檔案放到有 Cloudflare CDN 的儲存服務：
- AWS S3 + CloudFront
- Backblaze B2 + Cloudflare
- Cloudflare R2

### 3. ngrok Pro（替代方案）

如果只是臨時需要公網訪問：
```bash
ngrok http 5001
```
- 速度可能更快（直接連接）
- 但穩定性和安全性不如 Cloudflare

## 重新啟動 Tunnel 套用配置

```bash
# 停止當前 Tunnel
./stop_cloudflare_tunnel.sh

# 重新啟動（套用新配置）
./start_cloudflare_tunnel.sh

# 檢查是否正常運作
curl https://cw1005host.com
```

## 監控和調整

建議持續監控並調整：

1. **觀察實際下載速度**
2. **調整 originRequest 參數**
3. **根據用戶反饋優化**
4. **考慮升級 Cloudflare 付費方案**（如果預算允許）

## 常見問題

### Q: 為什麼速度還是很慢？

A: 檢查：
1. 本地上傳頻寬（`speedtest-cli --upload`）
2. Cloudflare Dashboard 設定是否正確
3. 是否被 Cloudflare 速率限制（檢查日誌）
4. 用戶端網路是否正常

### Q: HTTP/3 (QUIC) 一定更快嗎？

A: 不一定，視網路環境而定。可以嘗試：
```yaml
# 改回 HTTP/2
protocol: http2
```

### Q: 是否需要付費方案？

A: Free Plan 適合：
- 個人使用
- 低流量場景
- 檔案 < 500MB

需要付費如果：
- 大量並發下載
- 檔案 > 1GB
- 需要更好的全球速度（Argo）

---

最後更新: 2025-10-07
