"""
config_manager.py — Persistent local configuration for the MiniLang Compiler.
CIT4004 · University of Technology, Jamaica

Settings are stored in ~/.minilang_config.json on the user's home directory.
This file is NEVER committed to git (.gitignore excludes it via *.key / .env rules,
and the filename itself is outside the repo tree).

Usage:
    from config_manager import apply_api_key, get_api_key, set_api_key

    apply_api_key()   # call once at startup — injects saved key into env
    set_api_key(k)    # call from Settings dialog to persist a new key
    get_api_key()     # returns the currently saved key string (or '')
"""

import json
import os
from pathlib import Path

# ── Storage location ──────────────────────────────────────────────────────────
# ~/.minilang_config.json   (cross-platform: works on macOS, Windows, Linux)
_CONFIG_PATH = Path.home() / ".minilang_config.json"


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
