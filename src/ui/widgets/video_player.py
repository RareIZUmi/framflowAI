"""
OpenCV-backed video player widget for FrameFlow AI.

Provides a QWidget that renders video frames from OpenCV
with efficient QImage conversion and aspect-ratio-preserving display.
"""

from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPainter, QPaintEvent, QResizeEvent
from PySide6.QtWidgets import QSizePolicy, QWidget


class VideoPlayerWidget(QWidget):
    """
    A lightweight widget that renders BGR numpy frames with
    correct aspect ratio and smooth scaling.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._frame: np.ndarray | None = None
        self._q_image: QImage | None = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(160, 90)
        self.setStyleSheet("background-color: #0D0D0D;")

    def set_frame(self, frame: np.ndarray) -> None:
        """
        Display a new BGR frame.

        Args:
            frame: OpenCV BGR numpy array.
        """
        self._frame = frame
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        self._q_image = QImage(
            rgb.data.tobytes(), w, h, bytes_per_line, QImage.Format.Format_RGB888,
        )
        self.update()

    def clear(self) -> None:
        """Clear the displayed frame."""
        self._frame = None
        self._q_image = None
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if self._q_image is None:
            painter.fillRect(self.rect(), Qt.GlobalColor.black)
            painter.setPen(Qt.GlobalColor.darkGray)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No Frame")
            painter.end()
            return

        # Calculate aspect-ratio-preserving rect
        img_w, img_h = self._q_image.width(), self._q_image.height()
        widget_w, widget_h = self.width(), self.height()

        scale = min(widget_w / img_w, widget_h / img_h)
        scaled_w = int(img_w * scale)
        scaled_h = int(img_h * scale)
        x = (widget_w - scaled_w) // 2
        y = (widget_h - scaled_h) // 2

        target_rect = QRect(x, y, scaled_w, scaled_h)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        painter.drawImage(target_rect, self._q_image)
        painter.end()

    @property
    def has_frame(self) -> bool:
        return self._q_image is not None
