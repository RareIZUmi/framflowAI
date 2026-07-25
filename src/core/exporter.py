"""
Video and image sequence exporter for FrameFlow AI.

Handles:
- Exporting kept frames as a new video (via FFmpeg)
- Exporting image sequences (PNG, JPEG, EXR)
- Surgical audio trimming to maintain sync when frames are removed
- Progress reporting for the UI
- Metadata/report export alongside video
"""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

from src.core.duplicate_detector import FrameAnalysis
from src.core.frame_cache import FrameCache
from src.core.video_loader import VideoFile
from src.utils.constants import ExportCodec, FrameDecision, ImageFormat
from src.utils.ffmpeg import FFmpegManager, get_ffmpeg
from src.utils.logger import ProcessingStats, get_logger
from src.utils.reports import FrameReport, ReportGenerator

logger = get_logger("core.exporter")


# ---------------------------------------------------------------------------
# Export Configuration
# ---------------------------------------------------------------------------

class ExportConfig:
    """Configuration for video/image export."""

    def __init__(
        self,
        output_path: str | Path = "",
        codec: ExportCodec = ExportCodec.H264,
        output_fps: float = 0.0,  # 0 = same as source
        crf: int = 18,
        pixel_format: str = "yuv420p",
        preserve_audio: bool = True,
        image_format: ImageFormat | None = None,  # None = export video
        image_quality: int = 95,  # JPEG quality
        generate_report_json: bool = True,
        generate_report_csv: bool = False,
    ) -> None:
        self.output_path = Path(output_path) if output_path else Path()
        self.codec = codec
        self.output_fps = output_fps
        self.crf = crf
        self.pixel_format = pixel_format
        self.preserve_audio = preserve_audio
        self.image_format = image_format
        self.image_quality = image_quality
        self.generate_report_json = generate_report_json
        self.generate_report_csv = generate_report_csv

    @property
    def is_image_sequence(self) -> bool:
        return self.image_format is not None


# ---------------------------------------------------------------------------
# Export Progress
# ---------------------------------------------------------------------------

class ExportProgress:
    """Thread-safe progress tracking for export operations."""

    def __init__(self, total_frames: int) -> None:
        self._total = total_frames
        self._current = 0
        self._lock = threading.Lock()
        self._cancelled = False
        self._callback: Callable[[float, str], None] | None = None

    def set_callback(self, callback: Callable[[float, str], None]) -> None:
        """Set a progress callback: callback(progress_0_to_1, status_message)."""
        self._callback = callback

    def update(self, frames_done: int, message: str = "") -> None:
        with self._lock:
            self._current = frames_done
            if self._callback:
                progress = self._current / max(self._total, 1)
                self._callback(progress, message)

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------

class Exporter:
    """
    Exports processed video or image sequences.

    Workflow for video export:
    1. Write kept frames as a numbered PNG sequence to a temp directory
    2. Encode PNG sequence to video via FFmpeg
    3. Extract audio from original video
    4. Surgically trim audio (remove segments for deleted frames)
    5. Mux trimmed audio with new video
    6. Clean up temp files
    7. Generate reports if requested

    Usage:
        exporter = Exporter(video, analyses, config)
        exporter.set_progress_callback(my_callback)
        success = exporter.export()
    """

    def __init__(
        self,
        video: VideoFile,
        analyses: list[FrameAnalysis],
        config: ExportConfig,
        cache: FrameCache | None = None,
        ffmpeg: FFmpegManager | None = None,
        stats: ProcessingStats | None = None,
    ) -> None:
        self._video = video
        self._analyses = analyses
        self._config = config
        self._cache = cache or FrameCache()
        self._ffmpeg = ffmpeg or get_ffmpeg()
        self._stats = stats
        self._progress = ExportProgress(self._count_kept_frames())

    def set_progress_callback(self, callback: Callable[[float, str], None]) -> None:
        """Set progress reporting callback."""
        self._progress.set_callback(callback)

    def cancel(self) -> None:
        """Cancel the current export."""
        self._progress.cancel()

    # -- Main Export --------------------------------------------------------

    def export(self) -> bool:
        """
        Execute the export operation.

        Returns:
            True on success, False on failure or cancellation.
        """
        if self._config.is_image_sequence:
            return self._export_image_sequence()
        return self._export_video()

    # -- Video Export -------------------------------------------------------

    def _export_video(self) -> bool:
        """Export kept frames as a video file with audio."""
        output_path = self._config.output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create temp directory for intermediate files
        temp_dir = Path(tempfile.mkdtemp(prefix="frameflow_export_"))

        try:
            # Step 1: Write kept frames as PNGs
            self._progress.update(0, "Writing frames...")
            frame_dir = temp_dir / "frames"
            frame_dir.mkdir()
            if not self._write_kept_frames_to_dir(frame_dir):
                return False

            # Step 2: Determine output FPS
            fps = self._config.output_fps if self._config.output_fps > 0 else self._video.fps

            # Step 3: Encode to video
            self._progress.update(0, "Encoding video...")
            video_only = temp_dir / f"video_only{self._config.codec.file_extension}"
            if not self._ffmpeg.encode_frames_to_video(
                frame_dir=str(frame_dir),
                output_path=str(video_only),
                fps=fps,
                codec=self._config.codec.value,
                crf=self._config.crf,
                pixel_format=self._config.pixel_format,
            ):
                logger.error("Video encoding failed.")
                return False

            # Step 4: Handle audio
            if self._config.preserve_audio and self._video.metadata.has_audio:
                self._progress.update(0, "Processing audio...")
                final_path = self._process_audio(video_only, temp_dir, output_path)
                if final_path:
                    if final_path != output_path:
                        shutil.move(str(final_path), str(output_path))
                else:
                    # Audio processing failed; export without audio
                    logger.warning("Audio processing failed; exporting without audio.")
                    shutil.move(str(video_only), str(output_path))
            else:
                shutil.move(str(video_only), str(output_path))

            # Step 5: Generate reports
            self._generate_reports(output_path)

            logger.info("Video exported successfully: %s", output_path)
            self._progress.update(self._count_kept_frames(), "Export complete!")
            return True

        except Exception as exc:
            logger.error("Export failed: %s", exc)
            return False
        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _write_kept_frames_to_dir(self, frame_dir: Path) -> bool:
        """Write all kept frames as numbered PNGs."""
        kept_indices = self._get_kept_frame_indices()
        total = len(kept_indices)

        for seq_num, frame_idx in enumerate(kept_indices):
            if self._progress.is_cancelled:
                logger.info("Export cancelled by user.")
                return False

            # Try cache first, then read from video
            frame = self._cache.get(str(self._video.path), frame_idx)
            if frame is None:
                frame = self._video.read_frame(frame_idx)
            if frame is None:
                logger.warning("Could not read frame %d; skipping.", frame_idx)
                continue

            filename = frame_dir / f"frame_{seq_num:06d}.png"
            cv2.imwrite(str(filename), frame)

            if seq_num % 50 == 0:
                self._progress.update(
                    seq_num,
                    f"Writing frames: {seq_num}/{total}",
                )

        self._progress.update(total, f"Wrote {total} frames.")
        return True

    def _process_audio(
        self, video_path: Path, temp_dir: Path, output_path: Path,
    ) -> Path | None:
        """Extract, trim, and mux audio."""
        # Extract audio
        audio_raw = temp_dir / "audio_raw.wav"
        if not self._ffmpeg.extract_audio(str(self._video.path), str(audio_raw)):
            return None

        # Calculate audio segments to keep
        keep_segments = self._compute_audio_keep_segments()
        if not keep_segments:
            return None

        # Trim audio
        audio_trimmed = temp_dir / "audio_trimmed.wav"
        if not self._ffmpeg.trim_audio_segments(
            str(audio_raw), keep_segments, str(audio_trimmed),
        ):
            return None

        # Mux
        final = temp_dir / f"final{output_path.suffix}"
        if not self._ffmpeg.mux_video_audio(
            str(video_path), str(audio_trimmed), str(final),
        ):
            return None

        return final

    def _compute_audio_keep_segments(self) -> list[tuple[float, float]]:
        """
        Compute the audio time segments to keep based on frame decisions.

        For each kept frame, we keep the corresponding audio duration.
        This implements the "surgical trim" approach — audio is cut at
        the exact timestamps of removed frames.
        """
        fps = self._video.fps
        if fps <= 0:
            return []

        frame_duration = 1.0 / fps
        segments: list[tuple[float, float]] = []
        current_start: float | None = None
        current_end: float = 0.0

        for analysis in self._analyses:
            frame_time = analysis.frame_index * frame_duration
            if analysis.decision in (FrameDecision.KEEP, FrameDecision.UNCERTAIN, FrameDecision.SCENE_BOUNDARY):
                if current_start is None:
                    current_start = frame_time
                current_end = frame_time + frame_duration
            else:
                # Frame is removed — close current segment
                if current_start is not None:
                    segments.append((current_start, current_end))
                    current_start = None

        # Close final segment
        if current_start is not None:
            segments.append((current_start, current_end))

        return segments

    # -- Image Sequence Export ----------------------------------------------

    def _export_image_sequence(self) -> bool:
        """Export kept frames as an image sequence."""
        output_dir = self._config.output_path
        output_dir.mkdir(parents=True, exist_ok=True)

        fmt = self._config.image_format or ImageFormat.PNG
        ext = f".{fmt.value}"
        kept_indices = self._get_kept_frame_indices()
        total = len(kept_indices)

        for seq_num, frame_idx in enumerate(kept_indices):
            if self._progress.is_cancelled:
                return False

            frame = self._cache.get(str(self._video.path), frame_idx)
            if frame is None:
                frame = self._video.read_frame(frame_idx)
            if frame is None:
                continue

            filename = output_dir / f"frame_{seq_num:06d}{ext}"

            if fmt == ImageFormat.JPEG:
                cv2.imwrite(str(filename), frame, [
                    cv2.IMWRITE_JPEG_QUALITY, self._config.image_quality,
                ])
            elif fmt == ImageFormat.PNG:
                cv2.imwrite(str(filename), frame, [
                    cv2.IMWRITE_PNG_COMPRESSION, 3,
                ])
            elif fmt == ImageFormat.EXR:
                # Convert to float32 for EXR
                frame_float = frame.astype(np.float32) / 255.0
                cv2.imwrite(str(filename), frame_float)

            if seq_num % 50 == 0:
                self._progress.update(seq_num, f"Exporting images: {seq_num}/{total}")

        self._generate_reports(output_dir)
        self._progress.update(total, "Image sequence export complete!")
        logger.info("Image sequence exported: %d frames to %s", total, output_dir)
        return True

    # -- Reports ------------------------------------------------------------

    def _generate_reports(self, output_location: Path) -> None:
        """Generate JSON and/or CSV reports alongside the export."""
        if not (self._config.generate_report_json or self._config.generate_report_csv):
            return

        frame_reports = [
            FrameReport(
                frame_index=a.frame_index,
                similarity_score=a.weighted_score,
                ssim_score=a.ssim_score,
                phash_score=a.phash_score,
                histogram_score=a.histogram_score,
                optical_flow_score=a.optical_flow_score,
                ai_score=a.ai_score,
                dead_frame_probability=a.weighted_score,
                decision=a.decision.name.lower(),
                is_scene_boundary=a.is_scene_boundary,
            )
            for a in self._analyses
        ]

        video_meta = {
            "path": str(self._video.path),
            "resolution": self._video.metadata.resolution_str,
            "fps": self._video.metadata.fps,
            "duration": self._video.metadata.duration_str,
            "codec": self._video.metadata.codec_name,
        }

        generator = ReportGenerator(
            stats=self._stats or ProcessingStats(),
            frame_reports=frame_reports,
            video_metadata=video_meta,
        )

        report_dir = output_location.parent if output_location.is_file() else output_location
        stem = output_location.stem if output_location.is_file() else "report"

        if self._config.generate_report_json:
            generator.generate_json(report_dir / f"{stem}_report.json")

        if self._config.generate_report_csv:
            generator.generate_csv(report_dir / f"{stem}_report.csv")

    # -- Helpers ------------------------------------------------------------

    def _get_kept_frame_indices(self) -> list[int]:
        """Get sorted list of frame indices that are kept."""
        return sorted(
            a.frame_index for a in self._analyses
            if a.decision in (FrameDecision.KEEP, FrameDecision.UNCERTAIN, FrameDecision.SCENE_BOUNDARY)
        )

    def _count_kept_frames(self) -> int:
        return len(self._get_kept_frame_indices())
