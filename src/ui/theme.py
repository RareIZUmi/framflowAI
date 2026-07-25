"""
Professional dark theme for FrameFlow AI.

Inspired by DaVinci Resolve and Adobe Premiere Pro.
Provides a complete QSS stylesheet and QPalette for PySide6.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication


# ---------------------------------------------------------------------------
# Color Palette
# ---------------------------------------------------------------------------

class Colors:
    """Application color palette — DaVinci Resolve inspired dark theme."""

    # Backgrounds
    BG_DARKEST = "#0D0D0D"
    BG_DARKER = "#141414"
    BG_DARK = "#1A1A1A"
    BG_MEDIUM = "#242424"
    BG_LIGHT = "#2D2D2D"
    BG_LIGHTER = "#383838"
    BG_HOVER = "#404040"

    # Foregrounds
    FG_PRIMARY = "#E0E0E0"
    FG_SECONDARY = "#A0A0A0"
    FG_DISABLED = "#5A5A5A"
    FG_BRIGHT = "#FFFFFF"

    # Accents
    ACCENT_PRIMARY = "#00BCD4"     # Teal/Cyan
    ACCENT_HOVER = "#26C6DA"
    ACCENT_PRESSED = "#0097A7"
    ACCENT_SECONDARY = "#7C4DFF"   # Purple

    # Status colors
    STATUS_GREEN = "#4CAF50"
    STATUS_RED = "#F44336"
    STATUS_YELLOW = "#FFC107"
    STATUS_BLUE = "#2196F3"
    STATUS_ORANGE = "#FF9800"

    # Timeline frame colors
    FRAME_KEEP = "#4CAF50"
    FRAME_REMOVE = "#F44336"
    FRAME_UNCERTAIN = "#FFC107"
    FRAME_SCENE_BOUNDARY = "#2196F3"

    # Borders
    BORDER_DARK = "#1A1A1A"
    BORDER_MEDIUM = "#333333"
    BORDER_LIGHT = "#444444"
    BORDER_FOCUS = "#00BCD4"

    # Scrollbar
    SCROLLBAR_BG = "#1A1A1A"
    SCROLLBAR_HANDLE = "#444444"
    SCROLLBAR_HOVER = "#555555"

    # Progress bar
    PROGRESS_BG = "#1A1A1A"
    PROGRESS_FILL = "#00BCD4"


# ---------------------------------------------------------------------------
# QSS Stylesheet
# ---------------------------------------------------------------------------

STYLESHEET = f"""
/* ═══════════════════════════════════════════════════════════════════
   FrameFlow AI — Professional Dark Theme
   ═══════════════════════════════════════════════════════════════════ */

/* ── Global ────────────────────────────────────────────────────── */
QWidget {{
    background-color: {Colors.BG_DARK};
    color: {Colors.FG_PRIMARY};
    font-family: "Segoe UI", "Inter", "Roboto", sans-serif;
    font-size: 13px;
    selection-background-color: {Colors.ACCENT_PRIMARY};
    selection-color: {Colors.FG_BRIGHT};
}}

QMainWindow {{
    background-color: {Colors.BG_DARKEST};
}}

/* ── Menu Bar ──────────────────────────────────────────────────── */
QMenuBar {{
    background-color: {Colors.BG_DARKER};
    color: {Colors.FG_PRIMARY};
    border-bottom: 1px solid {Colors.BORDER_DARK};
    padding: 2px 0px;
    spacing: 0px;
}}

QMenuBar::item {{
    padding: 6px 12px;
    border-radius: 3px;
    margin: 1px 2px;
}}

QMenuBar::item:selected {{
    background-color: {Colors.BG_HOVER};
}}

QMenu {{
    background-color: {Colors.BG_MEDIUM};
    border: 1px solid {Colors.BORDER_MEDIUM};
    border-radius: 4px;
    padding: 4px;
}}

QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 3px;
}}

QMenu::item:selected {{
    background-color: {Colors.ACCENT_PRIMARY};
    color: {Colors.FG_BRIGHT};
}}

QMenu::separator {{
    height: 1px;
    background: {Colors.BORDER_MEDIUM};
    margin: 4px 8px;
}}

/* ── Toolbar ───────────────────────────────────────────────────── */
QToolBar {{
    background-color: {Colors.BG_DARKER};
    border: none;
    border-bottom: 1px solid {Colors.BORDER_DARK};
    padding: 4px;
    spacing: 4px;
}}

QToolButton {{
    background-color: transparent;
    color: {Colors.FG_PRIMARY};
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 6px 10px;
    font-weight: 500;
}}

QToolButton:hover {{
    background-color: {Colors.BG_HOVER};
    border-color: {Colors.BORDER_LIGHT};
}}

QToolButton:pressed {{
    background-color: {Colors.ACCENT_PRESSED};
}}

QToolButton:checked {{
    background-color: {Colors.ACCENT_PRIMARY};
    color: {Colors.FG_BRIGHT};
}}

/* ── Push Button ───────────────────────────────────────────────── */
QPushButton {{
    background-color: {Colors.BG_LIGHTER};
    color: {Colors.FG_PRIMARY};
    border: 1px solid {Colors.BORDER_MEDIUM};
    border-radius: 5px;
    padding: 7px 18px;
    font-weight: 500;
    min-height: 20px;
}}

QPushButton:hover {{
    background-color: {Colors.BG_HOVER};
    border-color: {Colors.BORDER_LIGHT};
}}

QPushButton:pressed {{
    background-color: {Colors.BG_MEDIUM};
}}

QPushButton:disabled {{
    background-color: {Colors.BG_DARK};
    color: {Colors.FG_DISABLED};
    border-color: {Colors.BORDER_DARK};
}}

QPushButton#primaryButton {{
    background-color: {Colors.ACCENT_PRIMARY};
    color: {Colors.FG_BRIGHT};
    border: none;
    font-weight: 600;
}}

QPushButton#primaryButton:hover {{
    background-color: {Colors.ACCENT_HOVER};
}}

QPushButton#primaryButton:pressed {{
    background-color: {Colors.ACCENT_PRESSED};
}}

QPushButton#dangerButton {{
    background-color: {Colors.STATUS_RED};
    color: {Colors.FG_BRIGHT};
    border: none;
}}

/* ── Labels ────────────────────────────────────────────────────── */
QLabel {{
    color: {Colors.FG_PRIMARY};
    background-color: transparent;
}}

QLabel#heading {{
    font-size: 16px;
    font-weight: 600;
    color: {Colors.FG_BRIGHT};
}}

QLabel#subtitle {{
    font-size: 12px;
    color: {Colors.FG_SECONDARY};
}}

/* ── Line Edit / Text Input ────────────────────────────────────── */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {Colors.BG_MEDIUM};
    color: {Colors.FG_PRIMARY};
    border: 1px solid {Colors.BORDER_MEDIUM};
    border-radius: 4px;
    padding: 6px 10px;
    min-height: 20px;
}}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {Colors.BORDER_FOCUS};
}}

/* ── Combo Box ─────────────────────────────────────────────────── */
QComboBox {{
    background-color: {Colors.BG_MEDIUM};
    color: {Colors.FG_PRIMARY};
    border: 1px solid {Colors.BORDER_MEDIUM};
    border-radius: 4px;
    padding: 6px 10px;
    min-height: 20px;
}}

QComboBox:hover {{
    border-color: {Colors.BORDER_LIGHT};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {Colors.BG_MEDIUM};
    border: 1px solid {Colors.BORDER_MEDIUM};
    selection-background-color: {Colors.ACCENT_PRIMARY};
    selection-color: {Colors.FG_BRIGHT};
    outline: none;
}}

/* ── Slider ────────────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    border: none;
    height: 4px;
    background: {Colors.BG_LIGHTER};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: {Colors.ACCENT_PRIMARY};
    border: none;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}

QSlider::handle:horizontal:hover {{
    background: {Colors.ACCENT_HOVER};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}

QSlider::sub-page:horizontal {{
    background: {Colors.ACCENT_PRIMARY};
    border-radius: 2px;
}}

/* ── Progress Bar ──────────────────────────────────────────────── */
QProgressBar {{
    background-color: {Colors.PROGRESS_BG};
    border: none;
    border-radius: 4px;
    text-align: center;
    color: {Colors.FG_PRIMARY};
    height: 8px;
    font-size: 11px;
}}

QProgressBar::chunk {{
    background-color: {Colors.PROGRESS_FILL};
    border-radius: 4px;
}}

/* ── Tab Widget ────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {Colors.BORDER_MEDIUM};
    border-radius: 4px;
    background-color: {Colors.BG_DARK};
}}

QTabBar::tab {{
    background-color: {Colors.BG_MEDIUM};
    color: {Colors.FG_SECONDARY};
    border: 1px solid {Colors.BORDER_MEDIUM};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 8px 16px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: {Colors.BG_DARK};
    color: {Colors.ACCENT_PRIMARY};
    border-bottom: 2px solid {Colors.ACCENT_PRIMARY};
}}

QTabBar::tab:hover:!selected {{
    background-color: {Colors.BG_LIGHT};
    color: {Colors.FG_PRIMARY};
}}

/* ── Scroll Bar ────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: {Colors.SCROLLBAR_BG};
    width: 10px;
    margin: 0;
    border-radius: 5px;
}}

QScrollBar::handle:vertical {{
    background: {Colors.SCROLLBAR_HANDLE};
    min-height: 30px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical:hover {{
    background: {Colors.SCROLLBAR_HOVER};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background: {Colors.SCROLLBAR_BG};
    height: 10px;
    margin: 0;
    border-radius: 5px;
}}

QScrollBar::handle:horizontal {{
    background: {Colors.SCROLLBAR_HANDLE};
    min-width: 30px;
    border-radius: 5px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {Colors.SCROLLBAR_HOVER};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ── Table / List View ─────────────────────────────────────────── */
QTableWidget, QListWidget, QTreeWidget {{
    background-color: {Colors.BG_MEDIUM};
    border: 1px solid {Colors.BORDER_MEDIUM};
    border-radius: 4px;
    gridline-color: {Colors.BORDER_DARK};
    outline: none;
}}

QTableWidget::item, QListWidget::item, QTreeWidget::item {{
    padding: 4px 8px;
}}

QTableWidget::item:selected, QListWidget::item:selected, QTreeWidget::item:selected {{
    background-color: {Colors.ACCENT_PRIMARY};
    color: {Colors.FG_BRIGHT};
}}

QHeaderView::section {{
    background-color: {Colors.BG_LIGHTER};
    color: {Colors.FG_PRIMARY};
    border: none;
    border-right: 1px solid {Colors.BORDER_DARK};
    border-bottom: 1px solid {Colors.BORDER_DARK};
    padding: 6px 8px;
    font-weight: 600;
}}

/* ── Group Box ─────────────────────────────────────────────────── */
QGroupBox {{
    border: 1px solid {Colors.BORDER_MEDIUM};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    padding: 0 8px;
    color: {Colors.ACCENT_PRIMARY};
}}

/* ── Check Box / Radio Button ──────────────────────────────────── */
QCheckBox, QRadioButton {{
    color: {Colors.FG_PRIMARY};
    spacing: 8px;
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 2px solid {Colors.BORDER_LIGHT};
    background: {Colors.BG_MEDIUM};
}}

QCheckBox::indicator {{
    border-radius: 3px;
}}

QRadioButton::indicator {{
    border-radius: 10px;
}}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {Colors.ACCENT_PRIMARY};
    border-color: {Colors.ACCENT_PRIMARY};
}}

/* ── Splitter ──────────────────────────────────────────────────── */
QSplitter::handle {{
    background-color: {Colors.BORDER_DARK};
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}

/* ── Status Bar ────────────────────────────────────────────────── */
QStatusBar {{
    background-color: {Colors.BG_DARKER};
    color: {Colors.FG_SECONDARY};
    border-top: 1px solid {Colors.BORDER_DARK};
    font-size: 12px;
}}

QStatusBar::item {{
    border: none;
}}

/* ── Dock Widget ───────────────────────────────────────────────── */
QDockWidget {{
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
    border: 1px solid {Colors.BORDER_DARK};
}}

QDockWidget::title {{
    background-color: {Colors.BG_DARKER};
    padding: 6px 10px;
    font-weight: 600;
    text-align: left;
    border-bottom: 1px solid {Colors.BORDER_DARK};
}}

/* ── Tooltip ───────────────────────────────────────────────────── */
QToolTip {{
    background-color: {Colors.BG_LIGHTER};
    color: {Colors.FG_BRIGHT};
    border: 1px solid {Colors.BORDER_LIGHT};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}}

/* ── Dialog ────────────────────────────────────────────────────── */
QDialog {{
    background-color: {Colors.BG_DARK};
}}
"""


# ---------------------------------------------------------------------------
# Theme Application
# ---------------------------------------------------------------------------

def apply_theme(app: QApplication) -> None:
    """Apply the dark theme to the entire application."""
    # Set stylesheet
    app.setStyleSheet(STYLESHEET)

    # Set palette for any widgets not covered by QSS
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(Colors.BG_DARK))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(Colors.FG_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(Colors.BG_MEDIUM))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(Colors.BG_LIGHT))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(Colors.BG_LIGHTER))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(Colors.FG_BRIGHT))
    palette.setColor(QPalette.ColorRole.Text, QColor(Colors.FG_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(Colors.BG_LIGHTER))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(Colors.FG_PRIMARY))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(Colors.FG_BRIGHT))
    palette.setColor(QPalette.ColorRole.Link, QColor(Colors.ACCENT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(Colors.ACCENT_PRIMARY))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(Colors.FG_BRIGHT))

    # Disabled colors
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(Colors.FG_DISABLED))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(Colors.FG_DISABLED))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(Colors.FG_DISABLED))

    app.setPalette(palette)
