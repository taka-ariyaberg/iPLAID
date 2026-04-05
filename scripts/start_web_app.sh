#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/frontend"
LOG_DIR="${ROOT_DIR}/outputs/logs"
BACKEND_LOG="${LOG_DIR}/backend-dev.log"
FRONTEND_LOG="${LOG_DIR}/frontend-dev.log"
BACKEND_URL="http://127.0.0.1:8000/api/health"
FRONTEND_URL="http://127.0.0.1:5173"
OPEN_BROWSER=0

for arg in "$@"; do
  case "$arg" in
    --open)
      OPEN_BROWSER=1
      ;;
    *)
      echo "Unknown option: $arg" >&2
      echo "Usage: scripts/start_web_app.sh [--open]" >&2
      exit 1
      ;;
  esac
done

mkdir -p "$LOG_DIR"

pick_python() {
  if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
    echo "${VIRTUAL_ENV}/bin/python"
    return
  fi

  if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
    echo "${ROOT_DIR}/.venv/bin/python"
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi

  if command -v python >/dev/null 2>&1; then
    command -v python
    return
  fi

  echo "No Python interpreter found. Create .venv or activate an environment first." >&2
  exit 1
}

PYTHON_BIN="$(pick_python)"

require_command() {
  local command_name="$1"
  local install_hint="$2"

  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "$install_hint" >&2
    exit 1
  fi
}

python_module_installed() {
  local module_name="$1"

  "$PYTHON_BIN" -c "import ${module_name}" >/dev/null 2>&1
}

wait_for_http() {
  local url="$1"
  local label="$2"
  local pid="$3"
  local attempts=30

  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi

    if ! kill -0 "$pid" >/dev/null 2>&1; then
      echo "$label exited before it became ready. Check its log for details." >&2
      return 1
    fi

    sleep 1
  done

  echo "$label did not become ready within ${attempts} seconds." >&2
  return 1
}

cleanup() {
  local exit_code="$?"

  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi

  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi

  wait >/dev/null 2>&1 || true
  exit "$exit_code"
}

trap cleanup INT TERM EXIT

require_command npm "npm is required. Install Node.js and npm first."
require_command curl "curl is required to verify service startup."

if ! python_module_installed fastapi || ! python_module_installed uvicorn; then
  echo "Installing backend dependencies into ${PYTHON_BIN}..."
  "$PYTHON_BIN" -m pip install -r "${ROOT_DIR}/backend/requirements.txt"
fi

if [[ ! -d "${FRONTEND_DIR}/node_modules" ]]; then
  echo "Installing frontend dependencies..."
  cd "$FRONTEND_DIR"
  npm install
fi

echo "Using Python: ${PYTHON_BIN}"
echo "Backend log: ${BACKEND_LOG}"
echo "Frontend log: ${FRONTEND_LOG}"

cd "$ROOT_DIR"
"$PYTHON_BIN" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

if ! wait_for_http "$BACKEND_URL" "Backend" "$BACKEND_PID"; then
  exit 1
fi

cd "$FRONTEND_DIR"
npm run dev -- --host 127.0.0.1 --port 5173 >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

if ! wait_for_http "$FRONTEND_URL" "Frontend" "$FRONTEND_PID"; then
  exit 1
fi

echo
echo "PLAID iDOT web app is running."
echo "Frontend: ${FRONTEND_URL}"
echo "Backend:  http://127.0.0.1:8000"
echo
echo "Press Ctrl+C to stop both services."

if [[ "$OPEN_BROWSER" -eq 1 ]]; then
  open "$FRONTEND_URL"
fi

wait "$BACKEND_PID" "$FRONTEND_PID"