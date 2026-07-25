"""
Visual confidence indicator bar for FrameFlow AI.

A horizontal bar that fills with a gradient from green (low similarity)
to red (high similarity / dead frame) based on the confidence score.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget


class ConfidenceBar(QWidget):
    """
    A colored bar showing dead frame probability.

    Green (0%) → Yellow (50%) → Red (100%).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value: float = 0.0  # 0.0–1.0
        self.setFixedHeight(12)
        self.setMinimumWidth(60)

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float) -> None:
        self._value = max(0.0, min(1.0, v))
        self.setToolTip(f"Dead frame probability: {self._value * 100:.1f}%")
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        bg_rect = QRect(rect)

        # Background
        painter.fillRect(bg_rect, QColor("#1A1A1A"))

        # Filled portion
        fill_width = int(bg_rect.width() * self._value)
        if fill_width > 0:
            fill_rect = QRect(bg_rect.x(), bg_rect.y(), fill_width, bg_rect.height())

            # Color interpolation: green → yellow → red
            if self._value < 0.5:
                t = self._value * 2
                r = int(76 + (255 - 76) * t)
                g = int(175 + (193 - 175) * t)
                b = int(80 + (7 - 80) * t)
            else:
                t = (self._value - 0.5) * 2
                r = int(255 - (255 - 244) * t)
                g = int(193 - (193 - 67) * t)
                b = int(7 + (54 - 7) * t)

            color = QColor(r, g, b)
            painter.fillRect(fill_rect, color)

        # Border
        painter.setPen(QColor("#333333"))
        painter.drawRoundedRect(bg_rect.adjusted(0, 0, -1, -1), 3, 3)

        painter.end()
