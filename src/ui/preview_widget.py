"""
Video preview widget for FrameFlow AI.

Single large frame display with decision badge overlay,
playback controls, and scrubber.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from PySide6.QtCore import QSize, Qt, QTimer, Signal, Slot
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

from src.core.duplicate_detector import FrameAnalysis
from src.core.frame_extractor import FrameExtractor
from src.core.video_loader import VideoFile
from src.utils.constants import MAX_PREVIEW_RESOLUTION, FrameDecision


class PreviewWidget(QWidget):
    """
    Single large frame preview with decision badge overlay.

    Shows the current frame with KEEP/REMOVE/UNCERTAIN badge.
    """

    frame_changed = Signal(int)  # Emitted when the displayed frame changes

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._video: VideoFile | None = None
        self._extractor: FrameExtractor | None = None
        self._analyses: list[FrameAnalysis] = []
        self._current_frame: int = 0
        self._is_playing: bool = False

        self._setup_ui()

        # Playback timer
        self._play_timer = QTimer(self)
        self._play_timer.timeout.connect(self._on_play_tick)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Preview frame ──────────────────────────────────────────────
        self._frame_container = QWidget()
        self._frame_container.setStyleSheet("background: #0A0A0A;")
        frame_layout = QVBoxLayout(self._frame_container)
        frame_layout.setContentsMargins(0, 0, 0, 0)

        self._frame_view = QLabel()
        self._frame_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._frame_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._frame_view.setMinimumSize(320, 180)
        self._frame_view.setStyleSheet(
            "background-color: #0A0A0A; border: none;"
        )
        frame_layout.addWidget(self._frame_view)

        layout.addWidget(self._frame_container, stretch=1)

        # ── Decision badge + frame info ────────────────────────────────
        info_bar = QFrame()
        info_bar.setStyleSheet(
            "QFrame { background: #141414; border-top: 1px solid #2A2A2A; }"
        )
        info_layout = QHBoxLayout(info_bar)
        info_layout.setContentsMargins(12, 4, 12, 4)

        self._decision_badge = QLabel("")
        self._decision_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._decision_badge.setFixedWidth(100)
        self._decision_badge.setStyleSheet(
            "background: #333; color: #888; border-radius: 4px; "
            "padding: 3px 8px; font-size: 11px; font-weight: 700;"
        )
        info_layout.addWidget(self._decision_badge)

        self._score_label = QLabel("")
        self._score_label.setStyleSheet(
            "color: #888; font-size: 11px; background: transparent; border: none;"
        )
        info_layout.addWidget(self._score_label)

        info_layout.addStretch()

        self._frame_counter = QLabel("0 / 0")
        self._frame_counter.setStyleSheet(
            "color: #888; font-size: 12px; font-weight: 600; "
            "background: transparent; border: none;"
        )
        info_layout.addWidget(self._frame_counter)

        layout.addWidget(info_bar)

        # ── Scrubber ───────────────────────────────────────────────────
        self._scrubber = QSlider(Qt.Orientation.Horizontal)
        self._scrubber.setMinimum(0)
        self._scrubber.setMaximum(0)
        self._scrubber.valueChanged.connect(self._on_scrubber_changed)
        self._scrubber.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #2D2D2D; height: 6px; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #00BCD4; width: 14px; margin: -4px 0;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, x2:1, stop:0 #00BCD4, stop:1 #7C4DFF);
                border-radius: 3px;
            }
        """)
        layout.addWidget(self._scrubber)

        # ── Playback controls ──────────────────────────────────────────
        controls = QFrame()
        controls.setStyleSheet(
            "QFrame { background: #141414; border-top: 1px solid #2A2A2A; }"
        )
        ctrl_layout = QHBoxLayout(controls)
        ctrl_layout.setContentsMargins(8, 4, 8, 4)
        ctrl_layout.setSpacing(4)

        btn_style = """
            QPushButton {
                background: #2D2D2D; border: 1px solid #444;
                border-radius: 4px; padding: 5px 12px; font-size: 14px;
                min-width: 32px; color: #CCC;
            }
            QPushButton:hover { background: #404040; border-color: #00BCD4; }
            QPushButton:pressed { background: #00BCD4; color: white; }
        """

        self._btn_start = QPushButton("⏮")
        self._btn_start.setStyleSheet(btn_style)
        self._btn_start.setToolTip("Go to Start")
        self._btn_start.clicked.connect(self._go_to_start)
        ctrl_layout.addWidget(self._btn_start)

        self._btn_prev = QPushButton("◀")
        self._btn_prev.setStyleSheet(btn_style)
        self._btn_prev.setToolTip("Previous Frame (←)")
        self._btn_prev.clicked.connect(self.step_backward)
        ctrl_layout.addWidget(self._btn_prev)

        self._btn_play = QPushButton("▶")
        self._btn_play.setStyleSheet(btn_style)
        self._btn_play.setToolTip("Play / Pause (Space)")
        self._btn_play.clicked.connect(self.toggle_playback)
        ctrl_layout.addWidget(self._btn_play)

        self._btn_next = QPushButton("▶")
        self._btn_next.setStyleSheet(btn_style)
        self._btn_next.setToolTip("Next Frame (→)")
        self._btn_next.clicked.connect(self.step_forward)
        ctrl_layout.addWidget(self._btn_next)

        self._btn_end = QPushButton("⏭")
        self._btn_end.setStyleSheet(btn_style)
        self._btn_end.setToolTip("Go to End")
        self._btn_end.clicked.connect(self._go_to_end)
        ctrl_layout.addWidget(self._btn_end)

        ctrl_layout.addStretch()

        layout.addWidget(controls)

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

    def set_analyses(self, analyses: list[FrameAnalysis]) -> None:
        """Attach analysis results for decision badges."""
        self._analyses = analyses
        # Refresh current frame badge
        self._update_badge()

    def show_frame(self, index: int) -> None:
        """Display a specific frame in the preview."""
        if self._extractor is None or self._video is None:
            return

        index = max(0, min(index, self._video.frame_count - 1))
        self._current_frame = index

        frame = self._extractor.get_frame(index)
        if frame is not None:
            self._display_frame(frame, self._frame_view)

        # Update scrubber without triggering signal loop
        self._scrubber.blockSignals(True)
        self._scrubber.setValue(index)
        self._scrubber.blockSignals(False)

        self._frame_counter.setText(
            f"{index:,} / {self._video.frame_count - 1:,}"
        )

        self._update_badge()
        self.frame_changed.emit(index)

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

    def _update_badge(self) -> None:
        """Update the decision badge for the current frame."""
        idx = self._current_frame
        if 0 <= idx < len(self._analyses):
            analysis = self._analyses[idx]
            decision = analysis.decision
            badge_styles = {
                FrameDecision.KEEP: (
                    "✅ KEEP",
                    "background: #1B5E20; color: #A5D6A7; border-radius: 4px; "
                    "padding: 3px 8px; font-size: 11px; font-weight: 700;",
                ),
                FrameDecision.REMOVE: (
                    "❌ REMOVE",
                    "background: #B71C1C; color: #EF9A9A; border-radius: 4px; "
                    "padding: 3px 8px; font-size: 11px; font-weight: 700;",
                ),
                FrameDecision.UNCERTAIN: (
                    "⚠ UNCERTAIN",
                    "background: #E65100; color: #FFE0B2; border-radius: 4px; "
                    "padding: 3px 8px; font-size: 11px; font-weight: 700;",
                ),
                FrameDecision.SCENE_BOUNDARY: (
                    "🎬 SCENE",
                    "background: #0D47A1; color: #90CAF9; border-radius: 4px; "
                    "padding: 3px 8px; font-size: 11px; font-weight: 700;",
                ),
            }
            text, style = badge_styles.get(
                decision,
                ("—", "background: #333; color: #888; border-radius: 4px; "
                 "padding: 3px 8px; font-size: 11px; font-weight: 700;"),
            )
            self._decision_badge.setText(text)
            self._decision_badge.setStyleSheet(style)
            self._score_label.setText(
                f"Similarity: {analysis.similarity_percentage:.1f}%"
            )
        else:
            self._decision_badge.setText("")
            self._decision_badge.setStyleSheet(
                "background: #333; color: #888; border-radius: 4px; "
                "padding: 3px 8px; font-size: 11px; font-weight: 700;"
            )
            self._score_label.setText("")

    def _display_frame(self, frame: np.ndarray, label: QLabel) -> None:
        """Convert BGR numpy array to QPixmap and display in a QLabel."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape

        # Scale down for preview if too large
        max_w = max(label.width(), 320)
        max_h = max(label.height(), 180)
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
