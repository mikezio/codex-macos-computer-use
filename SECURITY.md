# Security notes

This plugin is intentionally local first and allowlist driven.

## Expected guardrails

- install and run only on machines you control
- grant macOS Accessibility and Screen Recording only to the Codex host or terminal process you trust
- keep `allowed_apps` narrow and task specific
- use the kill switch file at `~/.config/macos-computer-use/DISABLED` to stop writes instantly
- require explicit approval for typing, hotkeys, drags, or anything that transmits sensitive data
- review the audit log at `~/.local/state/macos-computer-use/audit.jsonl`

## Not in scope for v0.2.0

- semantic element targeting through the Accessibility tree
- OCR or content redaction in screenshots
- remote control from another machine
- automatic execution of unreviewed model generated shell scripts
