---
name: macos-operator
description: Inspect and operate approved macOS apps through the bundled local helper.
---

Use the local helper at `./bin/macos_operator.py`.

Operating principles:
- start with visual context first by using `snapshot` or `screenshot`
- take one small action at a time
- confirm only at the point of risk, not before safe progress is possible
- never target an app that is not allowlisted
- verify with a fresh screenshot or state snapshot before claiming success
- use `--expect-frontmost` on actions when a misfire would matter
- respect the kill switch and blocked hotkeys

Preferred flow:
1. `python3 ./bin/macos_operator.py doctor` when starting on a new machine or after permission issues
2. `python3 ./bin/macos_operator.py snapshot`
3. decide the next single action from that state
4. perform one action
5. call `snapshot` again and compare before continuing

Risk policy:
- do not pass `--approve` until the user has already approved that specific risky action in the conversation
- risky actions include `type-text`, `press-key`, `hotkey`, and `drag`
- typing sensitive data counts as transmission, so confirm before doing it
- do not use blocked hotkeys or try to bypass macOS privacy controls
- do not change system security settings, passwords, or similar high impact controls

Useful commands:

```bash
python3 ./bin/macos_operator.py doctor
python3 ./bin/macos_operator.py snapshot
python3 ./bin/macos_operator.py screenshot --output ~/Desktop/codex-shot.png
python3 ./bin/macos_operator.py screen-info
python3 ./bin/macos_operator.py frontmost-app
python3 ./bin/macos_operator.py list-windows
python3 ./bin/macos_operator.py open-app --app "Safari"
python3 ./bin/macos_operator.py focus-app --app "Xcode"
python3 ./bin/macos_operator.py click --x 640 --y 420 --expect-frontmost "Safari"
python3 ./bin/macos_operator.py scroll --dy -600 --expect-frontmost "Safari"
python3 ./bin/macos_operator.py type-text --text "hello" --approve --expect-frontmost "Terminal"
python3 ./bin/macos_operator.py hotkey --keys "cmd+shift+p" --approve --expect-frontmost "Xcode"
python3 ./bin/macos_operator.py wait --seconds 1.5
```

When reporting back, include:
- the active app
- what you observed before acting
- the exact action taken
- what changed after the action
- whether any approval boundary was crossed
