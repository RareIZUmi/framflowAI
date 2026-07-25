"""Tests for the AI detector module."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.ai_detector import AIDetector


class TestAIDetector:
    """Tests for the AI detector (works regardless of model availability)."""

    def test_init_without_model(self) -> None:
        """Detector should initialize gracefully without model file."""
        detector = AIDetector(model_path="/nonexistent/model.onnx")
        assert not detector.available

    def test_compare_returns_zero_when_unavailable(self) -> None:
        """Comparing frames without a model should return 0.0."""
        detector = AIDetector(model_path="/nonexistent/model.onnx")
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        score = detector.compare_frames(frame, frame)
        assert score == 0.0

    def test_extract_features_returns_none_when_unavailable(self) -> None:
        """Feature extraction without a model should return None."""
        detector = AIDetector(model_path="/nonexistent/model.onnx")
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        features = detector.extract_features(frame)
        assert features is None

    def test_cosine_similarity_identical(self) -> None:
        """Cosine similarity of identical vectors should be 1.0."""
        vec = np.random.randn(384).astype(np.float32)
        sim = AIDetector._cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 0.001

    def test_cosine_similarity_orthogonal(self) -> None:
        """Cosine similarity of orthogonal vectors should be ~0."""
        a = np.array([1, 0, 0, 0], dtype=np.float32)
        b = np.array([0, 1, 0, 0], dtype=np.float32)
        sim = AIDetector._cosine_similarity(a, b)
        assert abs(sim) < 0.001

    def test_cosine_similarity_zero_vector(self) -> None:
        """Cosine similarity with a zero vector should be 0."""
        a = np.zeros(10, dtype=np.float32)
        b = np.random.randn(10).astype(np.float32)
        sim = AIDetector._cosine_similarity(a, b)
        assert sim == 0.0

    def test_batch_extract_returns_list(self) -> None:
        """Batch extraction should return a list of Nones when model is unavailable."""
        detector = AIDetector(model_path="/nonexistent/model.onnx")
        frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in range(3)]
        results = detector.extract_features_batch(frames)
        assert len(results) == 3
        assert all(r is None for r in results)
