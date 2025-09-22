#!/bin/bash

# fix_database_lock.sh - Session management script for TGDL
# Stops all running TGDL processes and clears Telegram session SQLite locks

set -e

PORT=${1:-5001}

echo "🔧 修復資料庫鎖定並重新啟動 TGDL (Port: $PORT)"

# 停止所有相關進程
echo "📴 停止所有運行中的 TGDL 進程..."
pkill -f "python.*media_downloader" || true
pkill -f "WEB_PORT.*python" || true

# 等待進程結束
sleep 2

# 清理 SQLite WAL 和 SHM 檔案
echo "🗑️  清理 SQLite 鎖定檔案..."
if [ -f "tgdl.db-wal" ]; then
    echo "移除 tgdl.db-wal"
    rm -f tgdl.db-wal
fi

if [ -f "tgdl.db-shm" ]; then
    echo "移除 tgdl.db-shm"
    rm -f tgdl.db-shm
fi

# 清理其他可能的鎖定檔案
find . -name "*.db-wal" -delete 2>/dev/null || true
find . -name "*.db-shm" -delete 2>/dev/null || true

# 清理 Telegram session 鎖定檔案
echo "🗑️  清理 Telegram session 鎖定檔案..."
find ~/.telegram_sessions -name "*.session-wal" -delete 2>/dev/null || true
find ~/.telegram_sessions -name "*.session-shm" -delete 2>/dev/null || true
find ~/.telegram_sessions -name "*.session-journal" -delete 2>/dev/null || true

# 檢查 PID 檔案並清理
if [ -f ".tgdl_pid" ]; then
    echo "清理 PID 檔案"
    rm -f .tgdl_pid
fi

echo "✅ 資料庫鎖定清理完成"

# 如果指定了端口，則重新啟動應用程式
if [ ! -z "$PORT" ]; then
    echo "🚀 在 Port $PORT 重新啟動 TGDL..."
    WEB_PORT=$PORT python3 media_downloader.py &
    echo $! > .tgdl_pid
    echo "✅ TGDL 已在背景啟動，PID: $(cat .tgdl_pid)"
    echo "🌐 Web 介面: http://localhost:$PORT"
    echo "📄 Message Downloader: http://localhost:$PORT/message_downloader"
else
    echo "ℹ️  僅清理完成，未重新啟動應用程式"
fi