# File        : config_manager.py
# Description : Persistent local configuration for the NovaScript Compiler
# =============================================================================
# Authors     : Rachjaye Gayle      - 2100400
#             : Rushane  Green      - 2006930
#             : Abbygayle Higgins   - 2106327
#             : Lamar Haye          - 2111690
# -----------------------------------------------------------------------------
# Institution : University of Technology, Jamaica
# Faculty     : School of Computing & Information Technology (FENC)
# Course      : Analysis of Programming Languages | CIT4004
# Tutor       : Dr. David White
# =============================================================================

import json
import os
from pathlib import Path

# ── Storage location ──────────────────────────────────────────────────────────
# ~/.novascript_config.json   (cross-platform: works on macOS, Windows, Linux)
_CONFIG_PATH = Path.home() / ".novascript_config.json"


# ── Low-level helpers ─────────────────────────────────────────────────────────

def load_config() -> dict:
    """Load the config dict from disk. Returns {} if missing or unreadable."""
    try:
        if _CONFIG_PATH.exists():
            with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
    except Exception:
        pass
    return {}


def save_config(cfg: dict) -> None:
    """Write *cfg* to disk. Silently prints a warning on failure."""
    try:
        with open(_CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
    except Exception as exc:
        print(f"Warning: could not save config to {_CONFIG_PATH}: {exc}")


# ── API-key helpers ───────────────────────────────────────────────────────────

def get_api_key() -> str:
    """Return the saved Google API key, or '' if none is stored."""
    cfg = load_config()
    # Support migrating from the old anthropic_api_key field (ignored now)
    return cfg.get("google_api_key", "")


def set_api_key(key: str) -> None:
    """
    Persist *key* to the config file and inject it into the current process
    environment so llm_runner.py sees it immediately (no restart required).
    Pass an empty string to clear the key.
    """
    key = key.strip()
    cfg = load_config()
    if key:
        cfg["google_api_key"] = key
        os.environ["GOOGLE_API_KEY"] = key
    else:
        cfg.pop("google_api_key", None)
        os.environ.pop("GOOGLE_API_KEY", None)
    save_config(cfg)


def apply_api_key() -> bool:
    """
    Load the saved Google API key from disk and inject it into the environment.
    Call this once at application startup — before any LLM calls are made.

    Returns True if a key was found and applied, False otherwise.
    """
    key = get_api_key()
    if key:
        os.environ["GOOGLE_API_KEY"] = key
        return True
    return False


def mask_key(key: str) -> str:
    """
    Return a safe display version of *key* for the Settings dialog,
    e.g.  'sk-ant-api03-…………………………xxxx'
    Shows first 12 chars + dots + last 4 chars.
    """
    if not key:
        return "(not set)"
    if len(key) <= 16:
        return "*" * len(key)
    return key[:12] + "…" * 10 + key[-4:]
