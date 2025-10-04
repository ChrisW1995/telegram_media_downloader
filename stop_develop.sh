#!/bin/bash

# stop_develop.sh - Stop TGDL development environment

set -e

PORT=5002

echo "🛑 停止 TGDL 開發環境 (Port: $PORT)"

# 檢查 PID 檔案
if [ -f ".tgdl_dev_pid" ]; then
    TGDL_PID=$(cat .tgdl_dev_pid)

    if kill -0 $TGDL_PID 2>/dev/null; then
        echo "📴 停止進程 PID: $TGDL_PID"
        kill $TGDL_PID
        sleep 1

        # 確保進程已停止
        if kill -0 $TGDL_PID 2>/dev/null; then
            echo "⚠️  進程未正常停止，強制終止..."
            kill -9 $TGDL_PID 2>/dev/null || true
        fi
    else
        echo "⚠️  PID $TGDL_PID 進程不存在"
    fi

    rm -f .tgdl_dev_pid
else
    echo "⚠️  找不到 .tgdl_dev_pid 檔案，嘗試使用 Port 查找進程..."

    # 透過 Port 查找並停止進程
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        pkill -f "WEB_PORT=$PORT" || true
        sleep 1
    fi
fi

# 額外清理：停止所有可能的開發環境進程
pkill -f "python.*media_downloader.*config_develop" || true

# 檢查端口是否已釋放
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "❌ Port $PORT 仍被佔用"
    exit 1
else
    echo "✅ TGDL 開發環境已停止"
fi
