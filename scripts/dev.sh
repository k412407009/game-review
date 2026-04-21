#!/usr/bin/env bash
# game-review · 本地一键启动脚本 (Phase 3)
#
# 功能:
#   - 如果 .venv 不存在, 建好 + pip install -e . + pip install -e apps/api
#   - 如果 apps/web/node_modules 不存在, npm install
#   - 同时启动 FastAPI (:8787) + Next.js (:3000) 到两个 tmux window / 后台
#
# 用法:
#   ./scripts/dev.sh                 # 提示用法 (前台模式需开两个终端)
#   ./scripts/dev.sh start           # 推荐: nohup 后台起两个服务, 关 Cursor 也不死
#   ./scripts/dev.sh api             # 前台只起后端 (开发调试用)
#   ./scripts/dev.sh web             # 前台只起前端 (开发调试用)
#   ./scripts/dev.sh setup           # 只装依赖, 不起服务
#   ./scripts/dev.sh stop            # 停所有服务 (kill 8787/3000 占用)
#   ./scripts/dev.sh status          # 看两个服务状态
#   ./scripts/dev.sh logs            # tail -f 两个服务日志
#   ./scripts/dev.sh restart         # stop + start 一条龙

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LOG_DIR="${GAME_REVIEW_LOG_DIR:-/tmp/game-review-logs}"
API_LOG="$LOG_DIR/api.log"
WEB_LOG="$LOG_DIR/web.log"

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { printf "${GREEN}[dev]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[dev]${NC} %s\n" "$*"; }
fail() { printf "${RED}[dev]${NC} %s\n" "$*" >&2; exit 1; }

check_port_free() {
    local port="$1"
    if lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
        warn "端口 $port 已被占用, 先 stop"
        stop_services
    fi
}

setup_backend() {
    if [[ ! -d .venv ]]; then
        info "建 .venv..."
        python3 -m venv .venv
    fi
    # shellcheck disable=SC1091
    source .venv/bin/activate
    info "pip install -e . (CLI)..."
    pip install -e . -q
    info "pip install -e apps/api (API)..."
    pip install -e apps/api -q
    info "后端依赖就绪"
}

setup_frontend() {
    if [[ ! -d apps/web/node_modules ]]; then
        info "npm install (web)..."
        (cd apps/web && npm install --silent)
    fi
    info "前端依赖就绪"
}

run_api() {
    check_port_free 8787
    # shellcheck disable=SC1091
    source .venv/bin/activate
    cd apps/api
    info "启动 FastAPI → http://localhost:8787"
    exec uvicorn api.main:app --reload --port 8787 --log-level info
}

run_web() {
    check_port_free 3000
    cd apps/web
    info "启动 Next.js → http://localhost:3000"
    exec npm run dev
}

stop_services() {
    for port in 8787 3000; do
        pids=$(lsof -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            info "kill port $port (pid=$pids)"
            kill -TERM $pids 2>/dev/null || true
            sleep 1
            pids=$(lsof -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)
            if [[ -n "$pids" ]]; then
                kill -9 $pids 2>/dev/null || true
            fi
        fi
    done
    info "已停止所有服务"
}

status() {
    for port in 8787 3000; do
        if lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
            info "port $port: UP"
        else
            warn "port $port: DOWN"
        fi
    done
}

start_background() {
    setup_backend
    setup_frontend
    mkdir -p "$LOG_DIR"
    if lsof -iTCP:8787 -sTCP:LISTEN >/dev/null 2>&1 || lsof -iTCP:3000 -sTCP:LISTEN >/dev/null 2>&1; then
        warn "已有服务占用 8787 或 3000, 先 stop"
        stop_services
    fi

    info "后台启动 FastAPI → http://localhost:8787  (log: $API_LOG)"
    (cd apps/api && nohup "$REPO_ROOT/.venv/bin/uvicorn" api.main:app --host 127.0.0.1 --port 8787 --log-level info > "$API_LOG" 2>&1 < /dev/null &)

    info "后台启动 Next.js → http://localhost:3000  (log: $WEB_LOG)"
    (cd apps/web && nohup npm run dev > "$WEB_LOG" 2>&1 < /dev/null &)

    sleep 4

    local ok=true
    if ! lsof -iTCP:8787 -sTCP:LISTEN >/dev/null 2>&1; then
        warn "API 未起来, 看 tail -n 30 $API_LOG"
        tail -n 20 "$API_LOG" >&2 || true
        ok=false
    fi
    if ! lsof -iTCP:3000 -sTCP:LISTEN >/dev/null 2>&1; then
        warn "Web 未起来 (Next.js 首次启动可能要 10-15 秒, 再等几秒后跑 status)"
        ok=false
    fi
    if $ok; then
        info "两个服务已脱离终端 background, 关 Cursor / 关终端不影响"
        info "打开浏览器: http://localhost:3000"
    fi
}

logs() {
    if [[ ! -f "$API_LOG" && ! -f "$WEB_LOG" ]]; then
        warn "还没起过 background 服务, 先 ./scripts/dev.sh start"
        exit 1
    fi
    info "tail -f $API_LOG $WEB_LOG  (Ctrl-C 退出, 不会停服务)"
    tail -F "$API_LOG" "$WEB_LOG" 2>/dev/null
}

cmd="${1:-all}"
case "$cmd" in
    setup)
        setup_backend
        setup_frontend
        ;;
    api)
        setup_backend
        run_api
        ;;
    web)
        setup_frontend
        run_web
        ;;
    stop)
        stop_services
        ;;
    status)
        status
        ;;
    start)
        start_background
        ;;
    restart)
        stop_services
        start_background
        ;;
    logs)
        logs
        ;;
    all|"")
        setup_backend
        setup_frontend
        info ""
        info "推荐: ./scripts/dev.sh start  (后台脱离终端, 关 Cursor 不死)"
        info "      ./scripts/dev.sh status (确认服务在跑)"
        info "      ./scripts/dev.sh logs   (看实时日志)"
        info "      ./scripts/dev.sh stop   (停止)"
        info ""
        info "也可以前台跑 (调试用, 开两个终端):"
        info "  终端 1: ./scripts/dev.sh api"
        info "  终端 2: ./scripts/dev.sh web"
        info ""
        info "浏览器打开: http://localhost:3000"
        ;;
    *)
        fail "未知命令: $cmd. 用: setup / start / restart / stop / status / logs / api / web / all"
        ;;
esac
