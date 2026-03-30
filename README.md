# macOS Computer Use for Codex

A local Codex plugin for guarded macOS desktop control.

This version is intentionally closer to a product than a demo. It keeps the plugin surface simple, pushes deterministic behavior into a local helper, and makes risky actions explicit.

## Why this shape

OpenAI documents Codex plugins as installable bundles with a required `.codex-plugin/plugin.json` manifest and optional bundled skills, app mappings, and MCP configuration. This plugin uses the supported plugin shape and bundles a skill plus a local shell helper instead of inventing unsupported manifest behavior.

The helper follows the same core computer-use loop OpenAI documents for the API:

1. get fresh visual context first
2. take one small action
3. capture the updated state
4. decide the next step from the new state

## What is included

- `.codex-plugin/plugin.json` with richer install metadata
- `skills/macos-operator/SKILL.md` with operating rules for Codex
- `bin/macos_operator.py` local helper with structured JSON output
- `scripts/install_personal_marketplace.sh` for a home-scoped install
- `scripts/install_repo_marketplace.sh` for a repo-scoped install
- `tests/` with unit tests for the non-macOS logic
- `docs/` with architecture, threat model, and release notes

## Design goals

- screenshot first
- approvals at the point of risk
- allowlisted apps only
- redacted logs for typed text
- small reversible steps
- explicit verification before claiming success
- predictable local install story

## Requirements

- macOS
- Python 3.10+
- Codex app or Codex CLI in local mode
- Accessibility permission for the terminal or Codex host process
- Screen Recording permission for screenshots

Install the runtime dependency:

```bash
python3 -m pip install -r requirements.txt
```

## Configure the allowlist

```bash
mkdir -p ~/.config/macos-computer-use
cp ./config.example.json ~/.config/macos-computer-use/config.json
```

Edit `allowed_apps` before first use.

## Install in the personal marketplace

```bash
./scripts/install_personal_marketplace.sh
```

Then restart Codex and install `macos-computer-use` from the `personal-local` marketplace.

## Install in a repo marketplace

From the repository root where you want the plugin to appear:

```bash
/path/to/plugin/scripts/install_repo_marketplace.sh /path/to/repo
```

Then restart Codex and install `macos-computer-use` from the `local-repo` marketplace.

## Verify the environment

```bash
python3 ./bin/macos_operator.py doctor
```

## Core commands

Take a screenshot:

```bash
python3 ./bin/macos_operator.py screenshot
```

Capture a structured state snapshot:

```bash
python3 ./bin/macos_operator.py snapshot
```

Focus an allowed app:

```bash
python3 ./bin/macos_operator.py focus-app --app "Xcode"
```

Click with an expected frontmost app guard:

```bash
python3 ./bin/macos_operator.py click --x 640 --y 420 --expect-frontmost "Safari"
```

Type text after explicit approval:

```bash
python3 ./bin/macos_operator.py type-text --text "hello world" --approve --expect-frontmost "Terminal"
```

Run a dry run instead of acting:

```bash
python3 ./bin/macos_operator.py hotkey --keys "cmd+shift+p" --approve --dry-run
```

## Safety model

The helper is intentionally opinionated.

- apps must be in the allowlist before they can be opened or targeted
- a kill switch file can disable all state changing actions instantly
- blocked hotkeys are denied outright
- typing, keypresses, hotkeys, and drags require explicit approval by default
- logs record metadata and outcomes, not typed text
- actions can assert the expected frontmost app to reduce misfires

## What still needs a real Mac to validate

This package was built and syntax checked outside macOS. The macOS specific execution paths still need validation on an actual Mac for:

- Accessibility trust behavior
- screen capture permissions
- Quartz event posting
- frontmost app and window listing edge cases

That part is normal for this kind of plugin. The package includes tests for the platform agnostic pieces and a `doctor` command for the Mac side.
