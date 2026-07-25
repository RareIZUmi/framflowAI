"""
Side-by-side video preview widget for FrameFlow AI.

Shows Original vs Processed frames with playback controls:
Play, Pause, Step Forward, Step Backward, Loop, Zoom.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from PySide6.QtCore import QSize, Qt, QTimer, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.core.frame_extractor import FrameExtractor
from src.core.video_loader import VideoFile
from src.utils.constants import MAX_PREVIEW_RESOLUTION


class PreviewWidget(QWidget):
    """
    Side-by-side preview: Original frame vs Processed frame.

    Playback controls at the bottom.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._video: VideoFile | None = None
        self._extractor: FrameExtractor | None = None
        self._current_frame: int = 0
        self._is_playing: bool = False
        self._zoom: float = 1.0

        self._setup_ui()

        # Playback timer
        self._play_timer = QTimer(self)
        self._play_timer.timeout.connect(self._on_play_tick)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # ── Preview area ───────────────────────────────────────────────
        preview_row = QHBoxLayout()
        preview_row.setSpacing(4)

        # Original frame
        orig_container = QVBoxLayout()
        orig_label = QLabel("ORIGINAL")
        orig_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        orig_label.setStyleSheet(
            "color: #A0A0A0; font-size: 11px; font-weight: 600; "
            "letter-spacing: 1px; padding: 2px;"
        )
        orig_container.addWidget(orig_label)

        self._original_view = QLabel()
        self._original_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._original_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._original_view.setMinimumSize(200, 120)
        self._original_view.setStyleSheet("background-color: #0D0D0D; border: 1px solid #333; border-radius: 4px;")
        orig_container.addWidget(self._original_view, stretch=1)
        preview_row.addLayout(orig_container)

        # Processed frame
        proc_container = QVBoxLayout()
        proc_label = QLabel("PROCESSED")
        proc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        proc_label.setStyleSheet(
            "color: #00BCD4; font-size: 11px; font-weight: 600; "
            "letter-spacing: 1px; padding: 2px;"
        )
        proc_container.addWidget(proc_label)

        self._processed_view = QLabel()
        self._processed_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._processed_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._processed_view.setMinimumSize(200, 120)
        self._processed_view.setStyleSheet("background-color: #0D0D0D; border: 1px solid #333; border-radius: 4px;")
        proc_container.addWidget(self._processed_view, stretch=1)
        preview_row.addLayout(proc_container)

        layout.addLayout(preview_row, stretch=1)

        # ── Frame info overlay ─────────────────────────────────────────
        self._info_label = QLabel("")
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info_label.setStyleSheet(
            "color: #888; font-size: 11px; padding: 2px; background: transparent;"
        )
        layout.addWidget(self._info_label)

        # ── Scrubber ───────────────────────────────────────────────────
        self._scrubber = QSlider(Qt.Orientation.Horizontal)
        self._scrubber.setMinimum(0)
        self._scrubber.setMaximum(0)
        self._scrubber.valueChanged.connect(self._on_scrubber_changed)
        layout.addWidget(self._scrubber)

        # ── Controls ───────────────────────────────────────────────────
        controls = QHBoxLayout()
        controls.setSpacing(6)

        btn_style = """
            QPushButton {
                background: #2D2D2D; border: 1px solid #444;
                border-radius: 4px; padding: 6px 14px; font-size: 14px;
                min-width: 36px;
            }
            QPushButton:hover { background: #404040; }
            QPushButton:pressed { background: #00BCD4; }
        """

        self._btn_start = QPushButton("⏮")
        self._btn_start.setStyleSheet(btn_style)
        self._btn_start.setToolTip("Go to Start")
        self._btn_start.clicked.connect(self._go_to_start)
        controls.addWidget(self._btn_start)

        self._btn_prev = QPushButton("◀")
        self._btn_prev.setStyleSheet(btn_style)
        self._btn_prev.setToolTip("Previous Frame")
        self._btn_prev.clicked.connect(self.step_backward)
        controls.addWidget(self._btn_prev)

        self._btn_play = QPushButton("▶")
        self._btn_play.setStyleSheet(btn_style)
        self._btn_play.setToolTip("Play / Pause")
        self._btn_play.clicked.connect(self.toggle_playback)
        controls.addWidget(self._btn_play)

        self._btn_next = QPushButton("▶")
        self._btn_next.setStyleSheet(btn_style)
        self._btn_next.setToolTip("Next Frame")
        self._btn_next.clicked.connect(self.step_forward)
        controls.addWidget(self._btn_next)

        self._btn_end = QPushButton("⏭")
        self._btn_end.setStyleSheet(btn_style)
        self._btn_end.setToolTip("Go to End")
        self._btn_end.clicked.connect(self._go_to_end)
        controls.addWidget(self._btn_end)

        controls.addStretch()

        self._frame_counter = QLabel("0 / 0")
        self._frame_counter.setStyleSheet("color: #888; font-size: 12px;")
        controls.addWidget(self._frame_counter)

        layout.addLayout(controls)

    # ══════════════════════════════════════════════════════════════════
    # Public API
    # ══════════════════════════════════════════════════════════════════

    def set_video(self, video: VideoFile, extractor: FrameExtractor) -> None:
        """Set the video source for preview."""
        self._video = video
        self._extractor = extractor
        self._current_frame = 0
        self._scrubber.setMaximum(max(0, video.frame_count - 1))
        self._scrubber.setValue(0)
        self.show_frame(0)

    def show_frame(self, index: int) -> None:
        """Display a specific frame in the preview."""
        if self._extractor is None or self._video is None:
            return

        index = max(0, min(index, self._video.frame_count - 1))
        self._current_frame = index

        frame = self._extractor.get_frame(index)
        if frame is not None:
            self._display_frame(frame, self._original_view)
            self._display_frame(frame, self._processed_view)

        # Update scrubber without triggering signal loop
        self._scrubber.blockSignals(True)
        self._scrubber.setValue(index)
        self._scrubber.blockSignals(False)

        self._frame_counter.setText(f"{index:,} / {self._video.frame_count - 1:,}")

    def toggle_playback(self) -> None:
        """Toggle play/pause."""
        if self._video is None:
            return
        self._is_playing = not self._is_playing
        if self._is_playing:
            interval = max(1, int(1000 / self._video.fps))
            self._play_timer.start(interval)
            self._btn_play.setText("⏸")
        else:
            self._play_timer.stop()
            self._btn_play.setText("▶")

    def step_forward(self) -> None:
        if self._video:
            self.show_frame(self._current_frame + 1)

    def step_backward(self) -> None:
        if self._video:
            self.show_frame(self._current_frame - 1)

    # ══════════════════════════════════════════════════════════════════
    # Internal
    # ══════════════════════════════════════════════════════════════════

    def _display_frame(self, frame: np.ndarray, label: QLabel) -> None:
        """Convert BGR numpy array to QPixmap and display in a QLabel."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape

        # Scale down for preview if too large
        max_w, max_h = label.width() or 640, label.height() or 360
        if w > max_w or h > max_h:
            scale = min(max_w / w, max_h / h)
            new_w, new_h = int(w * scale), int(h * scale)
            rgb = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)
            h, w, ch = rgb.shape

        bytes_per_line = ch * w
        q_image = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_image)
        label.setPixmap(pixmap)

    @Slot()
    def _on_play_tick(self) -> None:
        if self._video is None:
            self.toggle_playback()
            return
        next_frame = self._current_frame + 1
        if next_frame >= self._video.frame_count:
            next_frame = 0  # Loop
        self.show_frame(next_frame)

    @Slot(int)
    def _on_scrubber_changed(self, value: int) -> None:
        self.show_frame(value)

    def _go_to_start(self) -> None:
        self.show_frame(0)

    def _go_to_end(self) -> None:
        if self._video:
            self.show_frame(self._video.frame_count - 1)
