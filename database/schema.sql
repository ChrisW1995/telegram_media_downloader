-- Telegram Media Downloader Database Schema
-- SQLite Database Schema for TGDL Application

-- 應用程式配置表
CREATE TABLE IF NOT EXISTS app_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT,
    value_type TEXT DEFAULT 'str', -- str, int, float, bool, list, dict
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 聊天/頻道配置表
CREATE TABLE IF NOT EXISTS chats (
    chat_id TEXT PRIMARY KEY,
    chat_title TEXT,
    chat_type TEXT, -- channel, group, supergroup
    last_read_message_id INTEGER DEFAULT 0,
    download_filter TEXT,
    upload_telegram_chat_id TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 下載歷史表
CREATE TABLE IF NOT EXISTS download_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    file_name TEXT,
    file_path TEXT,
    file_size INTEGER,
    media_type TEXT, -- audio, video, photo, document, etc.
    download_status TEXT DEFAULT 'pending', -- pending, success, failed, skipped
    download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chat_id) REFERENCES chats(chat_id),
    UNIQUE(chat_id, message_id)
);

-- 自訂下載配置表
CREATE TABLE IF NOT EXISTS custom_downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL,
    target_message_ids TEXT, -- JSON array of message IDs
    group_tag TEXT,
    is_enabled BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chat_id) REFERENCES chats(chat_id)
);

-- 使用者權限表
CREATE TABLE IF NOT EXISTS authorized_users (
    user_id TEXT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    is_active BOOLEAN DEFAULT 1,
    permissions TEXT, -- JSON array of permissions
    last_activity TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 下載任務佇列表（用於重試機制）
CREATE TABLE IF NOT EXISTS download_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    priority INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    current_retries INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending', -- pending, processing, completed, failed
    scheduled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chat_id) REFERENCES chats(chat_id),
    UNIQUE(chat_id, message_id)
);

-- 應用統計表
CREATE TABLE IF NOT EXISTS app_statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_date DATE DEFAULT (DATE('now')),
    chat_id TEXT,
    total_messages INTEGER DEFAULT 0,
    successful_downloads INTEGER DEFAULT 0,
    failed_downloads INTEGER DEFAULT 0,
    skipped_downloads INTEGER DEFAULT 0,
    total_file_size INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stat_date, chat_id)
);

-- 索引建立
CREATE INDEX IF NOT EXISTS idx_download_history_chat_id ON download_history(chat_id);
CREATE INDEX IF NOT EXISTS idx_download_history_message_id ON download_history(message_id);
CREATE INDEX IF NOT EXISTS idx_download_history_status ON download_history(download_status);
CREATE INDEX IF NOT EXISTS idx_download_history_date ON download_history(download_date);
CREATE INDEX IF NOT EXISTS idx_download_queue_status ON download_queue(status);
CREATE INDEX IF NOT EXISTS idx_download_queue_scheduled ON download_queue(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_chats_active ON chats(is_active);
CREATE INDEX IF NOT EXISTS idx_users_active ON authorized_users(is_active);

-- 觸發器：更新 updated_at 欄位
CREATE TRIGGER IF NOT EXISTS update_chats_updated_at
    AFTER UPDATE ON chats
    FOR EACH ROW
    BEGIN
        UPDATE chats SET updated_at = CURRENT_TIMESTAMP WHERE chat_id = NEW.chat_id;
    END;

CREATE TRIGGER IF NOT EXISTS update_download_history_updated_at
    AFTER UPDATE ON download_history
    FOR EACH ROW
    BEGIN
        UPDATE download_history SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_download_queue_updated_at
    AFTER UPDATE ON download_queue
    FOR EACH ROW
    BEGIN
        UPDATE download_queue SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_authorized_users_updated_at
    AFTER UPDATE ON authorized_users
    FOR EACH ROW
    BEGIN
        UPDATE authorized_users SET updated_at = CURRENT_TIMESTAMP WHERE user_id = NEW.user_id;
    END;

-- 視圖：下載統計
CREATE VIEW IF NOT EXISTS download_stats AS
SELECT 
    chat_id,
    COUNT(*) as total_downloads,
    COUNT(CASE WHEN download_status = 'success' THEN 1 END) as successful_downloads,
    COUNT(CASE WHEN download_status = 'failed' THEN 1 END) as failed_downloads,
    COUNT(CASE WHEN download_status = 'skipped' THEN 1 END) as skipped_downloads,
    SUM(COALESCE(file_size, 0)) as total_file_size,
    MAX(download_date) as last_download_date
FROM download_history
GROUP BY chat_id;

-- 視圖：待重試的下載
CREATE VIEW IF NOT EXISTS pending_retries AS
SELECT 
    dq.*,
    dh.file_name,
    dh.error_message as last_error
FROM download_queue dq
LEFT JOIN download_history dh ON dq.chat_id = dh.chat_id AND dq.message_id = dh.message_id
WHERE dq.status = 'pending' AND dq.current_retries < dq.max_retries
ORDER BY dq.priority DESC, dq.scheduled_at ASC;