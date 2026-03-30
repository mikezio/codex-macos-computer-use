# Threat model

## Assets to protect

- local session state
- sensitive text typed by the operator
- application windows outside the intended flow
- system settings and destructive shortcuts

## Main risks

### Mis-targeted input
A click or hotkey lands in the wrong app or window.

Mitigations:
- app allowlist
- `--expect-frontmost`
- screenshot-first loop
- small reversible actions

### Sensitive text leakage
Secrets or personal data are written into logs.

Mitigations:
- typed text is redacted in audit logs
- approval required before `type-text`

### Over-broad control surface
The helper can act on apps it should not touch.

Mitigations:
- allowlisted apps only
- blocked hotkeys
- kill switch file

### Unclear success reporting
The tool claims success without checking the UI changed.

Mitigations:
- snapshot after every meaningful action
- structured JSON responses with the observed frontmost app

## Non-goals for this version

- OCR or automatic visual parsing
- Accessibility-tree element targeting
- remote multi-host orchestration
- bypassing macOS privacy permissions
