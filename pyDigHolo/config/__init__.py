"""Load unified app settings from appSettings.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_SETTINGS_FILE = Path(__file__).resolve().parent / "appSettings.json"


@lru_cache(maxsize=1)
def load_app_settings() -> dict[str, Any]:
    """Return appSettings.json as a dict (cached)."""
    with _SETTINGS_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def reload_app_settings() -> dict[str, Any]:
    """Drop cache and re-read appSettings.json (useful after edits)."""
    load_app_settings.cache_clear()
    return load_app_settings()
