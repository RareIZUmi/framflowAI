"""
Compact sidebar import panel for FrameFlow AI.

Displays video file info in a vertical card layout with a
drag-and-drop zone and analysis statistics.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.video_loader import VideoFile
from src.utils.constants import SUPPORTED_VIDEO_EXTENSIONS


class ImportPanel(QWidget):
    """
    Compact sidebar panel showing video metadata and analysis stats.

    Features a drop zone at the top, metadata below, and stats at the bottom.
    """

    file_dropped = Signal(str)
    import_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFixedWidth(260)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Drop Zone ──────────────────────────────────────────────────
        self._drop_zone = QFrame()
        self._drop_zone.setStyleSheet("""
            QFrame {
                background: #141E28;
                border: 2px dashed #2A3A4A;
                border-radius: 8px;
                margin: 8px;
            }
            QFrame:hover {
                border-color: #00BCD4;
                background: #1A2A38;
            }
        """)
        drop_layout = QVBoxLayout(self._drop_zone)
        drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.setSpacing(4)

        drop_icon = QLabel("📂")
        drop_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_icon.setStyleSheet("font-size: 24px; background: transparent; border: none;")
        drop_layout.addWidget(drop_icon)

        drop_text = QLabel("Drop Video Here")
        drop_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_text.setStyleSheet(
            "color: #7A8A9A; font-size: 11px; font-weight: 600; "
            "background: transparent; border: none;"
        )
        drop_layout.addWidget(drop_text)

        formats = QLabel("MP4 · MKV · MOV · AVI · WebM")
        formats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        formats.setStyleSheet(
            "color: #4A5A6A; font-size: 9px; background: transparent; border: none;"
        )
        drop_layout.addWidget(formats)

        self._drop_zone.setFixedHeight(90)
        layout.addWidget(self._drop_zone)

        # ── Open Button ────────────────────────────────────────────────
        self._btn_open = QPushButton("📂 Open File")
        self._btn_open.setStyleSheet("""
            QPushButton {
                background: #00838F; border: none; border-radius: 6px;
                padding: 8px; font-size: 12px; font-weight: 600;
                color: white; margin: 0 8px;
            }
            QPushButton:hover { background: #00ACC1; }
            QPushButton:pressed { background: #00BCD4; }
        """)
        self._btn_open.clicked.connect(self.import_clicked.emit)
        layout.addWidget(self._btn_open)

        # ── File Info Section ──────────────────────────────────────────
        info_header = QLabel("FILE INFO")
        info_header.setStyleSheet(
            "color: #00BCD4; font-size: 10px; font-weight: 700; "
            "letter-spacing: 1.5px; padding: 12px 12px 4px 12px;"
        )
        layout.addWidget(info_header)

        # Info rows
        self._info_container = QWidget()
        info_layout = QVBoxLayout(self._info_container)
        info_layout.setContentsMargins(12, 0, 12, 0)
        info_layout.setSpacing(2)

        self._filename_label = self._create_info_row(info_layout, "File", "—")
        self._resolution_label = self._create_info_row(info_layout, "Res", "—")
        self._fps_label = self._create_info_row(info_layout, "FPS", "—")
        self._codec_label = self._create_info_row(info_layout, "Codec", "—")
        self._duration_label = self._create_info_row(info_layout, "Dur", "—")
        self._frames_label = self._create_info_row(info_layout, "Frames", "—")
        self._size_label = self._create_info_row(info_layout, "Size", "—")
        self._audio_label = self._create_info_row(info_layout, "Audio", "—")

        layout.addWidget(self._info_container)

        # ── Analysis Stats Section ─────────────────────────────────────
        stats_header = QLabel("ANALYSIS")
        stats_header.setStyleSheet(
            "color: #00BCD4; font-size: 10px; font-weight: 700; "
            "letter-spacing: 1.5px; padding: 12px 12px 4px 12px;"
        )
        layout.addWidget(stats_header)

        self._stats_container = QWidget()
        stats_layout = QVBoxLayout(self._stats_container)
        stats_layout.setContentsMargins(12, 0, 12, 8)
        stats_layout.setSpacing(4)

        self._stat_kept = self._create_stat_row(stats_layout, "Kept", "—", "#4CAF50")
        self._stat_removed = self._create_stat_row(stats_layout, "Removed", "—", "#F44336")
        self._stat_uncertain = self._create_stat_row(stats_layout, "Uncertain", "—", "#FFC107")
        self._stat_scenes = self._create_stat_row(stats_layout, "Scenes", "—", "#2196F3")

        layout.addWidget(self._stats_container)

        layout.addStretch()

    def _create_info_row(self, parent_layout: QVBoxLayout, label: str, value: str) -> QLabel:
        """Create a compact key-value row."""
        row = QHBoxLayout()
        row.setSpacing(8)

        key = QLabel(label)
        key.setFixedWidth(48)
        key.setStyleSheet("color: #666; font-size: 11px; font-weight: 600;")
        row.addWidget(key)

        val = QLabel(value)
        val.setStyleSheet("color: #CCC; font-size: 11px;")
        val.setWordWrap(True)
        row.addWidget(val, stretch=1)

        parent_layout.addLayout(row)
        return val

    def _create_stat_row(
        self, parent_layout: QVBoxLayout, label: str, value: str, color: str,
    ) -> QLabel:
        """Create a colored stat row."""
        row = QHBoxLayout()
        row.setSpacing(8)

        dot = QLabel("●")
        dot.setFixedWidth(12)
        dot.setStyleSheet(f"color: {color}; font-size: 8px;")
        row.addWidget(dot)

        key = QLabel(label)
        key.setStyleSheet("color: #888; font-size: 11px;")
        row.addWidget(key)

        row.addStretch()

        val = QLabel(value)
        val.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 700;")
        row.addWidget(val)

        parent_layout.addLayout(row)
        return val

    # ══════════════════════════════════════════════════════════════════
    # Public API
    # ══════════════════════════════════════════════════════════════════

    def set_video_info(self, video: VideoFile) -> None:
        """Update the panel with video metadata."""
        meta = video.metadata
        self._filename_label.setText(video.path.name)
        self._resolution_label.setText(meta.resolution_str)
        self._fps_label.setText(meta.fps_str)
        self._codec_label.setText(f"{meta.codec_name}" if meta.codec_name else "—")
        self._duration_label.setText(meta.duration_str)
        self._frames_label.setText(f"{video.frame_count:,}")
        self._size_label.setText(meta.file_size_str)
        self._audio_label.setText(
            f"{meta.audio_codec} · {meta.audio_sample_rate}Hz"
            if meta.audio_codec else "None"
        )

    def set_stats(
        self, kept: int, removed: int, uncertain: int, scenes: int,
    ) -> None:
        """Update analysis statistics."""
        self._stat_kept.setText(str(kept))
        self._stat_removed.setText(str(removed))
        self._stat_uncertain.setText(str(uncertain))
        self._stat_scenes.setText(str(scenes))

    def clear_stats(self) -> None:
        """Reset stats to default."""
        for label in (self._stat_kept, self._stat_removed, self._stat_uncertain, self._stat_scenes):
            label.setText("—")

    # ══════════════════════════════════════════════════════════════════
    # Drag and Drop
    # ══════════════════════════════════════════════════════════════════

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if Path(url.toLocalFile()).suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
                    event.acceptProposedAction()
                    self._drop_zone.setStyleSheet("""
                        QFrame {
                            background: #1A2A38;
                            border: 2px solid #00BCD4;
                            border-radius: 8px;
                            margin: 8px;
                        }
                    """)
                    return
        event.ignore()

    def dragLeaveEvent(self, event: any) -> None:
        self._drop_zone.setStyleSheet("""
            QFrame {
                background: #141E28;
                border: 2px dashed #2A3A4A;
                border-radius: 8px;
                margin: 8px;
            }
            QFrame:hover {
                border-color: #00BCD4;
                background: #1A2A38;
            }
        """)

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if Path(file_path).suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
                self.file_dropped.emit(file_path)
                break
        self._drop_zone.setStyleSheet("""
            QFrame {
                background: #141E28;
                border: 2px dashed #2A3A4A;
                border-radius: 8px;
                margin: 8px;
            }
            QFrame:hover {
                border-color: #00BCD4;
                background: #1A2A38;
            }
        """)
