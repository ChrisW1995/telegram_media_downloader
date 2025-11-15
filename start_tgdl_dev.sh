#!/bin/bash

# start_tgdl_dev.sh - Start TGDL-dev environment
# 獨立的 TGDL-dev 啟動腳本，避免與 ../TGDL 衝突

PORT=5002  # 使用 config_develop.yaml 定義的 port
CONFIG_FILE="config_develop.yaml"
PID_FILE=".tgdl_dev_5002.pid"

echo "🚀 啟動 TGDL-dev 環境 (Port: $PORT)"

# 檢查是否已經在運行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "⚠️  TGDL-dev 已經在運行 (PID: $OLD_PID)"
        echo "💡 如需重啟，請先執行: ./stop_tgdl_dev.sh"
        exit 1
    else
        echo "📝 清理過期的 PID 檔案"
        rm -f "$PID_FILE"
    fi
fi

# 檢查配置檔案
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ 找不到 $CONFIG_FILE"
    exit 1
fi

# 檢查端口是否被佔用
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Port $PORT 已被佔用，嘗試清理..."
    lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
    sleep 2

    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "❌ 無法釋放 Port $PORT"
        exit 1
    fi
fi

# 清理可能殘留的進程
echo "📴 清理殘留進程..."
pkill -f "media_downloader.py.*config_develop" 2>/dev/null || true
sleep 1

# 建立 TGDL-dev 獨立的 session 目錄
DEV_SESSION_DIR="$HOME/.telegram_sessions_tgdl_dev"
mkdir -p "$DEV_SESSION_DIR"

# 啟動應用程式
echo "🎯 在 Port $PORT 啟動 TGDL-dev 環境..."
nohup python3 media_downloader.py --config-file $CONFIG_FILE > tgdl_dev.log 2>&1 &
TGDL_PID=$!
echo $TGDL_PID > "$PID_FILE"

# 等待應用程式啟動
echo "⏳ 等待服務啟動..."
sleep 5

# 檢查進程是否正常運行
if ! kill -0 $TGDL_PID 2>/dev/null; then
    echo "❌ TGDL-dev 環境啟動失敗"
    echo "📋 日誌內容："
    tail -20 tgdl_dev.log
    rm -f "$PID_FILE"
    exit 1
fi

# 檢查 Port 是否監聽
sleep 2
if ! lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "❌ 服務啟動但未監聽 Port $PORT"
    echo "📋 日誌內容："
    tail -20 tgdl_dev.log
    kill $TGDL_PID 2>/dev/null || true
    rm -f "$PID_FILE"
    exit 1
fi

echo ""
echo "✅ TGDL-dev 環境已成功啟動"
echo "📊 PID: $TGDL_PID"
echo "🌐 Web 介面: http://localhost:$PORT"
echo "📄 Message Downloader: http://localhost:$PORT/message_downloader"
echo "⚙️  配置檔案: $CONFIG_FILE"
echo "📁 Session 目錄: $DEV_SESSION_DIR"
echo "📋 日誌檔案: tgdl_dev.log"
echo ""
echo "💡 停止開發環境: ./stop_tgdl_dev.sh"
echo "💡 查看日誌: tail -f tgdl_dev.log"
