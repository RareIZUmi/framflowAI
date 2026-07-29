"""
Frame Review Panel for FrameFlow AI.

After analysis, allows users to scroll through removed frames
one by one and override decisions (keep/remove) with visual
comparison against the previous unique frame.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.duplicate_detector import FrameAnalysis
from src.core.frame_extractor import FrameExtractor
from src.utils.constants import FrameDecision


class ReviewPanel(QWidget):
    """
    Panel for reviewing removed frames one-by-one after analysis.

    Shows the removed frame alongside its reference (previous unique frame)
    with Keep/Remove buttons and navigation.
    """

    # Signals
    frame_decision_changed = Signal(int, str)  # (frame_index, decision_name)
    frame_selected = Signal(int)  # Navigate timeline to this frame

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._analyses: list[FrameAnalysis] = []
        self._extractor: FrameExtractor | None = None
        self._removed_indices: list[int] = []  # Indices of removed frames
        self._current_review_pos: int = 0  # Position within _removed_indices
        self._setup_ui()
        self._set_empty_state()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ─────────────────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet(
            "QFrame { background: #1A2332; border-bottom: 1px solid #2A3A4A; }"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("🔍 Frame Review")
        title.setStyleSheet(
            "color: #00BCD4; font-size: 13px; font-weight: 700; "
            "letter-spacing: 0.5px; background: transparent; border: none;"
        )
        header_layout.addWidget(title)

        header_layout.addStretch()

        self._counter_label = QLabel("0 / 0 removed frames")
        self._counter_label.setStyleSheet(
            "color: #888; font-size: 12px; background: transparent; border: none;"
        )
        header_layout.addWidget(self._counter_label)

        layout.addWidget(header)

        # ── Comparison area ────────────────────────────────────────────
        comparison = QHBoxLayout()
        comparison.setSpacing(8)
        comparison.setContentsMargins(8, 8, 8, 8)

        # Reference frame (previous unique)
        ref_col = QVBoxLayout()
        ref_title = QLabel("REFERENCE (Previous Unique)")
        ref_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ref_title.setStyleSheet(
            "color: #4CAF50; font-size: 10px; font-weight: 600; "
            "letter-spacing: 1px; padding: 2px;"
        )
        ref_col.addWidget(ref_title)

        self._ref_view = QLabel()
        self._ref_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ref_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._ref_view.setMinimumSize(160, 90)
        self._ref_view.setStyleSheet(
            "background: #0D0D0D; border: 1px solid #333; border-radius: 4px;"
        )
        ref_col.addWidget(self._ref_view, stretch=1)
        comparison.addLayout(ref_col)

        # Current removed frame
        cur_col = QVBoxLayout()
        self._cur_title = QLabel("REMOVED FRAME #0")
        self._cur_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cur_title.setStyleSheet(
            "color: #F44336; font-size: 10px; font-weight: 600; "
            "letter-spacing: 1px; padding: 2px;"
        )
        cur_col.addWidget(self._cur_title)

        self._cur_view = QLabel()
        self._cur_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cur_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._cur_view.setMinimumSize(160, 90)
        self._cur_view.setStyleSheet(
            "background: #0D0D0D; border: 2px solid #F44336; border-radius: 4px;"
        )
        cur_col.addWidget(self._cur_view, stretch=1)
        comparison.addLayout(cur_col)

        layout.addLayout(comparison, stretch=1)

        # ── Score info ─────────────────────────────────────────────────
        self._score_label = QLabel("")
        self._score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._score_label.setStyleSheet(
            "color: #AAA; font-size: 11px; padding: 4px; "
            "background: #141414; border-top: 1px solid #2A2A2A;"
        )
        layout.addWidget(self._score_label)

        # ── Controls ───────────────────────────────────────────────────
        controls = QFrame()
        controls.setStyleSheet(
            "QFrame { background: #1A1A1A; border-top: 1px solid #333; }"
        )
        ctrl_layout = QHBoxLayout(controls)
        ctrl_layout.setContentsMargins(12, 8, 12, 8)
        ctrl_layout.setSpacing(8)

        btn_style_nav = """
            QPushButton {
                background: #2D2D2D; border: 1px solid #444;
                border-radius: 4px; padding: 6px 16px; font-size: 12px;
                color: #CCC; min-width: 100px;
            }
            QPushButton:hover { background: #404040; border-color: #00BCD4; }
            QPushButton:pressed { background: #00BCD4; color: white; }
            QPushButton:disabled { background: #1A1A1A; color: #555; border-color: #333; }
        """

        self._btn_prev_removed = QPushButton("◀ Prev Removed")
        self._btn_prev_removed.setStyleSheet(btn_style_nav)
        self._btn_prev_removed.clicked.connect(self._go_prev_removed)
        ctrl_layout.addWidget(self._btn_prev_removed)

        ctrl_layout.addStretch()

        # Keep / Remove buttons
        btn_keep_style = """
            QPushButton {
                background: #1B5E20; border: 1px solid #4CAF50;
                border-radius: 6px; padding: 8px 24px; font-size: 13px;
                font-weight: 700; color: white; min-width: 100px;
            }
            QPushButton:hover { background: #2E7D32; }
            QPushButton:pressed { background: #4CAF50; }
            QPushButton:disabled { background: #1A1A1A; color: #555; border-color: #333; }
        """
        btn_remove_style = """
            QPushButton {
                background: #B71C1C; border: 1px solid #F44336;
                border-radius: 6px; padding: 8px 24px; font-size: 13px;
                font-weight: 700; color: white; min-width: 100px;
            }
            QPushButton:hover { background: #C62828; }
            QPushButton:pressed { background: #F44336; }
            QPushButton:disabled { background: #1A1A1A; color: #555; border-color: #333; }
        """

        self._btn_keep = QPushButton("✅ Keep (K)")
        self._btn_keep.setStyleSheet(btn_keep_style)
        self._btn_keep.clicked.connect(self._keep_current)
        ctrl_layout.addWidget(self._btn_keep)

        self._btn_remove = QPushButton("❌ Remove (R)")
        self._btn_remove.setStyleSheet(btn_remove_style)
        self._btn_remove.clicked.connect(self._remove_current)
        ctrl_layout.addWidget(self._btn_remove)

        ctrl_layout.addStretch()

        self._btn_next_removed = QPushButton("Next Removed ▶")
        self._btn_next_removed.setStyleSheet(btn_style_nav)
        self._btn_next_removed.clicked.connect(self._go_next_removed)
        ctrl_layout.addWidget(self._btn_next_removed)

        layout.addWidget(controls)

    # ══════════════════════════════════════════════════════════════════
    # Public API
    # ══════════════════════════════════════════════════════════════════

    def set_data(
        self,
        analyses: list[FrameAnalysis],
        extractor: FrameExtractor | None,
    ) -> None:
        """Set analysis results and frame extractor for review."""
        self._analyses = analyses
        self._extractor = extractor
        self._rebuild_removed_list()

        if self._removed_indices:
            self._current_review_pos = 0
            self._show_current()
        else:
            self._set_empty_state()

    def refresh(self) -> None:
        """Rebuild the removed list and update display after external changes."""
        old_frame_idx = (
            self._removed_indices[self._current_review_pos]
            if self._removed_indices and 0 <= self._current_review_pos < len(self._removed_indices)
            else -1
        )
        self._rebuild_removed_list()

        if not self._removed_indices:
            self._set_empty_state()
            return

        # Try to stay on the same frame or nearby
        if old_frame_idx >= 0 and old_frame_idx in self._removed_indices:
            self._current_review_pos = self._removed_indices.index(old_frame_idx)
        else:
            self._current_review_pos = min(
                self._current_review_pos, len(self._removed_indices) - 1
            )
        self._show_current()

    def navigate_to_frame(self, frame_index: int) -> None:
        """Navigate to a specific frame if it's in the removed list."""
        if frame_index in self._removed_indices:
            self._current_review_pos = self._removed_indices.index(frame_index)
            self._show_current()

    def clear(self) -> None:
        """Reset the panel."""
        self._analyses = []
        self._extractor = None
        self._removed_indices = []
        self._current_review_pos = 0
        self._set_empty_state()

    # ══════════════════════════════════════════════════════════════════
    # Internal
    # ══════════════════════════════════════════════════════════════════

    def _rebuild_removed_list(self) -> None:
        """Rebuild the list of frame indices marked as REMOVE."""
        self._removed_indices = [
            i for i, a in enumerate(self._analyses)
            if a.decision == FrameDecision.REMOVE
        ]

    def _set_empty_state(self) -> None:
        """Show empty/no-data state."""
        self._counter_label.setText("No removed frames")
        self._cur_title.setText("REMOVED FRAME")
        self._score_label.setText("Run analysis to detect duplicate frames")
        self._ref_view.clear()
        self._ref_view.setText("—")
        self._ref_view.setStyleSheet(
            "background: #0D0D0D; border: 1px solid #333; border-radius: 4px; "
            "color: #555; font-size: 24px;"
        )
        self._cur_view.clear()
        self._cur_view.setText("—")
        self._cur_view.setStyleSheet(
            "background: #0D0D0D; border: 1px solid #333; border-radius: 4px; "
            "color: #555; font-size: 24px;"
        )
        self._btn_prev_removed.setEnabled(False)
        self._btn_next_removed.setEnabled(False)
        self._btn_keep.setEnabled(False)
        self._btn_remove.setEnabled(False)

    def _show_current(self) -> None:
        """Display the current removed frame and its reference."""
        if not self._removed_indices or self._extractor is None:
            self._set_empty_state()
            return

        pos = self._current_review_pos
        frame_idx = self._removed_indices[pos]
        analysis = self._analyses[frame_idx]

        # Update counter
        self._counter_label.setText(
            f"{pos + 1} / {len(self._removed_indices)} removed frames"
        )
        self._cur_title.setText(f"REMOVED FRAME #{frame_idx}")

        # Show current removed frame
        cur_frame = self._extractor.get_frame(frame_idx)
        if cur_frame is not None:
            self._display_frame(cur_frame, self._cur_view)
            self._cur_view.setStyleSheet(
                "background: #0D0D0D; border: 2px solid #F44336; border-radius: 4px;"
            )

        # Find and show reference frame (previous unique frame)
        ref_idx = self._find_reference_frame(frame_idx)
        if ref_idx >= 0:
            ref_frame = self._extractor.get_frame(ref_idx)
            if ref_frame is not None:
                self._display_frame(ref_frame, self._ref_view)
                self._ref_view.setStyleSheet(
                    "background: #0D0D0D; border: 1px solid #4CAF50; border-radius: 4px;"
                )

        # Show score info
        score_text = f"Similarity: {analysis.similarity_percentage:.1f}%"
        if hasattr(analysis, "algorithm_scores") and analysis.algorithm_scores:
            parts = []
            for name, val in analysis.algorithm_scores.items():
                parts.append(f"{name}: {val:.1%}")
            score_text += "  •  " + "  |  ".join(parts)
        self._score_label.setText(score_text)

        # Update nav buttons
        self._btn_prev_removed.setEnabled(pos > 0)
        self._btn_next_removed.setEnabled(pos < len(self._removed_indices) - 1)
        self._btn_keep.setEnabled(True)
        self._btn_remove.setEnabled(True)

        # Sync with timeline
        self.frame_selected.emit(frame_idx)

    def _find_reference_frame(self, frame_idx: int) -> int:
        """Find the previous unique (non-removed) frame before frame_idx."""
        for i in range(frame_idx - 1, -1, -1):
            if self._analyses[i].decision != FrameDecision.REMOVE:
                return i
        return 0  # Fallback to first frame

    def _display_frame(self, frame: np.ndarray, label: QLabel) -> None:
        """Convert BGR numpy array to QPixmap and display."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape

        max_w = max(label.width(), 200)
        max_h = max(label.height(), 120)
        if w > max_w or h > max_h:
            scale = min(max_w / w, max_h / h)
            new_w, new_h = int(w * scale), int(h * scale)
            rgb = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)
            h, w, ch = rgb.shape

        bytes_per_line = ch * w
        q_image = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_image)
        label.setPixmap(pixmap)

    # ── Navigation ─────────────────────────────────────────────────────

    @Slot()
    def _go_prev_removed(self) -> None:
        if self._current_review_pos > 0:
            self._current_review_pos -= 1
            self._show_current()

    @Slot()
    def _go_next_removed(self) -> None:
        if self._current_review_pos < len(self._removed_indices) - 1:
            self._current_review_pos += 1
            self._show_current()

    # ── Keep / Remove ──────────────────────────────────────────────────

    @Slot()
    def _keep_current(self) -> None:
        """Mark the current frame as KEEP and advance to next."""
        if not self._removed_indices:
            return
        frame_idx = self._removed_indices[self._current_review_pos]
        self._analyses[frame_idx].decision = FrameDecision.KEEP
        self.frame_decision_changed.emit(frame_idx, "KEEP")

        # Rebuild and advance
        old_pos = self._current_review_pos
        self._rebuild_removed_list()
        if not self._removed_indices:
            self._set_empty_state()
            self._counter_label.setText("✅ All frames reviewed!")
            return
        self._current_review_pos = min(old_pos, len(self._removed_indices) - 1)
        self._show_current()

    @Slot()
    def _remove_current(self) -> None:
        """Confirm removal and advance to next removed frame."""
        if not self._removed_indices:
            return
        frame_idx = self._removed_indices[self._current_review_pos]
        # Already marked as REMOVE, just advance
        self.frame_decision_changed.emit(frame_idx, "REMOVE")

        if self._current_review_pos < len(self._removed_indices) - 1:
            self._current_review_pos += 1
        self._show_current()
