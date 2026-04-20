#!/usr/bin/env bash
# game-review · 本地一键启动脚本 (Phase 3)
#
# 功能:
#   - 如果 .venv 不存在, 建好 + pip install -e . + pip install -e apps/api
#   - 如果 apps/web/node_modules 不存在, npm install
#   - 同时启动 FastAPI (:8787) + Next.js (:3000) 到两个 tmux window / 后台
#
# 用法:
#   ./scripts/dev.sh                 # 起所有服务
#   ./scripts/dev.sh api             # 只起后端
#   ./scripts/dev.sh web             # 只起前端
#   ./scripts/dev.sh setup           # 只装依赖, 不起服务
#   ./scripts/dev.sh stop            # 停所有服务 (kill 8787/3000 占用)
#   ./scripts/dev.sh status          # 看两个服务状态

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

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
    all|"")
        setup_backend
        setup_frontend
        info ""
        info "两个服务需要各自前台运行. 推荐开两个终端:"
        info "  终端 1:  ./scripts/dev.sh api"
        info "  终端 2:  ./scripts/dev.sh web"
        info ""
        info "或者用 tmux/iterm split:"
        info "  ./scripts/dev.sh api &      # 后台"
        info "  ./scripts/dev.sh web        # 前台"
        info ""
        info "打开: http://localhost:3000"
        ;;
    *)
        fail "未知命令: $cmd. 用: setup / api / web / stop / status / all"
        ;;
esac
