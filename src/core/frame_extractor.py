"""
Multi-threaded frame extraction for FrameFlow AI.

Provides a producer-consumer pattern for efficient frame reading:
- Producer thread reads frames sequentially via OpenCV
- Consumer (the caller) processes frames as they arrive
- Frames are cached in the LRU FrameCache for random access

Also handles thumbnail generation for the timeline widget.
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Generator

import cv2
import numpy as np

from src.core.frame_cache import FrameCache
from src.core.video_loader import VideoFile
from src.utils.constants import MAX_WORKER_THREADS, THUMBNAIL_SIZE
from src.utils.logger import get_logger

logger = get_logger("core.frame_extractor")


# ---------------------------------------------------------------------------
# Frame Data
# ---------------------------------------------------------------------------

class FrameData:
    """Container for a single extracted frame with its index."""

    __slots__ = ("index", "frame", "thumbnail")

    def __init__(
        self,
        index: int,
        frame: np.ndarray,
        thumbnail: np.ndarray | None = None,
    ) -> None:
        self.index = index
        self.frame = frame  # BGR, full resolution
        self.thumbnail = thumbnail  # RGB, THUMBNAIL_SIZE


# ---------------------------------------------------------------------------
# Frame Extractor
# ---------------------------------------------------------------------------

class FrameExtractor:
    """
    Extracts frames from a VideoFile with caching and thumbnail generation.

    Usage:
        extractor = FrameExtractor(video_file, cache)

        # Sequential extraction (producer-consumer)
        for frame_data in extractor.extract_all():
            process(frame_data)

        # Random access (uses cache)
        frame = extractor.get_frame(42)

        # Batch extraction
        frames = extractor.extract_range(100, 200)
    """

    def __init__(
        self,
        video: VideoFile,
        cache: FrameCache | None = None,
        generate_thumbnails: bool = True,
    ) -> None:
        self._video = video
        self._cache = cache or FrameCache()
        self._generate_thumbnails = generate_thumbnails
        self._thumbnails: dict[int, np.ndarray] = {}
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()

    # -- Properties ---------------------------------------------------------

    @property
    def video(self) -> VideoFile:
        return self._video

    @property
    def video_path_str(self) -> str:
        return str(self._video.path)

    @property
    def frame_count(self) -> int:
        return self._video.frame_count

    # -- Sequential Extraction (Generator) ----------------------------------

    def extract_all(
        self,
        start: int = 0,
        end: int | None = None,
        prefetch_size: int = 64,
    ) -> Generator[FrameData, None, None]:
        """
        Yield all frames sequentially using a background reader thread.

        Args:
            start: First frame index (inclusive).
            end: Last frame index (exclusive). None = all frames.
            prefetch_size: Number of frames to buffer ahead.

        Yields:
            FrameData objects in order.
        """
        end = end or self._video.frame_count
        frame_queue: queue.Queue[FrameData | None] = queue.Queue(maxsize=prefetch_size)
        self._cancel_event.clear()

        # Background reader thread
        reader_thread = threading.Thread(
            target=self._read_frames_worker,
            args=(start, end, frame_queue),
            daemon=True,
            name="FrameReader",
        )
        reader_thread.start()

        try:
            while True:
                frame_data = frame_queue.get(timeout=30.0)
                if frame_data is None:
                    break  # Sentinel: reader is done
                yield frame_data
        except queue.Empty:
            logger.error("Frame reader timed out after 30s.")
        finally:
            self._cancel_event.set()
            reader_thread.join(timeout=5.0)

    def _read_frames_worker(
        self,
        start: int,
        end: int,
        out_queue: queue.Queue[FrameData | None],
    ) -> None:
        """Background thread that reads frames and pushes to queue."""
        # Use a dedicated capture to avoid contention
        cap = cv2.VideoCapture(str(self._video.path))
        if not cap.isOpened():
            logger.error("Background reader failed to open video.")
            out_queue.put(None)
            return

        try:
            if start > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, start)

            for idx in range(start, end):
                if self._cancel_event.is_set():
                    break

                ret, frame = cap.read()
                if not ret or frame is None:
                    logger.warning("Reader: failed at frame %d, stopping.", idx)
                    break

                # Cache the frame
                self._cache.put(self.video_path_str, idx, frame)

                # Generate thumbnail
                thumb = None
                if self._generate_thumbnails:
                    thumb = self._make_thumbnail(frame)
                    self._thumbnails[idx] = thumb

                out_queue.put(FrameData(index=idx, frame=frame, thumbnail=thumb))

        except Exception as exc:
            logger.error("Frame reader error: %s", exc)
        finally:
            cap.release()
            out_queue.put(None)  # Sentinel

    # -- Random Access ------------------------------------------------------

    def get_frame(self, index: int) -> np.ndarray | None:
        """
        Get a single frame by index, using cache if available.

        Args:
            index: Zero-based frame index.

        Returns:
            BGR numpy array, or None if unavailable.
        """
        # Try cache first
        cached = self._cache.get(self.video_path_str, index)
        if cached is not None:
            return cached

        # Read from video
        frame = self._video.read_frame(index)
        if frame is not None:
            self._cache.put(self.video_path_str, index, frame)
        return frame

    def get_frame_rgb(self, index: int) -> np.ndarray | None:
        """Get a single frame in RGB format."""
        frame = self.get_frame(index)
        if frame is not None:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return None

    def get_thumbnail(self, index: int) -> np.ndarray | None:
        """
        Get the thumbnail for a frame (RGB, THUMBNAIL_SIZE).

        Generates it on-the-fly if not already cached.
        """
        if index in self._thumbnails:
            return self._thumbnails[index]

        frame = self.get_frame(index)
        if frame is not None:
            thumb = self._make_thumbnail(frame)
            self._thumbnails[index] = thumb
            return thumb
        return None

    # -- Batch Extraction ---------------------------------------------------

    def extract_range(self, start: int, end: int) -> list[FrameData]:
        """
        Extract a contiguous range of frames.

        Args:
            start: First frame index (inclusive).
            end: Last frame index (exclusive).

        Returns:
            List of FrameData objects.
        """
        return list(self.extract_all(start=start, end=end))

    def extract_pair(self, index: int) -> tuple[np.ndarray | None, np.ndarray | None]:
        """
        Extract a consecutive frame pair for comparison.

        Args:
            index: Index of the second frame.

        Returns:
            (previous_frame, current_frame) as BGR arrays.
        """
        if index <= 0:
            return None, self.get_frame(0)
        prev = self.get_frame(index - 1)
        curr = self.get_frame(index)
        return prev, curr

    # -- Utilities ----------------------------------------------------------

    @staticmethod
    def _make_thumbnail(frame: np.ndarray) -> np.ndarray:
        """Resize and convert a BGR frame to an RGB thumbnail."""
        thumb = cv2.resize(
            frame,
            THUMBNAIL_SIZE,
            interpolation=cv2.INTER_AREA,
        )
        return cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB)

    def cancel(self) -> None:
        """Signal the background reader to stop."""
        self._cancel_event.set()

    def clear_thumbnails(self) -> None:
        """Free thumbnail memory."""
        self._thumbnails.clear()

    @property
    def thumbnail_count(self) -> int:
        return len(self._thumbnails)
