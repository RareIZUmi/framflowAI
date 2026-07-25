"""
Processing log viewer for FrameFlow AI.

Displays timestamped log entries in a scrollable text area.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class LogViewer(QWidget):
    """
    Scrollable log viewer panel.

    Shows processing log entries with timestamps and auto-scrolls
    to the latest entry.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header
        header = QHBoxLayout()
        title = QLabel("Log")
        title.setStyleSheet("font-weight: 600; font-size: 12px; color: #A0A0A0;")
        header.addWidget(title)
        header.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(24)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: 1px solid #444;
                border-radius: 3px; padding: 2px 10px; color: #888;
                font-size: 11px;
            }
            QPushButton:hover { background: #333; color: #CCC; }
        """)
        clear_btn.clicked.connect(self._on_clear)
        header.addWidget(clear_btn)
        layout.addLayout(header)

        # Text area
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setStyleSheet("""
            QTextEdit {
                background-color: #0D0D0D;
                color: #A0A0A0;
                border: 1px solid #333;
                border-radius: 4px;
                font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
                font-size: 11px;
                padding: 6px;
            }
        """)
        layout.addWidget(self._text)

    def append_log(self, message: str, level: str = "INFO") -> None:
        """
        Append a timestamped log entry.

        Args:
            message: Log message text.
            level: Log level (INFO, WARNING, ERROR).
        """
        timestamp = datetime.now().strftime("%H:%M:%S")

        color_map = {
            "INFO": "#A0A0A0",
            "WARNING": "#FFC107",
            "ERROR": "#F44336",
            "SUCCESS": "#4CAF50",
        }
        color = color_map.get(level.upper(), "#A0A0A0")

        html = (
            f'<span style="color: #555;">[{timestamp}]</span> '
            f'<span style="color: {color};">{message}</span>'
        )
        self._text.append(html)

        # Auto-scroll to bottom
        scrollbar = self._text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @Slot()
    def _on_clear(self) -> None:
        self._text.clear()
