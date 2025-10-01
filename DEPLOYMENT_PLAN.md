# TGDL 產品/開發雙版本部署方案 + Local Expose 公開訪問

> **版本**: v1.0.0
> **建立日期**: 2025-10-01
> **狀態**: 已建立 Git Tag `v1.0.0-product` 和 `develop` 分支

## 📋 目標

1. 建立 **Product** (5001 port) 和 **Develop** (5002 port) 兩個獨立運行環境
2. 產品版本保持穩定在線，開發版本用於測試新功能
3. 使用 **Cloudflare Tunnel** 將產品版本發佈到公網
4. 提供完整的管理腳本和部署文檔

## 🌐 Local Expose 方案：Cloudflare Tunnel（推薦）

### 為什麼選擇 Cloudflare Tunnel？

| 特性 | 說明 |
|------|------|
| 💰 **成本** | 完全免費（只需擁有一個網域，約 $8/年） |
| ⚡ **效能** | 全球 CDN 網路，速度最快 |
| 🔒 **安全** | 自動 HTTPS + DDoS 防護 |
| 🎯 **穩定** | 企業級可靠性，不像 localtunnel 容易斷線 |
| 🌍 **網域** | 自定義網域支援 |
| 📊 **流量** | 無流量限制（ngrok 免費版有限制） |

### 方案對比

| 方案 | 免費版 | 優點 | 缺點 | 適用場景 |
|------|--------|------|------|----------|
| **Cloudflare Tunnel** ⭐ | ✅ 完全免費 | 速度快、穩定、自定義網域、HTTPS | 需要網域 | **生產環境（推薦）**|
| **ngrok** | 有限免費 | 設定簡單、功能豐富 | 免費版限制多、隨機網址 | 臨時測試 |
| **localtunnel** | ✅ 完全免費 | 極簡單 | 不穩定、專案少維護 | 快速展示 |
| **Tailscale** | ✅ 免費 | 安全、P2P | 需要安裝客戶端 | 私密訪問 |

## 🏗️ 完整架構設計

```
本地環境 (Mac)
├── /Users/chriswang/Documents/Py/TGDL/
│   │                                   # 📦 Product 版本 (Port 5001)
│   ├── .git/                           # Git Repository (master 分支)
│   ├── config.yaml                     # 產品配置 (web_port: 5001)
│   ├── tgdl.db                         # 產品資料庫
│   ├── .telegram_sessions/             # 產品 Session
│   ├── TGDL/unified_downloads/         # 產品下載目錄
│   ├── .tgdl_pid                       # 產品 PID 檔案
│   ├── output.log                      # 產品 Log
│   │
│   ├── 📜 管理腳本
│   ├── start_product.sh                # 啟動產品版本
│   ├── stop_product.sh                 # 停止產品版本
│   ├── start_cloudflare_tunnel.sh      # 啟動 Cloudflare Tunnel
│   ├── stop_cloudflare_tunnel.sh       # 停止 Cloudflare Tunnel
│   ├── restart_all.sh                  # 重啟產品版本和 Tunnel
│   ├── status.sh                       # 查看所有服務狀態
│   │
│   ├── 📋 配置檔案
│   ├── config.product.yaml             # 產品配置模板
│   ├── cloudflare_tunnel_config.yml    # Cloudflare Tunnel 配置
│   ├── .env.product                    # 產品環境變數
│   │
│   ├── 📖 文檔
│   ├── DEPLOYMENT_PLAN.md              # 本計劃檔案
│   ├── DEPLOYMENT_GUIDE.md             # 部署指南
│   ├── CLOUDFLARE_TUNNEL_SETUP.md      # Cloudflare Tunnel 設置教學
│   └── ENVIRONMENT_MANAGEMENT.md       # 環境管理說明
│
│   └── [Cloudflare Tunnel] ──────────> 🌍 https://tgdl.yourdomain.com
│
└── /Users/chriswang/Documents/Py/TGDL-dev/
    │                                   # 🔧 Develop 版本 (Port 5002)
    ├── .git/                           # Git Repository (develop 分支)
    ├── config.yaml                     # 開發配置 (web_port: 5002)
    ├── tgdl_dev.db                     # 開發資料庫
    ├── .telegram_sessions_dev/         # 開發 Session
    ├── TGDL_DEV/downloads/             # 開發下載目錄
    ├── .tgdl_dev_pid                   # 開發 PID 檔案
    ├── output_dev.log                  # 開發 Log
    │
    ├── 📜 管理腳本
    ├── start_develop.sh                # 啟動開發版本
    ├── stop_develop.sh                 # 停止開發版本
    ├── deploy_to_product.sh            # 部署到產品環境
    ├── status.sh                       # 查看服務狀態
    │
    ├── 📋 配置檔案
    ├── config.develop.yaml             # 開發配置模板
    └── .env.develop                    # 開發環境變數
    │
    └── [本地訪問] ────────────────────> 🏠 http://localhost:5002
```

## 🔧 配置差異總覽

| 項目 | Product (公開) | Develop (內網) |
|------|----------------|----------------|
| **訪問地址** | 🌍 https://tgdl.yourdomain.com<br/>🏠 http://localhost:5001 | 🏠 http://localhost:5002 |
| **Port** | 5001 | 5002 |
| **Git 分支** | master | develop |
| **資料庫** | tgdl.db | tgdl_dev.db |
| **PID 檔案** | .tgdl_pid | .tgdl_dev_pid |
| **Session 目錄** | .telegram_sessions/ | .telegram_sessions_dev/ |
| **下載路徑** | TGDL/unified_downloads | TGDL_DEV/downloads |
| **Log 檔案** | output.log | output_dev.log |
| **Bot 保存路徑** | /Users/chriswang/.../TGDL/unified_downloads | /Users/chriswang/.../TGDL_DEV/downloads |
| **Cloudflare Tunnel** | ✅ 啟用 | ❌ 關閉 |
| **用途** | 穩定運行、公開服務 | 開發測試、功能驗證 |

## 📝 實施計劃

### ✅ 階段 1: Git 版本管理（已完成）

- [x] 提交所有當前修改（跳轉功能、UI 優化）
- [x] 建立 tag: `v1.0.0-product`
- [x] 建立 `develop` 分支
- [x] 推送到 remote

**執行結果**:
```bash
Commit: 8eba81f - feat: Message Downloader 訊息快速跳轉功能
Tag: v1.0.0-product
Branch: develop (已創建並推送)
```

### 階段 2: 建立開發環境目錄

**步驟**:
```bash
# 1. 複製整個 TGDL 目錄到 TGDL-dev
cd /Users/chriswang/Documents/Py
cp -r TGDL TGDL-dev

# 2. 進入開發目錄並切換分支
cd TGDL-dev
git checkout develop

# 3. 清理不需要的檔案
rm -f .tgdl_pid
rm -f tgdl.db tgdl.db-wal tgdl.db-shm
rm -rf .telegram_sessions/

# 4. 複製配置檔案為開發版本
cp config.yaml config.yaml.backup
```

### 階段 3: 創建管理腳本

#### 3.1 產品環境腳本（在 TGDL/ 目錄）

1. **`start_product.sh`** - 啟動產品版本
2. **`stop_product.sh`** - 停止產品版本
3. **`start_cloudflare_tunnel.sh`** - 啟動 Cloudflare Tunnel
4. **`stop_cloudflare_tunnel.sh`** - 停止 Cloudflare Tunnel
5. **`restart_all.sh`** - 重啟產品版本和 Tunnel

#### 3.2 開發環境腳本（在 TGDL-dev/ 目錄）

6. **`start_develop.sh`** - 啟動開發版本
7. **`stop_develop.sh`** - 停止開發版本
8. **`deploy_to_product.sh`** - 部署到產品環境

#### 3.3 通用腳本

9. **`status.sh`** - 查看所有服務狀態（兩個目錄都有）

### 階段 4: 創建配置檔案

1. **`config.product.yaml`** - 產品環境配置模板
2. **`config.develop.yaml`** - 開發環境配置模板
3. **`cloudflare_tunnel_config.yml`** - Cloudflare Tunnel 配置
4. **`.env.product`** - 產品環境變數
5. **`.env.develop`** - 開發環境變數

### 階段 5: 創建文檔

1. **`DEPLOYMENT_PLAN.md`** ✅ - 本計劃檔案（已創建）
2. **`DEPLOYMENT_GUIDE.md`** - 完整部署指南
3. **`CLOUDFLARE_TUNNEL_SETUP.md`** - Cloudflare Tunnel 設置教學
4. **`ENVIRONMENT_MANAGEMENT.md`** - 環境管理說明

### 階段 6: 更新 Git 配置

1. 更新 `.gitignore` - 添加開發環境特定忽略規則
2. 建立 `.gitignore.develop` - 開發環境專用忽略規則

## 📊 日常工作流程

### 🔧 開發新功能

```bash
# 1. 進入開發環境
cd /Users/chriswang/Documents/Py/TGDL-dev

# 2. 確認在 develop 分支
git checkout develop
git pull origin develop

# 3. 修改代碼...
# 編輯檔案、添加新功能

# 4. 啟動開發版本測試
./start_develop.sh

# 5. 訪問測試
open http://localhost:5002/message_downloader

# 6. 查看運行狀態
./status.sh

# 7. 滿意後提交變更
git add .
git commit -m "feat: 新增某功能"
git push origin develop

# 8. 停止開發版本（可選）
./stop_develop.sh
```

### 🚢 部署到產品

```bash
# 在開發目錄執行部署腳本
cd /Users/chriswang/Documents/Py/TGDL-dev
./deploy_to_product.sh

# 腳本會自動執行以下步驟：
# 1. 檢查當前在 develop 分支
# 2. 拉取最新的 develop 分支
# 3. 停止產品版本
# 4. 切換到產品目錄
# 5. 切換到 master 分支
# 6. 合併 develop 分支
# 7. 建立新的版本 tag
# 8. 推送到 remote
# 9. 重啟產品版本
# 10. 重啟 Cloudflare Tunnel（如果有運行）
# 11. 切換回開發目錄
```

### 📊 檢查狀態

```bash
# 在任一目錄執行
./status.sh

# 輸出示例：
# ═══════════════════════════════════════════════════════════
# 📊 TGDL 運行狀態
# ═══════════════════════════════════════════════════════════
#
# Product (Port 5001):
#   ✅ 運行中 (PID: 12345)
#   🌍 公網訪問: https://tgdl.yourdomain.com
#   🏠 本地訪問: http://localhost:5001
#   📂 Git Branch: master
#   🏷️  Git Tag: v1.2.3-product
#   📊 已運行: 2小時34分
#
# Develop (Port 5002):
#   ✅ 運行中 (PID: 12346)
#   🏠 本地訪問: http://localhost:5002
#   📂 Git Branch: develop
#   📊 已運行: 45分鐘
#
# Cloudflare Tunnel:
#   ✅ 運行中 (PID: 12347)
#   🌍 連接到: tgdl.yourdomain.com
#   📊 已運行: 2小時30分
#
# ═══════════════════════════════════════════════════════════
```

### 🛑 停止服務

```bash
# 停止產品版本
cd /Users/chriswang/Documents/Py/TGDL
./stop_product.sh

# 停止開發版本
cd /Users/chriswang/Documents/Py/TGDL-dev
./stop_develop.sh

# 停止 Cloudflare Tunnel
cd /Users/chriswang/Documents/Py/TGDL
./stop_cloudflare_tunnel.sh
```

### 🔄 重啟服務

```bash
# 重啟產品版本和 Tunnel
cd /Users/chriswang/Documents/Py/TGDL
./restart_all.sh
```

## 🛡️ 安全考量

### Cloudflare Tunnel 安全特性

| 特性 | 說明 |
|------|------|
| 🔒 **HTTPS 加密** | 自動 SSL/TLS 證書，所有流量加密 |
| 🛡️ **DDoS 防護** | Cloudflare 的 DDoS 防護免費啟用 |
| 🔥 **防火牆** | 不需要開放本地端口，更安全 |
| 👤 **存取控制** | 可設定 Cloudflare Access 認證 |
| 📊 **流量分析** | Cloudflare Dashboard 即時監控 |

### 建議的安全設置

#### 1. Cloudflare Access（免費）
```yaml
# 添加登入保護
- 設定電子郵件認證
- 設定 Google/GitHub OAuth
- 設定 IP 白名單
```

#### 2. 應用層安全
```python
# Flask 安全標頭
- Content-Security-Policy
- X-Frame-Options
- X-Content-Type-Options
```

#### 3. 速率限制
```yaml
# Cloudflare Rate Limiting
- 每分鐘最多 100 次請求
- 下載 API 每分鐘 10 次
```

#### 4. 監控告警
```yaml
# Cloudflare Notifications
- 異常流量告警
- 錯誤率告警
- 延遲告警
```

## 📦 檔案清單

### 產品環境（TGDL/）

#### 🔧 管理腳本（5 個）
- [ ] `start_product.sh` - 啟動產品版本
- [ ] `stop_product.sh` - 停止產品版本
- [ ] `start_cloudflare_tunnel.sh` - 啟動 Tunnel
- [ ] `stop_cloudflare_tunnel.sh` - 停止 Tunnel
- [ ] `restart_all.sh` - 重啟所有服務

#### 📋 配置檔案（3 個）
- [ ] `config.product.yaml` - 產品配置模板
- [ ] `cloudflare_tunnel_config.yml` - Tunnel 配置
- [ ] `.env.product` - 產品環境變數

#### 📖 文檔（4 個）
- [x] `DEPLOYMENT_PLAN.md` - 本計劃檔案 ✅
- [ ] `DEPLOYMENT_GUIDE.md` - 部署指南
- [ ] `CLOUDFLARE_TUNNEL_SETUP.md` - Tunnel 設置教學
- [ ] `ENVIRONMENT_MANAGEMENT.md` - 環境管理說明

#### ⚙️ Git 配置（1 個）
- [ ] `.gitignore` 更新 - 添加環境特定忽略規則

### 開發環境（TGDL-dev/）

#### 🔧 管理腳本（3 個）
- [ ] `start_develop.sh` - 啟動開發版本
- [ ] `stop_develop.sh` - 停止開發版本
- [ ] `deploy_to_product.sh` - 部署到產品

#### 📋 配置檔案（1 個）
- [ ] `config.develop.yaml` - 開發配置模板
- [ ] `.env.develop` - 開發環境變數

#### 🔄 通用（1 個）
- [ ] `status.sh` - 狀態查看（兩個目錄都有）

## ✅ 進度檢查清單

### 階段 1: Git 版本管理
- [x] 提交當前所有修改到 master
- [x] 建立 tag `v1.0.0-product`
- [x] 建立並推送 `develop` 分支

### 階段 2: 目錄和配置
- [ ] 複製 TGDL 到 TGDL-dev
- [ ] 修改開發環境配置
- [ ] 清理開發環境不需要的檔案

### 階段 3: 創建腳本
- [ ] 創建產品環境腳本（5 個）
- [ ] 創建開發環境腳本（3 個）
- [ ] 創建狀態查看腳本
- [ ] 賦予所有腳本執行權限

### 階段 4: 創建配置
- [ ] 創建產品配置模板
- [ ] 創建開發配置模板
- [ ] 創建 Cloudflare Tunnel 配置
- [ ] 創建環境變數檔案

### 階段 5: 創建文檔
- [x] 匯出 DEPLOYMENT_PLAN.md
- [ ] 撰寫 DEPLOYMENT_GUIDE.md
- [ ] 撰寫 CLOUDFLARE_TUNNEL_SETUP.md
- [ ] 撰寫 ENVIRONMENT_MANAGEMENT.md

### 階段 6: Git 配置
- [ ] 更新 .gitignore
- [ ] 測試 Git 工作流程

### 階段 7: 測試運行
- [ ] 測試產品版本啟動
- [ ] 測試開發版本啟動
- [ ] 測試雙版本同時運行
- [ ] 測試停止腳本
- [ ] 測試狀態查看腳本

### 階段 8: Cloudflare Tunnel（需要網域）
- [ ] 安裝 cloudflared
- [ ] 註冊 Cloudflare 帳號
- [ ] 添加網域到 Cloudflare
- [ ] 建立 Tunnel
- [ ] 配置 DNS
- [ ] 測試公網訪問

### 階段 9: 部署測試
- [ ] 在開發環境做測試修改
- [ ] 執行 deploy_to_product.sh
- [ ] 驗證產品環境更新成功
- [ ] 驗證 Cloudflare Tunnel 正常

### 階段 10: 文檔完善
- [ ] 補充實際操作細節
- [ ] 添加故障排除案例
- [ ] 添加常見問題 FAQ

## 🎯 最終效果

### 訪問方式

| 環境 | 訪問地址 | 說明 |
|------|----------|------|
| **產品版本（公開）** | 🌍 https://tgdl.yourdomain.com | 全球訪問，HTTPS 加密 |
| **產品版本（本地）** | 🏠 http://localhost:5001 | 本地開發和調試 |
| **開發版本（本地）** | 🏠 http://localhost:5002 | 功能開發和測試 |

### 管理便利性

- ✅ 一鍵啟動/停止任一版本
- ✅ 一鍵部署開發到產品
- ✅ 即時查看運行狀態
- ✅ Git 版本清晰管理
- ✅ 自動 HTTPS 和 CDN 加速
- ✅ 完整的操作文檔

### 隔離性

| 項目 | 隔離狀態 | 說明 |
|------|----------|------|
| **代碼** | ✅ 完全隔離 | 不同 Git 分支和目錄 |
| **配置** | ✅ 完全隔離 | 獨立的 config.yaml |
| **資料庫** | ✅ 完全隔離 | 不同的 DB 檔案 |
| **Session** | ✅ 完全隔離 | 不同的 Session 目錄 |
| **下載** | ✅ 完全隔離 | 不同的下載路徑 |
| **Log** | ✅ 完全隔離 | 獨立的 Log 檔案 |
| **進程** | ✅ 完全隔離 | 不同的 PID 和 Port |

## 🎉 執行此計劃後，您將擁有：

1. ✅ **穩定的產品環境**
   - Port 5001
   - 公網可訪問（https://tgdl.yourdomain.com）
   - Git master 分支
   - 持續穩定運行

2. ✅ **獨立的開發環境**
   - Port 5002
   - 本地測試（http://localhost:5002）
   - Git develop 分支
   - 功能驗證和測試

3. ✅ **完整的腳本工具**
   - 9 個管理腳本
   - 一鍵操作
   - 狀態監控

4. ✅ **清晰的 Git 分支管理**
   - master 分支：穩定的產品版本
   - develop 分支：開發和測試
   - 版本標籤管理

5. ✅ **免費的公網訪問**
   - Cloudflare Tunnel
   - 全球 CDN 加速
   - 無流量限制

6. ✅ **完整的操作文檔**
   - 4 份 Markdown 文檔
   - 詳細的操作指南
   - 故障排除手冊

7. ✅ **安全的 HTTPS 加密**
   - 自動 SSL 證書
   - DDoS 防護
   - 存取控制（可選）

8. ✅ **完全的環境隔離**
   - 配置獨立
   - 資料庫獨立
   - 進程獨立

---

## 📞 支援和故障排除

### 常見問題

1. **Q: 如何查看當前運行的服務？**
   - A: 執行 `./status.sh` 查看所有服務狀態

2. **Q: 產品版本和開發版本可以同時運行嗎？**
   - A: 可以！它們使用不同的 Port 和配置，完全獨立

3. **Q: 如何回滾到之前的版本？**
   - A: 使用 `git checkout <tag>` 切換到特定版本的 tag

4. **Q: Cloudflare Tunnel 斷線怎麼辦？**
   - A: 執行 `./restart_cloudflare_tunnel.sh` 重啟 Tunnel

5. **Q: 如何更新產品版本？**
   - A: 在開發環境測試後，執行 `./deploy_to_product.sh` 自動部署

### 故障排除

詳細的故障排除指南請參考 `DEPLOYMENT_GUIDE.md` 文檔。

### 聯絡資訊

- **文檔位置**: `/Users/chriswang/Documents/Py/TGDL/`
- **Git Repository**: https://github.com/ChrisW1995/telegram_media_downloader
- **產品版本**: master 分支
- **開發版本**: develop 分支

---

## 📝 更新日誌

### v1.0.0 - 2025-10-01
- ✅ 建立初始部署計劃
- ✅ 建立 Git tag `v1.0.0-product`
- ✅ 建立 `develop` 分支
- ✅ 匯出 DEPLOYMENT_PLAN.md

---

**總共將創建：19 個新檔案（9 腳本 + 5 配置 + 4 文檔 + 1 Git 更新）**

> 📌 **下一步**: 繼續執行階段 2-10，創建所有管理腳本和配置檔案。
