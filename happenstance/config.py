import json
import os
from pathlib import Path
from typing import Any, Dict

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config_logic.json"


def _load_raw_config() -> Dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config(profile: str | None = None) -> Dict[str, Any]:
    """Load a profile configuration and apply environment overrides."""
    raw = _load_raw_config()
    profiles = raw.get("profiles", {})
    selected = profile or os.getenv("PROFILE") or "default"
    if selected not in profiles:
        raise ValueError(f"Profile '{selected}' not found in config.")

    config = profiles[selected].copy()
    live_search_mode = os.getenv("LIVE_SEARCH_MODE")
    if live_search_mode:
        config.setdefault("live_search", {})
        config["live_search"]["mode"] = live_search_mode

    event_window = os.getenv("EVENT_WINDOW_DAYS")
    if event_window:
        try:
            config["event_window_days"] = int(event_window)
        except ValueError as err:
            raise ValueError(f"EVENT_WINDOW_DAYS must be an integer, got: {event_window}") from err
    else:
        config["event_window_days"] = config.get("event_window_days", 14)

    base_url = os.getenv("BASE_URL")
    if base_url:
        config["base_url"] = base_url

    config["profile"] = selected
    return config
