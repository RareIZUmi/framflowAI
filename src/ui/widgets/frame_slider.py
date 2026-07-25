"""
Custom frame scrubber slider for FrameFlow AI.

A styled QSlider with frame number display and snap-to-frame behavior.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QSlider, QToolTip, QWidget


class FrameSlider(QSlider):
    """
    Frame-accurate scrubber slider.

    Shows a tooltip with the current frame number while dragging.
    Emits frame_changed(int) when the user finishes dragging.
    """

    frame_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setTracking(True)
        self.sliderReleased.connect(self._on_released)

    def _on_released(self) -> None:
        self.frame_changed.emit(self.value())

    def mouseMoveEvent(self, event: object) -> None:
        super().mouseMoveEvent(event)
        QToolTip.showText(
            self.mapToGlobal(self.rect().center()),
            f"Frame {self.value():,}",
            self,
        )
