#!/bin/bash

# status.sh - 查看 TGDL 所有服務運行狀態
# 用途：快速查看產品版本、開發版本和 Cloudflare Tunnel 的運行狀態

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 格式化時間
format_time() {
    local seconds=$1
    local days=$((seconds / 86400))
    local hours=$(((seconds % 86400) / 3600))
    local minutes=$(((seconds % 3600) / 60))

    if [ $days -gt 0 ]; then
        echo "${days}天${hours}小時"
    elif [ $hours -gt 0 ]; then
        echo "${hours}小時${minutes}分鐘"
    else
        echo "${minutes}分鐘"
    fi
}

# 檢查服務狀態
check_service() {
    local name=$1
    local port=$2
    local pid_file=$3
    local git_dir=$4

    echo ""
    echo "────────────────────────────────────────"
    echo -e "${BLUE}$name${NC}"
    echo "────────────────────────────────────────"

    # 檢查 PID 檔案
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")

        # 檢查進程是否存在
        if kill -0 $pid 2>/dev/null; then
            # 獲取進程資訊
            local start_time=$(ps -p $pid -o lstart= 2>/dev/null)
            local elapsed=$(ps -p $pid -o etimes= 2>/dev/null | tr -d ' ')
            local elapsed_formatted=$(format_time $elapsed)

            echo -e "狀態: ${GREEN}✅ 運行中${NC}"
            echo "PID: $pid"
            echo "運行時間: $elapsed_formatted"

            # 訪問地址
            if [ ! -z "$port" ]; then
                echo "本地訪問: http://localhost:$port"
                echo "Message Downloader: http://localhost:$port/message_downloader"
            fi

            # Git 資訊
            if [ -d "$git_dir" ]; then
                pushd "$git_dir" > /dev/null 2>&1
                local branch=$(git branch --show-current 2>/dev/null || echo "unknown")
                local tag=$(git describe --tags --abbrev=0 2>/dev/null || echo "未標記")
                local commit=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
                echo "Git Branch: $branch"
                echo "Git Tag: $tag"
                echo "Git Commit: $commit"
                popd > /dev/null 2>&1
            fi
        else
            echo -e "狀態: ${RED}❌ 已停止${NC}"
            echo "PID 檔案存在但進程不存在 (PID: $pid)"
            echo "建議: 清理 PID 檔案或重新啟動"
        fi
    else
        # 嘗試透過 Port 查找
        if [ ! -z "$port" ] && lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            local pid=$(lsof -Pi :$port -sTCP:LISTEN -t)
            echo -e "狀態: ${YELLOW}⚠️  運行中但缺少 PID 檔案${NC}"
            echo "PID: $pid"
            echo "Port: $port"
            echo "建議: 執行停止腳本後重新啟動"
        else
            echo -e "狀態: ${RED}❌ 未運行${NC}"
            if [ ! -z "$port" ]; then
                echo "Port: $port (未佔用)"
            fi
        fi
    fi
}

# 檢查 Cloudflare Tunnel
check_cloudflare_tunnel() {
    echo ""
    echo "────────────────────────────────────────"
    echo -e "${BLUE}Cloudflare Tunnel${NC}"
    echo "────────────────────────────────────────"

    local tunnel_pids=$(pgrep -f "cloudflared tunnel" 2>/dev/null)

    if [ ! -z "$tunnel_pids" ]; then
        echo -e "狀態: ${GREEN}✅ 運行中${NC}"

        # 可能有多個進程
        for pid in $tunnel_pids; do
            local elapsed=$(ps -p $pid -o etimes= 2>/dev/null | tr -d ' ')
            local elapsed_formatted=$(format_time $elapsed)
            echo "PID: $pid (運行時間: $elapsed_formatted)"
        done

        # 檢查配置檔案中的網域
        if [ -f "cloudflare_tunnel_config.yml" ]; then
            local hostname=$(grep "hostname:" cloudflare_tunnel_config.yml 2>/dev/null | awk '{print $2}')
            if [ ! -z "$hostname" ]; then
                echo "公網訪問: https://$hostname"
            fi
        fi

        # 檢查 URL 檔案
        if [ -f ".cloudflare_tunnel_url" ]; then
            local tunnel_url=$(cat .cloudflare_tunnel_url)
            echo "Tunnel URL: https://$tunnel_url"
        fi
    else
        echo -e "狀態: ${RED}❌ 未運行${NC}"
        echo "建議: 執行 ./start_cloudflare_tunnel.sh 啟動"
    fi
}

# 主函數
main() {
    clear
    echo "═══════════════════════════════════════════════════════════"
    echo -e "  ${BLUE}📊 TGDL 運行狀態${NC}"
    echo "═══════════════════════════════════════════════════════════"

    # 檢查產品版本
    check_service "Product 版本 (Port 5001)" "5001" ".tgdl_pid" "."

    # 檢查開發版本
    local dev_dir="../TGDL-dev"
    if [ -d "$dev_dir" ]; then
        pushd "$dev_dir" > /dev/null 2>&1
        check_service "Develop 版本 (Port 5002)" "5002" ".tgdl_dev_pid" "."
        popd > /dev/null 2>&1
    else
        echo ""
        echo "────────────────────────────────────────"
        echo -e "${BLUE}Develop 版本 (Port 5002)${NC}"
        echo "────────────────────────────────────────"
        echo -e "狀態: ${YELLOW}⚠️  開發環境目錄不存在${NC}"
        echo "路徑: $dev_dir"
        echo "建議: 執行 DEPLOYMENT_PLAN.md 中的設置步驟"
    fi

    # 檢查 Cloudflare Tunnel
    check_cloudflare_tunnel

    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo -e "  ${BLUE}📋 管理命令${NC}"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "產品版本:"
    echo "  ./start_product.sh     - 啟動產品版本"
    echo "  ./stop_product.sh      - 停止產品版本"
    echo ""
    echo "開發版本 (在 TGDL-dev/ 目錄):"
    echo "  ./start_develop.sh     - 啟動開發版本"
    echo "  ./stop_develop.sh      - 停止開發版本"
    echo ""
    echo "Cloudflare Tunnel:"
    echo "  ./start_cloudflare_tunnel.sh  - 啟動 Tunnel"
    echo "  ./stop_cloudflare_tunnel.sh   - 停止 Tunnel"
    echo ""
    echo "═══════════════════════════════════════════════════════════"
}

# 執行主函數
main
