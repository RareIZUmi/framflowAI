"""
Video loading and metadata extraction for FrameFlow AI.

Wraps FFprobe for metadata and OpenCV for frame access.
Validates file format, extracts stream info, and provides
a high-level VideoFile object for the rest of the application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.utils.constants import SUPPORTED_VIDEO_EXTENSIONS
from src.utils.ffmpeg import FFmpegManager, VideoMetadata, get_ffmpeg
from src.utils.logger import get_logger

logger = get_logger("core.video_loader")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class VideoLoadError(Exception):
    """Raised when a video file cannot be loaded or is invalid."""


class UnsupportedFormatError(VideoLoadError):
    """Raised when the video format is not supported."""


# ---------------------------------------------------------------------------
# Video File
# ---------------------------------------------------------------------------

@dataclass
class VideoFile:
    """
    Represents a loaded video file with metadata and frame access.

    This is the primary data object passed through the application.
    It holds metadata from FFprobe and an OpenCV capture object for
    frame-by-frame reading.
    """

    path: Path
    metadata: VideoMetadata
    _capture: cv2.VideoCapture | None = field(default=None, repr=False)

    @property
    def capture(self) -> cv2.VideoCapture:
        """Lazily open the OpenCV capture. Reuses if already open."""
        if self._capture is None or not self._capture.isOpened():
            self._capture = cv2.VideoCapture(str(self.path))
            if not self._capture.isOpened():
                raise VideoLoadError(f"OpenCV failed to open: {self.path}")
        return self._capture

    @property
    def width(self) -> int:
        return self.metadata.width

    @property
    def height(self) -> int:
        return self.metadata.height

    @property
    def fps(self) -> float:
        return self.metadata.fps

    @property
    def frame_count(self) -> int:
        return self.metadata.frame_count

    @property
    def duration(self) -> float:
        return self.metadata.duration

    def read_frame(self, index: int) -> np.ndarray | None:
        """
        Read a specific frame by index.

        Args:
            index: Zero-based frame index.

        Returns:
            BGR numpy array, or None if the frame cannot be read.
        """
        cap = self.capture
        current_pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES))

        # Only seek if not already at the target position
        if current_pos != index:
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)

        ret, frame = cap.read()
        if not ret or frame is None:
            logger.warning("Failed to read frame %d from %s", index, self.path.name)
            return None
        return frame

    def read_frame_rgb(self, index: int) -> np.ndarray | None:
        """Read a frame and convert from BGR to RGB."""
        frame = self.read_frame(index)
        if frame is not None:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return None

    def close(self) -> None:
        """Release the OpenCV capture object."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None
            logger.debug("Released capture for %s", self.path.name)

    def __del__(self) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Video Loader
# ---------------------------------------------------------------------------

class VideoLoader:
    """
    Loads and validates video files.

    Usage:
        loader = VideoLoader()
        video = loader.load("path/to/video.mp4")
        print(video.metadata)
    """

    def __init__(self, ffmpeg: FFmpegManager | None = None) -> None:
        self._ffmpeg = ffmpeg or get_ffmpeg()

    def load(self, path: str | Path) -> VideoFile:
        """
        Load a video file: validate format, extract metadata, verify readability.

        Args:
            path: Path to the video file.

        Returns:
            A VideoFile object ready for frame extraction.

        Raises:
            UnsupportedFormatError: If the file extension is not supported.
            VideoLoadError: If the file doesn't exist, is corrupt, or cannot be read.
        """
        path = Path(path).resolve()
        logger.info("Loading video: %s", path)

        # Validate existence
        if not path.exists():
            raise VideoLoadError(f"File not found: {path}")
        if not path.is_file():
            raise VideoLoadError(f"Not a file: {path}")

        # Validate extension
        ext = path.suffix.lower()
        if ext not in SUPPORTED_VIDEO_EXTENSIONS:
            raise UnsupportedFormatError(
                f"Unsupported format '{ext}'. "
                f"Supported: {', '.join(SUPPORTED_VIDEO_EXTENSIONS)}"
            )

        # Extract metadata via FFprobe
        try:
            metadata = self._ffmpeg.probe(str(path))
        except Exception as exc:
            raise VideoLoadError(f"Failed to probe video: {exc}") from exc

        # Validate video has frames
        if metadata.frame_count <= 0:
            raise VideoLoadError(
                f"Video reports 0 frames. File may be corrupt: {path}"
            )
        if metadata.width <= 0 or metadata.height <= 0:
            raise VideoLoadError(
                f"Invalid resolution {metadata.width}x{metadata.height}: {path}"
            )

        # Verify OpenCV can open it
        video = VideoFile(path=path, metadata=metadata)
        try:
            test_frame = video.read_frame(0)
            if test_frame is None:
                raise VideoLoadError(f"OpenCV cannot read frames from: {path}")
        except Exception as exc:
            video.close()
            raise VideoLoadError(f"Frame read test failed: {exc}") from exc

        logger.info(
            "Video loaded: %s | %s | %s | %s | %d frames",
            path.name,
            metadata.resolution_str,
            metadata.fps_str,
            metadata.duration_str,
            metadata.frame_count,
        )
        return video

    def validate_path(self, path: str | Path) -> tuple[bool, str]:
        """
        Quick validation without full loading.

        Returns:
            (is_valid, message) tuple.
        """
        path = Path(path)
        if not path.exists():
            return False, "File does not exist."
        if not path.is_file():
            return False, "Path is not a file."
        ext = path.suffix.lower()
        if ext not in SUPPORTED_VIDEO_EXTENSIONS:
            return False, f"Unsupported format: {ext}"
        return True, "OK"
