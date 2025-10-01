#!/bin/bash

# stop_product.sh - 停止 TGDL 產品版本
# 用途：安全地停止產品環境服務

set -e

PORT=5001
PID_FILE=".tgdl_pid"

echo "🛑 停止 TGDL 產品版本 (Port: $PORT)"

# 檢查 PID 檔案
if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  找不到 PID 檔案，嘗試透過 Port 尋找進程..."

    # 透過 Port 尋找進程
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        PID=$(lsof -Pi :$PORT -sTCP:LISTEN -t)
        echo "   發現佔用 Port $PORT 的進程 (PID: $PID)"
    else
        echo "✅ Port $PORT 沒有被佔用，服務可能已停止"
        exit 0
    fi
else
    PID=$(cat "$PID_FILE")
    echo "📋 從 PID 檔案讀取到 PID: $PID"
fi

# 檢查進程是否存在
if ! kill -0 $PID 2>/dev/null; then
    echo "⚠️  進程 (PID: $PID) 不存在"
    rm -f "$PID_FILE"
    echo "✅ 已清理 PID 檔案"
    exit 0
fi

# 顯示進程資訊
echo "📊 進程資訊:"
ps -p $PID -o pid,ppid,etime,command

# 優雅地停止進程
echo "⏳ 正在優雅地停止進程..."
kill -TERM $PID 2>/dev/null || true

# 等待進程結束（最多 10 秒）
for i in {1..10}; do
    if ! kill -0 $PID 2>/dev/null; then
        echo "✅ 進程已優雅停止"
        rm -f "$PID_FILE"
        echo "🗑️  已清理 PID 檔案"
        exit 0
    fi
    sleep 1
    echo -n "."
done
echo ""

# 如果優雅停止失敗，強制停止
echo "⚠️  優雅停止超時，強制停止進程..."
kill -KILL $PID 2>/dev/null || true
sleep 1

# 再次檢查
if ! kill -0 $PID 2>/dev/null; then
    echo "✅ 進程已強制停止"
    rm -f "$PID_FILE"
    echo "🗑️  已清理 PID 檔案"
else
    echo "❌ 無法停止進程 (PID: $PID)"
    echo "   請手動執行: kill -9 $PID"
    exit 1
fi
