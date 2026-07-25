"""
Structured logging for FrameFlow AI.

Provides a centralized logging system with:
- Rotating file handler (max 10 MB per file, 5 backups)
- Console output with color-coded levels
- Processing statistics tracking
- Structured log format for machine parsing
"""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from src.utils.constants import APP_NAME, LOG_DIR


# ---------------------------------------------------------------------------
# Processing Statistics
# ---------------------------------------------------------------------------

@dataclass
class ProcessingStats:
    """Tracks frame processing statistics for a single video."""

    video_path: str = ""
    total_frames: int = 0
    frames_analyzed: int = 0
    frames_kept: int = 0
    frames_removed: int = 0
    frames_uncertain: int = 0
    scene_boundaries: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def elapsed_seconds(self) -> float:
        """Total processing time in seconds."""
        end = self.end_time if self.end_time > 0 else time.time()
        return end - self.start_time

    @property
    def fps_processing(self) -> float:
        """Frames processed per second."""
        elapsed = self.elapsed_seconds
        if elapsed <= 0:
            return 0.0
        return self.frames_analyzed / elapsed

    @property
    def removal_percentage(self) -> float:
        """Percentage of frames marked for removal."""
        if self.frames_analyzed == 0:
            return 0.0
        return (self.frames_removed / self.frames_analyzed) * 100.0

    @property
    def progress(self) -> float:
        """Processing progress as 0.0–1.0."""
        if self.total_frames == 0:
            return 0.0
        return min(self.frames_analyzed / self.total_frames, 1.0)

    def finalize(self) -> None:
        """Mark processing as complete."""
        self.end_time = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON reports."""
        return {
            "video_path": self.video_path,
            "total_frames": self.total_frames,
            "frames_analyzed": self.frames_analyzed,
            "frames_kept": self.frames_kept,
            "frames_removed": self.frames_removed,
            "frames_uncertain": self.frames_uncertain,
            "scene_boundaries": self.scene_boundaries,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "processing_fps": round(self.fps_processing, 2),
            "removal_percentage": round(self.removal_percentage, 2),
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Custom Formatter
# ---------------------------------------------------------------------------

class ColorFormatter(logging.Formatter):
    """Adds ANSI color codes to console log output."""

    COLORS = {
        logging.DEBUG: "\033[36m",     # Cyan
        logging.INFO: "\033[32m",      # Green
        logging.WARNING: "\033[33m",   # Yellow
        logging.ERROR: "\033[31m",     # Red
        logging.CRITICAL: "\033[41m",  # Red background
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


# ---------------------------------------------------------------------------
# Logger Setup
# ---------------------------------------------------------------------------

_logger_initialized: bool = False


def setup_logger(
    log_level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = True,
) -> logging.Logger:
    """
    Configure and return the application logger.

    Creates a rotating file handler and optional console handler.
    Safe to call multiple times — subsequent calls are no-ops.

    Args:
        log_level: Minimum log level (default: INFO).
        log_to_file: Whether to write logs to disk.
        log_to_console: Whether to print logs to stderr.

    Returns:
        Configured root logger for the application.
    """
    global _logger_initialized  # noqa: PLW0603
    logger = logging.getLogger(APP_NAME)

    if _logger_initialized:
        return logger

    logger.setLevel(log_level)
    logger.propagate = False

    # Structured format for file logs
    file_format = logging.Formatter(
        fmt=(
            "%(asctime)s | %(levelname)-8s | %(name)s.%(funcName)s:%(lineno)d | "
            "%(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console format (shorter, with color)
    console_format = ColorFormatter(
        fmt="%(asctime)s │ %(levelname)-8s │ %(message)s",
        datefmt="%H:%M:%S",
    )

    if log_to_file:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOG_DIR / "frameflow.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)

    _logger_initialized = True
    logger.info("FrameFlow AI logger initialized (level=%s)", logging.getLevelName(log_level))
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Get a child logger for a specific module.

    Args:
        name: Module name (e.g., 'core.detector'). If None, returns root logger.

    Returns:
        Logger instance.
    """
    base = logging.getLogger(APP_NAME)
    if name:
        return base.getChild(name)
    return base
