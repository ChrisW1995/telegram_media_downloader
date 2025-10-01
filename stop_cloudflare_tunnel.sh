#!/bin/bash

# stop_cloudflare_tunnel.sh - 停止 Cloudflare Tunnel

set -e

PID_FILE=".cloudflare_tunnel_pid"

echo "🛑 停止 Cloudflare Tunnel"

# 檢查 PID 檔案
if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  找不到 PID 檔案"

    # 嘗試查找進程
    if pgrep -f "cloudflared tunnel" >/dev/null 2>&1; then
        echo "   發現 cloudflared 進程，正在停止..."
        pkill -f "cloudflared tunnel"
        sleep 2

        if pgrep -f "cloudflared tunnel" >/dev/null 2>&1; then
            echo "❌ 無法停止 cloudflared 進程"
            exit 1
        else
            echo "✅ 已停止所有 cloudflared 進程"
            exit 0
        fi
    else
        echo "✅ Cloudflared Tunnel 沒有在運行"
        exit 0
    fi
fi

# 讀取 PID
PID=$(cat "$PID_FILE")
echo "📋 從 PID 檔案讀取到 PID: $PID"

# 檢查進程是否存在
if ! kill -0 $PID 2>/dev/null; then
    echo "⚠️  進程 (PID: $PID) 不存在"
    rm -f "$PID_FILE"
    echo "✅ 已清理 PID 檔案"
    exit 0
fi

# 停止進程
echo "⏳ 正在停止進程..."
kill $PID 2>/dev/null || true
sleep 2

# 檢查是否已停止
if ! kill -0 $PID 2>/dev/null; then
    echo "✅ Cloudflare Tunnel 已停止"
    rm -f "$PID_FILE"
    rm -f .cloudflare_tunnel_url
else
    # 強制停止
    echo "⚠️  優雅停止失敗，強制停止..."
    kill -9 $PID 2>/dev/null || true
    sleep 1

    if ! kill -0 $PID 2>/dev/null; then
        echo "✅ Cloudflare Tunnel 已強制停止"
        rm -f "$PID_FILE"
        rm -f .cloudflare_tunnel_url
    else
        echo "❌ 無法停止進程 (PID: $PID)"
        exit 1
    fi
fi
