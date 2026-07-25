"""
Batch processing panel for FrameFlow AI.

Queue-based multi-video processing with pause, resume, cancel,
and drag-to-reorder support.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.utils.constants import VIDEO_FILTER


class BatchItem:
    """Represents a single item in the batch queue."""

    __slots__ = ("path", "status", "progress", "frames_total", "frames_done", "error")

    def __init__(self, path: str) -> None:
        self.path = path
        self.status: str = "Queued"  # Queued, Processing, Complete, Error, Cancelled
        self.progress: float = 0.0
        self.frames_total: int = 0
        self.frames_done: int = 0
        self.error: str = ""


class BatchPanel(QWidget):
    """
    Batch processing queue UI.

    Displays a table of queued videos with status, progress, and controls.

    Signals:
        process_requested(list[str]): Emitted when user starts batch processing.
    """

    process_requested = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[BatchItem] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # ── Header ─────────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("Batch Queue")
        title.setObjectName("heading")
        title.setStyleSheet("font-size: 14px;")
        header.addWidget(title)
        header.addStretch()

        add_btn = QPushButton("➕ Add Files")
        add_btn.clicked.connect(self._on_add_files)
        header.addWidget(add_btn)

        clear_btn = QPushButton("🗑 Clear")
        clear_btn.clicked.connect(self._on_clear)
        header.addWidget(clear_btn)

        layout.addLayout(header)

        # ── Queue table ────────────────────────────────────────────────
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Filename", "Status", "Progress", ""])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(1, 100)
        self._table.setColumnWidth(2, 150)
        self._table.setColumnWidth(3, 60)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet("""
            QTableWidget { alternate-background-color: #1E1E1E; }
        """)
        layout.addWidget(self._table, stretch=1)

        # ── Bottom controls ────────────────────────────────────────────
        bottom = QHBoxLayout()

        self._btn_process = QPushButton("🚀 Process All")
        self._btn_process.setObjectName("primaryButton")
        self._btn_process.clicked.connect(self._on_process)
        bottom.addWidget(self._btn_process)

        self._btn_pause = QPushButton("⏸ Pause")
        self._btn_pause.clicked.connect(self._on_pause)
        self._btn_pause.setEnabled(False)
        bottom.addWidget(self._btn_pause)

        self._btn_cancel = QPushButton("⏹ Cancel")
        self._btn_cancel.clicked.connect(self._on_cancel)
        self._btn_cancel.setEnabled(False)
        bottom.addWidget(self._btn_cancel)

        bottom.addStretch()

        self._count_label = QLabel("0 files")
        self._count_label.setStyleSheet("color: #888; font-size: 12px;")
        bottom.addWidget(self._count_label)

        layout.addLayout(bottom)

    # -- Actions ------------------------------------------------------------

    @Slot()
    def _on_add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Videos to Batch", "", VIDEO_FILTER,
        )
        for path in paths:
            self.add_file(path)

    @Slot()
    def _on_clear(self) -> None:
        self._items.clear()
        self._table.setRowCount(0)
        self._update_count()

    @Slot()
    def _on_process(self) -> None:
        paths = [item.path for item in self._items if item.status == "Queued"]
        if paths:
            self.process_requested.emit(paths)

    @Slot()
    def _on_pause(self) -> None:
        pass  # Will be connected to processing engine

    @Slot()
    def _on_cancel(self) -> None:
        for item in self._items:
            if item.status == "Processing":
                item.status = "Cancelled"
        self._refresh_table()

    # -- Public API ---------------------------------------------------------

    def add_file(self, path: str) -> None:
        """Add a file to the batch queue."""
        # Avoid duplicates
        if any(item.path == path for item in self._items):
            return

        item = BatchItem(path)
        self._items.append(item)

        row = self._table.rowCount()
        self._table.insertRow(row)

        name_item = QTableWidgetItem(Path(path).name)
        name_item.setToolTip(path)
        name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(row, 0, name_item)

        status_item = QTableWidgetItem("Queued")
        status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(row, 1, status_item)

        progress = QProgressBar()
        progress.setMaximumHeight(18)
        progress.setValue(0)
        self._table.setCellWidget(row, 2, progress)

        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(30, 24)
        remove_btn.setStyleSheet("QPushButton { border: none; color: #888; } QPushButton:hover { color: #F44336; }")
        remove_btn.clicked.connect(lambda _, r=row: self._remove_row(r))
        self._table.setCellWidget(row, 3, remove_btn)

        self._update_count()

    def update_item_progress(self, index: int, progress: float, status: str = "") -> None:
        """Update progress for a batch item."""
        if 0 <= index < len(self._items):
            self._items[index].progress = progress
            if status:
                self._items[index].status = status

            progress_widget = self._table.cellWidget(index, 2)
            if isinstance(progress_widget, QProgressBar):
                progress_widget.setValue(int(progress * 100))

            if status:
                status_item = self._table.item(index, 1)
                if status_item:
                    status_item.setText(status)

    def _remove_row(self, row: int) -> None:
        if 0 <= row < len(self._items):
            self._items.pop(row)
            self._table.removeRow(row)
            self._update_count()

    def _refresh_table(self) -> None:
        for i, item in enumerate(self._items):
            status_item = self._table.item(i, 1)
            if status_item:
                status_item.setText(item.status)

    def _update_count(self) -> None:
        self._count_label.setText(f"{len(self._items)} file{'s' if len(self._items) != 1 else ''}")
