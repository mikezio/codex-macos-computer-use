#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 /path/to/repo [plugin-source]" >&2
  exit 1
fi

REPO_ROOT="$(cd "$1" && pwd)"
PLUGIN_SRC="${2:-$(cd "$(dirname "$0")/.." && pwd)}"
PLUGIN_DEST="$REPO_ROOT/plugins/macos-computer-use"
MARKETPLACE_DIR="$REPO_ROOT/.agents/plugins"
MARKETPLACE_FILE="$MARKETPLACE_DIR/marketplace.json"

mkdir -p "$REPO_ROOT/plugins" "$MARKETPLACE_DIR"
rm -rf "$PLUGIN_DEST"
cp -R "$PLUGIN_SRC" "$PLUGIN_DEST"

python3 - "$MARKETPLACE_FILE" <<'PY'
import json
import sys
from pathlib import Path

marketplace_file = Path(sys.argv[1])
marketplace_file.parent.mkdir(parents=True, exist_ok=True)
if marketplace_file.exists():
    data = json.loads(marketplace_file.read_text(encoding="utf-8"))
else:
    data = {"name": "local-repo", "plugins": []}

plugins = [p for p in data.get("plugins", []) if p.get("name") != "macos-computer-use"]
plugins.append({
    "name": "macos-computer-use",
    "source": {"source": "local", "path": "./plugins/macos-computer-use"},
    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
    "category": "Developer Tools"
})
data["name"] = data.get("name") or "local-repo"
data["plugins"] = plugins
marketplace_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY

echo "installed plugin to $PLUGIN_DEST"
echo "updated marketplace at $MARKETPLACE_FILE"
echo "restart Codex and install macos-computer-use from the local-repo marketplace"
