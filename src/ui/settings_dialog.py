"""
Settings dialog for FrameFlow AI.

Tabbed settings with Detection, AI, Export, Performance, and Appearance tabs.
All changes auto-save to the JSON settings file.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.gpu.gpu_manager import get_gpu_manager
from src.utils.constants import ExportCodec
from src.utils.settings import get_settings


class SettingsDialog(QDialog):
    """
    Application settings dialog with tabbed sections.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings – FrameFlow AI")
        self.setMinimumSize(560, 520)
        self._settings = get_settings()
        self._setup_ui()
        self._load_values()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        tabs = QTabWidget()

        # Detection tab
        detection_tab = QWidget()
        self._setup_detection_tab(detection_tab)
        tabs.addTab(detection_tab, "🔍 Detection")

        # AI tab
        ai_tab = QWidget()
        self._setup_ai_tab(ai_tab)
        tabs.addTab(ai_tab, "🤖 AI")

        # Export tab
        export_tab = QWidget()
        self._setup_export_tab(export_tab)
        tabs.addTab(export_tab, "💾 Export")

        # Performance tab
        perf_tab = QWidget()
        self._setup_performance_tab(perf_tab)
        tabs.addTab(perf_tab, "⚡ Performance")

        # Appearance tab
        appearance_tab = QWidget()
        self._setup_appearance_tab(appearance_tab)
        tabs.addTab(appearance_tab, "🎨 Appearance")

        layout.addWidget(tabs)

        # Buttons
        buttons = QDialogButtonBox()
        save_btn = buttons.addButton("Save", QDialogButtonBox.ButtonRole.AcceptRole)
        save_btn.setObjectName("primaryButton")
        cancel_btn = buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        reset_btn = buttons.addButton("Reset Defaults", QDialogButtonBox.ButtonRole.ResetRole)
        reset_btn.clicked.connect(self._on_reset)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ── Detection Tab ──────────────────────────────────────────────────

    def _setup_detection_tab(self, tab: QWidget) -> None:
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        # Thresholds
        thresh_group = QGroupBox("Thresholds")
        thresh_form = QFormLayout(thresh_group)
        thresh_form.setSpacing(8)

        self._similarity_slider = self._create_slider(0, 100, 97)
        self._similarity_label = QLabel("0.97")
        row = QHBoxLayout()
        row.addWidget(self._similarity_slider)
        row.addWidget(self._similarity_label)
        self._similarity_slider.valueChanged.connect(
            lambda v: self._similarity_label.setText(f"{v / 100:.2f}")
        )
        thresh_form.addRow("Similarity Threshold:", row)

        self._uncertain_slider = self._create_slider(0, 100, 90)
        self._uncertain_label = QLabel("0.90")
        row2 = QHBoxLayout()
        row2.addWidget(self._uncertain_slider)
        row2.addWidget(self._uncertain_label)
        self._uncertain_slider.valueChanged.connect(
            lambda v: self._uncertain_label.setText(f"{v / 100:.2f}")
        )
        thresh_form.addRow("Uncertain Threshold:", row2)

        self._min_frames_spin = QSpinBox()
        self._min_frames_spin.setRange(1, 100)
        self._min_frames_spin.setValue(1)
        thresh_form.addRow("Min Consecutive Frames:", self._min_frames_spin)

        self._scene_slider = self._create_slider(5, 95, 35)
        self._scene_label = QLabel("0.35")
        row3 = QHBoxLayout()
        row3.addWidget(self._scene_slider)
        row3.addWidget(self._scene_label)
        self._scene_slider.valueChanged.connect(
            lambda v: self._scene_label.setText(f"{v / 100:.2f}")
        )
        thresh_form.addRow("Scene Threshold:", row3)

        layout.addWidget(thresh_group)

        # Weights
        weights_group = QGroupBox("Algorithm Weights")
        weights_form = QFormLayout(weights_group)
        weights_form.setSpacing(8)

        self._w_ssim = self._create_slider(0, 100, 30)
        weights_form.addRow("SSIM:", self._w_ssim)

        self._w_phash = self._create_slider(0, 100, 20)
        weights_form.addRow("pHash:", self._w_phash)

        self._w_histogram = self._create_slider(0, 100, 15)
        weights_form.addRow("Histogram:", self._w_histogram)

        self._w_flow = self._create_slider(0, 100, 25)
        weights_form.addRow("Optical Flow:", self._w_flow)

        self._w_ai = self._create_slider(0, 100, 10)
        weights_form.addRow("AI Features:", self._w_ai)

        layout.addWidget(weights_group)
        layout.addStretch()

    # ── AI Tab ─────────────────────────────────────────────────────────

    def _setup_ai_tab(self, tab: QWidget) -> None:
        form = QFormLayout(tab)
        form.setSpacing(10)
        form.setContentsMargins(16, 16, 16, 16)

        self._ai_enabled = QCheckBox("Enable AI detection mode")
        self._ai_enabled.setChecked(True)
        form.addRow(self._ai_enabled)

        self._ai_confidence = self._create_slider(0, 100, 85)
        self._ai_conf_label = QLabel("0.85")
        row = QHBoxLayout()
        row.addWidget(self._ai_confidence)
        row.addWidget(self._ai_conf_label)
        self._ai_confidence.valueChanged.connect(
            lambda v: self._ai_conf_label.setText(f"{v / 100:.2f}")
        )
        form.addRow("AI Confidence Threshold:", row)

        info = QLabel(
            "AI mode uses DINOv2-Small (Vision Transformer) to extract deep features.\n"
            "It distinguishes actual motion from duplicated frames by comparing\n"
            "semantic features rather than pixel values.\n\n"
            "Preserves: camera shake, film grain, lighting flicker,\n"
            "compression artifacts, facial micro-movements, subtitle changes."
        )
        info.setStyleSheet("color: #888; font-size: 12px; padding: 8px; line-height: 1.4;")
        info.setWordWrap(True)
        form.addRow(info)

    # ── Export Tab ──────────────────────────────────────────────────────

    def _setup_export_tab(self, tab: QWidget) -> None:
        form = QFormLayout(tab)
        form.setSpacing(10)
        form.setContentsMargins(16, 16, 16, 16)

        self._default_codec = QComboBox()
        for codec in ExportCodec:
            self._default_codec.addItem(codec.display_name, codec.value)
        form.addRow("Default Codec:", self._default_codec)

        self._default_fps = QDoubleSpinBox()
        self._default_fps.setRange(0, 240)
        self._default_fps.setValue(0)
        self._default_fps.setSpecialValueText("Same as source")
        form.addRow("Default FPS:", self._default_fps)

        self._preserve_audio = QCheckBox("Preserve audio by default")
        self._preserve_audio.setChecked(True)
        form.addRow(self._preserve_audio)

    # ── Performance Tab ────────────────────────────────────────────────

    def _setup_performance_tab(self, tab: QWidget) -> None:
        form = QFormLayout(tab)
        form.setSpacing(10)
        form.setContentsMargins(16, 16, 16, 16)

        # GPU
        self._gpu_enabled = QCheckBox("Enable GPU acceleration")
        self._gpu_enabled.setChecked(True)
        form.addRow(self._gpu_enabled)

        self._gpu_device = QComboBox()
        gpu_mgr = get_gpu_manager()
        for device in gpu_mgr.devices:
            self._gpu_device.addItem(device.display_name, device.index)
        form.addRow("GPU Device:", self._gpu_device)

        # Cache
        self._cache_size = QSpinBox()
        self._cache_size.setRange(256, 16384)
        self._cache_size.setValue(2048)
        self._cache_size.setSuffix(" MB")
        form.addRow("Frame Cache Size:", self._cache_size)

        # Batch size
        self._batch_size = QSpinBox()
        self._batch_size.setRange(1, 256)
        self._batch_size.setValue(32)
        form.addRow("Batch Size:", self._batch_size)

    # ── Appearance Tab ─────────────────────────────────────────────────

    def _setup_appearance_tab(self, tab: QWidget) -> None:
        form = QFormLayout(tab)
        form.setSpacing(10)
        form.setContentsMargins(16, 16, 16, 16)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["Dark", "Light"])
        form.addRow("Theme:", self._theme_combo)

        self._preview_quality = QComboBox()
        self._preview_quality.addItems(["Low", "Medium", "High"])
        self._preview_quality.setCurrentIndex(2)
        form.addRow("Preview Quality:", self._preview_quality)

        self._show_frame_numbers = QCheckBox("Show frame numbers on timeline")
        self._show_frame_numbers.setChecked(True)
        form.addRow(self._show_frame_numbers)

        self._show_confidence = QCheckBox("Show confidence overlay on preview")
        self._show_confidence.setChecked(True)
        form.addRow(self._show_confidence)

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _create_slider(min_val: int, max_val: int, default: int) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default)
        return slider

    def _load_values(self) -> None:
        """Load current settings into the UI widgets."""
        s = self._settings

        self._similarity_slider.setValue(int(s.get("detection.similarity_threshold", 0.97) * 100))
        self._uncertain_slider.setValue(int(s.get("detection.uncertain_lower_bound", 0.90) * 100))
        self._min_frames_spin.setValue(s.get("detection.min_consecutive_frames", 1))
        self._scene_slider.setValue(int(s.get("detection.scene_threshold", 0.35) * 100))

        weights = s.get_section("detection.weights") if s.get_section("detection") else {}
        self._w_ssim.setValue(int(weights.get("ssim", 0.30) * 100))
        self._w_phash.setValue(int(weights.get("phash", 0.20) * 100))
        self._w_histogram.setValue(int(weights.get("histogram", 0.15) * 100))
        self._w_flow.setValue(int(weights.get("optical_flow", 0.25) * 100))
        self._w_ai.setValue(int(weights.get("ai_features", 0.10) * 100))

        self._ai_enabled.setChecked(s.get("detection.enable_ai_mode", True))
        self._ai_confidence.setValue(int(s.get("detection.ai_confidence_threshold", 0.85) * 100))

        self._gpu_enabled.setChecked(s.get("performance.gpu_enabled", True))
        self._cache_size.setValue(s.get("performance.cache_size_mb", 2048))
        self._batch_size.setValue(s.get("performance.batch_size", 32))

        self._preview_quality.setCurrentText(
            (s.get("ui.preview_quality", "high") or "high").capitalize()
        )
        self._show_frame_numbers.setChecked(s.get("ui.show_frame_numbers", True))
        self._show_confidence.setChecked(s.get("ui.show_confidence_overlay", True))

    @Slot()
    def _on_save(self) -> None:
        s = self._settings

        s.set("detection.similarity_threshold", self._similarity_slider.value() / 100, auto_save=False)
        s.set("detection.uncertain_lower_bound", self._uncertain_slider.value() / 100, auto_save=False)
        s.set("detection.min_consecutive_frames", self._min_frames_spin.value(), auto_save=False)
        s.set("detection.scene_threshold", self._scene_slider.value() / 100, auto_save=False)

        s.set("detection.weights.ssim", self._w_ssim.value() / 100, auto_save=False)
        s.set("detection.weights.phash", self._w_phash.value() / 100, auto_save=False)
        s.set("detection.weights.histogram", self._w_histogram.value() / 100, auto_save=False)
        s.set("detection.weights.optical_flow", self._w_flow.value() / 100, auto_save=False)
        s.set("detection.weights.ai_features", self._w_ai.value() / 100, auto_save=False)

        s.set("detection.enable_ai_mode", self._ai_enabled.isChecked(), auto_save=False)
        s.set("detection.ai_confidence_threshold", self._ai_confidence.value() / 100, auto_save=False)

        s.set("performance.gpu_enabled", self._gpu_enabled.isChecked(), auto_save=False)
        s.set("performance.gpu_device_index", self._gpu_device.currentData() or 0, auto_save=False)
        s.set("performance.cache_size_mb", self._cache_size.value(), auto_save=False)
        s.set("performance.batch_size", self._batch_size.value(), auto_save=False)

        s.set("ui.preview_quality", self._preview_quality.currentText().lower(), auto_save=False)
        s.set("ui.show_frame_numbers", self._show_frame_numbers.isChecked(), auto_save=False)
        s.set("ui.show_confidence_overlay", self._show_confidence.isChecked(), auto_save=False)

        s.save()
        self.accept()

    @Slot()
    def _on_reset(self) -> None:
        self._settings.reset()
        self._load_values()
