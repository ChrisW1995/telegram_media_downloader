# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Telegram Media Downloader - a Python application that downloads media files from Telegram channels and chats. It supports both one-time downloads and continuous bot operation.

## Development Commands

### Setup
```bash
# Install dependencies
make install

# Install development dependencies  
make dev_install

# For systems without make:
pip3 install -r requirements.txt
pip3 install -r dev-requirements.txt
```

### Code Quality
```bash
# Run type checking
make static_type_check
# Or directly: mypy media_downloader.py utils module --ignore-missing-imports

# Run linting
make pylint  
# Or directly: pylint media_downloader.py utils module -r y

# Run both type checking and linting
make style_check

# Run tests
make test
# Or directly: py.test --cov media_downloader --doctest-modules --cov utils --cov-report term-missing tests/
```

### Running the Application
```bash
# Main script - starts either web UI or one-time download
python3 media_downloader.py

# Web interface available at localhost:5001 (configurable via web_port in config.yaml)

# Quick start with automatic cleanup
./start_tgdl.sh [PORT]

# Fix database lock issues and restart
./fix_database_lock.sh [PORT]
```

### Web Interface Endpoints
- **`/`** - Main dashboard and traditional download interface
- **`/message_downloader`** - Modern message browser interface
- **`/message_downloader/login`** - Dedicated login page for Message Downloader
- **API endpoints**:
  - `/api/auth/*` - Authentication flow (phone, code, password, QR)
  - `/api/groups/*` - Group listing and message fetching
  - `/api/message_downloader_thumbnail/<chat_id>/<message_id>` - Thumbnail generation
  - `/api/fast_download/*` - Download queue management

### Utility Scripts
- **`fix_database_lock.sh`** - Session management script that:
  - Stops all running TGDL processes
  - Clears Telegram session SQLite locks (WAL/journal files)
  - Optionally restarts the application on specified port
- **`start_tgdl.sh`** - Quick start script for development that handles process cleanup and port management

## Architecture

### Core Components

- **`media_downloader.py`** - Main entry point and download logic
- **`module/app.py`** - Application class managing configuration, data persistence, and core application state
- **`module/bot.py`** - Telegram bot implementation for remote control via bot commands
- **`module/web.py`** - Flask web interface for browser-based control
- **`module/pyrogram_extension.py`** - Extended Pyrogram functionality and client management
- **`module/filter.py`** - Message filtering system based on date ranges and content
- **`module/cloud_drive.py`** - Cloud upload functionality (rclone, aligo)
- **`module/multiuser_auth.py`** - Multi-user authentication system for web interface
- **`module/session_storage.py`** - Session management for Fast Test and user authentication
- **`module/download_stat.py`** - Download statistics and progress tracking

### Configuration System

- **`config.yaml`** - Main configuration file containing:
  - Telegram API credentials (api_id, api_hash) 
  - Bot token for remote control
  - Chat configurations with download filters
  - Media types and file format preferences
  - Save paths and file naming conventions
  - Web interface settings
  - Cloud upload settings

- **`data.yaml`** - Runtime data storage for:
  - Download progress tracking
  - Failed download retry queue
  - Message ID bookmarks

### Download Flow

1. Application reads config.yaml and data.yaml
2. Initializes Pyrogram client with API credentials
3. For each configured chat:
   - Fetches message history using `get_chat_history_v2`
   - Applies filters to determine which messages to process
   - Downloads media files with organized directory structure
   - Updates progress in data.yaml
   - Optionally uploads to cloud storage

### File Organization

Downloads are saved with configurable directory structure via `file_path_prefix`:
- `chat_title` - Channel/group name
- `media_datetime` - Date-based folders (format configurable via `date_format`)
- `media_type` - Organized by media type

File naming supports prefix customization via `file_name_prefix`:
- `message_id` - Telegram message ID
- `file_name` - Original filename
- `caption` - Message caption text

## Key Features

- **Dual Operation Modes**: Web interface (localhost:5001) and Telegram bot control
- **Multi-user Web Interface**: Supports multiple Telegram accounts with separate authentication
- **Message Downloader**: Comprehensive browser-based interface for message browsing and downloading
- **Fast Test**: Quick message testing and preview functionality
- **Filtering System**: Date range and content-based filtering of messages
- **Cloud Integration**: Upload to cloud storage via rclone or aligo
- **Progress Tracking**: Persistent download state and retry mechanism
- **Multi-format Support**: Audio, video, photo, document, voice, animation
- **Custom Downloads**: Targeted download of specific message IDs
- **Session & Data Storage**: SQLite primarily for Telegram session management, with database architecture available for future expansion

### Message Downloader Interface (/message_downloader)

Modern web interface featuring authentication system, group browsing, selective downloading with Apple-inspired UI and modular architecture.

## Testing

Test files are organized in `tests/` with coverage for:
- Core downloader functionality
- Utility modules (crypto, file management, formatting)
- Application configuration and filters

## Code Style

- **Linting**: Configured via `pylintrc` with max line length 90
- **Type Checking**: mypy configuration in `mypy.ini`
- **Python Version**: Supports Python 3.7+

## Dependencies

- **Pyrogram**: Telegram client library (custom fork)
- **Flask**: Web interface framework
- **PyYAML**: Configuration file parsing
- **Rich/Loguru**: Enhanced logging and console output
- **Cryptographic Libraries**: For Telegram protocol support

## Development Notes

- 程式預設啟動在 5001 port
- 如果前一次有背景運行程式，修改程式碼後需要重新執行一次
- 重新執行環境建議直接使用 `./fix_database_lock.sh`
- 不需要關心 media_types 的變動
- Telegram session 鎖定問題使用 `fix_database_lock.sh` 腳本解決

## Critical Bug Fix Records

### Bot 進度更新問題修復 (2025-09-20)

**核心問題**: TaskNode ID 不匹配導致 bot 進度跳過更新

**問題根源**:
1. **雙重 TaskNode 系統存在**:
   - 主要 TaskNode: 用於 bot 進度報告，有唯一的 task_id
   - 單個訊息 TaskNode: 每個下載訊息創建時都會產生新的 task_id

2. **匹配失敗鏈**:
   ```
   download_stat.py (單個訊息 TaskNode)
   → 更新 download_result[chat_id][message_id]["task_id"]
   → bot 檢查時用主要 TaskNode 的 task_id 比較
   → task_id 不匹配 → 跳過進度顯示
   ```

**容易搞混的陷阱**:
- ❌ 誤以為所有 TaskNode 都是同一個
- ❌ 以為 TaskNode 統計更新了就會自動顯示在 bot
- ❌ 看到 "download_result has chats" 就以為有數據

**修復關鍵** (`module/custom_download.py:347-357`):
```python
# 統一 TaskNode ID - 確保單個訊息 TaskNode 使用與主要 TaskNode 相同的 task_id
main_task_node = getattr(self, 'task_node', None)
if main_task_node:
    node = TaskNode(
        chat_id=main_task_node.chat_id,
        task_id=main_task_node.task_id  # 關鍵：使用相同的 task_id
    )
```

**調試要點**:
1. 檢查 TaskNode ID 一致性：確保 download_result 中的 task_id 與 bot 檢查用的 task_id 相同
2. 驗證數據流向：`download_stat.py → download_result → _report_bot_status → bot 訊息`
3. 關注匹配條件：`task_id != node.task_id` 是最關鍵的過濾條件

**經驗教訓**: 在分佈式或多層架構中，對象標識符的一致性是確保數據正確流轉的關鍵

### Bot 進度更新系統架構修復完成 (2025-09-23)

**完整修復**: 成功恢復機器人進度更新功能到完全正常狀態

#### 核心架構組件

**1. TaskNode 統一管理系統**:
- **主要 TaskNode**: 機器人創建，包含完整的 bot、reply_message_id、task_id 信息
- **單個訊息 TaskNode**: 下載時創建，統一使用主要 TaskNode 的 task_id
- **關鍵修復**: `module/custom_download.py:347-357` 確保 TaskNode ID 統一

**2. 實時進度更新流程**:
```
下載完成事件 → _process_final_results()
→ 實時更新 TaskNode 統計 (success/failed/skip_download_task++)
→ 調用 report_bot_download_status()
→ 機器人立即收到進度通知
```

**3. 機器人進度報告系統**:
- **觸發條件**: `TaskNode.is_running = True` 且有 `bot`、`reply_message_id`
- **更新頻率**: 每 3 秒檢查 + 實時事件觸發
- **匹配機制**: `download_result[chat_id][message_id]["task_id"] == node.task_id`

**4. 任務完成通知系統** (`module/bot.py:101-137`):
- **智能狀態判斷**: 🎉完全成功 / ⚠️部分完成 / ❌下載失敗
- **詳細統計**: 成功率、總數、失敗數、跳過數
- **聊天信息**: 自動獲取群組名稱
- **Markdown 格式**: 美觀的完成報告

#### 關鍵程式碼位置

**TaskNode 創建與初始化**:
- `media_downloader.py:769`: `node.is_running = True` (一般下載)
- `module/bot.py:888,1060`: 機器人創建 TaskNode 時設置 `is_running = True`
- `module/custom_download.py:406`: Custom download TaskNode 初始化

**實時進度更新**:
- `module/custom_download.py:481-524`: 三種狀態的實時 TaskNode 更新和機器人通知
- `module/pyrogram_extension.py:793-812`: `report_bot_download_status` 函數

**機器人進度檢查**:
- `module/bot.py:254-271`: `update_reply_message` 每 3 秒掃描活躍任務
- `module/pyrogram_extension.py:882-886`: task_id 匹配邏輯

#### 修復後的完整流程

1. **任務啟動**: 機器人創建 TaskNode (含正確 task_id, bot, reply_message_id)
2. **下載進行**: 使用統一的 task_id 創建單個訊息 TaskNode
3. **進度記錄**: `download_stat.py` 記錄進度到 `download_result`
4. **實時更新**: 每個檔案完成後立即更新 TaskNode 統計並呼叫 `report_bot_download_status`
5. **定期檢查**: 機器人每 3 秒掃描 `is_running=True` 的 TaskNode
6. **進度匹配**: 透過 task_id 匹配 `download_result` 中的進度數據
7. **任務完成**: 自動發送詳細完成通知並移除 TaskNode

### 訊息縮圖取得機制

三層架構: 數據準備 (`multiuser_auth.py`) → API 後端 (`/api/message_downloader_thumbnail`) → 前端顯示，使用記憶體下載和 base64 Data URL 優化效能。


### Message Downloader 大型重構 (2025-09-21)

**重構目標**:
大規模代碼重構，將原本 3,693 行的單一 HTML 檔案分離為模組化架構，提升可維護性和開發效率

**問題分析**:
- 原始 `message_downloader.html` 檔案過於龐大，包含 1600+ 行 CSS 和複雜 JavaScript 邏輯
- 代碼混雜在 HTML 中，缺乏模組化設計，維護困難
- 無法有效重用樣式和邏輯組件

**重構架構**:

**CSS 模組化架構** (`module/static/css/message_downloader/`):
```
├── base.css          # 基礎樣式和變數系統
├── theme.css         # 主題管理（明亮/黑暗模式）
├── layout.css        # 佈局和結構樣式
├── components.css    # UI 元件樣式（按鈕、表單、卡片等）
├── chat.css          # 聊天介面和訊息氣泡樣式
├── controls.css      # 聊天控制和導航元件
├── animations.css    # 動畫效果和轉場
├── responsive.css    # 響應式設計和媒體查詢
└── main.css          # CSS 模組索引檔案
```

**JavaScript 模組化架構** (`module/static/js/message_downloader/`):
```
├── core.js           # 核心變數、常數和工具函數
├── theme.js          # 主題切換邏輯
├── auth.js           # Telegram 認證相關功能
├── groups.js         # 群組管理和側邊欄渲染
├── messages.js       # 訊息載入、渲染和滾動處理
├── selection.js      # 訊息選擇和下載管理
├── notifications.js  # 通知系統和進度追蹤
├── ui.js             # UI 交互邏輯和事件處理
├── main.js           # 應用程式初始化
└── index.js          # 模組架構說明文檔
```

**重構成果**:

**檔案大小對比**:
- **重構前**: 3,693 行混合代碼
- **重構後**: 245 行純 HTML + 19 個模組檔案
- **減少比例**: 93% 的代碼被分離到獨立模組

**模組載入順序**:
1. **基礎模組**: core.js (變數和工具) → theme.js (主題系統)
2. **功能模組**: auth.js (認證) → groups.js (群組管理) → messages.js (訊息處理)
3. **交互模組**: selection.js (選擇邏輯) → notifications.js (通知系統) → ui.js (UI 邏輯)
4. **初始化**: main.js (應用程式啟動)

**CSS 架構特點**:
- **變數系統**: 統一的主題變數定義，支援動態主題切換
- **模組化**: 按功能分類的樣式組織方式
- **響應式**: 完整的移動設備適配
- **Apple 風格**: 液體玻璃效果和現代設計語言

**JavaScript 架構特點**:
- **關注點分離**: 每個模組負責特定功能領域
- **依賴管理**: 清晰的模組依賴關係和載入順序
- **全域變數**: 統一管理的應用程式狀態
- **事件處理**: 模組化的用戶交互邏輯

**開發效益**:
1. **可維護性**: 代碼按功能組織，便於定位和修改
2. **可擴展性**: 新功能可以獨立模組的形式添加
3. **可重用性**: CSS 和 JS 組件可以在其他頁面中重用
4. **協作效率**: 多人開發時可以同時編輯不同模組
5. **調試便利**: 問題可以快速定位到特定模組

**向後兼容**:
- 保持所有現有功能完整性
- 原始檔案備份為 `message_downloader_backup.html`
- API 接口和用戶體驗保持不變
