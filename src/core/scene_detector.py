"""
Scene and shot boundary detection for FrameFlow AI.

Detects hard cuts and gradual transitions between scenes using
histogram difference with an adaptive threshold. Scene boundaries
are critical for the duplicate detector — we never mark a frame
as a "dead frame" if it's the first frame of a new scene.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generator

import cv2
import numpy as np

from src.utils.constants import DEFAULT_SCENE_THRESHOLD
from src.utils.logger import get_logger

logger = get_logger("core.scene_detector")


# ---------------------------------------------------------------------------
# Scene Boundary
# ---------------------------------------------------------------------------

@dataclass
class SceneBoundary:
    """Represents a detected scene change."""

    frame_index: int
    confidence: float  # 0.0 = no change, 1.0 = complete scene change
    transition_type: str  # "hard_cut" or "gradual"

    @property
    def is_hard_cut(self) -> bool:
        return self.transition_type == "hard_cut"


# ---------------------------------------------------------------------------
# Scene Detector
# ---------------------------------------------------------------------------

class SceneDetector:
    """
    Detects scene boundaries in a video using histogram-based analysis.

    Uses a combination of:
    1. Global histogram difference (HSV space)
    2. Edge density difference (Canny edge detection)
    3. Adaptive thresholding based on running statistics

    Usage:
        detector = SceneDetector(threshold=0.35)
        boundary = detector.check_boundary(prev_frame, curr_frame, frame_index=100)
        if boundary:
            print(f"Scene change at frame {boundary.frame_index}")
    """

    def __init__(
        self,
        threshold: float = DEFAULT_SCENE_THRESHOLD,
        adaptive: bool = True,
        window_size: int = 30,
    ) -> None:
        """
        Args:
            threshold: Base threshold for scene detection (0.0–1.0).
                       Lower = more sensitive.
            adaptive: Use adaptive thresholding based on recent history.
            window_size: Number of recent scores for adaptive threshold.
        """
        self._threshold = threshold
        self._adaptive = adaptive
        self._window_size = window_size
        self._recent_scores: list[float] = []
        self._hard_cut_multiplier = 2.5  # Hard cuts have much higher scores

    @property
    def threshold(self) -> float:
        return self._threshold

    @threshold.setter
    def threshold(self, value: float) -> None:
        self._threshold = max(0.05, min(0.95, value))

    def check_boundary(
        self,
        frame_a: np.ndarray,
        frame_b: np.ndarray,
        frame_index: int,
    ) -> SceneBoundary | None:
        """
        Check if there's a scene boundary between two frames.

        Args:
            frame_a: Previous frame (BGR).
            frame_b: Current frame (BGR).
            frame_index: Index of frame_b.

        Returns:
            SceneBoundary if a scene change is detected, None otherwise.
        """
        # Compute histogram difference
        hist_diff = self._histogram_difference(frame_a, frame_b)

        # Compute edge density difference
        edge_diff = self._edge_density_difference(frame_a, frame_b)

        # Combined score (weighted average)
        combined_score = 0.7 * hist_diff + 0.3 * edge_diff

        # Update running window
        self._recent_scores.append(combined_score)
        if len(self._recent_scores) > self._window_size:
            self._recent_scores.pop(0)

        # Determine effective threshold
        effective_threshold = self._get_effective_threshold()

        if combined_score > effective_threshold:
            transition = (
                "hard_cut"
                if combined_score > effective_threshold * self._hard_cut_multiplier
                else "gradual"
            )
            boundary = SceneBoundary(
                frame_index=frame_index,
                confidence=min(1.0, combined_score),
                transition_type=transition,
            )
            logger.debug(
                "Scene boundary at frame %d: %s (score=%.3f, threshold=%.3f)",
                frame_index, transition, combined_score, effective_threshold,
            )
            return boundary

        return None

    def _get_effective_threshold(self) -> float:
        """Calculate adaptive threshold from recent history."""
        if not self._adaptive or len(self._recent_scores) < 5:
            return self._threshold

        # Use mean + 2*std as adaptive threshold
        mean = np.mean(self._recent_scores)
        std = np.std(self._recent_scores)
        adaptive = mean + 2.0 * std

        # Never go below the base threshold
        return max(self._threshold, float(adaptive))

    @staticmethod
    def _histogram_difference(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
        """Compute normalized histogram difference in HSV space."""
        hsv_a = cv2.cvtColor(frame_a, cv2.COLOR_BGR2HSV)
        hsv_b = cv2.cvtColor(frame_b, cv2.COLOR_BGR2HSV)

        h_bins, s_bins, v_bins = 50, 60, 60
        hist_size = [h_bins, s_bins, v_bins]
        ranges = [0, 180, 0, 256, 0, 256]

        hist_a = cv2.calcHist([hsv_a], [0, 1, 2], None, hist_size, ranges)
        hist_b = cv2.calcHist([hsv_b], [0, 1, 2], None, hist_size, ranges)

        cv2.normalize(hist_a, hist_a, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(hist_b, hist_b, 0, 1, cv2.NORM_MINMAX)

        # Bhattacharyya distance: 0 = identical, 1 = completely different
        distance = cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_BHATTACHARYYA)
        return float(max(0.0, min(1.0, distance)))

    @staticmethod
    def _edge_density_difference(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
        """Compare edge density between two frames."""
        gray_a = cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY)
        gray_b = cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY)

        edges_a = cv2.Canny(gray_a, 50, 150)
        edges_b = cv2.Canny(gray_b, 50, 150)

        density_a = np.mean(edges_a) / 255.0
        density_b = np.mean(edges_b) / 255.0

        diff = abs(density_a - density_b)
        return float(min(1.0, diff * 5.0))  # Scale up small differences

    def reset(self) -> None:
        """Reset the detector state between videos."""
        self._recent_scores.clear()

    def detect_all(
        self,
        frames: list[np.ndarray],
    ) -> list[SceneBoundary]:
        """
        Detect all scene boundaries in a list of frames.

        Args:
            frames: Ordered list of BGR frames.

        Returns:
            List of detected SceneBoundary objects.
        """
        self.reset()
        boundaries: list[SceneBoundary] = []

        for i in range(1, len(frames)):
            boundary = self.check_boundary(frames[i - 1], frames[i], frame_index=i)
            if boundary:
                boundaries.append(boundary)

        logger.info("Detected %d scene boundaries in %d frames.", len(boundaries), len(frames))
        return boundaries
