#!/bin/bash

# start_tgdl.sh - Quick start script for TGDL development
# Handles process cleanup and port management

set -e

PORT=${1:-5001}

echo "🚀 啟動 TGDL (Port: $PORT)"

# 檢查端口是否被佔用
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Port $PORT 已被佔用，嘗試停止現有進程..."
    pkill -f "WEB_PORT=$PORT" || true
    sleep 2

    # 再次檢查
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "❌ 無法釋放 Port $PORT，請手動停止佔用該端口的進程"
        exit 1
    fi
fi

# 停止所有其他 TGDL 實例
echo "📴 清理現有 TGDL 進程..."
pkill -f "python.*media_downloader" || true
sleep 1

# 清理 PID 檔案
if [ -f ".tgdl_pid" ]; then
    rm -f .tgdl_pid
fi

# 啟動應用程式
echo "🎯 在 Port $PORT 啟動 TGDL..."
WEB_PORT=$PORT python3 media_downloader.py &
TGDL_PID=$!
echo $TGDL_PID > .tgdl_pid

# 等待應用程式啟動
sleep 3

# 檢查進程是否正常運行
if kill -0 $TGDL_PID 2>/dev/null; then
    echo "✅ TGDL 已成功啟動"
    echo "📊 PID: $TGDL_PID"
    echo "🌐 Web 介面: http://localhost:$PORT"
    echo "📄 Message Downloader: http://localhost:$PORT/message_downloader"
    echo ""
    echo "💡 停止應用程式: pkill -f 'WEB_PORT=$PORT' 或 ./fix_database_lock.sh"
else
    echo "❌ TGDL 啟動失敗"
    rm -f .tgdl_pid
    exit 1
fi