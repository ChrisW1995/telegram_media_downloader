#!/bin/bash

# start_develop.sh - Start TGDL development environment
# Uses config_develop.yaml and runs on port 5002

set -e

PORT=5002
CONFIG_FILE="config_develop.yaml"

echo "🚀 啟動 TGDL 開發環境 (Port: $PORT)"

# 檢查配置檔案
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ 找不到 $CONFIG_FILE"
    exit 1
fi

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

# 停止所有其他開發環境實例
echo "📴 清理現有開發環境進程..."
pkill -f "python.*media_downloader.*config_develop" || true
sleep 1

# 清理 PID 檔案
if [ -f ".tgdl_dev_pid" ]; then
    rm -f .tgdl_dev_pid
fi

# 建立開發環境獨立的 session 目錄
DEV_SESSION_DIR="$HOME/.telegram_sessions_dev"
mkdir -p "$DEV_SESSION_DIR"

# 啟動應用程式
echo "🎯 在 Port $PORT 啟動開發環境..."
SESSION_DIR=$DEV_SESSION_DIR WEB_PORT=$PORT CONFIG_FILE=$CONFIG_FILE python3 media_downloader.py &
TGDL_PID=$!
echo $TGDL_PID > .tgdl_dev_pid

# 等待應用程式啟動
sleep 3

# 檢查進程是否正常運行
if kill -0 $TGDL_PID 2>/dev/null; then
    echo "✅ TGDL 開發環境已成功啟動"
    echo "📊 PID: $TGDL_PID"
    echo "🌐 Web 介面: http://localhost:$PORT"
    echo "📄 Message Downloader: http://localhost:$PORT/message_downloader"
    echo "⚙️  配置檔案: $CONFIG_FILE"
    echo ""
    echo "💡 停止開發環境: ./stop_develop.sh 或 pkill -f 'WEB_PORT=$PORT'"
else
    echo "❌ TGDL 開發環境啟動失敗"
    rm -f .tgdl_dev_pid
    exit 1
fi
