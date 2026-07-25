"""
LRU frame cache with configurable memory limits for FrameFlow AI.

Thread-safe, memory-aware caching of decoded video frames (numpy arrays).
Evicts least-recently-used frames when the memory limit is exceeded.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Final

import numpy as np

from src.utils.constants import DEFAULT_CACHE_SIZE_MB
from src.utils.logger import get_logger

logger = get_logger("core.frame_cache")


class FrameCache:
    """
    Thread-safe LRU cache for video frames (numpy arrays).

    Frames are keyed by (video_path, frame_index) and evicted
    when total cached memory exceeds the configured limit.

    Usage:
        cache = FrameCache(max_size_mb=2048)
        cache.put("video.mp4", 42, frame_array)
        frame = cache.get("video.mp4", 42)
    """

    def __init__(self, max_size_mb: int = DEFAULT_CACHE_SIZE_MB) -> None:
        self._max_bytes: Final[int] = max_size_mb * 1024 * 1024
        self._lock = threading.Lock()
        self._cache: OrderedDict[tuple[str, int], np.ndarray] = OrderedDict()
        self._current_bytes: int = 0
        self._hits: int = 0
        self._misses: int = 0

    # -- Public API ---------------------------------------------------------

    def get(self, video_path: str, frame_index: int) -> np.ndarray | None:
        """
        Retrieve a cached frame.

        Args:
            video_path: Identifier for the video.
            frame_index: Zero-based frame index.

        Returns:
            Cached numpy array (BGR), or None on miss.
        """
        key = (video_path, frame_index)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)  # Mark as recently used
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None

    def put(self, video_path: str, frame_index: int, frame: np.ndarray) -> None:
        """
        Store a frame in the cache.

        Evicts LRU entries if adding the frame would exceed the memory limit.

        Args:
            video_path: Identifier for the video.
            frame_index: Zero-based frame index.
            frame: BGR numpy array to cache.
        """
        key = (video_path, frame_index)
        frame_bytes = frame.nbytes

        # Don't cache frames larger than 25% of max cache
        if frame_bytes > self._max_bytes // 4:
            return

        with self._lock:
            # If already cached, remove old version
            if key in self._cache:
                old = self._cache.pop(key)
                self._current_bytes -= old.nbytes

            # Evict until we have room
            while self._current_bytes + frame_bytes > self._max_bytes and self._cache:
                _, evicted = self._cache.popitem(last=False)
                self._current_bytes -= evicted.nbytes

            self._cache[key] = frame
            self._current_bytes += frame_bytes

    def invalidate(self, video_path: str | None = None) -> None:
        """
        Remove cached frames for a specific video or all videos.

        Args:
            video_path: Video to invalidate, or None to clear everything.
        """
        with self._lock:
            if video_path is None:
                self._cache.clear()
                self._current_bytes = 0
                logger.debug("Frame cache cleared entirely.")
            else:
                keys_to_remove = [k for k in self._cache if k[0] == video_path]
                for key in keys_to_remove:
                    frame = self._cache.pop(key)
                    self._current_bytes -= frame.nbytes
                logger.debug(
                    "Invalidated %d cached frames for %s",
                    len(keys_to_remove),
                    video_path,
                )

    def contains(self, video_path: str, frame_index: int) -> bool:
        """Check if a frame is in the cache without updating LRU order."""
        return (video_path, frame_index) in self._cache

    # -- Stats --------------------------------------------------------------

    @property
    def size(self) -> int:
        """Number of cached frames."""
        return len(self._cache)

    @property
    def memory_used_mb(self) -> float:
        """Current cache memory usage in MB."""
        return self._current_bytes / (1024 * 1024)

    @property
    def memory_limit_mb(self) -> float:
        """Maximum cache size in MB."""
        return self._max_bytes / (1024 * 1024)

    @property
    def hit_rate(self) -> float:
        """Cache hit rate as a percentage."""
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return (self._hits / total) * 100.0

    def stats(self) -> dict[str, float | int]:
        """Return cache statistics."""
        return {
            "cached_frames": self.size,
            "memory_used_mb": round(self.memory_used_mb, 1),
            "memory_limit_mb": round(self.memory_limit_mb, 1),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": round(self.hit_rate, 1),
        }
