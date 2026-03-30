from pathlib import Path
import importlib.util


SPEC = importlib.util.spec_from_file_location(
    "macos_operator",
    Path(__file__).resolve().parents[1] / "bin" / "macos_operator.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_normalize_hotkey():
    assert MODULE.normalize_hotkey(" Cmd + Shift + P ") == "cmd+shift+p"


def test_parse_hotkey():
    modifiers, key = MODULE.parse_hotkey("cmd+shift+p")
    assert modifiers == ["cmd", "shift"]
    assert key == "p"


def test_sanitize_log_params_redacts_text():
    payload = MODULE.sanitize_log_params("type-text", {"text": "secret", "approve": True})
    assert payload["text_redacted"] is True
    assert payload["typed_length"] == 6
    assert "text" not in payload


def test_redact_config_for_output():
    config = {
        "allowed_apps": ["Safari"],
        "require_approval_for": ["type_text"],
        "blocked_hotkeys": ["cmd+q"],
        "disable_file": "~/disabled",
    }
    redacted = MODULE.redact_config_for_output(config)
    assert redacted["allowed_apps"] == ["Safari"]
    assert redacted["require_approval_for"] == ["type_text"]
    assert redacted["blocked_hotkeys"] == ["cmd+q"]
    assert redacted["disable_file"] == "~/disabled"
