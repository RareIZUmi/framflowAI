"""
Import panel for FrameFlow AI.

Provides a drag-and-drop zone and video metadata display.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.video_loader import VideoFile
from src.utils.constants import SUPPORTED_VIDEO_EXTENSIONS


class DropZone(QFrame):
    """Drag-and-drop area that accepts video files."""

    file_dropped = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setStyleSheet("""
            DropZone {
                border: 2px dashed #444444;
                border-radius: 8px;
                background-color: #1A1A1A;
            }
            DropZone:hover {
                border-color: #00BCD4;
                background-color: #1E2A2D;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel("📁")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 28px; background: transparent;")
        layout.addWidget(icon_label)

        text_label = QLabel("Drag & Drop Video Here")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setStyleSheet(
            "color: #A0A0A0; font-size: 13px; font-weight: 500; background: transparent;"
        )
        layout.addWidget(text_label)

        formats_label = QLabel("MP4 · MKV · MOV · AVI · WebM")
        formats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        formats_label.setStyleSheet(
            "color: #5A5A5A; font-size: 11px; background: transparent;"
        )
        layout.addWidget(formats_label)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if Path(url.toLocalFile()).suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
                    event.acceptProposedAction()
                    self.setStyleSheet("""
                        DropZone {
                            border: 2px solid #00BCD4;
                            border-radius: 8px;
                            background-color: #1E2A2D;
                        }
                    """)
                    return
        event.ignore()

    def dragLeaveEvent(self, event: object) -> None:
        self.setStyleSheet("""
            DropZone {
                border: 2px dashed #444444;
                border-radius: 8px;
                background-color: #1A1A1A;
            }
            DropZone:hover {
                border-color: #00BCD4;
                background-color: #1E2A2D;
            }
        """)

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if Path(file_path).suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
                self.file_dropped.emit(file_path)
                break
        self.dragLeaveEvent(event)


class ImportPanel(QWidget):
    """
    Panel showing drag-and-drop zone, open button, and video metadata.
    """

    file_dropped = Signal(str)
    import_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # ── Header row ─────────────────────────────────────────────────
        header_row = QHBoxLayout()
        title = QLabel("Import")
        title.setObjectName("heading")
        header_row.addWidget(title)

        header_row.addStretch()

        open_btn = QPushButton("📂 Open File")
        open_btn.setObjectName("primaryButton")
        open_btn.clicked.connect(self.import_clicked.emit)
        header_row.addWidget(open_btn)

        layout.addLayout(header_row)

        # ── Drop zone ──────────────────────────────────────────────────
        self._drop_zone = DropZone()
        self._drop_zone.file_dropped.connect(self.file_dropped.emit)
        layout.addWidget(self._drop_zone)

        # ── Video info grid ────────────────────────────────────────────
        self._info_frame = QFrame()
        self._info_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._info_frame.setStyleSheet("""
            QFrame {
                background-color: #1A1A1A;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        self._info_frame.hide()

        info_layout = QGridLayout(self._info_frame)
        info_layout.setSpacing(6)
        info_layout.setColumnStretch(1, 1)

        self._labels: dict[str, QLabel] = {}
        fields = [
            ("Filename:", "filename"),
            ("Resolution:", "resolution"),
            ("FPS:", "fps"),
            ("Codec:", "codec"),
            ("Duration:", "duration"),
            ("Frames:", "frames"),
            ("File Size:", "size"),
            ("Audio:", "audio"),
        ]

        for row, (label_text, key) in enumerate(fields):
            label = QLabel(label_text)
            label.setStyleSheet("color: #A0A0A0; font-weight: 600; background: transparent;")
            value = QLabel("—")
            value.setStyleSheet("color: #E0E0E0; background: transparent;")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            info_layout.addWidget(label, row, 0)
            info_layout.addWidget(value, row, 1)
            self._labels[key] = value

        layout.addWidget(self._info_frame)

    def set_video_info(self, video: VideoFile) -> None:
        """Populate the info panel with video metadata."""
        m = video.metadata
        self._labels["filename"].setText(video.path.name)
        self._labels["resolution"].setText(m.resolution_str)
        self._labels["fps"].setText(m.fps_str)
        self._labels["codec"].setText(f"{m.codec_name} ({m.pixel_format})")
        self._labels["duration"].setText(m.duration_str)
        self._labels["frames"].setText(f"{m.frame_count:,}")
        self._labels["size"].setText(m.file_size_str)
        self._labels["audio"].setText(
            f"{m.audio_codec} · {m.audio_sample_rate}Hz · {m.audio_channels}ch"
            if m.has_audio else "None"
        )
        self._info_frame.show()
