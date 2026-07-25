"""Tests for the exporter module."""

from __future__ import annotations

import numpy as np
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.duplicate_detector import FrameAnalysis
from src.core.exporter import ExportConfig, Exporter
from src.utils.constants import ExportCodec, FrameDecision, ImageFormat


class TestExportConfig:
    def test_defaults(self) -> None:
        config = ExportConfig()
        assert config.codec == ExportCodec.H264
        assert config.preserve_audio is True
        assert config.crf == 18
        assert not config.is_image_sequence

    def test_image_sequence_mode(self) -> None:
        config = ExportConfig(image_format=ImageFormat.PNG)
        assert config.is_image_sequence

    def test_video_mode(self) -> None:
        config = ExportConfig(codec=ExportCodec.H265)
        assert not config.is_image_sequence


class TestExporter:
    @pytest.fixture
    def mock_analyses(self) -> list[FrameAnalysis]:
        """Create mock frame analyses: 5 kept, 3 removed."""
        analyses = []
        for i in range(8):
            decision = FrameDecision.REMOVE if i in (2, 4, 6) else FrameDecision.KEEP
            analyses.append(FrameAnalysis(frame_index=i, decision=decision))
        return analyses

    def test_get_kept_frame_indices(self, mock_analyses: list[FrameAnalysis]) -> None:
        """Should return only kept frame indices."""
        mock_video = MagicMock()
        mock_video.fps = 24.0
        mock_video.path = Path("/test/video.mp4")
        mock_video.metadata.has_audio = False

        config = ExportConfig(output_path="/tmp/out.mp4")
        exporter = Exporter(mock_video, mock_analyses, config)

        kept = exporter._get_kept_frame_indices()
        assert kept == [0, 1, 3, 5, 7]
        assert 2 not in kept
        assert 4 not in kept
        assert 6 not in kept

    def test_compute_audio_keep_segments(self, mock_analyses: list[FrameAnalysis]) -> None:
        """Audio segments should correspond to consecutive kept frames."""
        mock_video = MagicMock()
        mock_video.fps = 24.0
        mock_video.path = Path("/test/video.mp4")
        mock_video.metadata.has_audio = True

        config = ExportConfig(output_path="/tmp/out.mp4")
        exporter = Exporter(mock_video, mock_analyses, config)

        segments = exporter._compute_audio_keep_segments()
        assert len(segments) > 0
        # All segments should have start < end
        for start, end in segments:
            assert start < end

    def test_count_kept_frames(self, mock_analyses: list[FrameAnalysis]) -> None:
        mock_video = MagicMock()
        mock_video.fps = 24.0
        mock_video.path = Path("/test/video.mp4")

        config = ExportConfig(output_path="/tmp/out.mp4")
        exporter = Exporter(mock_video, mock_analyses, config)

        assert exporter._count_kept_frames() == 5
