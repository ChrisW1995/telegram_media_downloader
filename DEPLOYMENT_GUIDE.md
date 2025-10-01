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
# 1. 複製專案到開發目錄
cd /Users/chriswang/Documents/Py
cp -r TGDL TGDL-dev

# 2. 進入開發目錄
cd TGDL-dev

# 3. 切換到 develop 分支
git checkout develop

# 4. 複製開發配置
cp config.develop.yaml config.yaml
vi config.yaml  # 填入 API 資訊（可與產品版本相同）

# 5. 複製開發腳本（從產品版本）
cp ../TGDL/start_product.sh start_develop.sh
cp ../TGDL/stop_product.sh stop_develop.sh

# 6. 修改開發腳本的變數
sed -i '' 's/PORT=5001/PORT=5002/g' start_develop.sh
sed -i '' 's/PORT=5001/PORT=5002/g' stop_develop.sh
sed -i '' 's/.tgdl_pid/.tgdl_dev_pid/g' start_develop.sh
sed -i '' 's/.tgdl_pid/.tgdl_dev_pid/g' stop_develop.sh

# 7. 啟動開發版本
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
   cloudflared tunnel route dns tgdl tgdl.your-domain.com
   ```

6. **啟動 Tunnel**
   ```bash
   ./start_cloudflare_tunnel.sh
   ```

7. **測試訪問**
   ```bash
   open https://tgdl.your-domain.com/message_downloader
   ```

✅ **公網訪問已啟用！**

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
```

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
