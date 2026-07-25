"""
Main application window for FrameFlow AI.

Professional layout inspired by DaVinci Resolve / Premiere Pro.
Features: menu bar, toolbar, dockable panels, drag-and-drop,
keyboard shortcuts, status bar, and auto-save.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QMimeData, QSize, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.core.ai_detector import AIDetector
from src.core.duplicate_detector import (
    DetectionConfig,
    DuplicateDetector,
    FrameAnalysis,
)
from src.core.exporter import ExportConfig, Exporter
from src.core.frame_cache import FrameCache
from src.core.frame_extractor import FrameExtractor
from src.core.scene_detector import SceneDetector
from src.core.video_loader import VideoFile, VideoLoader, VideoLoadError
from src.ui.batch_panel import BatchPanel
from src.ui.export_dialog import ExportDialog
from src.ui.import_panel import ImportPanel
from src.ui.log_viewer import LogViewer
from src.ui.preview_widget import PreviewWidget
from src.ui.settings_dialog import SettingsDialog
from src.ui.timeline_widget import TimelineWidget
from src.utils.constants import (
    AUTOSAVE_INTERVAL_MS,
    DEFAULT_WINDOW_SIZE,
    MAX_RECENT_FILES,
    MIN_WINDOW_SIZE,
    RECENT_FILES_PATH,
    SHORTCUTS,
    SUPPORTED_VIDEO_EXTENSIONS,
    VIDEO_FILTER,
    FrameDecision,
)
from src.utils.logger import ProcessingStats, get_logger, setup_logger
from src.utils.settings import get_settings

logger = get_logger("ui.main_window")


class ProcessingWorker:
    """Background processing controller for frame analysis."""

    def __init__(self) -> None:
        self.is_running = False
        self.is_paused = False
        self.should_cancel = False
        self.progress = 0.0
        self.status_message = ""


class MainWindow(QMainWindow):
    """
    Central application window for FrameFlow AI.

    Layout:
    ┌──────────────────────────────────────────────────┐
    │  Menu Bar                                        │
    ├──────────────────────────────────────────────────┤
    │  Toolbar                                         │
    ├───────────────────────┬──────────────────────────┤
    │                       │                          │
    │   Import / Preview    │    Frame Info / Log      │
    │                       │                          │
    ├───────────────────────┴──────────────────────────┤
    │  Timeline                                        │
    ├──────────────────────────────────────────────────┤
    │  Status Bar                                      │
    └──────────────────────────────────────────────────┘
    """

    # Signals
    processing_started = Signal()
    processing_finished = Signal()
    processing_progress = Signal(float, str)  # progress, message
    frame_selected = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FrameFlow AI – Intelligent Dead Frame Remover")
        self.setMinimumSize(*MIN_WINDOW_SIZE)
        self.resize(*DEFAULT_WINDOW_SIZE)
        self.setAcceptDrops(True)

        # ── State ──────────────────────────────────────────────────────
        self._settings = get_settings()
        self._video: VideoFile | None = None
        self._extractor: FrameExtractor | None = None
        self._analyses: list[FrameAnalysis] = []
        self._undo_stack: list[tuple[int, FrameDecision]] = []
        self._redo_stack: list[tuple[int, FrameDecision]] = []
        self._cache = FrameCache(
            max_size_mb=self._settings.get("performance.cache_size_mb", 2048)
        )
        self._worker = ProcessingWorker()
        self._recent_files: list[str] = self._load_recent_files()
        self._stats: ProcessingStats | None = None

        # ── Core components ────────────────────────────────────────────
        self._loader = VideoLoader()
        self._detector = DuplicateDetector()
        self._scene_detector = SceneDetector()
        self._ai_detector: AIDetector | None = None

        # ── Build UI ───────────────────────────────────────────────────
        self._setup_ui()
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_status_bar()
        self._setup_shortcuts()

        # ── Auto-save timer ────────────────────────────────────────────
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._auto_save_session)
        self._autosave_timer.start(AUTOSAVE_INTERVAL_MS)

        # ── Window state restore disabled ─────────────────────────────────
        # Positioning is handled by app.py _center_on_screen() for reliability.
        # self._restore_window_state()

        # ── Initialize AI (async) ──────────────────────────────────────
        if self._settings.get("detection.enable_ai_mode", True):
            QTimer.singleShot(500, self._init_ai_detector)

        logger.info("MainWindow initialized.")

    # ══════════════════════════════════════════════════════════════════
    # UI Setup
    # ══════════════════════════════════════════════════════════════════

    def _setup_ui(self) -> None:
        """Create the main layout with dockable panels."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Top splitter: Import/Preview + Info ────────────────────────
        top_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Import panel + Preview
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(4, 4, 4, 4)
        left_layout.setSpacing(4)

        self._import_panel = ImportPanel()
        self._import_panel.file_dropped.connect(self._on_file_dropped)
        self._import_panel.import_clicked.connect(self._on_import_clicked)

        self._preview = PreviewWidget()
        self._preview.setMinimumHeight(300)

        left_layout.addWidget(self._import_panel)
        left_layout.addWidget(self._preview, stretch=1)

        # Right: Batch panel + Log viewer
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 4, 4, 4)
        right_layout.setSpacing(4)

        self._batch_panel = BatchPanel()
        self._log_viewer = LogViewer()

        right_layout.addWidget(self._batch_panel, stretch=1)
        right_layout.addWidget(self._log_viewer, stretch=1)

        top_splitter.addWidget(left_panel)
        top_splitter.addWidget(right_panel)
        top_splitter.setSizes([800, 400])

        # ── Bottom: Timeline ───────────────────────────────────────────
        self._timeline = TimelineWidget()
        self._timeline.setMinimumHeight(80)
        self._timeline.setMaximumHeight(200)
        self._timeline.frame_clicked.connect(self._on_timeline_frame_clicked)
        self._timeline.frame_decision_changed.connect(self._on_frame_decision_changed)

        # ── Main splitter: Top + Timeline ──────────────────────────────
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(self._timeline)
        main_splitter.setSizes([600, 120])

        main_layout.addWidget(main_splitter)

    def _setup_menu_bar(self) -> None:
        """Create the menu bar."""
        menubar = self.menuBar()

        # ── File menu ──────────────────────────────────────────────────
        file_menu = menubar.addMenu("&File")

        open_action = QAction("&Open Video...", self)
        open_action.setShortcut(QKeySequence(SHORTCUTS["open_file"]))
        open_action.triggered.connect(self._on_import_clicked)
        file_menu.addAction(open_action)

        # Recent files submenu
        self._recent_menu = file_menu.addMenu("Recent Files")
        self._update_recent_files_menu()

        file_menu.addSeparator()

        export_action = QAction("&Export...", self)
        export_action.setShortcut(QKeySequence(SHORTCUTS["export"]))
        export_action.triggered.connect(self._on_export)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        settings_action = QAction("&Settings...", self)
        settings_action.setShortcut(QKeySequence(SHORTCUTS["settings"]))
        settings_action.triggered.connect(self._on_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence(SHORTCUTS["quit"]))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # ── Edit menu ─────────────────────────────────────────────────
        edit_menu = menubar.addMenu("&Edit")

        undo_action = QAction("&Undo", self)
        undo_action.setShortcut(QKeySequence(SHORTCUTS["undo"]))
        undo_action.triggered.connect(self._on_undo)
        edit_menu.addAction(undo_action)

        redo_action = QAction("&Redo", self)
        redo_action.setShortcut(QKeySequence(SHORTCUTS["redo"]))
        redo_action.triggered.connect(self._on_redo)
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()

        keep_action = QAction("&Keep Selected Frame", self)
        keep_action.setShortcut(QKeySequence(SHORTCUTS["toggle_keep"]))
        keep_action.triggered.connect(lambda: self._set_selected_frame_decision(FrameDecision.KEEP))
        edit_menu.addAction(keep_action)

        remove_action = QAction("&Remove Selected Frame", self)
        remove_action.setShortcut(QKeySequence(SHORTCUTS["toggle_remove"]))
        remove_action.triggered.connect(lambda: self._set_selected_frame_decision(FrameDecision.REMOVE))
        edit_menu.addAction(remove_action)

        # ── Process menu ──────────────────────────────────────────────
        process_menu = menubar.addMenu("&Process")

        analyze_action = QAction("&Analyze Video", self)
        analyze_action.setShortcut(QKeySequence("Ctrl+R"))
        analyze_action.triggered.connect(self._on_analyze)
        process_menu.addAction(analyze_action)

        process_menu.addSeparator()

        stop_action = QAction("&Stop Analysis", self)
        stop_action.setShortcut(QKeySequence("Escape"))
        stop_action.triggered.connect(self._on_stop_analysis)
        process_menu.addAction(stop_action)

        # ── View menu ─────────────────────────────────────────────────
        view_menu = menubar.addMenu("&View")

        zoom_in_action = QAction("Zoom &In", self)
        zoom_in_action.setShortcut(QKeySequence(SHORTCUTS["zoom_in"]))
        zoom_in_action.triggered.connect(self._on_zoom_in)
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom &Out", self)
        zoom_out_action.setShortcut(QKeySequence(SHORTCUTS["zoom_out"]))
        zoom_out_action.triggered.connect(self._on_zoom_out)
        view_menu.addAction(zoom_out_action)

        # ── Help menu ────────────────────────────────────────────────
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About FrameFlow AI", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self) -> None:
        """Create the main toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(toolbar)

        self._btn_open = toolbar.addAction("📂 Open")
        self._btn_open.triggered.connect(self._on_import_clicked)

        toolbar.addSeparator()

        self._btn_analyze = toolbar.addAction("🔍 Analyze")
        self._btn_analyze.triggered.connect(self._on_analyze)

        self._btn_stop = toolbar.addAction("⏹ Stop")
        self._btn_stop.triggered.connect(self._on_stop_analysis)
        self._btn_stop.setEnabled(False)

        toolbar.addSeparator()

        self._btn_play = toolbar.addAction("▶ Play")
        self._btn_play.triggered.connect(self._on_play_pause)

        self._btn_prev = toolbar.addAction("◀ Prev")
        self._btn_prev.triggered.connect(self._on_frame_backward)

        self._btn_next = toolbar.addAction("▶ Next")
        self._btn_next.triggered.connect(self._on_frame_forward)

        toolbar.addSeparator()

        self._btn_export = toolbar.addAction("💾 Export")
        self._btn_export.triggered.connect(self._on_export)

        toolbar.addSeparator()

        self._btn_settings = toolbar.addAction("⚙ Settings")
        self._btn_settings.triggered.connect(self._on_settings)

    def _setup_status_bar(self) -> None:
        """Create the status bar with progress indicator."""
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._status_label = QLabel("Ready")
        self._status_bar.addWidget(self._status_label, stretch=1)

        self._gpu_label = QLabel("")
        self._status_bar.addPermanentWidget(self._gpu_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximumWidth(200)
        self._progress_bar.setMaximumHeight(16)
        self._progress_bar.hide()
        self._status_bar.addPermanentWidget(self._progress_bar)

        self._frame_label = QLabel("")
        self._status_bar.addPermanentWidget(self._frame_label)

    def _setup_shortcuts(self) -> None:
        """Configure additional keyboard shortcuts."""
        pass  # Shortcuts are already bound via menu actions

    # ══════════════════════════════════════════════════════════════════
    # Drag and Drop
    # ══════════════════════════════════════════════════════════════════

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if Path(url.toLocalFile()).suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if Path(file_path).suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
                self._load_video(file_path)
                break

    # ══════════════════════════════════════════════════════════════════
    # Video Loading
    # ══════════════════════════════════════════════════════════════════

    @Slot()
    def _on_import_clicked(self) -> None:
        """Open file dialog to import a video."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video", "", VIDEO_FILTER,
        )
        if path:
            self._load_video(path)

    @Slot(str)
    def _on_file_dropped(self, path: str) -> None:
        """Handle a file dropped on the import panel."""
        self._load_video(path)

    def _load_video(self, path: str) -> None:
        """Load a video file and update the UI."""
        try:
            self._status_label.setText(f"Loading {Path(path).name}...")
            QApplication.processEvents()

            video = self._loader.load(path)
            self._video = video
            self._extractor = FrameExtractor(video, self._cache)
            self._analyses.clear()
            self._undo_stack.clear()
            self._redo_stack.clear()

            # Update panels
            self._import_panel.set_video_info(video)
            self._preview.set_video(video, self._extractor)
            self._timeline.clear()

            # Add to recent files
            self._add_recent_file(path)

            self._status_label.setText(
                f"Loaded: {video.path.name} | "
                f"{video.metadata.resolution_str} | "
                f"{video.metadata.fps_str} | "
                f"{video.frame_count:,} frames"
            )
            logger.info("Video loaded in UI: %s", path)

        except VideoLoadError as exc:
            QMessageBox.warning(self, "Load Error", str(exc))
            self._status_label.setText("Load failed.")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Unexpected error: {exc}")
            logger.error("Video load error: %s", exc, exc_info=True)

    # ══════════════════════════════════════════════════════════════════
    # Analysis
    # ══════════════════════════════════════════════════════════════════

    @Slot()
    def _on_analyze(self) -> None:
        """Start frame analysis on the loaded video."""
        if self._video is None:
            QMessageBox.information(self, "No Video", "Please load a video first.")
            return

        if self._worker.is_running:
            return

        self._worker.is_running = True
        self._worker.should_cancel = False
        self._btn_analyze.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._progress_bar.show()
        self._progress_bar.setValue(0)
        self._analyses.clear()

        # Configure detector from settings
        detection_settings = self._settings.get_section("detection")
        config = DetectionConfig.from_settings(detection_settings)
        self._detector.config = config
        self._detector.reset()
        self._scene_detector.reset()

        # Attach AI scorer if available
        if config.enable_ai and self._ai_detector and self._ai_detector.available:
            self._detector.set_ai_scorer(self._ai_detector.compare_frames)

        # Stats tracking
        self._stats = ProcessingStats(
            video_path=str(self._video.path),
            total_frames=self._video.frame_count,
        )

        # Run analysis (using Qt timer for non-blocking processing)
        self._analysis_frame_index = 0
        self._analysis_prev_frame = None
        self._analysis_timer = QTimer(self)
        self._analysis_timer.timeout.connect(self._process_next_batch)
        self._analysis_timer.start(0)  # Process as fast as possible

        self._status_label.setText("Analyzing frames...")
        logger.info("Analysis started for %s", self._video.path.name)

    @Slot()
    def _process_next_batch(self) -> None:
        """Process a batch of frames (called by timer for non-blocking UI)."""
        if self._video is None or self._extractor is None:
            self._finish_analysis()
            return

        if self._worker.should_cancel:
            self._finish_analysis()
            return

        batch_size = 10  # Frames per UI tick
        total = self._video.frame_count

        for _ in range(batch_size):
            idx = self._analysis_frame_index
            if idx >= total:
                self._finish_analysis()
                return

            if idx == 0:
                # First frame is always kept
                analysis = self._detector.analyze_first_frame(0)
                self._analyses.append(analysis)
                frame = self._extractor.get_frame(0)
                self._analysis_prev_frame = frame
            else:
                curr_frame = self._extractor.get_frame(idx)
                if curr_frame is None or self._analysis_prev_frame is None:
                    self._analysis_frame_index += 1
                    continue

                analysis = self._detector.analyze_pair(
                    self._analysis_prev_frame, curr_frame, idx,
                )
                self._analyses.append(analysis)

                # Only update prev_frame if current frame is NOT a dead frame
                # This way we compare against the last unique frame
                if analysis.decision != FrameDecision.REMOVE:
                    self._analysis_prev_frame = curr_frame

                # Update stats
                if self._stats:
                    self._stats.frames_analyzed += 1
                    if analysis.decision == FrameDecision.KEEP:
                        self._stats.frames_kept += 1
                    elif analysis.decision == FrameDecision.REMOVE:
                        self._stats.frames_removed += 1
                    elif analysis.decision == FrameDecision.UNCERTAIN:
                        self._stats.frames_uncertain += 1
                    if analysis.is_scene_boundary:
                        self._stats.scene_boundaries += 1

            self._analysis_frame_index += 1

        # Update progress
        progress = self._analysis_frame_index / max(total, 1) * 100
        self._progress_bar.setValue(int(progress))
        self._status_label.setText(
            f"Analyzing: {self._analysis_frame_index:,}/{total:,} frames "
            f"({progress:.1f}%)"
        )
        self._timeline.set_analyses(self._analyses)

    def _finish_analysis(self) -> None:
        """Complete the analysis process."""
        if hasattr(self, "_analysis_timer"):
            self._analysis_timer.stop()

        self._worker.is_running = False
        self._btn_analyze.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._progress_bar.hide()

        if self._stats:
            self._stats.finalize()

        # Update timeline with final results
        self._timeline.set_analyses(self._analyses)

        # Status summary
        if self._stats and self._analyses:
            kept = sum(1 for a in self._analyses if a.decision in (FrameDecision.KEEP, FrameDecision.SCENE_BOUNDARY))
            removed = sum(1 for a in self._analyses if a.decision == FrameDecision.REMOVE)
            uncertain = sum(1 for a in self._analyses if a.decision == FrameDecision.UNCERTAIN)
            self._status_label.setText(
                f"Analysis complete: {kept:,} kept, {removed:,} removed, "
                f"{uncertain:,} uncertain | {self._stats.fps_processing:.1f} fps"
            )
            self._log_viewer.append_log(
                f"Analysis complete: {len(self._analyses):,} frames analyzed in "
                f"{self._stats.elapsed_seconds:.1f}s"
            )
        else:
            self._status_label.setText("Analysis cancelled.")

        logger.info("Analysis finished. %d frames analyzed.", len(self._analyses))

    @Slot()
    def _on_stop_analysis(self) -> None:
        """Cancel the running analysis."""
        self._worker.should_cancel = True

    # ══════════════════════════════════════════════════════════════════
    # Manual Override (Undo/Redo)
    # ══════════════════════════════════════════════════════════════════

    def _set_selected_frame_decision(self, decision: FrameDecision) -> None:
        """Set the decision for the currently selected frame."""
        idx = self._timeline.selected_frame_index
        if idx < 0 or idx >= len(self._analyses):
            return

        old_decision = self._analyses[idx].decision
        self._undo_stack.append((idx, old_decision))
        self._redo_stack.clear()
        self._analyses[idx].decision = decision
        self._timeline.update_frame(idx, decision)
        logger.debug("Frame %d: %s → %s (manual)", idx, old_decision.name, decision.name)

    @Slot()
    def _on_undo(self) -> None:
        if not self._undo_stack:
            return
        idx, old_decision = self._undo_stack.pop()
        current = self._analyses[idx].decision
        self._redo_stack.append((idx, current))
        self._analyses[idx].decision = old_decision
        self._timeline.update_frame(idx, old_decision)

    @Slot()
    def _on_redo(self) -> None:
        if not self._redo_stack:
            return
        idx, decision = self._redo_stack.pop()
        current = self._analyses[idx].decision
        self._undo_stack.append((idx, current))
        self._analyses[idx].decision = decision
        self._timeline.update_frame(idx, decision)

    @Slot(int, str)
    def _on_frame_decision_changed(self, index: int, decision_name: str) -> None:
        """Handle decision changes from timeline context menu."""
        if 0 <= index < len(self._analyses):
            old = self._analyses[index].decision
            new_decision = FrameDecision[decision_name]
            self._undo_stack.append((index, old))
            self._redo_stack.clear()
            self._analyses[index].decision = new_decision

    # ══════════════════════════════════════════════════════════════════
    # Timeline & Preview Interaction
    # ══════════════════════════════════════════════════════════════════

    @Slot(int)
    def _on_timeline_frame_clicked(self, index: int) -> None:
        """Handle clicking a frame on the timeline."""
        if self._extractor:
            self._preview.show_frame(index)
            if 0 <= index < len(self._analyses):
                a = self._analyses[index]
                self._frame_label.setText(
                    f"Frame {index} | Score: {a.similarity_percentage:.1f}% | "
                    f"{a.decision.name}"
                )

    @Slot()
    def _on_play_pause(self) -> None:
        self._preview.toggle_playback()

    @Slot()
    def _on_frame_forward(self) -> None:
        self._preview.step_forward()

    @Slot()
    def _on_frame_backward(self) -> None:
        self._preview.step_backward()

    @Slot()
    def _on_zoom_in(self) -> None:
        self._timeline.zoom_in()

    @Slot()
    def _on_zoom_out(self) -> None:
        self._timeline.zoom_out()

    # ══════════════════════════════════════════════════════════════════
    # Export
    # ══════════════════════════════════════════════════════════════════

    @Slot()
    def _on_export(self) -> None:
        """Open the export dialog."""
        if not self._analyses:
            QMessageBox.information(
                self, "No Analysis",
                "Please analyze a video before exporting.",
            )
            return

        dialog = ExportDialog(self._video, self._analyses, parent=self)
        if dialog.exec():
            config = dialog.get_config()
            self._run_export(config)

    def _run_export(self, config: ExportConfig) -> None:
        """Execute the export with progress tracking."""
        if self._video is None:
            return

        self._status_label.setText("Exporting...")
        self._progress_bar.show()
        self._progress_bar.setValue(0)
        QApplication.processEvents()

        exporter = Exporter(
            video=self._video,
            analyses=self._analyses,
            config=config,
            cache=self._cache,
            stats=self._stats,
        )

        def progress_cb(p: float, msg: str) -> None:
            self._progress_bar.setValue(int(p * 100))
            self._status_label.setText(msg)
            QApplication.processEvents()

        exporter.set_progress_callback(progress_cb)
        success = exporter.export()

        self._progress_bar.hide()
        if success:
            self._status_label.setText(f"Export complete: {config.output_path}")
            self._log_viewer.append_log(f"Exported to: {config.output_path}")
            QMessageBox.information(self, "Export Complete", f"Saved to:\n{config.output_path}")
        else:
            self._status_label.setText("Export failed.")
            QMessageBox.warning(self, "Export Failed", "Export encountered an error. Check logs.")

    # ══════════════════════════════════════════════════════════════════
    # Settings
    # ══════════════════════════════════════════════════════════════════

    @Slot()
    def _on_settings(self) -> None:
        dialog = SettingsDialog(parent=self)
        dialog.exec()

    # ══════════════════════════════════════════════════════════════════
    # AI Initialization
    # ══════════════════════════════════════════════════════════════════

    def _init_ai_detector(self) -> None:
        """Initialize the AI detector (deferred to avoid slow startup)."""
        try:
            gpu_enabled = self._settings.get("performance.gpu_enabled", True)
            self._ai_detector = AIDetector(gpu_enabled=gpu_enabled)
            if self._ai_detector.available:
                self._gpu_label.setText("🤖 AI Ready")
                logger.info("AI detector initialized successfully.")
            else:
                self._gpu_label.setText("🤖 AI Model Missing")
        except Exception as exc:
            logger.warning("AI detector initialization failed: %s", exc)
            self._gpu_label.setText("🤖 AI Unavailable")

    # ══════════════════════════════════════════════════════════════════
    # Recent Files
    # ══════════════════════════════════════════════════════════════════

    def _load_recent_files(self) -> list[str]:
        try:
            if RECENT_FILES_PATH.exists():
                with open(RECENT_FILES_PATH, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_recent_files(self) -> None:
        try:
            with open(RECENT_FILES_PATH, "w") as f:
                json.dump(self._recent_files, f, indent=2)
        except Exception:
            pass

    def _add_recent_file(self, path: str) -> None:
        if path in self._recent_files:
            self._recent_files.remove(path)
        self._recent_files.insert(0, path)
        self._recent_files = self._recent_files[:MAX_RECENT_FILES]
        self._save_recent_files()
        self._update_recent_files_menu()

    def _update_recent_files_menu(self) -> None:
        self._recent_menu.clear()
        for path in self._recent_files:
            action = QAction(Path(path).name, self)
            action.setToolTip(path)
            action.triggered.connect(lambda checked, p=path: self._load_video(p))
            self._recent_menu.addAction(action)
        if not self._recent_files:
            empty = QAction("(No recent files)", self)
            empty.setEnabled(False)
            self._recent_menu.addAction(empty)

    # ══════════════════════════════════════════════════════════════════
    # Session Auto-save / Window State
    # ══════════════════════════════════════════════════════════════════

    @Slot()
    def _auto_save_session(self) -> None:
        """Periodically save session state."""
        geom = self.geometry()
        self._settings.set("ui.window_geometry", [geom.x(), geom.y(), geom.width(), geom.height()])
        self._settings.set("ui.window_state", "maximized" if self.isMaximized() else "normal")

    def _restore_window_state(self) -> None:
        geom = self._settings.get("ui.window_geometry")
        if geom and isinstance(geom, list) and len(geom) == 4:
            x, y, w, h = geom
            # Validate the geometry is on a visible screen
            screen = QApplication.primaryScreen()
            if screen:
                avail = screen.availableGeometry()
                # Only restore if the saved position is within screen bounds
                if (avail.contains(x, y) and w > 100 and h > 100
                        and w <= avail.width() * 2 and h <= avail.height() * 2):
                    self.setGeometry(x, y, w, h)
                else:
                    logger.debug("Ignoring saved geometry (off-screen): %s", geom)
        state = self._settings.get("ui.window_state")
        if state == "maximized":
            self.showMaximized()

    # ══════════════════════════════════════════════════════════════════
    # About
    # ══════════════════════════════════════════════════════════════════

    @Slot()
    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            "About FrameFlow AI",
            "<h2>FrameFlow AI</h2>"
            "<p>Intelligent Dead Frame Remover for Video Editors</p>"
            "<p>Version 1.0.0</p>"
            "<p>Detects and removes duplicate animation frames using "
            "SSIM, pHash, Histogram, Optical Flow, and DINOv2 AI.</p>"
            "<hr>"
            "<p>Built with PySide6, OpenCV, and ONNX Runtime.</p>",
        )

    # ══════════════════════════════════════════════════════════════════
    # Close Event
    # ══════════════════════════════════════════════════════════════════

    def closeEvent(self, event: Any) -> None:
        """Clean up resources on close."""
        self._auto_save_session()

        if self._worker.is_running:
            self._worker.should_cancel = True

        if self._video:
            self._video.close()

        self._cache.invalidate()
        logger.info("Application closed.")
        event.accept()
