"""
Export dialog for FrameFlow AI.

Professional export configuration dialog with codec selection,
output format, quality settings, and report generation options.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.duplicate_detector import FrameAnalysis
from src.core.exporter import ExportConfig
from src.core.video_loader import VideoFile
from src.utils.constants import ExportCodec, FrameDecision, ImageFormat


class ExportDialog(QDialog):
    """
    Export configuration dialog.

    Provides tabs for Video Export, Image Sequence, and Reports.
    """

    def __init__(
        self,
        video: VideoFile | None,
        analyses: list[FrameAnalysis],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export – FrameFlow AI")
        self.setMinimumSize(520, 480)
        self._video = video
        self._analyses = analyses
        self._config: ExportConfig | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── Summary ────────────────────────────────────────────────────
        kept = sum(1 for a in self._analyses if a.decision in (
            FrameDecision.KEEP, FrameDecision.UNCERTAIN, FrameDecision.SCENE_BOUNDARY,
        ))
        removed = sum(1 for a in self._analyses if a.decision == FrameDecision.REMOVE)
        summary = QLabel(
            f"📊 {len(self._analyses):,} frames analyzed  •  "
            f"✅ {kept:,} kept  •  ❌ {removed:,} removed"
        )
        summary.setStyleSheet("font-size: 13px; padding: 8px; background: #1E2A2D; border-radius: 6px; color: #00BCD4;")
        summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(summary)

        # ── Tabs ───────────────────────────────────────────────────────
        tabs = QTabWidget()

        # Video tab
        video_tab = QWidget()
        self._setup_video_tab(video_tab)
        tabs.addTab(video_tab, "🎬 Video")

        # Image sequence tab
        image_tab = QWidget()
        self._setup_image_tab(image_tab)
        tabs.addTab(image_tab, "🖼 Image Sequence")

        # Reports tab
        report_tab = QWidget()
        self._setup_report_tab(report_tab)
        tabs.addTab(report_tab, "📄 Reports")

        layout.addWidget(tabs)

        self._tabs = tabs

        # ── Buttons ────────────────────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Export")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primaryButton")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _setup_video_tab(self, tab: QWidget) -> None:
        form = QFormLayout(tab)
        form.setSpacing(10)
        form.setContentsMargins(16, 16, 16, 16)

        # Output path
        path_row = QHBoxLayout()
        self._video_output = QLineEdit()
        if self._video:
            stem = self._video.path.stem
            default_out = str(self._video.path.parent / f"{stem}_cleaned.mp4")
            self._video_output.setText(default_out)
        path_row.addWidget(self._video_output)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_video_output)
        path_row.addWidget(browse_btn)
        form.addRow("Output File:", path_row)

        # Codec
        self._codec_combo = QComboBox()
        for codec in ExportCodec:
            self._codec_combo.addItem(codec.display_name, codec.value)
        form.addRow("Codec:", self._codec_combo)

        # CRF / Quality
        self._crf_spin = QSpinBox()
        self._crf_spin.setRange(0, 51)
        self._crf_spin.setValue(18)
        self._crf_spin.setToolTip("Lower = higher quality. 0 = lossless. 18 = visually lossless.")
        form.addRow("CRF (Quality):", self._crf_spin)

        # FPS
        self._fps_spin = QDoubleSpinBox()
        self._fps_spin.setRange(0, 240)
        self._fps_spin.setValue(0)
        self._fps_spin.setDecimals(3)
        self._fps_spin.setToolTip("0 = same as source")
        self._fps_spin.setSpecialValueText("Same as source")
        form.addRow("Output FPS:", self._fps_spin)

        # Audio
        self._audio_check = QCheckBox("Preserve audio (surgical trim)")
        self._audio_check.setChecked(True)
        form.addRow("Audio:", self._audio_check)

    def _setup_image_tab(self, tab: QWidget) -> None:
        form = QFormLayout(tab)
        form.setSpacing(10)
        form.setContentsMargins(16, 16, 16, 16)

        # Output directory
        dir_row = QHBoxLayout()
        self._image_output = QLineEdit()
        if self._video:
            default_dir = str(self._video.path.parent / f"{self._video.path.stem}_frames")
            self._image_output.setText(default_dir)
        dir_row.addWidget(self._image_output)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_image_output)
        dir_row.addWidget(browse_btn)
        form.addRow("Output Folder:", dir_row)

        # Format
        self._image_format = QComboBox()
        self._image_format.addItem("PNG (Lossless)", "png")
        self._image_format.addItem("JPEG (Lossy)", "jpeg")
        self._image_format.addItem("EXR (HDR)", "exr")
        form.addRow("Format:", self._image_format)

        # JPEG quality
        self._jpeg_quality = QSpinBox()
        self._jpeg_quality.setRange(1, 100)
        self._jpeg_quality.setValue(95)
        form.addRow("JPEG Quality:", self._jpeg_quality)

    def _setup_report_tab(self, tab: QWidget) -> None:
        form = QFormLayout(tab)
        form.setSpacing(10)
        form.setContentsMargins(16, 16, 16, 16)

        self._json_check = QCheckBox("Generate JSON report")
        self._json_check.setChecked(True)
        form.addRow(self._json_check)

        self._csv_check = QCheckBox("Generate CSV report")
        self._csv_check.setChecked(False)
        form.addRow(self._csv_check)

        info = QLabel(
            "Reports include per-frame analysis scores, decisions, "
            "processing statistics, and video metadata."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #888; font-size: 12px; padding: 8px;")
        form.addRow(info)

    # -- Browse Helpers -----------------------------------------------------

    def _browse_video_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Video As", self._video_output.text(),
            "MP4 (*.mp4);;MKV (*.mkv);;MOV (*.mov);;All Files (*.*)",
        )
        if path:
            self._video_output.setText(path)

    def _browse_image_output(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select Output Folder", self._image_output.text(),
        )
        if path:
            self._image_output.setText(path)

    # -- Result -------------------------------------------------------------

    def _on_accept(self) -> None:
        current_tab = self._tabs.currentIndex()

        if current_tab == 0:
            # Video export
            codec_value = self._codec_combo.currentData()
            codec = ExportCodec(codec_value)
            self._config = ExportConfig(
                output_path=self._video_output.text(),
                codec=codec,
                crf=self._crf_spin.value(),
                output_fps=self._fps_spin.value(),
                preserve_audio=self._audio_check.isChecked(),
                generate_report_json=self._json_check.isChecked(),
                generate_report_csv=self._csv_check.isChecked(),
            )
        elif current_tab == 1:
            # Image sequence export
            fmt_value = self._image_format.currentData()
            self._config = ExportConfig(
                output_path=self._image_output.text(),
                image_format=ImageFormat(fmt_value),
                image_quality=self._jpeg_quality.value(),
                generate_report_json=self._json_check.isChecked(),
                generate_report_csv=self._csv_check.isChecked(),
            )
        else:
            # Reports only — use video export path
            self._config = ExportConfig(
                output_path=self._video_output.text(),
                generate_report_json=self._json_check.isChecked(),
                generate_report_csv=self._csv_check.isChecked(),
            )

        self.accept()

    def get_config(self) -> ExportConfig:
        """Return the configured export config after dialog acceptance."""
        return self._config or ExportConfig()
