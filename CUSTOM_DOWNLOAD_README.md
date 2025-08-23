# 自定義下載功能 (Custom Download Feature)

這個功能允許您指定特定的訊息 ID 進行下載，這些訊息可以來自不同的聊天/頻道。

## 功能特色

- ✅ 指定特定訊息 ID 下載
- ✅ 支援多個不同聊天的訊息
- ✅ 自動跳過已下載的訊息
- ✅ 記錄下載歷史
- ✅ 失敗重試機制
- ✅ 互動式管理介面 (推薦)
- ✅ 命令行管理工具

## 🌟 推薦：使用互動式選單管理器

### 啟動互動式選單管理器
```bash
python3 interactive_menu_manager.py
```

**操作方式：**
- 🖥️ **真實終端機**：使用 ↑↓ 鍵選擇，Enter 確認
- 💻 **Claude Code/其他環境**：使用 w(上) s(下) 選擇，Enter 確認

### 功能介紹
- 📁 **群組管理**：新增/刪除群組，管理訊息 ID
- 🔽 **智慧下載**：可選擇全部下載或特定群組下載
- 📊 **歷史查看**：查看下載成功/失敗的記錄
- ⚙️  **系統設定**：啟用/停用自定義下載模式

### 使用流程
1. 執行 `python3 interactive_download_manager.py`
2. 選擇「群組管理」→「新增群組」
3. 輸入群組 ID (例如：-1002634361114)
4. 新增要下載的訊息 ID
5. 回到主選單選擇「開始下載」
6. 享受智慧下載！

### 功能亮點
- 🎯 **選擇性下載**：可以只下載特定群組的訊息
- 📋 **批量管理**：支援批量新增 ID、ID 範圍 (如：100-200)
- 🔄 **歷史管理**：清除歷史記錄以重新下載
- 📊 **即時狀態**：隨時查看下載進度和統計

## 快速開始 (命令行方式)

### 1. 啟用自定義下載功能

```bash
python3 custom_download_manager.py enable
```

### 2. 添加要下載的訊息 ID

```bash
# 添加單個聊天的多個訊息
python3 custom_download_manager.py add -1001234567890 123 456 789

# 添加另一個聊天的訊息
python3 custom_download_manager.py add -1009876543210 111 222 333
```

### 3. 查看當前設定

```bash
python3 custom_download_manager.py list
```

### 4. 執行下載

```bash
python3 media_downloader.py
```

## 詳細使用說明

### 命令行工具使用

#### 啟用/停用功能
```bash
# 啟用自定義下載
python3 custom_download_manager.py enable

# 停用自定義下載
python3 custom_download_manager.py disable
```

#### 管理下載清單
```bash
# 添加訊息 ID
python3 custom_download_manager.py add <chat_id> <message_id1> <message_id2> ...

# 移除訊息 ID
python3 custom_download_manager.py remove <chat_id> <message_id1> <message_id2> ...

# 查看當前下載清單
python3 custom_download_manager.py list
```

#### 歷史記錄管理
```bash
# 查看下載歷史
python3 custom_download_manager.py history

# 清除所有歷史
python3 custom_download_manager.py clear

# 清除特定聊天的歷史
python3 custom_download_manager.py clear --chat-id -1001234567890

# 清除特定訊息的歷史
python3 custom_download_manager.py clear --chat-id -1001234567890 --message-ids 123 456
```

### 配置檔案格式

在 `config.yaml` 中會自動添加以下配置：

```yaml
custom_downloads:
  enable: true
  target_ids:
    # 聊天 ID: [訊息 ID 列表]
    -1001234567890: [123, 456, 789]
    -1009876543210: [111, 222, 333]
```

### 歷史記錄格式

`custom_download_history.yaml` 記錄下載歷史：

```yaml
downloaded_ids:
  # 成功下載的訊息
  -1001234567890: [123, 456]
  
failed_ids:
  # 下載失敗的訊息（會在下次執行時重試）
  -1001234567890: [789]
```

## 使用範例

### 範例 1：下載特定頻道的精選訊息

```bash
# 1. 啟用功能
python3 custom_download_manager.py enable

# 2. 添加要下載的訊息（假設從頻道 -1001234567890 下載訊息 100, 200, 300）
python3 custom_download_manager.py add -1001234567890 100 200 300

# 3. 查看設定
python3 custom_download_manager.py list

# 4. 執行下載
python3 media_downloader.py
```

### 範例 2：管理多個聊天的下載

```bash
# 添加多個聊天的訊息
python3 custom_download_manager.py add -1001234567890 100 200 300
python3 custom_download_manager.py add -1009876543210 50 60 70
python3 custom_download_manager.py add me 10 20 30

# 查看所有設定
python3 custom_download_manager.py list

# 執行下載
python3 media_downloader.py
```

### 範例 3：管理下載歷史

```bash
# 查看下載歷史
python3 custom_download_manager.py history

# 如果某些訊息下載失敗，清除其歷史記錄以重新嘗試
python3 custom_download_manager.py clear --chat-id -1001234567890 --message-ids 100 200

# 重新執行下載
python3 media_downloader.py
```

## 工作原理

1. **配置載入**：程式啟動時讀取 `config.yaml` 中的 `custom_downloads` 配置
2. **歷史檢查**：檢查 `custom_download_history.yaml` 避免重複下載
3. **訊息獲取**：使用 Telegram API 獲取指定的訊息
4. **下載處理**：將訊息加入下載佇列進行處理
5. **歷史更新**：更新下載歷史記錄

## 注意事項

- 訊息 ID 必須是有效的數字
- 聊天 ID 需要是您有權限訪問的聊天
- 已下載的訊息會自動跳過
- 下載失敗的訊息會在下次執行時重試
- 支援私聊、群組、頻道的訊息下載

## 故障排除

### 常見問題

1. **訊息不存在**：確認訊息 ID 正確且您有權限訪問
2. **聊天 ID 無效**：確認聊天 ID 格式正確（頻道通常以 -100 開頭）
3. **權限不足**：確認您有權限訪問該聊天並下載媒體

### 除錯方法

1. 查看程式日誌輸出
2. 檢查 `custom_download_history.yaml` 中的失敗記錄
3. 使用 `python3 custom_download_manager.py history` 查看詳細狀態

## 與原功能的關係

- 自定義下載與原有的聊天下載功能並行運作
- 不會影響原有的下載邏輯
- 可以同時使用兩種下載模式