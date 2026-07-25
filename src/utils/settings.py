"""
User settings persistence for FrameFlow AI.

JSON-backed settings with schema defaults, validation, and auto-save.
Thread-safe read/write with a simple lock.
"""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.utils.constants import (
    DEFAULT_AI_CONFIDENCE_THRESHOLD,
    DEFAULT_AI_WEIGHT,
    DEFAULT_BATCH_SIZE,
    DEFAULT_CACHE_SIZE_MB,
    DEFAULT_HISTOGRAM_WEIGHT,
    DEFAULT_MIN_CONSECUTIVE_FRAMES,
    DEFAULT_OPTICAL_FLOW_WEIGHT,
    DEFAULT_PHASH_WEIGHT,
    DEFAULT_SCENE_THRESHOLD,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_SSIM_WEIGHT,
    DEFAULT_UNCERTAIN_LOWER,
    ExportCodec,
    SETTINGS_FILE,
)
from src.utils.logger import get_logger

logger = get_logger("settings")


# ---------------------------------------------------------------------------
# Default Settings Schema
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS: dict[str, Any] = {
    # Detection
    "detection": {
        "similarity_threshold": DEFAULT_SIMILARITY_THRESHOLD,
        "uncertain_lower_bound": DEFAULT_UNCERTAIN_LOWER,
        "ai_confidence_threshold": DEFAULT_AI_CONFIDENCE_THRESHOLD,
        "min_consecutive_frames": DEFAULT_MIN_CONSECUTIVE_FRAMES,
        "scene_threshold": DEFAULT_SCENE_THRESHOLD,
        "enable_ai_mode": True,
        "weights": {
            "ssim": DEFAULT_SSIM_WEIGHT,
            "phash": DEFAULT_PHASH_WEIGHT,
            "histogram": DEFAULT_HISTOGRAM_WEIGHT,
            "optical_flow": DEFAULT_OPTICAL_FLOW_WEIGHT,
            "ai_features": DEFAULT_AI_WEIGHT,
        },
    },

    # Export
    "export": {
        "codec": ExportCodec.H264.value,
        "output_fps": 0,  # 0 = same as source
        "output_directory": "",
        "preserve_audio": True,
        "audio_handling": "trim",  # "trim" or "stretch"
    },

    # Performance
    "performance": {
        "gpu_enabled": True,
        "gpu_device_index": 0,
        "cache_size_mb": DEFAULT_CACHE_SIZE_MB,
        "batch_size": DEFAULT_BATCH_SIZE,
        "max_worker_threads": 0,  # 0 = auto-detect
    },

    # UI
    "ui": {
        "theme": "dark",
        "preview_quality": "high",  # "low", "medium", "high"
        "show_frame_numbers": True,
        "show_confidence_overlay": True,
        "timeline_zoom": 1.0,
        "window_geometry": None,  # Saved as [x, y, width, height]
        "window_state": None,  # Maximized / normal
    },
}


# ---------------------------------------------------------------------------
# Settings Manager
# ---------------------------------------------------------------------------

class SettingsManager:
    """
    Thread-safe JSON-backed settings manager.

    Usage:
        settings = SettingsManager()
        threshold = settings.get("detection.similarity_threshold")
        settings.set("detection.similarity_threshold", 0.95)
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or SETTINGS_FILE
        self._lock = threading.RLock()
        self._data: dict[str, Any] = deepcopy(DEFAULT_SETTINGS)
        self._load()

    # -- Public API ---------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting by dot-separated key path.

        Args:
            key: Dot-separated key, e.g. "detection.similarity_threshold".
            default: Fallback value if key is missing.

        Returns:
            The setting value, or *default* if not found.
        """
        with self._lock:
            return self._resolve(key, default)

    def set(self, key: str, value: Any, *, auto_save: bool = True) -> None:
        """
        Set a setting by dot-separated key path.

        Args:
            key: Dot-separated key path.
            value: New value.
            auto_save: Persist to disk immediately (default True).
        """
        with self._lock:
            parts = key.split(".")
            node = self._data
            for part in parts[:-1]:
                if part not in node or not isinstance(node[part], dict):
                    node[part] = {}
                node = node[part]
            node[parts[-1]] = value
            if auto_save:
                self._save()
        logger.debug("Setting '%s' = %r", key, value)

    def get_section(self, section: str) -> dict[str, Any]:
        """Return an entire settings section as a dict copy."""
        with self._lock:
            val = self._resolve(section)
            if isinstance(val, dict):
                return deepcopy(val)
            return {}

    def reset(self, key: str | None = None) -> None:
        """
        Reset a setting or all settings to defaults.

        Args:
            key: Dot-separated key to reset, or None to reset everything.
        """
        with self._lock:
            if key is None:
                self._data = deepcopy(DEFAULT_SETTINGS)
            else:
                default_val = self._resolve_from(key, DEFAULT_SETTINGS)
                if default_val is not None:
                    self.set(key, deepcopy(default_val), auto_save=False)
            self._save()
        logger.info("Settings reset: %s", key or "ALL")

    def save(self) -> None:
        """Explicitly persist settings to disk."""
        with self._lock:
            self._save()

    def to_dict(self) -> dict[str, Any]:
        """Return a deep copy of all settings."""
        with self._lock:
            return deepcopy(self._data)

    # -- Private Helpers ----------------------------------------------------

    def _resolve(self, key: str, default: Any = None) -> Any:
        """Walk the nested dict by dot-separated key."""
        return self._resolve_from(key, self._data, default)

    @staticmethod
    def _resolve_from(key: str, data: dict[str, Any], default: Any = None) -> Any:
        parts = key.split(".")
        node: Any = data
        for part in parts:
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def _load(self) -> None:
        """Load settings from JSON file, merging with defaults."""
        if not self._path.exists():
            logger.info("No settings file found; using defaults.")
            self._save()
            return
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            self._data = self._deep_merge(deepcopy(DEFAULT_SETTINGS), loaded)
            logger.info("Settings loaded from %s", self._path)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load settings (%s); using defaults.", exc)
            self._data = deepcopy(DEFAULT_SETTINGS)

    def _save(self) -> None:
        """Persist current settings to JSON file."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.error("Failed to save settings: %s", exc)

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Recursively merge *override* into *base*, keeping base keys as defaults."""
        merged = base.copy()
        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = SettingsManager._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_instance: SettingsManager | None = None
_instance_lock = threading.Lock()


def get_settings() -> SettingsManager:
    """Return the global SettingsManager singleton."""
    global _instance  # noqa: PLW0603
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SettingsManager()
    return _instance
