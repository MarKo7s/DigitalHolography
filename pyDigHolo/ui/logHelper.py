"""Viewport widget file logger under ProgramData (paths from appSettings.json)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from ..config import load_app_settings

_LOGGER_NAME = "DigHoloViewport"
_cache: logging.Logger | None = None


def program_data_root() -> Path:
    """``C:\\ProgramData`` on Windows via ``%PROGRAMDATA%``."""
    return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))


def lab_root() -> Path:
    """``<ProgramData>/LAB``."""
    return program_data_root() / "LAB"


def _logger_cfg() -> dict:
    return load_app_settings().get("logger", {})


def _viewport_cfg() -> dict:
    return _logger_cfg().get("viewport", {})


def log_dir() -> Path:
    """``<ProgramData>/LAB/<base_path>/<viewport.subdir>``."""
    cfg = _logger_cfg()
    base = cfg.get("base_path", "algorithms")
    subdir = _viewport_cfg().get("subdir", "DigitalHolography/Viewport")
    return lab_root() / base / Path(subdir)


def log_path() -> Path:
    filename = _viewport_cfg().get("filename", "DigHoloViewport.log")
    return log_dir() / filename


def reset_logger_enabled() -> bool:
    return bool(_logger_cfg().get("reset_logger", False))


def get_logger(level: int = logging.INFO) -> logging.Logger:
    """Return DigHoloViewport file logger.

    If ``logger.reset_logger`` is true in appSettings.json, handlers are rebuilt
    and the log file is truncated on every call (fresh session log).
    """
    global _cache
    reset = reset_logger_enabled()
    if not reset and _cache is not None:
        return _cache

    directory = log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = log_path()

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)

    mode = "w" if reset else "a"
    handler = logging.FileHandler(path, mode=mode, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    logger.addHandler(handler)

    _cache = None if reset else logger
    return logger
