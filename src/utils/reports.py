"""
JSON and CSV report generation for FrameFlow AI.

Generates structured per-frame analysis reports and summary statistics
that can be used for post-processing, quality assurance, or archival.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.utils.constants import APP_NAME, APP_VERSION
from src.utils.logger import ProcessingStats, get_logger

logger = get_logger("reports")


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

class FrameReport:
    """Per-frame analysis data for reports."""

    __slots__ = (
        "frame_index", "similarity_score", "ssim_score", "phash_score",
        "histogram_score", "optical_flow_score", "ai_score",
        "dead_frame_probability", "decision", "is_scene_boundary",
    )

    def __init__(
        self,
        frame_index: int,
        similarity_score: float = 0.0,
        ssim_score: float = 0.0,
        phash_score: float = 0.0,
        histogram_score: float = 0.0,
        optical_flow_score: float = 0.0,
        ai_score: float = 0.0,
        dead_frame_probability: float = 0.0,
        decision: str = "keep",
        is_scene_boundary: bool = False,
    ) -> None:
        self.frame_index = frame_index
        self.similarity_score = similarity_score
        self.ssim_score = ssim_score
        self.phash_score = phash_score
        self.histogram_score = histogram_score
        self.optical_flow_score = optical_flow_score
        self.ai_score = ai_score
        self.dead_frame_probability = dead_frame_probability
        self.decision = decision
        self.is_scene_boundary = is_scene_boundary

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "similarity_score": round(self.similarity_score, 6),
            "ssim": round(self.ssim_score, 6),
            "phash": round(self.phash_score, 6),
            "histogram": round(self.histogram_score, 6),
            "optical_flow": round(self.optical_flow_score, 6),
            "ai_features": round(self.ai_score, 6),
            "dead_frame_probability": round(self.dead_frame_probability, 6),
            "decision": self.decision,
            "scene_boundary": self.is_scene_boundary,
        }


# ---------------------------------------------------------------------------
# Report Generator
# ---------------------------------------------------------------------------

class ReportGenerator:
    """Generates JSON and CSV reports from processing results."""

    def __init__(
        self,
        stats: ProcessingStats,
        frame_reports: list[FrameReport],
        video_metadata: dict[str, Any] | None = None,
    ) -> None:
        self._stats = stats
        self._frame_reports = frame_reports
        self._video_metadata = video_metadata or {}

    def generate_json(self, output_path: str | Path) -> Path:
        """
        Generate a comprehensive JSON report.

        Args:
            output_path: Path for the JSON output file.

        Returns:
            Path to the written file.
        """
        output_path = Path(output_path)
        report = {
            "application": APP_NAME,
            "version": APP_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "video_metadata": self._video_metadata,
            "summary": self._stats.to_dict(),
            "frames": [fr.to_dict() for fr in self._frame_reports],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)

        logger.info("JSON report written to: %s", output_path)
        return output_path

    def generate_csv(self, output_path: str | Path) -> Path:
        """
        Generate a CSV report with one row per frame.

        Args:
            output_path: Path for the CSV output file.

        Returns:
            Path to the written file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "frame_index", "similarity_score", "ssim", "phash",
            "histogram", "optical_flow", "ai_features",
            "dead_frame_probability", "decision", "scene_boundary",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for fr in self._frame_reports:
                writer.writerow(fr.to_dict())

        logger.info("CSV report written to: %s (%d rows)", output_path, len(self._frame_reports))
        return output_path

    def generate_summary_text(self) -> str:
        """Generate a human-readable processing summary string."""
        s = self._stats
        lines = [
            f"═══ FrameFlow AI Processing Report ═══",
            f"Video: {s.video_path}",
            f"Total Frames: {s.total_frames:,}",
            f"Analyzed: {s.frames_analyzed:,}",
            f"Kept: {s.frames_kept:,}",
            f"Removed: {s.frames_removed:,}",
            f"Uncertain: {s.frames_uncertain:,}",
            f"Scene Boundaries: {s.scene_boundaries:,}",
            f"Removal Rate: {s.removal_percentage:.1f}%",
            f"Processing Speed: {s.fps_processing:.1f} frames/sec",
            f"Total Time: {s.elapsed_seconds:.1f}s",
        ]
        if s.errors:
            lines.append(f"Errors: {len(s.errors)}")
            for err in s.errors[:5]:
                lines.append(f"  • {err}")
        return "\n".join(lines)
