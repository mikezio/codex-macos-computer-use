# Architecture

## Overview

The plugin is split into two layers.

1. Codex-facing plugin surface
   - `.codex-plugin/plugin.json`
   - `skills/macos-operator/SKILL.md`
   - marketplace install scripts

2. Local execution layer
   - `bin/macos_operator.py`
   - user config in `~/.config/macos-computer-use/config.json`
   - audit log in `~/.local/state/macos-computer-use/audit.jsonl`

## Execution model

The intended loop is:

1. gather current state with `snapshot`, `screenshot`, `frontmost-app`, `list-windows`, or `screen-info`
2. choose exactly one next action
3. perform the action with guards in place
4. gather state again before claiming success

## Guardrails

- app allowlist before opening or targeting an app
- optional expected-frontmost assertion on risky actions
- explicit approval for typing, hotkeys, drag, and keypresses
- kill switch file to disable write actions immediately
- structured JSON output so Codex can reason over results predictably
- redaction of typed text in the audit trail

## Runtime dependencies

The helper is intentionally thin.

- AppleScript through `osascript` for frontmost app, window enumeration, app activation, and text entry
- Quartz for pointer and keyboard events when installed
- `screencapture` for screenshots

## Why this shape

This keeps the plugin install story straightforward while leaving the operational logic in one local helper that can be tested and iterated independently.
