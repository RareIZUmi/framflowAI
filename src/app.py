"""
QApplication setup and lifecycle management for FrameFlow AI.

Initializes the Qt application, applies the theme, configures
the logger, and creates the main window with a splash screen.
"""

from __future__ import annotations

import ctypes
import os
import sys
from typing import NoReturn

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from src.utils.constants import APP_NAME, APP_VERSION, ORG_DOMAIN, ORG_NAME


def _center_on_screen(window) -> None:
    """Center the window on the primary screen."""
    screen = QApplication.primaryScreen()
    if screen:
        avail = screen.availableGeometry()
        w = min(window.width(), avail.width())
        h = min(window.height(), avail.height())
        x = avail.x() + (avail.width() - w) // 2
        y = avail.y() + (avail.height() - h) // 2
        window.setGeometry(x, y, w, h)


def _force_foreground(window) -> None:
    """Use Win32 API to force the window to the foreground on Windows."""
    try:
        hwnd = int(window.winId())
        user32 = ctypes.windll.user32
        # Allow our process to set foreground window
        user32.AllowSetForegroundWindow(os.getpid())
        user32.ShowWindow(hwnd, 5)   # SW_SHOW
        user32.ShowWindow(hwnd, 9)   # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
    except Exception:
        pass


def create_splash(app: QApplication) -> QSplashScreen:
    """Create and show a splash screen during startup."""
    pixmap = QPixmap(480, 280)
    pixmap.fill(QColor("#0D0D0D"))

    from PySide6.QtGui import QLinearGradient, QPainter, QPen

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    gradient = QLinearGradient(0, 0, 480, 0)
    gradient.setColorAt(0.0, QColor("#00BCD4"))
    gradient.setColorAt(1.0, QColor("#7C4DFF"))
    painter.fillRect(0, 0, 480, 4, gradient)

    font_title = QFont("Segoe UI", 28, QFont.Weight.Bold)
    painter.setFont(font_title)
    painter.setPen(QPen(QColor("#E0E0E0")))
    painter.drawText(40, 100, "FrameFlow AI")

    font_sub = QFont("Segoe UI", 12)
    painter.setFont(font_sub)
    painter.setPen(QPen(QColor("#00BCD4")))
    painter.drawText(40, 130, "Intelligent Dead Frame Remover")

    font_ver = QFont("Segoe UI", 10)
    painter.setFont(font_ver)
    painter.setPen(QPen(QColor("#666666")))
    painter.drawText(40, 220, f"v{APP_VERSION}")
    painter.drawText(40, 240, "Loading...")

    painter.end()

    splash = QSplashScreen(pixmap)
    splash.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
    splash.show()
    app.processEvents()
    return splash


def run_app() -> NoReturn:
    """Initialize and run the FrameFlow AI application."""
    # ── Enable High-DPI support ────────────────────────────────────────
    try:
        # Tell Windows this process is DPI-aware (per-monitor v2)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    # ── Setup logging first ────────────────────────────────────────────
    from src.utils.logger import setup_logger

    setup_logger()

    # ── Create QApplication ────────────────────────────────────────────
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Prevent quit when splash closes
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORG_NAME)
    app.setOrganizationDomain(ORG_DOMAIN)

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # ── Show splash ────────────────────────────────────────────────────
    splash = create_splash(app)

    # ── Apply theme ────────────────────────────────────────────────────
    splash.showMessage("Applying theme...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft, QColor("#666"))
    app.processEvents()

    from src.ui.theme import apply_theme

    apply_theme(app)

    # ── Check FFmpeg ───────────────────────────────────────────────────
    splash.showMessage("Checking FFmpeg...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft, QColor("#666"))
    app.processEvents()

    from src.utils.ffmpeg import get_ffmpeg

    ffmpeg = get_ffmpeg()
    if not ffmpeg.available:
        from PySide6.QtWidgets import QMessageBox

        splash.close()
        QMessageBox.warning(
            None,
            "FFmpeg Not Found",
            "FFmpeg was not found on your system.\n\n"
            "Please install FFmpeg and ensure it is on your PATH.\n"
            "Download: https://ffmpeg.org/download.html\n\n"
            "The application will start but export features will be disabled.",
        )

    # ── Create main window ─────────────────────────────────────────────
    splash.showMessage("Initializing...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft, QColor("#666"))
    app.processEvents()

    from src.ui.main_window import MainWindow

    window = MainWindow()

    # Close splash using the proper Qt transition
    splash.finish(window)
    app.processEvents()

    # Re-enable normal quit behavior
    app.setQuitOnLastWindowClosed(True)

    # Force center on screen (ignore any saved geometry for reliability)
    _center_on_screen(window)

    # Show the window
    window.show()
    app.processEvents()

    # Force to foreground via Win32
    _force_foreground(window)

    # ── Run event loop ─────────────────────────────────────────────────
    sys.exit(app.exec())
