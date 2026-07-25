"""
Application-wide constants for FrameFlow AI.

Centralizes all magic numbers, default values, supported formats,
and configuration constants used throughout the application.
"""

from __future__ import annotations

import os
from enum import Enum, auto
from pathlib import Path
from typing import Final

# ---------------------------------------------------------------------------
# Application Identity
# ---------------------------------------------------------------------------
APP_NAME: Final[str] = "FrameFlow AI"
APP_VERSION: Final[str] = "1.0.0"
APP_DESCRIPTION: Final[str] = "Intelligent Dead Frame Remover for Video Editors"
ORG_NAME: Final[str] = "FrameFlowAI"
ORG_DOMAIN: Final[str] = "frameflow.ai"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# Resolve base directory whether running from source or frozen (PyInstaller)
if getattr(os.sys, "frozen", False):
    BASE_DIR: Final[Path] = Path(os.sys.executable).parent  # type: ignore[attr-defined]
else:
    BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent.parent

SRC_DIR: Final[Path] = BASE_DIR / "src"
RESOURCES_DIR: Final[Path] = SRC_DIR / "resources"
ICONS_DIR: Final[Path] = RESOURCES_DIR / "icons"
FONTS_DIR: Final[Path] = RESOURCES_DIR / "fonts"
MODELS_DIR: Final[Path] = RESOURCES_DIR / "models"

# User data directory (per-user, writable)
USER_DATA_DIR: Final[Path] = Path(os.environ.get(
    "FRAMEFLOW_DATA_DIR",
    Path.home() / ".frameflow_ai",
))
LOG_DIR: Final[Path] = USER_DATA_DIR / "logs"
SESSIONS_DIR: Final[Path] = USER_DATA_DIR / "sessions"
CACHE_DIR: Final[Path] = USER_DATA_DIR / "cache"
SETTINGS_FILE: Final[Path] = USER_DATA_DIR / "settings.json"
RECENT_FILES_PATH: Final[Path] = USER_DATA_DIR / "recent_files.json"

# Ensure user directories exist
for _dir in (USER_DATA_DIR, LOG_DIR, SESSIONS_DIR, CACHE_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Supported Formats
# ---------------------------------------------------------------------------
SUPPORTED_VIDEO_EXTENSIONS: Final[tuple[str, ...]] = (
    ".mp4", ".mkv", ".mov", ".avi", ".webm",
)

SUPPORTED_IMAGE_EXTENSIONS: Final[tuple[str, ...]] = (
    ".png", ".jpg", ".jpeg", ".exr", ".tiff", ".bmp",
)

VIDEO_FILTER: Final[str] = "Video Files ({})".format(
    " ".join(f"*{ext}" for ext in SUPPORTED_VIDEO_EXTENSIONS)
)

# ---------------------------------------------------------------------------
# Export Codecs
# ---------------------------------------------------------------------------

class ExportCodec(Enum):
    """Supported video export codecs."""
    H264 = "libx264"
    H265 = "libx265"
    PRORES = "prores_ks"
    DNXHD = "dnxhd"
    FFV1 = "ffv1"
    LOSSLESS_H264 = "libx264rgb"

    @property
    def display_name(self) -> str:
        """Human-readable codec name."""
        names = {
            "libx264": "H.264 (AVC)",
            "libx265": "H.265 (HEVC)",
            "prores_ks": "Apple ProRes",
            "dnxhd": "Avid DNxHD",
            "ffv1": "FFV1 (Lossless)",
            "libx264rgb": "H.264 Lossless (RGB)",
        }
        return names.get(self.value, self.value)

    @property
    def file_extension(self) -> str:
        """Default file extension for this codec."""
        extensions = {
            "libx264": ".mp4",
            "libx265": ".mp4",
            "prores_ks": ".mov",
            "dnxhd": ".mxf",
            "ffv1": ".mkv",
            "libx264rgb": ".mkv",
        }
        return extensions.get(self.value, ".mp4")


class ImageFormat(Enum):
    """Supported image sequence export formats."""
    PNG = "png"
    JPEG = "jpeg"
    EXR = "exr"


# ---------------------------------------------------------------------------
# Frame Decision
# ---------------------------------------------------------------------------

class FrameDecision(Enum):
    """Classification for each analyzed frame."""
    KEEP = auto()
    REMOVE = auto()
    UNCERTAIN = auto()
    SCENE_BOUNDARY = auto()  # First frame of a new scene, always kept

    @property
    def color_hex(self) -> str:
        """Color for timeline visualization."""
        colors = {
            FrameDecision.KEEP: "#4CAF50",       # Green
            FrameDecision.REMOVE: "#F44336",      # Red
            FrameDecision.UNCERTAIN: "#FFC107",   # Amber
            FrameDecision.SCENE_BOUNDARY: "#2196F3",  # Blue
        }
        return colors[self]


# ---------------------------------------------------------------------------
# Detection Defaults
# ---------------------------------------------------------------------------

# Algorithm weights (must sum to 1.0)
DEFAULT_SSIM_WEIGHT: Final[float] = 0.30
DEFAULT_PHASH_WEIGHT: Final[float] = 0.20
DEFAULT_HISTOGRAM_WEIGHT: Final[float] = 0.15
DEFAULT_OPTICAL_FLOW_WEIGHT: Final[float] = 0.25
DEFAULT_AI_WEIGHT: Final[float] = 0.10

# Thresholds
DEFAULT_SIMILARITY_THRESHOLD: Final[float] = 0.97  # Above this = dead frame
DEFAULT_AI_CONFIDENCE_THRESHOLD: Final[float] = 0.85
DEFAULT_UNCERTAIN_LOWER: Final[float] = 0.90  # Below threshold but above this = uncertain
DEFAULT_MIN_CONSECUTIVE_FRAMES: Final[int] = 1  # Min repeated frames to mark as dead
DEFAULT_SCENE_THRESHOLD: Final[float] = 0.35  # Below this = scene change

# Optical flow
OPTICAL_FLOW_ZERO_THRESHOLD: Final[float] = 0.5  # Magnitude below this = "near zero"

# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------
DEFAULT_CACHE_SIZE_MB: Final[int] = 2048  # 2 GB frame cache
DEFAULT_BATCH_SIZE: Final[int] = 32  # Frames processed per batch
MAX_PREVIEW_RESOLUTION: Final[tuple[int, int]] = (1920, 1080)
THUMBNAIL_SIZE: Final[tuple[int, int]] = (160, 90)
MAX_WORKER_THREADS: Final[int] = min(os.cpu_count() or 4, 16)

# ---------------------------------------------------------------------------
# AI Model
# ---------------------------------------------------------------------------
AI_MODEL_NAME: Final[str] = "dinov2_small"
AI_MODEL_FILENAME: Final[str] = "dinov2_vits14.onnx"
AI_MODEL_URL: Final[str] = (
    "https://huggingface.co/facebook/dinov2-small/resolve/main/onnx/model.onnx"
)
AI_MODEL_INPUT_SIZE: Final[tuple[int, int]] = (518, 518)  # DINOv2 native patch size
AI_FEATURE_DIM: Final[int] = 384  # DINOv2-Small output dim

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
MIN_WINDOW_SIZE: Final[tuple[int, int]] = (1280, 720)
DEFAULT_WINDOW_SIZE: Final[tuple[int, int]] = (1600, 900)
MAX_RECENT_FILES: Final[int] = 20
AUTOSAVE_INTERVAL_MS: Final[int] = 60_000  # 1 minute

# ---------------------------------------------------------------------------
# Keyboard Shortcuts
# ---------------------------------------------------------------------------
SHORTCUTS: Final[dict[str, str]] = {
    "open_file": "Ctrl+O",
    "save_session": "Ctrl+S",
    "export": "Ctrl+E",
    "undo": "Ctrl+Z",
    "redo": "Ctrl+Shift+Z",
    "play_pause": "Space",
    "frame_forward": "Right",
    "frame_backward": "Left",
    "zoom_in": "Ctrl+=",
    "zoom_out": "Ctrl+-",
    "zoom_fit": "Ctrl+0",
    "toggle_keep": "K",
    "toggle_remove": "R",
    "select_all": "Ctrl+A",
    "deselect_all": "Ctrl+D",
    "settings": "Ctrl+,",
    "fullscreen": "F11",
    "quit": "Ctrl+Q",
}
