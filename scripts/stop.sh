#!/usr/bin/env bash
set -euo pipefail

# Stop the iPLAID docker compose stack.
#
# Usage:
#   scripts/stop.sh            # stop and remove containers (volumes preserved)
#   scripts/stop.sh --volumes  # also remove the named volumes

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

extra=()
for arg in "$@"; do
  case "$arg" in
    --volumes|-v) extra+=(--volumes) ;;
    -h|--help)
      sed -n '3,8p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

echo "==> Stopping iPLAID"
docker compose down ${extra[@]+"${extra[@]}"}
echo "==> Stopped."
