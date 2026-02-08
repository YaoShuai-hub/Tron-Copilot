#!/usr/bin/env bash
set -euo pipefail

TRIDENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$TRIDENT_DIR/frontend"

pick_copilot_port() {
  local preferred="${BC_COPILOT_PORT:-8000}"
  python3 - <<'PY'
import os
import socket

preferred = int(os.environ.get("BC_COPILOT_PORT", "8000"))
for port in (preferred, 8001, 8002, 8080):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
        except OSError:
            continue
        print(port)
        raise SystemExit(0)
print(preferred)
PY
}

start_copilot_api() {
  cd "$TRIDENT_DIR"
  if command -v uv >/dev/null 2>&1; then
    uv run frontend_server.py
  else
    python3 frontend_server.py
  fi
}

start_copilot_frontend() {
  cd "$FRONTEND_DIR"
  if command -v npm >/dev/null 2>&1; then
    if [ ! -d node_modules ]; then
      npm install
    fi
    npm run dev
  else
    echo "npm not found; cannot start frontend."
    return 1
  fi
}

start_trident_mcp() {
  cd "$TRIDENT_DIR"
  python3 run.py
}

start_telegram_bot() {
  cd "$TRIDENT_DIR"
  export PYTHONPATH="$TRIDENT_DIR${PYTHONPATH:+:$PYTHONPATH}"
  python3 agents/telegram_bot.py
}

ensure_singleton_telegram() {
  if pgrep -f "agents/telegram_bot.py" >/dev/null 2>&1; then
    echo "telegram_bot already running; stopping previous instance."
    pkill -f "agents/telegram_bot.py" || true
    sleep 1
  fi
}

PORT="$(pick_copilot_port)"
export BC_COPILOT_PORT="$PORT"
export MCP_SERVER_URL="http://localhost:${BC_COPILOT_PORT}"

start_copilot_api &
BC_API_PID=$!

start_copilot_frontend &
BC_FE_PID=$!

start_trident_mcp &
TRIDENT_PID=$!

ensure_singleton_telegram
start_telegram_bot &
TG_BOT_PID=$!

cleanup() {
  kill "$BC_API_PID" "$BC_FE_PID" "$TRIDENT_PID" "$TG_BOT_PID" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

wait "$BC_API_PID" "$BC_FE_PID" "$TRIDENT_PID" "$TG_BOT_PID"
