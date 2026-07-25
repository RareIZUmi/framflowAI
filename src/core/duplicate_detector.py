"""
Multi-algorithm dead frame detection engine for FrameFlow AI.

Combines five independent similarity metrics into a single weighted
confidence score to determine whether a frame is a "dead frame"
(a duplicated/held animation frame):

1. SSIM  – Structural Similarity Index
2. pHash – Perceptual Hash distance
3. Histogram – Color distribution comparison
4. Optical Flow – Motion magnitude detection
5. AI Features – Deep feature cosine similarity (optional, via ai_detector)

Each algorithm produces a score in [0, 1] where 1 = identical.
The weighted average becomes the "dead frame probability".
A configurable threshold then classifies the frame as KEEP / REMOVE / UNCERTAIN.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable

import cv2
import imagehash
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

from src.utils.constants import (
    DEFAULT_AI_WEIGHT,
    DEFAULT_HISTOGRAM_WEIGHT,
    DEFAULT_MIN_CONSECUTIVE_FRAMES,
    DEFAULT_OPTICAL_FLOW_WEIGHT,
    DEFAULT_PHASH_WEIGHT,
    DEFAULT_SCENE_THRESHOLD,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_SSIM_WEIGHT,
    DEFAULT_UNCERTAIN_LOWER,
    OPTICAL_FLOW_ZERO_THRESHOLD,
    FrameDecision,
)
from src.utils.logger import get_logger

logger = get_logger("core.duplicate_detector")


# ---------------------------------------------------------------------------
# Per-Frame Analysis Result
# ---------------------------------------------------------------------------

@dataclass
class FrameAnalysis:
    """Complete analysis result for a single frame."""

    frame_index: int
    ssim_score: float = 0.0
    phash_score: float = 0.0
    histogram_score: float = 0.0
    optical_flow_score: float = 0.0  # 1.0 = no motion, 0.0 = full motion
    ai_score: float = 0.0
    weighted_score: float = 0.0
    decision: FrameDecision = FrameDecision.KEEP
    is_scene_boundary: bool = False
    consecutive_duplicate_count: int = 0

    @property
    def similarity_percentage(self) -> float:
        """Weighted score as a percentage."""
        return self.weighted_score * 100.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "ssim": round(self.ssim_score, 6),
            "phash": round(self.phash_score, 6),
            "histogram": round(self.histogram_score, 6),
            "optical_flow": round(self.optical_flow_score, 6),
            "ai_features": round(self.ai_score, 6),
            "weighted_score": round(self.weighted_score, 6),
            "decision": self.decision.name,
            "scene_boundary": self.is_scene_boundary,
        }


# ---------------------------------------------------------------------------
# Detection Configuration
# ---------------------------------------------------------------------------

@dataclass
class DetectionConfig:
    """Configuration for the duplicate detection pipeline."""

    # Algorithm weights (must sum to ≤ 1.0)
    ssim_weight: float = DEFAULT_SSIM_WEIGHT
    phash_weight: float = DEFAULT_PHASH_WEIGHT
    histogram_weight: float = DEFAULT_HISTOGRAM_WEIGHT
    optical_flow_weight: float = DEFAULT_OPTICAL_FLOW_WEIGHT
    ai_weight: float = DEFAULT_AI_WEIGHT

    # Thresholds
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    uncertain_lower_bound: float = DEFAULT_UNCERTAIN_LOWER
    scene_threshold: float = DEFAULT_SCENE_THRESHOLD
    min_consecutive_frames: int = DEFAULT_MIN_CONSECUTIVE_FRAMES

    # Feature flags
    enable_ai: bool = True

    def normalize_weights(self) -> None:
        """Ensure weights sum to 1.0."""
        if not self.enable_ai:
            total = (
                self.ssim_weight + self.phash_weight
                + self.histogram_weight + self.optical_flow_weight
            )
        else:
            total = (
                self.ssim_weight + self.phash_weight
                + self.histogram_weight + self.optical_flow_weight
                + self.ai_weight
            )
        if total > 0 and abs(total - 1.0) > 1e-6:
            factor = 1.0 / total
            self.ssim_weight *= factor
            self.phash_weight *= factor
            self.histogram_weight *= factor
            self.optical_flow_weight *= factor
            if self.enable_ai:
                self.ai_weight *= factor

    @classmethod
    def from_settings(cls, settings_dict: dict[str, Any]) -> DetectionConfig:
        """Create config from a settings dictionary."""
        weights = settings_dict.get("weights", {})
        config = cls(
            ssim_weight=weights.get("ssim", DEFAULT_SSIM_WEIGHT),
            phash_weight=weights.get("phash", DEFAULT_PHASH_WEIGHT),
            histogram_weight=weights.get("histogram", DEFAULT_HISTOGRAM_WEIGHT),
            optical_flow_weight=weights.get("optical_flow", DEFAULT_OPTICAL_FLOW_WEIGHT),
            ai_weight=weights.get("ai_features", DEFAULT_AI_WEIGHT),
            similarity_threshold=settings_dict.get("similarity_threshold", DEFAULT_SIMILARITY_THRESHOLD),
            uncertain_lower_bound=settings_dict.get("uncertain_lower_bound", DEFAULT_UNCERTAIN_LOWER),
            scene_threshold=settings_dict.get("scene_threshold", DEFAULT_SCENE_THRESHOLD),
            min_consecutive_frames=settings_dict.get("min_consecutive_frames", DEFAULT_MIN_CONSECUTIVE_FRAMES),
            enable_ai=settings_dict.get("enable_ai_mode", True),
        )
        config.normalize_weights()
        return config


# ---------------------------------------------------------------------------
# Individual Algorithm Implementations
# ---------------------------------------------------------------------------

def compute_ssim(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
    """
    Compute Structural Similarity Index between two frames.

    Converts to grayscale for SSIM. Returns value in [0, 1].
    Handles compression artifacts better than pixel-level comparison.
    """
    gray_a = cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY)

    # Resize if dimensions don't match (shouldn't happen, but be safe)
    if gray_a.shape != gray_b.shape:
        gray_b = cv2.resize(gray_b, (gray_a.shape[1], gray_a.shape[0]))

    # Use a window size appropriate for the image
    min_dim = min(gray_a.shape)
    win_size = min(7, min_dim if min_dim % 2 == 1 else min_dim - 1)
    if win_size < 3:
        win_size = 3

    score = ssim(gray_a, gray_b, win_size=win_size, data_range=255)
    return float(max(0.0, min(1.0, score)))


def compute_phash(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
    """
    Compute perceptual hash similarity between two frames.

    Uses pHash which is robust to minor noise, compression artifacts,
    and small brightness changes. Returns value in [0, 1] where 1 = identical.
    """
    # Convert BGR to RGB PIL images
    img_a = Image.fromarray(cv2.cvtColor(frame_a, cv2.COLOR_BGR2RGB))
    img_b = Image.fromarray(cv2.cvtColor(frame_b, cv2.COLOR_BGR2RGB))

    hash_a = imagehash.phash(img_a, hash_size=16)
    hash_b = imagehash.phash(img_b, hash_size=16)

    # Hamming distance; max possible distance = hash_size^2 = 256
    max_distance = 16 * 16  # 256 bits
    distance = hash_a - hash_b  # Hamming distance

    # Convert distance to similarity [0, 1]
    similarity = 1.0 - (distance / max_distance)
    return float(max(0.0, min(1.0, similarity)))


def compute_histogram_similarity(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
    """
    Compare color histograms of two frames.

    Uses correlation method on H-S histograms in HSV space.
    Returns value in [0, 1] where 1 = identical distribution.
    """
    hsv_a = cv2.cvtColor(frame_a, cv2.COLOR_BGR2HSV)
    hsv_b = cv2.cvtColor(frame_b, cv2.COLOR_BGR2HSV)

    # 2D Hue-Saturation histogram
    h_bins, s_bins = 50, 60
    hist_size = [h_bins, s_bins]
    ranges = [0, 180, 0, 256]  # H: 0-180, S: 0-256
    channels = [0, 1]

    hist_a = cv2.calcHist([hsv_a], channels, None, hist_size, ranges)
    hist_b = cv2.calcHist([hsv_b], channels, None, hist_size, ranges)

    cv2.normalize(hist_a, hist_a, 0, 1, cv2.NORM_MINMAX)
    cv2.normalize(hist_b, hist_b, 0, 1, cv2.NORM_MINMAX)

    # Correlation ranges from -1 to 1; normalize to [0, 1]
    corr = cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL)
    similarity = (corr + 1.0) / 2.0
    return float(max(0.0, min(1.0, similarity)))


def compute_optical_flow_score(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
    """
    Estimate motion between two frames using Farneback dense optical flow.

    Returns a similarity score in [0, 1] where:
    - 1.0 = no motion detected (frames are effectively identical)
    - 0.0 = significant motion detected

    This is critical for distinguishing actual slight camera motion
    from truly duplicated/held frames.
    """
    gray_a = cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY)

    if gray_a.shape != gray_b.shape:
        gray_b = cv2.resize(gray_b, (gray_a.shape[1], gray_a.shape[0]))

    # Downsample for speed on high-res video
    max_dim = 512
    h, w = gray_a.shape
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        new_size = (int(w * scale), int(h * scale))
        gray_a = cv2.resize(gray_a, new_size, interpolation=cv2.INTER_AREA)
        gray_b = cv2.resize(gray_b, new_size, interpolation=cv2.INTER_AREA)

    # Compute dense optical flow
    flow = cv2.calcOpticalFlowFarneback(
        gray_a, gray_b,
        flow=None,
        pyr_scale=0.5,
        levels=3,
        winsize=15,
        iterations=3,
        poly_n=5,
        poly_sigma=1.2,
        flags=0,
    )

    # Compute magnitude of flow vectors
    magnitude, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    mean_magnitude = float(np.mean(magnitude))

    # Convert to similarity: low magnitude = high similarity
    # Use a sigmoid-like mapping: threshold controls the transition
    if mean_magnitude < OPTICAL_FLOW_ZERO_THRESHOLD:
        return 1.0  # Essentially no motion
    elif mean_magnitude > 10.0:
        return 0.0  # Strong motion

    # Smooth transition between 0.5 and 10.0
    similarity = 1.0 - (mean_magnitude - OPTICAL_FLOW_ZERO_THRESHOLD) / (10.0 - OPTICAL_FLOW_ZERO_THRESHOLD)
    return float(max(0.0, min(1.0, similarity)))


# ---------------------------------------------------------------------------
# Duplicate Detector
# ---------------------------------------------------------------------------

class DuplicateDetector:
    """
    Multi-algorithm dead frame detector.

    Combines SSIM, pHash, Histogram, Optical Flow, and (optionally) AI
    feature similarity into a weighted confidence score.

    Usage:
        detector = DuplicateDetector(config)
        result = detector.analyze_pair(prev_frame, curr_frame, frame_index=25)

        # Or analyze a batch
        results = detector.analyze_sequence(frames)
    """

    def __init__(
        self,
        config: DetectionConfig | None = None,
        ai_scorer: Callable[[np.ndarray, np.ndarray], float] | None = None,
    ) -> None:
        """
        Args:
            config: Detection configuration.
            ai_scorer: Optional callable that takes (frame_a, frame_b) and
                       returns AI feature similarity in [0, 1].
        """
        self._config = config or DetectionConfig()
        self._config.normalize_weights()
        self._ai_scorer = ai_scorer
        self._consecutive_count = 0
        self._lock = threading.Lock()

    @property
    def config(self) -> DetectionConfig:
        return self._config

    @config.setter
    def config(self, new_config: DetectionConfig) -> None:
        new_config.normalize_weights()
        self._config = new_config

    def set_ai_scorer(self, scorer: Callable[[np.ndarray, np.ndarray], float]) -> None:
        """Attach or replace the AI feature scorer."""
        self._ai_scorer = scorer

    # -- Single Pair Analysis -----------------------------------------------

    def analyze_pair(
        self,
        frame_a: np.ndarray,
        frame_b: np.ndarray,
        frame_index: int,
    ) -> FrameAnalysis:
        """
        Analyze a pair of consecutive frames.

        Args:
            frame_a: Previous frame (BGR).
            frame_b: Current frame (BGR).
            frame_index: Index of frame_b.

        Returns:
            FrameAnalysis with all scores and decision.
        """
        cfg = self._config
        analysis = FrameAnalysis(frame_index=frame_index)

        # ── Check for scene boundary first ──────────────────────────────
        hist_sim = compute_histogram_similarity(frame_a, frame_b)
        analysis.histogram_score = hist_sim

        if hist_sim < cfg.scene_threshold:
            analysis.is_scene_boundary = True
            analysis.decision = FrameDecision.SCENE_BOUNDARY
            analysis.weighted_score = 0.0
            self._consecutive_count = 0
            logger.debug("Frame %d: scene boundary (histogram=%.3f)", frame_index, hist_sim)
            return analysis

        # ── Run algorithms in parallel for speed ────────────────────────
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(compute_ssim, frame_a, frame_b): "ssim",
                pool.submit(compute_phash, frame_a, frame_b): "phash",
                pool.submit(compute_optical_flow_score, frame_a, frame_b): "optical_flow",
            }

            # AI scoring (if enabled and scorer is attached)
            if cfg.enable_ai and self._ai_scorer is not None:
                futures[pool.submit(self._ai_scorer, frame_a, frame_b)] = "ai"

            for future in as_completed(futures):
                algo = futures[future]
                try:
                    score = future.result()
                    if algo == "ssim":
                        analysis.ssim_score = score
                    elif algo == "phash":
                        analysis.phash_score = score
                    elif algo == "optical_flow":
                        analysis.optical_flow_score = score
                    elif algo == "ai":
                        analysis.ai_score = score
                except Exception as exc:
                    logger.warning("Algorithm '%s' failed for frame %d: %s", algo, frame_index, exc)

        # ── Compute weighted score ──────────────────────────────────────
        weighted = (
            analysis.ssim_score * cfg.ssim_weight
            + analysis.phash_score * cfg.phash_weight
            + analysis.histogram_score * cfg.histogram_weight
            + analysis.optical_flow_score * cfg.optical_flow_weight
        )
        if cfg.enable_ai and self._ai_scorer is not None:
            weighted += analysis.ai_score * cfg.ai_weight
        else:
            # Redistribute AI weight to other algorithms
            non_ai_total = (
                cfg.ssim_weight + cfg.phash_weight
                + cfg.histogram_weight + cfg.optical_flow_weight
            )
            if non_ai_total > 0:
                weighted /= non_ai_total  # Renormalize

        analysis.weighted_score = max(0.0, min(1.0, weighted))

        # ── Make decision ───────────────────────────────────────────────
        if analysis.weighted_score >= cfg.similarity_threshold:
            self._consecutive_count += 1
            analysis.consecutive_duplicate_count = self._consecutive_count
            if self._consecutive_count >= cfg.min_consecutive_frames:
                analysis.decision = FrameDecision.REMOVE
            else:
                analysis.decision = FrameDecision.UNCERTAIN
        elif analysis.weighted_score >= cfg.uncertain_lower_bound:
            analysis.decision = FrameDecision.UNCERTAIN
            self._consecutive_count = 0
        else:
            analysis.decision = FrameDecision.KEEP
            self._consecutive_count = 0

        logger.debug(
            "Frame %d: score=%.4f decision=%s (ssim=%.3f phash=%.3f hist=%.3f flow=%.3f ai=%.3f)",
            frame_index, analysis.weighted_score, analysis.decision.name,
            analysis.ssim_score, analysis.phash_score, analysis.histogram_score,
            analysis.optical_flow_score, analysis.ai_score,
        )
        return analysis

    # -- Sequence Analysis --------------------------------------------------

    def analyze_first_frame(self, frame_index: int = 0) -> FrameAnalysis:
        """
        Create an analysis for the first frame (always kept).
        """
        self._consecutive_count = 0
        return FrameAnalysis(
            frame_index=frame_index,
            decision=FrameDecision.KEEP,
        )

    def reset(self) -> None:
        """Reset internal state between videos."""
        self._consecutive_count = 0

    # -- Batch Override -----------------------------------------------------

    def override_decision(
        self,
        analysis: FrameAnalysis,
        decision: FrameDecision,
    ) -> FrameAnalysis:
        """
        Manually override the decision for a frame.

        Used by the UI when the user manually keeps/removes frames.
        """
        analysis.decision = decision
        return analysis
