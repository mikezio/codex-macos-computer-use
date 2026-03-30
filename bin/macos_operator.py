#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import Quartz
except Exception:
    Quartz = None

DEFAULT_CONFIG: Dict[str, Any] = {
    "allowed_apps": [
        "Safari",
        "Google Chrome",
        "Finder",
        "Terminal",
        "iTerm",
        "Xcode",
        "Simulator",
        "Codex",
    ],
    "blocked_hotkeys": [
        "cmd+q",
        "cmd+w",
        "cmd+option+esc",
        "cmd+ctrl+q",
        "ctrl+eject",
    ],
    "require_approval_for": ["type_text", "press_key", "hotkey", "drag"],
    "screenshot_dir": "~/Pictures/codex-macos-operator",
    "log_file": "~/.local/state/macos-computer-use/audit.jsonl",
    "disable_file": "~/.config/macos-computer-use/DISABLED",
    "screenshot_format": "png",
    "max_click_count": 2,
    "max_drag_seconds": 2.0,
}

MOUSE_BUTTONS = {
    "left": Quartz.kCGMouseButtonLeft if Quartz else 0,
    "right": Quartz.kCGMouseButtonRight if Quartz else 1,
}

MODIFIER_MAP = {
    "cmd": "command down",
    "command": "command down",
    "shift": "shift down",
    "option": "option down",
    "alt": "option down",
    "ctrl": "control down",
    "control": "control down",
    "fn": "function down",
}

SPECIAL_KEY_CODES = {
    "enter": 36,
    "return": 36,
    "tab": 48,
    "space": 49,
    "delete": 51,
    "backspace": 51,
    "escape": 53,
    "esc": 53,
    "left": 123,
    "right": 124,
    "down": 125,
    "up": 126,
    "home": 115,
    "end": 119,
    "pageup": 116,
    "pagedown": 121,
    "forwarddelete": 117,
}

LETTER_KEY_CODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7,
    "c": 8, "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15,
    "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22,
    "5": 23, "=": 24, "9": 25, "7": 26, "-": 27, "8": 28, "0": 29,
    "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35, "l": 37,
    "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42, ",": 43, "/": 44,
    "n": 45, "m": 46, ".": 47, "`": 50,
}


class OperatorError(RuntimeError):
    pass


@dataclass
class ActionContext:
    config: Dict[str, Any]
    plugin_root: Path
    dry_run: bool = False


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def plugin_root() -> Path:
    return Path(__file__).resolve().parent.parent


def expand_path(value: str) -> Path:
    return Path(os.path.expanduser(value)).resolve()


def normalize_hotkey(keys: str) -> str:
    return "+".join(part.strip().lower() for part in keys.split("+") if part.strip())


def parse_hotkey(keys: str) -> Tuple[List[str], str]:
    parts = [part.strip().lower() for part in keys.split("+") if part.strip()]
    if not parts:
        raise OperatorError("hotkey cannot be empty")
    if len(parts) == 1:
        return [], parts[0]
    return parts[:-1], parts[-1]


def redact_config_for_output(config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "allowed_apps": list(config.get("allowed_apps", [])),
        "require_approval_for": list(config.get("require_approval_for", [])),
        "blocked_hotkeys": list(config.get("blocked_hotkeys", [])),
        "disable_file": str(config.get("disable_file", "")),
    }


def sanitize_log_params(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    redacted = copy.deepcopy(params)
    if action == "type-text" and "text" in redacted:
        value = str(redacted.pop("text"))
        redacted["text_redacted"] = True
        redacted["typed_length"] = len(value)
    return redacted


def load_config(path_override: Optional[str]) -> Dict[str, Any]:
    root = plugin_root()
    candidates: List[Path] = []
    if path_override:
        candidates.append(Path(path_override))
    env_path = os.getenv("MACOS_OPERATOR_CONFIG")
    if env_path:
        candidates.append(Path(env_path))
    candidates.extend([
        Path.home() / ".config" / "macos-computer-use" / "config.json",
        root / "config.json",
        root / "config.example.json",
    ])

    config = dict(DEFAULT_CONFIG)
    for candidate in candidates:
        if candidate.exists():
            with candidate.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            config.update(loaded)
            break

    config["allowed_apps"] = [str(x) for x in config.get("allowed_apps", [])]
    config["blocked_hotkeys"] = [normalize_hotkey(str(x)) for x in config.get("blocked_hotkeys", [])]
    config["require_approval_for"] = [str(x) for x in config.get("require_approval_for", [])]
    config["max_click_count"] = max(1, int(config.get("max_click_count", 2)))
    config["max_drag_seconds"] = max(0.1, float(config.get("max_drag_seconds", 2.0)))
    return config


def run(cmd: List[str], check: bool = True, capture_output: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, capture_output=capture_output, text=True)


def run_osascript(script: str) -> str:
    proc = run(["osascript", "-e", script])
    return proc.stdout.strip()


def ensure_macos() -> None:
    if platform.system() != "Darwin":
        raise OperatorError("this helper only runs on macOS")


def ensure_quartz() -> None:
    if Quartz is None:
        raise OperatorError("pyobjc Quartz is not installed. install with: pip install pyobjc-framework-Quartz")


def ensure_enabled(ctx: ActionContext, action: str) -> None:
    if action in {"doctor", "screenshot", "snapshot", "frontmost-app", "list-windows", "screen-info", "wait"}:
        return
    disable_file = expand_path(str(ctx.config.get("disable_file", DEFAULT_CONFIG["disable_file"])))
    if disable_file.exists():
        raise OperatorError(f"writes are disabled because kill switch file exists: {disable_file}")


def json_out(payload: Dict[str, Any], status: int = 0) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return status


def log_action(ctx: ActionContext, action: str, params: Dict[str, Any], result: Dict[str, Any]) -> None:
    log_path = expand_path(str(ctx.config["log_file"]))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": utc_now_iso(),
        "action": action,
        "params": sanitize_log_params(action, params),
        "result": result,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def current_frontmost_app() -> str:
    script = 'tell application "System Events" to get name of first application process whose frontmost is true'
    return run_osascript(script)


def ensure_allowed_app(ctx: ActionContext, app_name: Optional[str] = None) -> str:
    allowed = set(ctx.config.get("allowed_apps", []))
    current = app_name or current_frontmost_app()
    if allowed and current not in allowed:
        raise OperatorError(f'app "{current}" is not in allowed_apps. add it to config before continuing')
    return current


def ensure_expected_frontmost(expected: Optional[str]) -> Optional[str]:
    if not expected:
        return None
    actual = current_frontmost_app()
    if actual != expected:
        raise OperatorError(f'frontmost app mismatch: expected "{expected}", got "{actual}"')
    return actual


def requires_approval(ctx: ActionContext, action: str) -> bool:
    return action in set(ctx.config.get("require_approval_for", []))


def maybe_require_approval(ctx: ActionContext, action: str, approved: bool) -> None:
    if requires_approval(ctx, action) and not approved:
        raise OperatorError(f'action "{action}" requires explicit approval. rerun with --approve after user confirmation')


def ensure_hotkey_allowed(ctx: ActionContext, keys: str) -> str:
    normalized = normalize_hotkey(keys)
    blocked = set(ctx.config.get("blocked_hotkeys", []))
    if normalized in blocked:
        raise OperatorError(f'hotkey "{normalized}" is blocked by config')
    return normalized


def accessibility_trusted() -> Optional[bool]:
    if Quartz is None:
        return None
    try:
        return bool(Quartz.AXIsProcessTrusted())
    except Exception:
        return None


def cg_point(x: float, y: float):
    ensure_quartz()
    return Quartz.CGPointMake(float(x), float(y))


def do_move_mouse(x: float, y: float) -> None:
    point = cg_point(x, y)
    event = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, point, Quartz.kCGMouseButtonLeft)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
    time.sleep(0.03)


def do_click(x: float, y: float, button: str = "left", count: int = 1) -> None:
    ensure_quartz()
    point = cg_point(x, y)
    btn = MOUSE_BUTTONS[button]
    down_type = Quartz.kCGEventLeftMouseDown if button == "left" else Quartz.kCGEventRightMouseDown
    up_type = Quartz.kCGEventLeftMouseUp if button == "left" else Quartz.kCGEventRightMouseUp
    for idx in range(count):
        event = Quartz.CGEventCreateMouseEvent(None, down_type, point, btn)
        Quartz.CGEventSetIntegerValueField(event, Quartz.kCGMouseEventClickState, idx + 1)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
        time.sleep(0.02)
        event = Quartz.CGEventCreateMouseEvent(None, up_type, point, btn)
        Quartz.CGEventSetIntegerValueField(event, Quartz.kCGMouseEventClickState, idx + 1)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
        time.sleep(0.05)


def do_drag(x1: float, y1: float, x2: float, y2: float, duration: float = 0.35) -> None:
    ensure_quartz()
    start = cg_point(x1, y1)
    end = cg_point(x2, y2)
    button = Quartz.kCGMouseButtonLeft
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, start, button))
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, start, button))
    steps = max(4, int(duration / 0.02))
    for i in range(1, steps + 1):
        t = i / steps
        point = cg_point(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDragged, point, button))
        time.sleep(duration / steps)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, end, button))


def do_scroll(dx: int, dy: int) -> None:
    ensure_quartz()
    event = Quartz.CGEventCreateScrollWheelEvent(None, Quartz.kCGScrollEventUnitPixel, 2, int(dy), int(dx))
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
    time.sleep(0.03)


def escape_applescript_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def do_type_text(text: str) -> None:
    escaped = escape_applescript_text(text)
    run_osascript(f'tell application "System Events" to keystroke "{escaped}"')


def key_to_code(key: str) -> int:
    normalized = key.strip().lower()
    if normalized in SPECIAL_KEY_CODES:
        return SPECIAL_KEY_CODES[normalized]
    if normalized in LETTER_KEY_CODES:
        return LETTER_KEY_CODES[normalized]
    raise OperatorError(f"unsupported key: {key}")


def do_press_key(key: str, modifiers: Optional[Iterable[str]] = None) -> None:
    code = key_to_code(key)
    using: List[str] = []
    for item in modifiers or []:
        mapped = MODIFIER_MAP.get(item.strip().lower())
        if not mapped:
            raise OperatorError(f"unsupported modifier: {item}")
        using.append(mapped)
    using_clause = f" using {{{', '.join(using)}}}" if using else ""
    run_osascript(f'tell application "System Events" to key code {code}{using_clause}')


def maybe_simulate(ctx: ActionContext, action: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not ctx.dry_run:
        return None
    result = {"ok": True, "dry_run": True, **payload}
    result.setdefault("action", action)
    return result


def take_screenshot(ctx: ActionContext, output: Optional[str]) -> Path:
    folder = expand_path(str(ctx.config["screenshot_dir"]))
    folder.mkdir(parents=True, exist_ok=True)
    ext = str(ctx.config.get("screenshot_format", "png")).lower().strip(".") or "png"
    target = Path(output).expanduser() if output else folder / f"shot-{int(time.time() * 1000)}.{ext}"
    target.parent.mkdir(parents=True, exist_ok=True)
    run(["screencapture", "-x", str(target)])
    return target.resolve()


def list_windows_payload() -> List[Dict[str, Any]]:
    script = r'''
set oldTIDs to AppleScript's text item delimiters
set AppleScript's text item delimiters to linefeed
set outputLines to {}
tell application "System Events"
  repeat with p in (application processes whose background only is false)
    set pname to name of p
    set pfront to false
    try
      set pfront to frontmost of p
    end try
    try
      repeat with w in windows of p
        set wname to name of w
        set end of outputLines to (pname & tab & (pfront as text) & tab & wname)
      end repeat
    on error
      set end of outputLines to (pname & tab & (pfront as text) & tab)
    end try
  end repeat
end tell
set AppleScript's text item delimiters to linefeed
set joinedOutput to outputLines as text
set AppleScript's text item delimiters to oldTIDs
return joinedOutput
'''
    raw = run_osascript(script)
    windows: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        windows.append({
            "app": parts[0].strip(),
            "frontmost": len(parts) > 1 and parts[1].strip().lower() == "true",
            "title": parts[2].strip() if len(parts) > 2 else "",
        })
    return windows


def screen_info_payload() -> Dict[str, Any]:
    if Quartz is None:
        return {"quartz_available": False, "displays": []}
    displays = []
    max_displays = 16
    active, count = Quartz.CGGetActiveDisplayList(max_displays, None, None)
    for display_id in active[:count]:
        bounds = Quartz.CGDisplayBounds(display_id)
        displays.append({
            "id": int(display_id),
            "x": int(bounds.origin.x),
            "y": int(bounds.origin.y),
            "width": int(bounds.size.width),
            "height": int(bounds.size.height),
            "main": bool(display_id == Quartz.CGMainDisplayID()),
        })
    return {"quartz_available": True, "displays": displays}


def handle_doctor(ctx: ActionContext, _args: argparse.Namespace) -> Dict[str, Any]:
    ensure_macos()
    quartz_ok = Quartz is not None
    accessibility = accessibility_trusted()
    screenshot_ok = False
    screenshot_error = None
    try:
        shot = take_screenshot(ctx, None)
        screenshot_ok = shot.exists() and shot.stat().st_size > 0
    except Exception as exc:
        screenshot_error = str(exc)
    return {
        "ok": quartz_ok and screenshot_ok,
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "quartz_installed": quartz_ok,
        "accessibility_trusted": accessibility,
        "screen_capture_ok": screenshot_ok,
        "screen_capture_error": screenshot_error,
        "frontmost_app": current_frontmost_app() if screenshot_ok else None,
        "config": redact_config_for_output(ctx.config),
    }


def handle_screenshot(ctx: ActionContext, args: argparse.Namespace) -> Dict[str, Any]:
    ensure_macos()
    out = take_screenshot(ctx, args.output)
    return {"ok": True, "path": str(out), "bytes": out.stat().st_size, "frontmost_app": current_frontmost_app()}


def handle_snapshot(ctx: ActionContext, args: argparse.Namespace) -> Dict[str, Any]:
    ensure_macos()
    out = take_screenshot(ctx, args.output)
    return {
        "ok": True,
        "path": str(out),
        "bytes": out.stat().st_size,
        "frontmost_app": current_frontmost_app(),
        "windows": list_windows_payload(),
        "screen_info": screen_info_payload(),
    }


def handle_frontmost_app(_ctx: ActionContext, _args: argparse.Namespace) -> Dict[str, Any]:
    ensure_macos()
    return {"ok": True, "frontmost_app": current_frontmost_app()}


def handle_list_windows(_ctx: ActionContext, _args: argparse.Namespace) -> Dict[str, Any]:
    ensure_macos()
    windows = list_windows_payload()
    return {"ok": True, "count": len(windows), "windows": windows}


def handle_screen_info(_ctx: ActionContext, _args: argparse.Namespace) -> Dict[str, Any]:
    ensure_macos()
    return {"ok": True, **screen_info_payload()}


def handle_open_app(ctx: ActionContext, args: argparse.Namespace) -> Dict[str, Any]:
    ensure_macos()
    ensure_enabled(ctx, "open-app")
    ensure_allowed_app(ctx, args.app)
    simulated = maybe_simulate(ctx, "open-app", {"requested_app": args.app})
    if simulated:
        return simulated
    run(["open", "-a", args.app])
    time.sleep(args.wait)
    return {"ok": True, "requested_app": args.app, "frontmost_app": current_frontmost_app()}


def handle_focus_app(ctx: ActionContext, args: argparse.Namespace) -> Dict[str, Any]:
    ensure_macos()
    ensure_enabled(ctx, "focus-app")
    ensure_allowed_app(ctx, args.app)
    simulated = maybe_simulate(ctx, "focus-app", {"requested_app": args.app})
    if simulated:
        return simulated
    run(["open", "-a", args.app])
    time.sleep(args.wait)
    return {"ok": True, "requested_app": args.app, "frontmost_app": current_frontmost_app()}


def handle_click(ctx: ActionContext, args: argparse.Namespace) -> Dict[str, Any]:
    ensure_macos()
    ensure_enabled(ctx, "click")
    ensure_expected_frontmost(args.expect_frontmost)
    app = ensure_allowed_app(ctx)
    max_click_count = int(ctx.config.get("max_click_count", 2))
    if args.count < 1 or args.count > max_click_count:
        raise OperatorError(f"count must be between 1 and {max_click_count}")
    simulated = maybe_simulate(ctx, "click", {"frontmost_app": app, "x": args.x, "y": args.y, "button": args.button, "count": args.count})
    if simulated:
        return simulated
    do_click(args.x, args.y, button=args.button, count=args.count)
    return {"ok": True, "frontmost_app": app, "x": args.x, "y": args.y, "button": args.button, "count": args.count}


def handle_move_mouse(ctx: ActionContext, args: argparse.Namespace) -> Dict[str, Any]:
    ensure_macos()
    ensure_enabled(ctx, "move-mouse")
    ensure_expected_frontmost(args.expect_frontmost)
    app = ensure_allowed_app(ctx)
    simulated = maybe_simulate(ctx, "move-mouse", {"frontmost_app": app, "x": args.x, "y": args.y})
    if simulated:
        return simulated
    do_move_mouse(args.x, args.y)
    return {"ok": True, "frontmost_app": app, "x": args.x, "y": args.y}


def handle_drag(ctx: ActionContext, args: argparse.Namespace) -> Dict[str, Any]:
    ensure_macos()
    ensure_enabled(ctx, "drag")
    maybe_require_approval(ctx, "drag", args.approve)
    ensure_expected_frontmost(args.expect_frontmost)
    app = ensure_allowed_app(ctx)
    if args.duration > float(ctx.config.get("max_drag_seconds", 2.0)):
        raise OperatorError(f"drag duration exceeds max_drag_seconds {ctx.config['max_drag_seconds']}")
    simulated = maybe_simulate(ctx, "drag", {"frontmost_app": app, "from": {"x": args.x1, "y": args.y1}, "to": {"x": args.x2, "y": args.y2}, "duration": args.duration})
    if simulated:
        return simulated
    do_drag(args.x1, args.y1, args.x2, args.y2, duration=args.duration)
    return {"ok": True, "frontmost_app": app, "from": {"x": args.x1, "y": args.y1}, "to": {"x": args.x2, "y": args.y2}, "duration": args.duration}


def handle_scroll(ctx: ActionContext, args: argparse.Namespace) -> Dict[str, Any]:
    ensure_macos()
    ensure_enabled(ctx, "scroll")
    ensure_expected_frontmost(args.expect_frontmost)
    app = ensure_allowed_app(ctx)
    simulated = maybe_simulate(ctx, "scroll", {"frontmost_app": app, "dx": args.dx, "dy": args.dy})
    if simulated:
        return simulated
    do_scroll(args.dx, args.dy)
    return {"ok": True, "frontmost_app": app, "dx": args.dx, "dy": args.dy}


def handle_type_text(ctx: ActionContext, args: argparse.Namespace) -> Dict[str, Any]:
    ensure_macos()
    ensure_enabled(ctx, "type-text")
    maybe_require_approval(ctx, "type_text", args.approve)
    ensure_expected_frontmost(args.expect_frontmost)
    app = ensure_allowed_app(ctx)
    simulated = maybe_simulate(ctx, "type-text", {"frontmost_app": app, "typed_length": len(args.text)})
    if simulated:
        return simulated
    do_type_text(args.text)
    return {"ok": True, "frontmost_app": app, "typed_length": len(args.text)}


def handle_press_key(ctx: ActionContext, args: argparse.Namespace) -> Dict[str, Any]:
    ensure_macos()
    ensure_enabled(ctx, "press-key")
    maybe_require_approval(ctx, "press_key", args.approve)
    ensure_expected_frontmost(args.expect_frontmost)
    app = ensure_allowed_app(ctx)
    modifiers = [part.strip() for part in args.modifiers.split(",") if part.strip()] if args.modifiers else []
    simulated = maybe_simulate(ctx, "press-key", {"frontmost_app": app, "key": args.key, "modifiers": modifiers})
    if simulated:
        return simulated
    do_press_key(args.key, modifiers=modifiers)
    return {"ok": True, "frontmost_app": app, "key": args.key, "modifiers": modifiers}


def handle_hotkey(ctx: ActionContext, args: argparse.Namespace) -> Dict[str, Any]:
    ensure_macos()
    ensure_enabled(ctx, "hotkey")
    maybe_require_approval(ctx, "hotkey", args.approve)
    ensure_expected_frontmost(args.expect_frontmost)
    normalized = ensure_hotkey_allowed(ctx, args.keys)
    app = ensure_allowed_app(ctx)
    modifiers, key = parse_hotkey(normalized)
    simulated = maybe_simulate(ctx, "hotkey", {"frontmost_app": app, "hotkey": normalized})
    if simulated:
        return simulated
    do_press_key(key, modifiers=modifiers)
    return {"ok": True, "frontmost_app": app, "hotkey": normalized}


def handle_wait(ctx: ActionContext, args: argparse.Namespace) -> Dict[str, Any]:
    if args.seconds < 0 or args.seconds > 15:
        raise OperatorError("wait seconds must be between 0 and 15")
    if not ctx.dry_run:
        time.sleep(args.seconds)
    return {"ok": True, "dry_run": ctx.dry_run, "seconds": args.seconds}


def add_expect_frontmost(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--expect-frontmost", help="fail unless this app is currently frontmost")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guarded local macOS desktop helper for Codex")
    parser.add_argument("--config", help="path to config.json")
    parser.add_argument("--dry-run", action="store_true", help="show what would happen without changing state")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor")
    sub.add_parser("frontmost-app")
    sub.add_parser("list-windows")
    sub.add_parser("screen-info")

    p = sub.add_parser("screenshot")
    p.add_argument("--output", help="where to write the screenshot")

    p = sub.add_parser("snapshot")
    p.add_argument("--output", help="where to write the screenshot")

    p = sub.add_parser("open-app")
    p.add_argument("--app", required=True)
    p.add_argument("--wait", type=float, default=1.0)

    p = sub.add_parser("focus-app")
    p.add_argument("--app", required=True)
    p.add_argument("--wait", type=float, default=0.5)

    p = sub.add_parser("click")
    p.add_argument("--x", required=True, type=float)
    p.add_argument("--y", required=True, type=float)
    p.add_argument("--button", choices=["left", "right"], default="left")
    p.add_argument("--count", type=int, default=1)
    add_expect_frontmost(p)

    p = sub.add_parser("move-mouse")
    p.add_argument("--x", required=True, type=float)
    p.add_argument("--y", required=True, type=float)
    add_expect_frontmost(p)

    p = sub.add_parser("drag")
    p.add_argument("--x1", required=True, type=float)
    p.add_argument("--y1", required=True, type=float)
    p.add_argument("--x2", required=True, type=float)
    p.add_argument("--y2", required=True, type=float)
    p.add_argument("--duration", type=float, default=0.35)
    p.add_argument("--approve", action="store_true")
    add_expect_frontmost(p)

    p = sub.add_parser("scroll")
    p.add_argument("--dx", type=int, default=0)
    p.add_argument("--dy", type=int, default=0)
    add_expect_frontmost(p)

    p = sub.add_parser("type-text")
    p.add_argument("--text", required=True)
    p.add_argument("--approve", action="store_true")
    add_expect_frontmost(p)

    p = sub.add_parser("press-key")
    p.add_argument("--key", required=True)
    p.add_argument("--modifiers")
    p.add_argument("--approve", action="store_true")
    add_expect_frontmost(p)

    p = sub.add_parser("hotkey")
    p.add_argument("--keys", required=True)
    p.add_argument("--approve", action="store_true")
    add_expect_frontmost(p)

    p = sub.add_parser("wait")
    p.add_argument("--seconds", type=float, required=True)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    ctx = ActionContext(config=load_config(args.config), plugin_root=plugin_root(), dry_run=bool(args.dry_run))
    handlers = {
        "doctor": handle_doctor,
        "screenshot": handle_screenshot,
        "snapshot": handle_snapshot,
        "frontmost-app": handle_frontmost_app,
        "list-windows": handle_list_windows,
        "screen-info": handle_screen_info,
        "open-app": handle_open_app,
        "focus-app": handle_focus_app,
        "click": handle_click,
        "move-mouse": handle_move_mouse,
        "drag": handle_drag,
        "scroll": handle_scroll,
        "type-text": handle_type_text,
        "press-key": handle_press_key,
        "hotkey": handle_hotkey,
        "wait": handle_wait,
    }
    try:
        result = handlers[args.command](ctx, args)
        payload = {"action": args.command, "timestamp": utc_now_iso(), **result}
        log_action(ctx, args.command, vars(args), payload)
        return json_out(payload)
    except Exception as exc:
        payload = {"action": args.command, "timestamp": utc_now_iso(), "ok": False, "dry_run": bool(args.dry_run), "error": str(exc)}
        try:
            log_action(ctx, args.command, vars(args), payload)
        except Exception:
            pass
        return json_out(payload, status=1)


if __name__ == "__main__":
    raise SystemExit(main())
