#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m compileall ./bin/macos_operator.py >/dev/null

echo "static checks passed"
if [[ "$(uname -s)" == "Darwin" ]]; then
  echo "running doctor on macOS"
  python3 ./bin/macos_operator.py doctor
else
  echo "not running doctor because this is not macOS"
fi
