"""Integration tests for the FrameFlow AI pipeline."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.duplicate_detector import DetectionConfig, DuplicateDetector
from src.core.frame_cache import FrameCache
from src.core.scene_detector import SceneDetector
from src.utils.constants import FrameDecision
from src.utils.logger import ProcessingStats
from src.utils.settings import SettingsManager


# ---------------------------------------------------------------------------
# Frame Cache
# ---------------------------------------------------------------------------

class TestFrameCache:
    def test_put_and_get(self) -> None:
        cache = FrameCache(max_size_mb=10)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        cache.put("video.mp4", 0, frame)
        result = cache.get("video.mp4", 0)
        assert result is not None
        assert np.array_equal(result, frame)

    def test_miss_returns_none(self) -> None:
        cache = FrameCache(max_size_mb=10)
        assert cache.get("video.mp4", 999) is None

    def test_eviction(self) -> None:
        # Use a very small cache that can hold ~1 frame
        # Each 100x100x3 frame is 30,000 bytes = ~0.03 MB
        # With max_size_mb=1, the 25% guard allows frames < 256 KB → fine
        cache = FrameCache(max_size_mb=1)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)  # ~30 KB
        # Fill cache with many frames to force eviction
        for i in range(50):
            cache.put("v", i, frame)
        # All should fit in 1 MB (50 * 30 KB = ~1.5 MB → some evicted)
        # At least some should remain, but not all 50
        assert 0 < cache.size < 50

    def test_invalidate_specific(self) -> None:
        cache = FrameCache(max_size_mb=10)
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        cache.put("a.mp4", 0, frame)
        cache.put("b.mp4", 0, frame)
        cache.invalidate("a.mp4")
        assert cache.get("a.mp4", 0) is None
        assert cache.get("b.mp4", 0) is not None

    def test_invalidate_all(self) -> None:
        cache = FrameCache(max_size_mb=10)
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        cache.put("a.mp4", 0, frame)
        cache.put("b.mp4", 0, frame)
        cache.invalidate()
        assert cache.size == 0

    def test_stats(self) -> None:
        cache = FrameCache(max_size_mb=10)
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        cache.put("v", 0, frame)
        cache.get("v", 0)  # hit
        cache.get("v", 1)  # miss
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1


# ---------------------------------------------------------------------------
# Scene Detector
# ---------------------------------------------------------------------------

class TestSceneDetector:
    def test_no_boundary_identical(self) -> None:
        detector = SceneDetector(threshold=0.35)
        frame = np.random.randint(50, 200, (100, 100, 3), dtype=np.uint8)
        result = detector.check_boundary(frame, frame.copy(), frame_index=1)
        assert result is None  # Identical frames = no scene change

    def test_boundary_different(self) -> None:
        detector = SceneDetector(threshold=0.2)
        frame_a = np.zeros((100, 100, 3), dtype=np.uint8)
        frame_b = np.full((100, 100, 3), 255, dtype=np.uint8)
        result = detector.check_boundary(frame_a, frame_b, frame_index=1)
        assert result is not None
        assert result.frame_index == 1

    def test_reset(self) -> None:
        detector = SceneDetector()
        detector._recent_scores = [0.1, 0.2, 0.3]
        detector.reset()
        assert len(detector._recent_scores) == 0


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class TestSettings:
    def test_get_set(self, tmp_path: object) -> None:
        from pathlib import Path
        settings = SettingsManager(path=Path(str(tmp_path)) / "test_settings.json")
        settings.set("detection.similarity_threshold", 0.95)
        assert settings.get("detection.similarity_threshold") == 0.95

    def test_default_values(self, tmp_path: object) -> None:
        from pathlib import Path
        settings = SettingsManager(path=Path(str(tmp_path)) / "test_settings.json")
        assert settings.get("detection.similarity_threshold") == 0.97

    def test_reset(self, tmp_path: object) -> None:
        from pathlib import Path
        settings = SettingsManager(path=Path(str(tmp_path)) / "test_settings.json")
        settings.set("detection.similarity_threshold", 0.5)
        settings.reset("detection.similarity_threshold")
        assert settings.get("detection.similarity_threshold") == 0.97

    def test_nested_get(self, tmp_path: object) -> None:
        from pathlib import Path
        settings = SettingsManager(path=Path(str(tmp_path)) / "test_settings.json")
        weights = settings.get_section("detection.weights")
        assert "ssim" in weights


# ---------------------------------------------------------------------------
# Processing Stats
# ---------------------------------------------------------------------------

class TestProcessingStats:
    def test_progress(self) -> None:
        stats = ProcessingStats(total_frames=100)
        stats.frames_analyzed = 50
        assert abs(stats.progress - 0.5) < 0.01

    def test_removal_percentage(self) -> None:
        stats = ProcessingStats()
        stats.frames_analyzed = 100
        stats.frames_removed = 25
        assert abs(stats.removal_percentage - 25.0) < 0.01

    def test_to_dict(self) -> None:
        stats = ProcessingStats(video_path="test.mp4", total_frames=100)
        d = stats.to_dict()
        assert d["video_path"] == "test.mp4"
        assert d["total_frames"] == 100


# ---------------------------------------------------------------------------
# End-to-End Mini Pipeline
# ---------------------------------------------------------------------------

class TestPipeline:
    """Test the detection pipeline with synthetic frames."""

    def test_detect_held_frames(self) -> None:
        """Simulate an animation with held frames and verify detection."""
        config = DetectionConfig(
            similarity_threshold=0.95,
            uncertain_lower_bound=0.85,
            min_consecutive_frames=1,
            enable_ai=False,
        )
        detector = DuplicateDetector(config)
        detector.reset()

        np.random.seed(42)

        # Create frames: unique → duplicate → unique → 3 duplicates → unique
        unique_a = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        unique_b = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        unique_c = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)

        frames = [
            unique_a,           # 0: unique (first frame)
            unique_a.copy(),    # 1: duplicate of 0
            unique_b,           # 2: unique
            unique_c,           # 3: unique
            unique_c.copy(),    # 4: duplicate of 3
            unique_c.copy(),    # 5: duplicate of 3
            unique_c.copy(),    # 6: duplicate of 3
        ]

        results = [detector.analyze_first_frame(0)]
        for i in range(1, len(frames)):
            result = detector.analyze_pair(frames[i - 1], frames[i], i)
            results.append(result)

        # Frame 0: always kept
        assert results[0].decision == FrameDecision.KEEP

        # Frame 1: duplicate of 0 → should be REMOVE or UNCERTAIN
        assert results[1].decision in (FrameDecision.REMOVE, FrameDecision.UNCERTAIN)

        # Frame 2: new content → KEEP
        assert results[2].decision == FrameDecision.KEEP

        # Frame 3: new content → KEEP
        assert results[3].decision == FrameDecision.KEEP

        # Frames 4-6: duplicates → REMOVE or UNCERTAIN
        for r in results[4:7]:
            assert r.decision in (FrameDecision.REMOVE, FrameDecision.UNCERTAIN)
