#!/bin/bash

# start_cloudflare_tunnel.sh - 啟動 Cloudflare Tunnel
# 用途：將本地產品版本暴露到公網

set -e

CONFIG_FILE="cloudflare_tunnel_config.yml"
PID_FILE=".cloudflare_tunnel_pid"

echo "🌐 啟動 Cloudflare Tunnel"

# 檢查 cloudflared 是否安裝
if ! command -v cloudflared &> /dev/null; then
    echo "❌ cloudflared 未安裝"
    echo ""
    echo "安裝方式："
    echo "  macOS: brew install cloudflare/cloudflare/cloudflared"
    echo "  Linux: 參考 https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation"
    echo ""
    exit 1
fi

# 檢查配置檔案
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ 找不到配置檔案: $CONFIG_FILE"
    echo ""
    echo "設置步驟："
    echo "  1. 複製範例配置: cp cloudflare_tunnel_config.yml.example $CONFIG_FILE"
    echo "  2. 編輯配置檔案，填入您的 Tunnel ID 和網域"
    echo "  3. 參考 CLOUDFLARE_TUNNEL_SETUP.md 完成 Cloudflare 設置"
    echo ""
    exit 1
fi

# 檢查是否已經在運行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 $OLD_PID 2>/dev/null; then
        echo "⚠️  Cloudflare Tunnel 已經在運行 (PID: $OLD_PID)"
        echo "   如需重啟，請先執行: ./stop_cloudflare_tunnel.sh"
        exit 0
    else
        echo "🗑️  清理舊的 PID 檔案"
        rm -f "$PID_FILE"
    fi
fi

# 檢查是否有其他 cloudflared 進程
if pgrep -f "cloudflared tunnel" >/dev/null 2>&1; then
    echo "⚠️  發現其他 cloudflared 進程正在運行"
    echo "   正在嘗試停止..."
    pkill -f "cloudflared tunnel" || true
    sleep 2
fi

# 啟動 Tunnel
echo "🚀 啟動 Cloudflare Tunnel..."
cloudflared tunnel --config "$CONFIG_FILE" run >> cloudflare_tunnel.log 2>&1 &
TUNNEL_PID=$!

# 保存 PID
echo $TUNNEL_PID > "$PID_FILE"

# 等待啟動
echo "⏳ 等待 Tunnel 連接..."
sleep 3

# 檢查進程
if kill -0 $TUNNEL_PID 2>/dev/null; then
    echo "✅ Cloudflare Tunnel 已成功啟動"
    echo ""
    echo "📊 狀態資訊："
    echo "   PID: $TUNNEL_PID"
    echo "   配置: $CONFIG_FILE"
    echo "   日誌: cloudflare_tunnel.log"
    echo ""

    # 嘗試從配置中讀取網域
    if grep -q "hostname:" "$CONFIG_FILE"; then
        HOSTNAME=$(grep "hostname:" "$CONFIG_FILE" | awk '{print $2}' | head -1)
        echo "🌍 公網訪問："
        echo "   https://$HOSTNAME"
        echo "   https://$HOSTNAME/message_downloader"
        echo ""

        # 保存 URL 到檔案
        echo "$HOSTNAME" > .cloudflare_tunnel_url
    fi

    echo "📋 管理命令："
    echo "   查看日誌: tail -f cloudflare_tunnel.log"
    echo "   查看狀態: ./status.sh"
    echo "   停止 Tunnel: ./stop_cloudflare_tunnel.sh"
    echo ""
    echo "💡 提示："
    echo "   - 確保產品版本正在運行: ./start_product.sh"
    echo "   - 如果無法訪問，檢查 Cloudflare DNS 設置"
else
    echo "❌ Cloudflare Tunnel 啟動失敗"
    echo "   請檢查日誌: tail -f cloudflare_tunnel.log"
    rm -f "$PID_FILE"
    exit 1
fi
