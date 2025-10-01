#!/bin/bash

# start_product.sh - 啟動 TGDL 產品版本 (Port 5001)
# 用途：啟動穩定的產品環境，對外提供服務

set -e

# 配置
PORT=5001
PID_FILE=".tgdl_pid"
LOG_FILE="output.log"
PYTHON_CMD="python3"
MAIN_SCRIPT="media_downloader.py"

echo "🚀 啟動 TGDL 產品版本 (Port: $PORT)"

# 檢查是否在正確的目錄
if [ ! -f "$MAIN_SCRIPT" ]; then
    echo "❌ 錯誤：找不到 $MAIN_SCRIPT"
    echo "   請確保在 TGDL 專案根目錄執行此腳本"
    exit 1
fi

# 檢查 Git 分支
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
if [ "$CURRENT_BRANCH" != "master" ]; then
    echo "⚠️  警告：當前不在 master 分支 (當前: $CURRENT_BRANCH)"
    echo "   產品版本應該在 master 分支運行"
    read -p "   是否繼續？(y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 檢查端口是否被佔用
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Port $PORT 已被佔用"
    PID=$(lsof -Pi :$PORT -sTCP:LISTEN -t)
    echo "   佔用進程 PID: $PID"

    # 檢查是否是之前的 TGDL 進程
    if ps -p $PID -o command= | grep -q "$MAIN_SCRIPT"; then
        echo "   偵測到之前的 TGDL 進程，嘗試停止..."
        kill $PID 2>/dev/null || true
        sleep 2

        # 再次檢查
        if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
            echo "❌ 無法釋放 Port $PORT"
            echo "   請執行: ./stop_product.sh"
            exit 1
        fi
    else
        echo "❌ Port 被其他程式佔用"
        echo "   請先停止佔用該端口的程式"
        exit 1
    fi
fi

# 清理資料庫鎖定檔案
echo "🗑️  清理資料庫鎖定檔案..."
rm -f tgdl.db-wal tgdl.db-shm 2>/dev/null || true

# 清理 Telegram session 鎖定檔案
if [ -d ".telegram_sessions" ]; then
    find .telegram_sessions -name "*.session-journal" -delete 2>/dev/null || true
    echo "   清理 Session 鎖定檔案"
fi

# 檢查舊的 PID 檔案
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 $OLD_PID 2>/dev/null; then
        echo "⚠️  發現舊的 TGDL 進程 (PID: $OLD_PID)，正在停止..."
        kill $OLD_PID 2>/dev/null || true
        sleep 2
    fi
    rm -f "$PID_FILE"
fi

# 啟動應用程式
echo "🎯 啟動產品版本..."
WEB_PORT=$PORT $PYTHON_CMD $MAIN_SCRIPT >> "$LOG_FILE" 2>&1 &
TGDL_PID=$!

# 保存 PID
echo $TGDL_PID > "$PID_FILE"

# 等待應用程式啟動
echo "⏳ 等待應用程式啟動..."
sleep 3

# 檢查進程是否正常運行
if kill -0 $TGDL_PID 2>/dev/null; then
    # 檢查端口是否已監聽
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "✅ TGDL 產品版本已成功啟動"
        echo ""
        echo "📊 狀態資訊："
        echo "   PID: $TGDL_PID"
        echo "   Port: $PORT"
        echo "   Branch: $CURRENT_BRANCH"

        # 顯示版本標籤
        LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "未標記")
        echo "   Version: $LATEST_TAG"

        echo ""
        echo "🌐 訪問地址："
        echo "   本地訪問: http://localhost:$PORT"
        echo "   Message Downloader: http://localhost:$PORT/message_downloader"

        # 如果有 Cloudflare Tunnel，提示公網地址
        if [ -f ".cloudflare_tunnel_url" ]; then
            TUNNEL_URL=$(cat .cloudflare_tunnel_url)
            echo "   公網訪問: https://$TUNNEL_URL"
        fi

        echo ""
        echo "📋 管理命令："
        echo "   查看狀態: ./status.sh"
        echo "   查看日誌: tail -f $LOG_FILE"
        echo "   停止服務: ./stop_product.sh"

        # 如果 Cloudflare Tunnel 沒有運行，提示啟動
        if ! pgrep -f "cloudflared tunnel" >/dev/null 2>&1; then
            echo ""
            echo "💡 提示: Cloudflare Tunnel 未運行"
            echo "   啟動公網訪問: ./start_cloudflare_tunnel.sh"
        fi
    else
        echo "❌ 應用程式啟動失敗：端口未監聽"
        echo "   請檢查日誌: tail -f $LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
else
    echo "❌ TGDL 啟動失敗"
    echo "   請檢查日誌: tail -f $LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi
