#!/usr/bin/env bash
set -euo pipefail

# Launch iPLAID via docker compose and open the workbench in the default browser.
#
# Usage:
#   scripts/start.sh           # start (build only if image is missing)
#   scripts/start.sh --build   # force a rebuild before starting
#   scripts/start.sh --no-open # skip opening the browser
#
# Honors $IPLAID_PORT (default 8000), matching compose.yml.

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

build=0
open_browser=1
for arg in "$@"; do
  case "$arg" in
    --build)    build=1 ;;
    --no-open)  open_browser=0 ;;
    -h|--help)
      sed -n '3,11p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

port="${IPLAID_PORT:-8000}"
url="http://127.0.0.1:${port}"

if [[ "$build" -eq 1 ]]; then
  echo "==> Building iPLAID image"
  docker compose build iplaid
fi

echo "==> Starting iPLAID on ${url}"
docker compose up -d iplaid

echo -n "==> Waiting for ${url}/api/health "
deadline=$(( SECONDS + 120 ))
until curl -fsS "${url}/api/health" >/dev/null 2>&1; do
  if (( SECONDS >= deadline )); then
    echo
    echo "iPLAID did not become healthy within 120s. Recent logs:" >&2
    docker compose logs --tail=50 iplaid >&2 || true
    exit 1
  fi
  echo -n "."
  sleep 2
done
echo " ready."

if [[ "$open_browser" -eq 1 ]]; then
  case "$(uname -s)" in
    Darwin) open "$url" ;;
    Linux)  xdg-open "$url" >/dev/null 2>&1 || true ;;
    *)      echo "Open ${url} in your browser." ;;
  esac
fi

echo "==> iPLAID is running. Stop with: scripts/stop.sh"
