# TGDL 部署指南

> 快速開始指南 - 5 分鐘設置雙環境系統

## 🎯 目標

- ✅ 產品版本 (Port 5001) - 穩定在線
- ✅ 開發版本 (Port 5002) - 測試新功能
- ✅ 公網訪問 (Cloudflare Tunnel) - 全球可訪問

## 📋 前置需求

- macOS/Linux 系統
- Python 3.7+
- Git
- Telegram API credentials (從 https://my.telegram.org/apps 獲取)

## 🚀 快速開始

### 1. 產品環境設置（3 分鐘）

```bash
# 1. 進入專案目錄
cd /Users/chriswang/Documents/Py/TGDL

# 2. 複製配置模板並填入您的 API 資訊
cp config.product.yaml config.yaml
vi config.yaml  # 編輯填入 api_hash, api_id

# 3. 啟動產品版本
./start_product.sh

# 4. 訪問測試
open http://localhost:5001/message_downloader
```

✅ **產品版本已啟動！**

### 2. 開發環境設置（2 分鐘）

```bash
# 1. 複製專案到開發目錄（使用 rsync 排除大檔案）
cd /Users/chriswang/Documents/Py
rsync -av --progress \
  --exclude='TGDL/' \
  --exclude='log/' \
  --exclude='sessions/' \
  --exclude='temp/' \
  --exclude='.telegram_sessions/' \
  --exclude='*.db' \
  --exclude='*.db-wal' \
  --exclude='*.db-shm' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  TGDL/ TGDL-dev/

# 2. 進入開發目錄
cd TGDL-dev

# 3. 切換到 develop 分支
git checkout develop

# 4. 複製並編輯開發配置
cp config_develop.yaml config.yaml
vi config.yaml  # 檢查配置（Port 應為 5002）

# 5. 啟動開發版本（腳本已包含在 develop 分支）
./start_develop.sh
```

✅ **開發環境已就緒！**

## 📊 日常使用

### 查看狀態

```bash
cd /Users/chriswang/Documents/Py/TGDL
./status.sh
```

### 啟動/停止服務

```bash
# 產品版本
./start_product.sh
./stop_product.sh

# 開發版本 (在 TGDL-dev/ 目錄)
./start_develop.sh
./stop_develop.sh
```

### 查看日誌

```bash
# 產品版本
tail -f output.log

# 開發版本
cd ../TGDL-dev
tail -f output.log
```

## 🌐 公網訪問設置（Cloudflare Tunnel）

### 前置需求

- 擁有一個網域
- Cloudflare 帳號

### 設置步驟

1. **安裝 cloudflared**
   ```bash
   brew install cloudflare/cloudflare/cloudflared
   ```

2. **登入 Cloudflare**
   ```bash
   cloudflared tunnel login
   ```

3. **建立 Tunnel**
   ```bash
   cloudflared tunnel create tgdl
   ```

4. **配置 Tunnel**
   ```bash
   cd /Users/chriswang/Documents/Py/TGDL
   cp cloudflare_tunnel_config.yml.example cloudflare_tunnel_config.yml
   vi cloudflare_tunnel_config.yml
   ```

   編輯內容：
   ```yaml
   tunnel: YOUR_TUNNEL_ID  # 從步驟 3 獲取
   credentials-file: /Users/chriswang/.cloudflared/YOUR_TUNNEL_ID.json

   ingress:
     - hostname: tgdl.your-domain.com
       service: http://localhost:5001
     - service: http_status:404
   ```

5. **配置 DNS**
   ```bash
   cloudflared tunnel route dns tgdl cw1005host.com
   ```

6. **驗證 Tunnel 設置**
   ```bash
   # 確認 Tunnel 資訊
   cloudflared tunnel info tgdl

   # 確認 DNS 解析
   nslookup cw1005host.com

   # 應該看到 Cloudflare 的 IP (104.21.x.x 或 172.67.x.x)
   ```

7. **Cloudflare Dashboard 設置** ⚠️ 重要

   登入 Cloudflare Dashboard (https://dash.cloudflare.com):

   a. **SSL/TLS 設置**
   - 進入域名 → SSL/TLS
   - 加密模式選擇: **"Flexible"** (本地用 HTTP)
   - 或選擇 **"Full"** (如果本地有 SSL 證書)

   b. **DNS 設置檢查**
   - 進入域名 → DNS → Records
   - 確認有 CNAME 記錄: `cw1005host.com` → `14a68aa7-97b1-4bc2-bf66-48961589b1c7.cfargotunnel.com`
   - 確保 **Proxy status 為橘色雲朵** (Proxied)

   c. **Zero Trust 設置** (可選,增強安全性)
   - 進入 Zero Trust → Access → Applications
   - 為你的應用設置訪問策略 (IP 白名單、Email 驗證等)

8. **啟動 Tunnel**
   ```bash
   ./start_cloudflare_tunnel.sh
   ```

9. **測試訪問**
   ```bash
   # 測試 HTTP 連線
   curl -I http://cw1005host.com/message_downloader

   # 測試 HTTPS 連線
   curl -I https://cw1005host.com/message_downloader

   # 瀏覽器訪問
   open https://cw1005host.com/message_downloader
   ```

✅ **公網訪問已啟用！**

**注意事項:**
- HTTP 和 HTTPS 都應該正常工作
- 第一次訪問可能需要 1-2 分鐘等待 DNS 傳播
- 如遇到 SSL 錯誤,請檢查 Cloudflare Dashboard 的 SSL/TLS 設置
- 建議使用 HTTPS 以確保安全性

### 安全性建議

1. **啟用 Cloudflare Access** (Zero Trust)
   ```bash
   # 在 Cloudflare Dashboard 設置訪問策略
   # 限制只有特定 IP 或通過 Email 驗證才能訪問
   ```

2. **啟用 Web Application Firewall (WAF)**
   - Cloudflare Dashboard → Security → WAF
   - 啟用 Managed Rules 防護常見攻擊

3. **設置 Rate Limiting**
   - 防止暴力破解和 DDoS 攻擊
   - Security → Rate Limiting

4. **監控 Tunnel 健康狀態**
   ```bash
   # 查看 Tunnel 連線狀態
   cloudflared tunnel info tgdl

   # 查看即時日誌
   tail -f cloudflare_tunnel.log

   # 檢查錯誤
   grep -i error cloudflare_tunnel.log
   ```

5. **自動重啟 Tunnel** (使用 launchd 或 systemd)
   - macOS: 建立 launchd plist
   - Linux: 建立 systemd service

### Tunnel 維護

**定期檢查:**
```bash
# 檢查 Tunnel 版本
cloudflared version

# 更新 cloudflared
brew upgrade cloudflared  # macOS

# 查看 Tunnel 統計
cloudflared tunnel info tgdl
```

**清理舊連線:**
```bash
# 列出所有 Tunnel
cloudflared tunnel list

# 刪除未使用的 Tunnel
cloudflared tunnel delete <tunnel-name>
```

## 🔄 開發到產品部署流程

### 方法：手動部署

```bash
# 1. 在開發環境測試完成
cd /Users/chriswang/Documents/Py/TGDL-dev
git add .
git commit -m "feat: 新功能"
git push origin develop

# 2. 切換到產品環境
cd /Users/chriswang/Documents/Py/TGDL

# 3. 停止產品版本
./stop_product.sh

# 4. 合併開發分支
git checkout master
git merge develop

# 5. 建立版本標籤
git tag -a v1.1.0 -m "Release v1.1.0"
git push origin master --tags

# 6. 重啟產品版本
./start_product.sh

# 7. 重啟 Tunnel（如果有）
./stop_cloudflare_tunnel.sh
./start_cloudflare_tunnel.sh
```

## 🛠️ 常見問題

### Q: Port 被佔用怎麼辦？

```bash
# 查看佔用 Port 的進程
lsof -i :5001

# 強制停止
./stop_product.sh
```

### Q: 資料庫鎖定錯誤？

```bash
# 使用現有的修復腳本
./fix_database_lock.sh 5001
```

### Q: Cloudflare Tunnel 斷線？

```bash
# 重啟 Tunnel
./stop_cloudflare_tunnel.sh
./start_cloudflare_tunnel.sh

# 查看日誌
tail -f cloudflare_tunnel.log

# 檢查 Tunnel 狀態
cloudflared tunnel info tgdl

# 檢查連線數
ps aux | grep cloudflared
```

### Q: Cloudflare Tunnel 無法訪問？

```bash
# 1. 檢查本地服務是否運行
curl -I http://localhost:5001/message_downloader

# 2. 檢查 Tunnel 是否運行
ps aux | grep cloudflared

# 3. 檢查 DNS 解析
nslookup cw1005host.com

# 4. 測試 HTTP 訪問
curl -I http://cw1005host.com/message_downloader

# 5. 測試 HTTPS 訪問
curl -I https://cw1005host.com/message_downloader

# 6. 檢查 Tunnel 日誌
tail -50 cloudflare_tunnel.log
```

**常見原因:**
- 本地服務未啟動 (Port 5001)
- Cloudflare Tunnel 未運行
- DNS 記錄未正確設置
- 瀏覽器快取需要清除

### Q: 如何清除所有資料重新開始？

```bash
# ⚠️ 注意：這會刪除所有下載記錄和 Session

# 停止服務
./stop_product.sh

# 清除資料
rm -rf .telegram_sessions/
rm -f tgdl.db tgdl.db-*
rm -f user_sessions.json

# 重新啟動
./start_product.sh
```

## 📞 支援

- **文檔**: `/Users/chriswang/Documents/Py/TGDL/DEPLOYMENT_PLAN.md`
- **GitHub**: https://github.com/ChrisW1995/telegram_media_downloader
- **問題回報**: GitHub Issues

## 🎉 完成！

您現在擁有：
- ✅ 穩定的產品環境 (Port 5001)
- ✅ 獨立的開發環境 (Port 5002)
- ✅ 公網訪問能力 (Cloudflare Tunnel)
- ✅ 完整的管理腳本

開始使用您的 TGDL 系統吧！ 🚀
