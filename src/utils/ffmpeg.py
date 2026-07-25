"""
FFmpeg detection and wrapper for FrameFlow AI.

Handles:
- Auto-detection of FFmpeg/FFprobe in PATH and common Windows locations
- Video metadata extraction via FFprobe
- Audio extraction, trimming, and muxing operations
- Progress monitoring for long-running encodes
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.utils.logger import get_logger

logger = get_logger("ffmpeg")


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VideoMetadata:
    """Immutable container for video file metadata."""

    path: str
    width: int
    height: int
    fps: float
    duration: float  # seconds
    frame_count: int
    codec_name: str
    codec_long_name: str
    pixel_format: str
    bit_rate: int  # bps, 0 if unknown
    file_size: int  # bytes
    has_audio: bool
    audio_codec: str
    audio_sample_rate: int
    audio_channels: int
    container_format: str

    @property
    def resolution_str(self) -> str:
        return f"{self.width}×{self.height}"

    @property
    def fps_str(self) -> str:
        if self.fps == int(self.fps):
            return f"{int(self.fps)} fps"
        return f"{self.fps:.3f} fps"

    @property
    def duration_str(self) -> str:
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        frac = f".{int((self.duration % 1) * 100):02d}" if self.duration % 1 else ""
        if h:
            return f"{h}:{m:02d}:{s:02d}{frac}"
        return f"{m}:{s:02d}{frac}"

    @property
    def file_size_str(self) -> str:
        size = self.file_size
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


# ---------------------------------------------------------------------------
# FFmpeg Manager
# ---------------------------------------------------------------------------

# Common Windows install locations for FFmpeg
_COMMON_PATHS = [
    r"C:\ffmpeg\bin",
    r"C:\Program Files\ffmpeg\bin",
    r"C:\Program Files (x86)\ffmpeg\bin",
    os.path.expanduser(r"~\ffmpeg\bin"),
    os.path.expanduser(r"~\scoop\shims"),
]


class FFmpegNotFoundError(RuntimeError):
    """Raised when FFmpeg or FFprobe cannot be located."""


class FFmpegManager:
    """
    Manages FFmpeg / FFprobe binary discovery and provides high-level
    wrappers for common video operations.
    """

    def __init__(self) -> None:
        self._ffmpeg_path: str | None = None
        self._ffprobe_path: str | None = None
        self._detect()

    # -- Discovery ----------------------------------------------------------

    def _detect(self) -> None:
        """Attempt to find ffmpeg and ffprobe on the system."""
        self._ffmpeg_path = self._find_binary("ffmpeg")
        self._ffprobe_path = self._find_binary("ffprobe")

        if self._ffmpeg_path:
            logger.info("FFmpeg found: %s", self._ffmpeg_path)
        else:
            logger.warning("FFmpeg not found on this system.")

        if self._ffprobe_path:
            logger.info("FFprobe found: %s", self._ffprobe_path)
        else:
            logger.warning("FFprobe not found on this system.")

    @staticmethod
    def _find_binary(name: str) -> str | None:
        """Search PATH and common locations for a binary."""
        # Try PATH first
        found = shutil.which(name)
        if found:
            return found

        # Try common Windows locations
        for directory in _COMMON_PATHS:
            candidate = Path(directory) / f"{name}.exe"
            if candidate.is_file():
                return str(candidate)
        return None

    @property
    def available(self) -> bool:
        """Whether both FFmpeg and FFprobe are available."""
        return self._ffmpeg_path is not None and self._ffprobe_path is not None

    @property
    def ffmpeg_path(self) -> str:
        if not self._ffmpeg_path:
            raise FFmpegNotFoundError(
                "FFmpeg not found. Please install FFmpeg and ensure it is on your PATH."
            )
        return self._ffmpeg_path

    @property
    def ffprobe_path(self) -> str:
        if not self._ffprobe_path:
            raise FFmpegNotFoundError(
                "FFprobe not found. Please install FFmpeg and ensure it is on your PATH."
            )
        return self._ffprobe_path

    def set_paths(self, ffmpeg: str, ffprobe: str | None = None) -> None:
        """Manually set FFmpeg/FFprobe paths."""
        self._ffmpeg_path = ffmpeg
        self._ffprobe_path = ffprobe or str(Path(ffmpeg).parent / "ffprobe")
        logger.info("FFmpeg paths set manually: %s", ffmpeg)

    # -- Probe --------------------------------------------------------------

    def probe(self, video_path: str | Path) -> VideoMetadata:
        """
        Extract comprehensive metadata from a video file using FFprobe.

        Args:
            video_path: Path to the video file.

        Returns:
            VideoMetadata with all extracted information.

        Raises:
            FFmpegNotFoundError: If FFprobe is not available.
            RuntimeError: If probing fails.
        """
        video_path = str(video_path)
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            "-count_frames",
            video_path,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"FFprobe timed out while probing: {video_path}")
        except FileNotFoundError:
            raise FFmpegNotFoundError("FFprobe binary not found at expected path.")

        if result.returncode != 0:
            raise RuntimeError(f"FFprobe error: {result.stderr.strip()}")

        data = json.loads(result.stdout)
        return self._parse_probe_data(data, video_path)

    def _parse_probe_data(self, data: dict[str, Any], path: str) -> VideoMetadata:
        """Parse FFprobe JSON output into VideoMetadata."""
        video_stream: dict[str, Any] = {}
        audio_stream: dict[str, Any] = {}

        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video" and not video_stream:
                video_stream = stream
            elif stream.get("codec_type") == "audio" and not audio_stream:
                audio_stream = stream

        if not video_stream:
            raise RuntimeError(f"No video stream found in: {path}")

        # Parse FPS from r_frame_rate (e.g., "24000/1001")
        fps_str = video_stream.get("r_frame_rate", "24/1")
        fps = self._parse_fraction(fps_str)

        # Frame count
        frame_count = int(video_stream.get("nb_read_frames", 0) or
                          video_stream.get("nb_frames", 0) or 0)

        # Duration
        fmt = data.get("format", {})
        duration = float(video_stream.get("duration", 0) or fmt.get("duration", 0) or 0)

        # Estimate frame count from duration if not reported
        if frame_count == 0 and duration > 0 and fps > 0:
            frame_count = int(duration * fps)

        file_size = int(fmt.get("size", 0) or 0)
        if file_size == 0:
            try:
                file_size = Path(path).stat().st_size
            except OSError:
                pass

        return VideoMetadata(
            path=path,
            width=int(video_stream.get("width", 0)),
            height=int(video_stream.get("height", 0)),
            fps=fps,
            duration=duration,
            frame_count=frame_count,
            codec_name=video_stream.get("codec_name", "unknown"),
            codec_long_name=video_stream.get("codec_long_name", "Unknown"),
            pixel_format=video_stream.get("pix_fmt", "unknown"),
            bit_rate=int(video_stream.get("bit_rate", 0) or fmt.get("bit_rate", 0) or 0),
            file_size=file_size,
            has_audio=bool(audio_stream),
            audio_codec=audio_stream.get("codec_name", ""),
            audio_sample_rate=int(audio_stream.get("sample_rate", 0) or 0),
            audio_channels=int(audio_stream.get("channels", 0) or 0),
            container_format=fmt.get("format_name", "unknown"),
        )

    # -- Audio Operations ---------------------------------------------------

    def extract_audio(self, video_path: str | Path, output_path: str | Path) -> bool:
        """
        Extract audio track from video to a WAV file.

        Returns:
            True if audio was extracted, False if no audio track exists.
        """
        cmd = [
            self.ffmpeg_path,
            "-y", "-i", str(video_path),
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "48000",
            str(output_path),
        ]
        return self._run(cmd, f"Extracting audio from {video_path}")

    def trim_audio_segments(
        self,
        audio_path: str | Path,
        keep_segments: list[tuple[float, float]],
        output_path: str | Path,
    ) -> bool:
        """
        Surgically trim audio by keeping only specified time segments.

        This is used to remove audio corresponding to deleted frames.
        Each segment is a (start_seconds, end_seconds) tuple.

        Args:
            audio_path: Path to source audio file (WAV).
            keep_segments: List of (start, end) time segments to keep.
            output_path: Path for the trimmed audio output.

        Returns:
            True on success.
        """
        if not keep_segments:
            logger.warning("No audio segments to keep; skipping audio trim.")
            return False

        # Build FFmpeg filter_complex for concatenating segments
        filter_parts: list[str] = []
        inputs_str = ""
        for i, (start, end) in enumerate(keep_segments):
            filter_parts.append(
                f"[0:a]atrim=start={start:.6f}:end={end:.6f},asetpts=PTS-STARTPTS[a{i}]"
            )
            inputs_str += f"[a{i}]"

        concat_filter = f"{inputs_str}concat=n={len(keep_segments)}:v=0:a=1[outa]"
        full_filter = ";".join(filter_parts) + ";" + concat_filter

        cmd = [
            self.ffmpeg_path,
            "-y", "-i", str(audio_path),
            "-filter_complex", full_filter,
            "-map", "[outa]",
            str(output_path),
        ]
        return self._run(cmd, "Trimming audio segments")

    def mux_video_audio(
        self,
        video_path: str | Path,
        audio_path: str | Path,
        output_path: str | Path,
    ) -> bool:
        """
        Mux a video file with an audio file into a single output.

        Args:
            video_path: Path to the video-only file.
            audio_path: Path to the audio file.
            output_path: Path for the muxed output.

        Returns:
            True on success.
        """
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "320k",
            "-shortest",
            str(output_path),
        ]
        return self._run(cmd, "Muxing video and audio")

    # -- Encode -------------------------------------------------------------

    def encode_frames_to_video(
        self,
        frame_dir: str | Path,
        output_path: str | Path,
        fps: float,
        codec: str = "libx264",
        crf: int = 18,
        pixel_format: str = "yuv420p",
        progress_callback: Callable[[float], None] | None = None,
    ) -> bool:
        """
        Encode a directory of numbered PNG frames into a video file.

        Args:
            frame_dir: Directory containing frame_%06d.png files.
            output_path: Output video path.
            fps: Output framerate.
            codec: FFmpeg codec name.
            crf: Constant rate factor (quality).
            pixel_format: Output pixel format.
            progress_callback: Optional callback receiving progress 0.0–1.0.

        Returns:
            True on success.
        """
        input_pattern = str(Path(frame_dir) / "frame_%06d.png")
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-framerate", str(fps),
            "-i", input_pattern,
            "-c:v", codec,
            "-crf", str(crf),
            "-pix_fmt", pixel_format,
            "-movflags", "+faststart",
            str(output_path),
        ]

        if codec == "prores_ks":
            # ProRes doesn't use CRF; use profile instead
            cmd = [
                self.ffmpeg_path,
                "-y",
                "-framerate", str(fps),
                "-i", input_pattern,
                "-c:v", "prores_ks",
                "-profile:v", "3",  # ProRes HQ
                "-pix_fmt", "yuva444p10le",
                str(output_path),
            ]
        elif codec in ("ffv1", "libx264rgb"):
            # Lossless codecs
            cmd = [
                self.ffmpeg_path,
                "-y",
                "-framerate", str(fps),
                "-i", input_pattern,
                "-c:v", codec,
                str(output_path),
            ]

        return self._run(cmd, f"Encoding video with {codec}")

    # -- Helpers ------------------------------------------------------------

    def _run(self, cmd: list[str], description: str) -> bool:
        """Run an FFmpeg command and log the result."""
        logger.debug("Running: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour max
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if result.returncode != 0:
                logger.error("%s failed: %s", description, result.stderr.strip()[-500:])
                return False
            logger.info("%s completed successfully.", description)
            return True
        except subprocess.TimeoutExpired:
            logger.error("%s timed out after 1 hour.", description)
            return False
        except Exception as exc:
            logger.error("%s failed with exception: %s", description, exc)
            return False

    @staticmethod
    def _parse_fraction(s: str) -> float:
        """Parse a fraction string like '24000/1001' into a float."""
        if "/" in s:
            num, den = s.split("/", 1)
            try:
                return float(num) / float(den)
            except (ValueError, ZeroDivisionError):
                return 24.0
        try:
            return float(s)
        except ValueError:
            return 24.0


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: FFmpegManager | None = None


def get_ffmpeg() -> FFmpegManager:
    """Return the global FFmpegManager singleton."""
    global _instance  # noqa: PLW0603
    if _instance is None:
        _instance = FFmpegManager()
    return _instance
