#!/bin/bash

# fix_database_lock.sh - Enhanced session management script for TGDL
# Stops all running TGDL processes and clears Telegram session SQLite locks
#
# Usage:
#   ./fix_database_lock.sh [PORT]           # Clean and restart on PORT (default: 5001)
#   ./fix_database_lock.sh --clean-only     # Only clean, don't restart
#   ./fix_database_lock.sh --help           # Show help

set -e

# 預設設定
DEFAULT_PORT=5001
CLEAN_ONLY=false
RESTART_APP=true

# 解析參數
case "${1:-}" in
    --clean-only|--clean|-c)
        CLEAN_ONLY=true
        RESTART_APP=false
        echo "🧹 僅清理模式：將清理所有程序和鎖定檔案，不重新啟動"
        ;;
    --help|-h)
        echo "📖 TGDL 資料庫鎖定修復腳本"
        echo ""
        echo "用法："
        echo "  $0 [PORT]           # 清理並在指定端口重新啟動 (預設: $DEFAULT_PORT)"
        echo "  $0 --clean-only     # 僅清理程序和鎖定檔案，不重新啟動"
        echo "  $0 --help           # 顯示此說明"
        echo ""
        echo "範例："
        echo "  $0                  # 清理並在端口 $DEFAULT_PORT 重新啟動"
        echo "  $0 5002             # 清理並在端口 5002 重新啟動"
        echo "  $0 --clean-only     # 僅清理，不重新啟動"
        exit 0
        ;;
    "")
        PORT=$DEFAULT_PORT
        ;;
    *)
        if [[ "$1" =~ ^[0-9]+$ ]] && [ "$1" -ge 1024 ] && [ "$1" -le 65535 ]; then
            PORT=$1
        else
            echo "❌ 錯誤：無效的端口號 '$1'"
            echo "端口號必須是 1024-65535 之間的數字"
            exit 1
        fi
        ;;
esac

if [ "$RESTART_APP" = true ]; then
    echo "🔧 修復資料庫鎖定並重新啟動 TGDL (Port: $PORT)"
else
    echo "🔧 清理 TGDL 程序和資料庫鎖定"
fi

# 函數：檢查進程是否還在運行
check_processes() {
    local count
    count=$(pgrep -f "python.*media_downloader" 2>/dev/null | wc -l)
    echo $count
}

# 函數：檢查端口是否被占用
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # 端口被占用
    else
        return 1  # 端口未被占用
    fi
}

# 函數：強制終止進程
force_kill_processes() {
    echo "📴 強制終止所有運行中的 TGDL 進程..."

    # 先嘗試優雅終止
    pkill -TERM -f "python.*media_downloader" 2>/dev/null || true
    pkill -TERM -f "WEB_PORT.*python" 2>/dev/null || true

    # 等待進程自然結束
    echo "⏳ 等待進程自然終止..."
    for i in {1..5}; do
        local count=$(check_processes)
        if [ "$count" -eq 0 ]; then
            echo "✅ 所有進程已正常終止"
            return 0
        fi
        echo "   等待中... ($i/5) [剩餘進程: $count]"
        sleep 1
    done

    # 如果還有進程在運行，強制殺死
    local remaining=$(check_processes)
    if [ "$remaining" -gt 0 ]; then
        echo "⚡ 強制終止剩餘的 $remaining 個進程..."
        pkill -KILL -f "python.*media_downloader" 2>/dev/null || true
        pkill -KILL -f "WEB_PORT.*python" 2>/dev/null || true
        sleep 2

        local final_count=$(check_processes)
        if [ "$final_count" -eq 0 ]; then
            echo "✅ 所有進程已強制終止"
        else
            echo "⚠️  警告：仍有 $final_count 個進程無法終止"
        fi
    fi
}

# 函數：清理鎖定檔案
cleanup_lock_files() {
    echo "🗑️  清理 SQLite 鎖定檔案..."

    # 清理主資料庫鎖定檔案
    for file in "tgdl.db-wal" "tgdl.db-shm"; do
        if [ -f "$file" ]; then
            echo "   移除 $file"
            rm -f "$file"
        fi
    done

    # 清理其他可能的鎖定檔案
    local wal_files=$(find . -name "*.db-wal" 2>/dev/null | wc -l)
    local shm_files=$(find . -name "*.db-shm" 2>/dev/null | wc -l)

    if [ "$wal_files" -gt 0 ] || [ "$shm_files" -gt 0 ]; then
        echo "   清理額外的鎖定檔案 (WAL: $wal_files, SHM: $shm_files)"
        find . -name "*.db-wal" -delete 2>/dev/null || true
        find . -name "*.db-shm" -delete 2>/dev/null || true
    fi

    echo "🗑️  清理 Telegram session 鎖定檔案..."

    # 清理 Telegram session 鎖定檔案
    local session_files=0
    if [ -d ~/.telegram_sessions ]; then
        session_files=$(find ~/.telegram_sessions -name "*.session-wal" -o -name "*.session-shm" -o -name "*.session-journal" 2>/dev/null | wc -l)
        if [ "$session_files" -gt 0 ]; then
            echo "   清理 $session_files 個 session 鎖定檔案"
            find ~/.telegram_sessions -name "*.session-wal" -delete 2>/dev/null || true
            find ~/.telegram_sessions -name "*.session-shm" -delete 2>/dev/null || true
            find ~/.telegram_sessions -name "*.session-journal" -delete 2>/dev/null || true
        fi
    fi

    # 檢查並清理 PID 檔案
    if [ -f ".tgdl_pid" ]; then
        local old_pid=$(cat .tgdl_pid 2>/dev/null || echo "unknown")
        echo "   清理 PID 檔案 (舊 PID: $old_pid)"
        rm -f .tgdl_pid
    fi
}

# 函數：等待端口釋放
wait_for_port_release() {
    local port=$1
    echo "🔍 檢查端口 $port 狀態..."

    for i in {1..15}; do
        if ! check_port $port; then
            echo "✅ 端口 $port 已釋放"
            return 0
        fi
        echo "   等待端口 $port 釋放... ($i/15)"
        sleep 1
    done

    echo "⚠️  警告：端口 $port 仍被占用，可能會導致啟動失敗"
    return 1
}

# 執行清理
force_kill_processes
cleanup_lock_files

echo "✅ 資料庫鎖定清理完成"

# 重新啟動應用程式（如果需要）
if [ "$RESTART_APP" = true ]; then
    wait_for_port_release $PORT

    echo "🚀 在 Port $PORT 重新啟動 TGDL..."

    # 在背景啟動應用程式
    WEB_PORT=$PORT nohup python3 media_downloader.py > output.log 2>&1 &
    new_pid=$!
    echo $new_pid > .tgdl_pid

    echo "✅ TGDL 已在背景啟動，PID: $new_pid"
    echo "🌐 Web 介面: http://localhost:$PORT"
    echo "📄 Message Downloader: http://localhost:$PORT/message_downloader"
    echo "📋 輸出日誌: output.log"

    # 檢查啟動狀態
    echo "🔍 檢查啟動狀態..."
    sleep 3

    if kill -0 $new_pid 2>/dev/null; then
        if check_port $PORT; then
            echo "🎉 應用程式啟動成功！"
        else
            echo "⚠️  應用程式正在啟動中，請稍候檢查端口 $PORT"
        fi
    else
        echo "❌ 應用程式啟動失敗，請檢查 output.log"
        rm -f .tgdl_pid
        exit 1
    fi
else
    echo "ℹ️  僅清理完成，未重新啟動應用程式"
    echo "💡 如需重新啟動，請執行: $0 [PORT]"
fi