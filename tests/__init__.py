"""Tests for the video loader module."""

from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from src.core.video_loader import VideoFile, VideoLoader, VideoLoadError, UnsupportedFormatError
from src.utils.ffmpeg import VideoMetadata


@pytest.fixture
def sample_metadata() -> VideoMetadata:
    """Create a mock VideoMetadata for testing."""
    return VideoMetadata(
        path="/test/video.mp4",
        width=1920,
        height=1080,
        fps=24.0,
        duration=10.0,
        frame_count=240,
        codec_name="h264",
        codec_long_name="H.264 / AVC",
        pixel_format="yuv420p",
        bit_rate=5000000,
        file_size=6250000,
        has_audio=True,
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channels=2,
        container_format="mp4",
    )


class TestVideoMetadata:
    """Tests for VideoMetadata properties."""

    def test_resolution_str(self, sample_metadata: VideoMetadata) -> None:
        assert sample_metadata.resolution_str == "1920×1080"

    def test_fps_str_integer(self, sample_metadata: VideoMetadata) -> None:
        assert sample_metadata.fps_str == "24 fps"

    def test_duration_str(self, sample_metadata: VideoMetadata) -> None:
        assert sample_metadata.duration_str == "0:10"

    def test_file_size_str(self, sample_metadata: VideoMetadata) -> None:
        assert "MB" in sample_metadata.file_size_str or "KB" in sample_metadata.file_size_str


class TestVideoLoader:
    """Tests for VideoLoader validation."""

    def test_validate_nonexistent_file(self) -> None:
        loader = VideoLoader()
        valid, msg = loader.validate_path("/nonexistent/video.mp4")
        assert not valid
        assert "not exist" in msg.lower() or "does not exist" in msg.lower()

    def test_validate_unsupported_format(self, tmp_path: Path) -> None:
        # Create a dummy file with unsupported extension
        bad_file = tmp_path / "test.xyz"
        bad_file.write_text("dummy")
        loader = VideoLoader()
        valid, msg = loader.validate_path(str(bad_file))
        assert not valid
        assert "unsupported" in msg.lower()

    def test_validate_supported_format(self, tmp_path: Path) -> None:
        mp4_file = tmp_path / "test.mp4"
        mp4_file.write_text("dummy")
        loader = VideoLoader()
        valid, msg = loader.validate_path(str(mp4_file))
        assert valid

    def test_load_unsupported_raises(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "test.gif"
        bad_file.write_text("dummy")
        loader = VideoLoader()
        with pytest.raises(UnsupportedFormatError):
            loader.load(str(bad_file))

    def test_load_nonexistent_raises(self) -> None:
        loader = VideoLoader()
        with pytest.raises(VideoLoadError):
            loader.load("/does/not/exist.mp4")
