#!/usr/bin/env bash
set -euo pipefail

PLUGIN_SRC="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
PLUGIN_DEST="$HOME/.codex/plugins/macos-computer-use"
MARKETPLACE_DIR="$HOME/.agents/plugins"
MARKETPLACE_FILE="$MARKETPLACE_DIR/marketplace.json"

mkdir -p "$HOME/.codex/plugins" "$MARKETPLACE_DIR"
rm -rf "$PLUGIN_DEST"
cp -R "$PLUGIN_SRC" "$PLUGIN_DEST"

python3 - <<'PY'
import json
from pathlib import Path

marketplace_file = Path.home() / ".agents" / "plugins" / "marketplace.json"
marketplace_file.parent.mkdir(parents=True, exist_ok=True)
if marketplace_file.exists():
    data = json.loads(marketplace_file.read_text(encoding="utf-8"))
else:
    data = {"name": "personal-local", "plugins": []}

plugins = [p for p in data.get("plugins", []) if p.get("name") != "macos-computer-use"]
plugins.append({
    "name": "macos-computer-use",
    "source": {"source": "local", "path": "./.codex/plugins/macos-computer-use"},
    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
    "category": "Developer Tools"
})
data["name"] = data.get("name") or "personal-local"
data["plugins"] = plugins
marketplace_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY

echo "installed plugin to $PLUGIN_DEST"
echo "updated marketplace at $MARKETPLACE_FILE"
echo "restart Codex and install macos-computer-use from the personal-local marketplace"
