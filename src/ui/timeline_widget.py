"""
Color-coded timeline widget for FrameFlow AI.

Displays frame-by-frame analysis results as a scrollable, zoomable
bar where each frame is color-coded:
  🟢 Green  = Keep
  🔴 Red    = Remove
  🟡 Yellow = Uncertain
  🔵 Blue   = Scene Boundary

Supports click-to-select, context menu overrides, and zoom.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal, Slot
from PySide6.QtGui import (
    QBrush,
    QColor,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.duplicate_detector import FrameAnalysis
from src.utils.constants import FrameDecision


# ---------------------------------------------------------------------------
# Frame colors
# ---------------------------------------------------------------------------

DECISION_COLORS: dict[FrameDecision, QColor] = {
    FrameDecision.KEEP: QColor("#4CAF50"),
    FrameDecision.REMOVE: QColor("#F44336"),
    FrameDecision.UNCERTAIN: QColor("#FFC107"),
    FrameDecision.SCENE_BOUNDARY: QColor("#2196F3"),
}

SELECTION_COLOR = QColor("#FFFFFF")
HOVER_COLOR = QColor(255, 255, 255, 60)
BG_COLOR = QColor("#141414")
LABEL_COLOR = QColor("#888888")


# ---------------------------------------------------------------------------
# Internal Canvas
# ---------------------------------------------------------------------------

class _TimelineCanvas(QWidget):
    """The paintable surface inside the scroll area."""

    frame_clicked = Signal(int)
    frame_decision_changed = Signal(int, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._analyses: list[FrameAnalysis] = []
        self._zoom: float = 1.0
        self._min_bar_width: int = 2
        self._max_bar_width: int = 30
        self._bar_width: float = 4.0
        self._selected_index: int = -1
        self._hovered_index: int = -1

    # -- Data ---------------------------------------------------------------

    def set_analyses(self, analyses: list[FrameAnalysis]) -> None:
        self._analyses = analyses
        self._recalc_size()
        self.update()

    def update_frame(self, index: int, decision: FrameDecision) -> None:
        if 0 <= index < len(self._analyses):
            self._analyses[index].decision = decision
            self.update()

    @property
    def selected_index(self) -> int:
        return self._selected_index

    # -- Zoom ---------------------------------------------------------------

    def zoom_in(self) -> None:
        self._zoom = min(self._zoom * 1.3, 10.0)
        self._recalc_size()
        self.update()

    def zoom_out(self) -> None:
        self._zoom = max(self._zoom / 1.3, 0.2)
        self._recalc_size()
        self.update()

    def _recalc_size(self) -> None:
        bw = max(self._min_bar_width, min(self._max_bar_width, 4.0 * self._zoom))
        self._bar_width = bw
        total_width = max(int(len(self._analyses) * bw) + 20, 100)
        self.setMinimumWidth(total_width)
        self.setFixedWidth(total_width)

    # -- Painting -----------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        painter.fillRect(rect, BG_COLOR)

        if not self._analyses:
            painter.setPen(QPen(LABEL_COLOR))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No analysis data — analyze a video first")
            painter.end()
            return

        bw = self._bar_width
        h = rect.height()
        header_h = 16  # Space for frame numbers
        bar_h = h - header_h - 4

        for i, analysis in enumerate(self._analyses):
            x = int(i * bw)
            color = DECISION_COLORS.get(analysis.decision, QColor("#555555"))

            # Draw bar
            bar_rect = QRect(x, header_h, max(int(bw) - 1, 1), bar_h)
            painter.fillRect(bar_rect, QBrush(color))

            # Hover highlight
            if i == self._hovered_index:
                painter.fillRect(bar_rect, QBrush(HOVER_COLOR))

            # Selection outline
            if i == self._selected_index:
                painter.setPen(QPen(SELECTION_COLOR, 2))
                painter.drawRect(bar_rect.adjusted(0, 0, 0, 0))

            # Frame number labels (only when zoomed in enough)
            if bw >= 14 and i % max(1, int(5 / self._zoom)) == 0:
                painter.setPen(QPen(LABEL_COLOR))
                painter.setFont(painter.font())
                painter.drawText(
                    QRect(x, 0, max(int(bw * 5), 30), header_h),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    str(i),
                )

        painter.end()

    # -- Mouse Events -------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._index_at(event.position().x())
            if 0 <= idx < len(self._analyses):
                self._selected_index = idx
                self.frame_clicked.emit(idx)
                self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            idx = self._index_at(event.position().x())
            if 0 <= idx < len(self._analyses):
                self._selected_index = idx
                self._show_context_menu(event.globalPosition().toPoint(), idx)
                self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        idx = self._index_at(event.position().x())
        if idx != self._hovered_index:
            self._hovered_index = idx
            if 0 <= idx < len(self._analyses):
                a = self._analyses[idx]
                self.setToolTip(
                    f"Frame {idx}\n"
                    f"Score: {a.weighted_score * 100:.1f}%\n"
                    f"Decision: {a.decision.name}"
                )
            self.update()

    def leaveEvent(self, event: Any) -> None:
        self._hovered_index = -1
        self.update()

    def _index_at(self, x: float) -> int:
        if self._bar_width <= 0:
            return -1
        return int(x / self._bar_width)

    def _show_context_menu(self, pos: QPoint, index: int) -> None:
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #242424; border: 1px solid #444; border-radius: 4px; padding: 4px; }
            QMenu::item { padding: 6px 20px; border-radius: 3px; }
            QMenu::item:selected { background-color: #00BCD4; color: white; }
        """)
        keep_act = menu.addAction("✅ Keep Frame")
        remove_act = menu.addAction("❌ Remove Frame")
        uncertain_act = menu.addAction("⚠️ Mark Uncertain")

        action = menu.exec(pos)
        if action == keep_act:
            self.frame_decision_changed.emit(index, "KEEP")
            self._analyses[index].decision = FrameDecision.KEEP
        elif action == remove_act:
            self.frame_decision_changed.emit(index, "REMOVE")
            self._analyses[index].decision = FrameDecision.REMOVE
        elif action == uncertain_act:
            self.frame_decision_changed.emit(index, "UNCERTAIN")
            self._analyses[index].decision = FrameDecision.UNCERTAIN
        self.update()


# ---------------------------------------------------------------------------
# Public Timeline Widget
# ---------------------------------------------------------------------------

class TimelineWidget(QWidget):
    """
    Scrollable, zoomable timeline showing per-frame analysis results.

    Signals:
        frame_clicked(int): Emitted when a frame is clicked.
        frame_decision_changed(int, str): Emitted when a frame decision
            is changed via context menu.
    """

    frame_clicked = Signal(int)
    frame_decision_changed = Signal(int, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ─────────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("Timeline")
        title.setStyleSheet("font-weight: 600; font-size: 12px; padding: 4px 8px; color: #A0A0A0;")
        header.addWidget(title)
        header.addStretch()

        self._stats_label = QLabel("")
        self._stats_label.setStyleSheet("font-size: 11px; color: #666; padding-right: 8px;")
        header.addWidget(self._stats_label)

        # Legend
        for decision, color_hex in [
            ("Keep", "#4CAF50"), ("Remove", "#F44336"),
            ("Uncertain", "#FFC107"), ("Scene", "#2196F3"),
        ]:
            dot = QLabel(f"● {decision}")
            dot.setStyleSheet(f"color: {color_hex}; font-size: 11px; padding: 0 4px;")
            header.addWidget(dot)

        layout.addLayout(header)

        # ── Scroll area with canvas ────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: #141414; }")

        self._canvas = _TimelineCanvas()
        self._canvas.frame_clicked.connect(self.frame_clicked.emit)
        self._canvas.frame_decision_changed.connect(self.frame_decision_changed.emit)
        self._scroll.setWidget(self._canvas)

        layout.addWidget(self._scroll)

    # -- Public API ---------------------------------------------------------

    def set_analyses(self, analyses: list[FrameAnalysis]) -> None:
        self._canvas.set_analyses(analyses)
        # Update stats
        kept = sum(1 for a in analyses if a.decision in (FrameDecision.KEEP, FrameDecision.SCENE_BOUNDARY))
        removed = sum(1 for a in analyses if a.decision == FrameDecision.REMOVE)
        uncertain = sum(1 for a in analyses if a.decision == FrameDecision.UNCERTAIN)
        self._stats_label.setText(
            f"{len(analyses):,} frames | {kept:,} keep | {removed:,} remove | {uncertain:,} uncertain"
        )

    def update_frame(self, index: int, decision: FrameDecision) -> None:
        self._canvas.update_frame(index, decision)

    def clear(self) -> None:
        self._canvas.set_analyses([])
        self._stats_label.setText("")

    def zoom_in(self) -> None:
        self._canvas.zoom_in()

    def zoom_out(self) -> None:
        self._canvas.zoom_out()

    @property
    def selected_frame_index(self) -> int:
        return self._canvas.selected_index

    def set_selected_frame(self, index: int) -> None:
        """Programmatically select a frame on the timeline."""
        self._canvas._selected_index = index
        self._canvas.update()
        # Scroll to make the selected frame visible
        bar_w = self._canvas._bar_width
        x_pos = int(index * bar_w)
        scroll_bar = self._scroll.horizontalScrollBar()
        viewport_w = self._scroll.viewport().width()
        if x_pos < scroll_bar.value() or x_pos > scroll_bar.value() + viewport_w:
            scroll_bar.setValue(max(0, x_pos - viewport_w // 2))

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Zoom on Ctrl+Scroll, horizontal scroll otherwise."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            # Forward to scroll area
            self._scroll.horizontalScrollBar().setValue(
                self._scroll.horizontalScrollBar().value() - event.angleDelta().y()
            )
            event.accept()
