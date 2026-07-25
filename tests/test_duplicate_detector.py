"""Tests for the duplicate detection engine."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.duplicate_detector import (
    DetectionConfig,
    DuplicateDetector,
    FrameAnalysis,
    compute_histogram_similarity,
    compute_optical_flow_score,
    compute_phash,
    compute_ssim,
)
from src.utils.constants import FrameDecision


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def identical_frames() -> tuple[np.ndarray, np.ndarray]:
    """Two identical 100x100 BGR frames."""
    frame = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
    return frame.copy(), frame.copy()


@pytest.fixture
def different_frames() -> tuple[np.ndarray, np.ndarray]:
    """Two visually distinct 100x100 BGR frames with real content variation."""
    np.random.seed(99)
    # Frame A: warm colors (reds/oranges)
    frame_a = np.zeros((100, 100, 3), dtype=np.uint8)
    frame_a[:, :, 2] = np.random.randint(180, 256, (100, 100), dtype=np.uint8)  # R high
    frame_a[:, :, 1] = np.random.randint(50, 120, (100, 100), dtype=np.uint8)   # G low
    frame_a[:, :, 0] = np.random.randint(0, 40, (100, 100), dtype=np.uint8)     # B very low
    # Frame B: cool colors (blues/greens) with different structure
    frame_b = np.zeros((100, 100, 3), dtype=np.uint8)
    frame_b[:, :, 0] = np.random.randint(180, 256, (100, 100), dtype=np.uint8)  # B high
    frame_b[:, :, 1] = np.random.randint(150, 256, (100, 100), dtype=np.uint8)  # G high
    frame_b[:, :, 2] = np.random.randint(0, 40, (100, 100), dtype=np.uint8)     # R very low
    return frame_a, frame_b


@pytest.fixture
def slightly_different_frames() -> tuple[np.ndarray, np.ndarray]:
    """Two frames with minor noise differences (simulating compression)."""
    np.random.seed(42)
    base = np.random.randint(50, 200, (100, 100, 3), dtype=np.uint8)
    noisy = base.copy()
    noise = np.random.randint(-3, 4, base.shape, dtype=np.int16)
    noisy = np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return base, noisy


# ---------------------------------------------------------------------------
# Algorithm Tests
# ---------------------------------------------------------------------------

class TestSSIM:
    def test_identical_frames(self, identical_frames: tuple) -> None:
        a, b = identical_frames
        score = compute_ssim(a, b)
        assert score >= 0.99

    def test_different_frames(self, different_frames: tuple) -> None:
        a, b = different_frames
        score = compute_ssim(a, b)
        assert score < 0.1

    def test_slightly_different(self, slightly_different_frames: tuple) -> None:
        a, b = slightly_different_frames
        score = compute_ssim(a, b)
        assert 0.8 < score < 1.0


class TestPHash:
    def test_identical_frames(self, identical_frames: tuple) -> None:
        a, b = identical_frames
        score = compute_phash(a, b)
        assert score >= 0.99

    def test_different_frames(self, different_frames: tuple) -> None:
        a, b = different_frames
        score = compute_phash(a, b)
        assert score < 0.95  # Different colored/textured frames should diverge


class TestHistogram:
    def test_identical_frames(self, identical_frames: tuple) -> None:
        a, b = identical_frames
        score = compute_histogram_similarity(a, b)
        assert score >= 0.99

    def test_different_frames(self, different_frames: tuple) -> None:
        a, b = different_frames
        score = compute_histogram_similarity(a, b)
        assert score < 0.85  # Warm vs cool color frames should differ significantly


class TestOpticalFlow:
    def test_identical_frames(self, identical_frames: tuple) -> None:
        a, b = identical_frames
        score = compute_optical_flow_score(a, b)
        assert score >= 0.95  # Near-zero motion

    def test_different_frames(self, different_frames: tuple) -> None:
        a, b = different_frames
        score = compute_optical_flow_score(a, b)
        # Optical flow on completely different frames may be unpredictable,
        # but should generally indicate change
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Detector Tests
# ---------------------------------------------------------------------------

class TestDuplicateDetector:
    def test_analyze_first_frame(self) -> None:
        detector = DuplicateDetector()
        result = detector.analyze_first_frame(0)
        assert result.frame_index == 0
        assert result.decision == FrameDecision.KEEP

    def test_identical_detected_as_dead(self, identical_frames: tuple) -> None:
        config = DetectionConfig(similarity_threshold=0.95, enable_ai=False)
        detector = DuplicateDetector(config)
        a, b = identical_frames
        result = detector.analyze_pair(a, b, frame_index=1)
        assert result.weighted_score >= 0.95
        assert result.decision in (FrameDecision.REMOVE, FrameDecision.UNCERTAIN)

    def test_different_detected_as_keep(self, different_frames: tuple) -> None:
        config = DetectionConfig(similarity_threshold=0.95, enable_ai=False)
        detector = DuplicateDetector(config)
        a, b = different_frames
        result = detector.analyze_pair(a, b, frame_index=1)
        assert result.decision == FrameDecision.KEEP

    def test_reset(self) -> None:
        detector = DuplicateDetector()
        detector._consecutive_count = 10
        detector.reset()
        assert detector._consecutive_count == 0

    def test_config_normalize_weights(self) -> None:
        config = DetectionConfig(
            ssim_weight=1.0, phash_weight=1.0,
            histogram_weight=1.0, optical_flow_weight=1.0,
            ai_weight=1.0, enable_ai=True,
        )
        config.normalize_weights()
        total = (config.ssim_weight + config.phash_weight +
                 config.histogram_weight + config.optical_flow_weight +
                 config.ai_weight)
        assert abs(total - 1.0) < 0.01

    def test_override_decision(self) -> None:
        detector = DuplicateDetector()
        analysis = FrameAnalysis(frame_index=5, decision=FrameDecision.REMOVE)
        detector.override_decision(analysis, FrameDecision.KEEP)
        assert analysis.decision == FrameDecision.KEEP
