#!/bin/bash

# stop_tgdl_dev.sh - Stop TGDL-dev environment

PORT=5002

echo "🛑 停止 TGDL-dev 環境 (Port: $PORT)"

# 停止使用該 port 的進程
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "📴 終止 Port $PORT 的進程..."
    pkill -f "WEB_PORT=$PORT" || true
    sleep 2

    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "⚠️  強制終止..."
        lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
    fi
fi

# 清理 PID 檔案
if [ -f ".tgdl_dev_5002.pid" ]; then
    PID=$(cat .tgdl_dev_5002.pid)
    kill $PID 2>/dev/null || true
    rm -f .tgdl_dev_5002.pid
fi

echo "✅ TGDL-dev 環境已停止"
