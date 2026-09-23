"""
Theme tokens and QSS Stylesheet definitions for SubtitleGo.
Supports both modern Dark theme (Slate / Sky) and clean Light theme (Zinc / Cobalt).
"""

DARK_THEME_PALETTE = {
    "bg_app": "#0b0f19",
    "bg_card": "#131b2e",
    "bg_card_elevated": "#1a243d",
    "bg_input": "#0b0f19",
    "bg_hover": "#1e2c4a",
    "bg_selected": "rgba(2, 132, 199, 0.28)",
    "border_subtle": "#1e293b",
    "border_default": "#293548",
    "border_hover": "#38bdf8",
    "border_focus": "#0284c7",
    "text_primary": "#f8fafc",
    "text_secondary": "#94a3b8",
    "text_muted": "#64748b",
    "accent_primary": "#0284c7",
    "accent_primary_hover": "#0ea5e9",
    "accent_cyan": "#38bdf8",
    "status_gpu_bg": "rgba(34, 197, 94, 0.15)",
    "status_gpu_border": "#166534",
    "status_gpu_text": "#22c55e",
    "status_cpu_bg": "rgba(245, 158, 11, 0.15)",
    "status_cpu_border": "#854d0e",
    "status_cpu_text": "#f59e0b",
    "status_err_bg": "rgba(239, 68, 68, 0.15)",
    "status_err_border": "#991b1b",
    "status_err_text": "#ef4444",
}

LIGHT_THEME_PALETTE = {
    "bg_app": "#f1f5f9",
    "bg_card": "#ffffff",
    "bg_card_elevated": "#f8fafc",
    "bg_input": "#f8fafc",
    "bg_hover": "#e2e8f0",
    "bg_selected": "rgba(2, 132, 199, 0.18)",
    "border_subtle": "#e2e8f0",
    "border_default": "#cbd5e1",
    "border_hover": "#0284c7",
    "border_focus": "#0284c7",
    "text_primary": "#0f172a",
    "text_secondary": "#475569",
    "text_muted": "#94a3b8",
    "accent_primary": "#0284c7",
    "accent_primary_hover": "#0369a1",
    "accent_cyan": "#0284c7",
    "status_gpu_bg": "rgba(34, 197, 94, 0.12)",
    "status_gpu_border": "#86efac",
    "status_gpu_text": "#15803d",
    "status_cpu_bg": "rgba(245, 158, 11, 0.12)",
    "status_cpu_border": "#fde047",
    "status_cpu_text": "#b45309",
    "status_err_bg": "rgba(239, 68, 68, 0.12)",
    "status_err_border": "#fca5a5",
    "status_err_text": "#b91c1c",
}


def build_qss(p: dict) -> str:
    return f"""
/* Global Base */
QWidget {{
    background-color: {p["bg_app"]};
    color: {p["text_primary"]};
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, "Helvetica Neue", sans-serif;
    font-size: 13px;
    selection-background-color: {p["accent_primary"]};
    selection-color: #ffffff;
}}

/* Main Window & Dialogs */
QMainWindow, QDialog {{
    background-color: {p["bg_app"]};
}}

/* Cards & Frames */
QFrame.cardFrame {{
    background-color: {p["bg_card"]};
    border: 1px solid {p["border_default"]};
    border-radius: 10px;
}}

QFrame.headerFrame {{
    background-color: {p["bg_card"]};
    border-bottom: 1px solid {p["border_default"]};
    padding: 10px 18px;
}}

QFrame.sidebarFrame {{
    background-color: {p["bg_card"]};
    border-right: 1px solid {p["border_default"]};
}}

QFrame.studioFrame {{
    background-color: {p["bg_card"]};
    border: 1px solid {p["border_default"]};
    border-radius: 10px;
}}

/* Brand Badges */
QLabel#brandBadge {{
    background-color: {p["accent_primary"]};
    color: #ffffff;
    font-weight: 700;
    font-size: 11px;
    padding: 4px 9px;
    border-radius: 5px;
    letter-spacing: 1px;
}}

QLabel#appTitle {{
    font-size: 16px;
    font-weight: 700;
    color: {p["text_primary"]};
}}

QLabel#appSubtitle {{
    font-size: 12px;
    color: {p["text_secondary"]};
}}

/* Status Badges */
QLabel#statusBadge {{
    background-color: {p["bg_input"]};
    border: 1px solid {p["border_default"]};
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 12px;
    color: {p["accent_cyan"]};
    font-weight: 500;
}}

QLabel#statusBadge.gpu {{
    background-color: {p["status_gpu_bg"]};
    color: {p["status_gpu_text"]};
    border: 1px solid {p["status_gpu_border"]};
    border-radius: 6px;
    font-weight: 600;
}}

QLabel#statusBadge.cpu {{
    background-color: {p["status_cpu_bg"]};
    color: {p["status_cpu_text"]};
    border: 1px solid {p["status_cpu_border"]};
    border-radius: 6px;
    font-weight: 600;
}}

/* Buttons */
QPushButton {{
    background-color: {p["bg_card_elevated"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border_default"]};
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
    font-size: 12px;
}}

QPushButton:hover {{
    background-color: {p["bg_hover"]};
    border-color: {p["border_hover"]};
}}

QPushButton:pressed {{
    background-color: {p["bg_input"]};
}}

QPushButton:disabled {{
    background-color: {p["bg_input"]};
    color: {p["text_muted"]};
    border-color: {p["border_subtle"]};
}}

/* Button Variants */
QPushButton.btnPrimary {{
    background-color: {p["accent_primary"]};
    color: #ffffff;
    border: 1px solid {p["accent_primary"]};
    font-weight: 600;
    font-size: 13px;
    padding: 8px 16px;
    border-radius: 6px;
}}

QPushButton.btnPrimary:hover {{
    background-color: {p["accent_primary_hover"]};
    border-color: {p["accent_cyan"]};
}}

QPushButton.btnPrimary:pressed {{
    background-color: #0369a1;
}}

QPushButton.btnOutline {{
    background-color: transparent;
    color: {p["accent_primary"]};
    border: 1px solid {p["accent_primary"]};
    font-weight: 600;
}}

QPushButton.btnOutline:hover {{
    background-color: {p["bg_selected"]};
}}

QPushButton.btnSecondary {{
    background-color: {p["bg_card_elevated"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border_default"]};
}}

QPushButton.btnSecondary:hover {{
    background-color: {p["bg_hover"]};
    border-color: {p["border_hover"]};
}}

QPushButton.btnDanger {{
    background-color: {p["status_err_bg"]};
    color: {p["status_err_text"]};
    border: 1px solid {p["status_err_border"]};
    font-weight: 600;
}}

QPushButton.btnDanger:hover {{
    background-color: {p["status_err_text"]};
    color: #ffffff;
}}

QPushButton.btnSuccess {{
    background-color: {p["status_gpu_bg"]};
    color: {p["status_gpu_text"]};
    border: 1px solid {p["status_gpu_border"]};
    font-weight: 600;
}}

QPushButton.btnSuccess:hover {{
    background-color: {p["status_gpu_text"]};
    color: #ffffff;
}}

QPushButton.btnGhost {{
    background-color: transparent;
    border: 1px solid transparent;
    color: {p["text_secondary"]};
    padding: 5px 10px;
    border-radius: 6px;
}}

QPushButton.btnGhost:hover {{
    background-color: {p["bg_hover"]};
    color: {p["text_primary"]};
    border-color: {p["border_default"]};
}}

QPushButton.btnPill {{
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11px;
}}

/* Text Inputs, Combobox, Spinbox */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {{
    background-color: {p["bg_input"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border_default"]};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {p["border_focus"]};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid {p["border_default"]};
}}

QComboBox QAbstractItemView {{
    background-color: {p["bg_card"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border_default"]};
    selection-background-color: {p["accent_primary"]};
    selection-color: #ffffff;
}}

/* CheckBox */
QCheckBox {{
    color: {p["text_primary"]};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {p["border_default"]};
    background-color: {p["bg_input"]};
}}

QCheckBox::indicator:checked {{
    background-color: {p["accent_primary"]};
    border-color: {p["accent_cyan"]};
}}

/* Progress Bar */
QProgressBar {{
    background-color: {p["bg_input"]};
    border: 1px solid {p["border_default"]};
    border-radius: 4px;
    text-align: center;
    color: {p["text_primary"]};
    font-size: 11px;
    height: 12px;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p["accent_primary"]}, stop:1 {p["accent_cyan"]});
    border-radius: 3px;
}}

/* Tab Widget */
QTabWidget::pane {{
    border: 1px solid {p["border_default"]};
    background-color: {p["bg_card"]};
    border-radius: 8px;
}}

QTabBar::tab {{
    background-color: {p["bg_input"]};
    color: {p["text_secondary"]};
    border: 1px solid {p["border_default"]};
    border-bottom: none;
    padding: 7px 16px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 500;
    font-size: 12px;
}}

QTabBar::tab:selected {{
    background-color: {p["bg_card"]};
    color: {p["accent_cyan"]};
    border-bottom: 2px solid {p["accent_cyan"]};
    font-weight: 600;
}}

QTabBar::tab:hover:!selected {{
    background-color: {p["bg_hover"]};
    color: {p["text_primary"]};
}}

/* Splitters */
QSplitter::handle {{
    background-color: {p["border_subtle"]};
}}

QSplitter::handle:hover {{
    background-color: {p["accent_primary"]};
}}

QSplitter::handle:horizontal {{
    width: 5px;
}}

QSplitter::handle:vertical {{
    height: 5px;
}}

/* Scroll Areas & Scrollbars */
QScrollArea {{
    background-color: transparent;
    border: none;
}}

QScrollBar:vertical {{
    background: {p["bg_input"]};
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: {p["border_default"]};
    min-height: 20px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {p["border_hover"]};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    background: none;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background: {p["bg_input"]};
    height: 8px;
    margin: 0px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal {{
    background: {p["border_default"]};
    min-width: 20px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {p["border_hover"]};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
    background: none;
}}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}

/* Group Box */
QGroupBox {{
    border: 1px solid {p["border_default"]};
    border-radius: 8px;
    margin-top: 22px;
    padding-top: 14px;
    font-weight: 600;
    color: {p["text_secondary"]};
    font-size: 12px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: 2px;
    padding: 0 6px;
    background-color: {p["bg_card"]};
}}

QGroupBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {p["border_default"]};
    background-color: {p["bg_input"]};
}}

QGroupBox::indicator:checked {{
    background-color: {p["accent_primary"]};
    border-color: {p["accent_cyan"]};
}}

/* Drop Zone Frame */
QFrame#dropZone {{
    background-color: {p["bg_input"]};
    border: 2px dashed {p["border_default"]};
    border-radius: 8px;
    padding: 16px;
}}

QFrame#dropZone:hover {{
    border-color: {p["accent_cyan"]};
    background-color: {p["bg_hover"]};
}}

/* Tables & Lists */
QTableWidget, QListWidget {{
    background-color: {p["bg_input"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border_default"]};
    border-radius: 6px;
    gridline-color: {p["border_subtle"]};
}}

QTableWidget::item {{
    padding: 5px 8px;
    border-bottom: 1px solid {p["border_subtle"]};
}}

QTableWidget::item:selected {{
    background-color: {p["bg_selected"]};
    color: {p["text_primary"]};
}}

QHeaderView::section {{
    background-color: {p["bg_card_elevated"]};
    color: {p["text_secondary"]};
    border: none;
    border-bottom: 1px solid {p["border_default"]};
    border-right: 1px solid {p["border_subtle"]};
    padding: 6px 8px;
    font-weight: 600;
    font-size: 11px;
}}

/* Sliders */
QSlider::groove:horizontal {{
    height: 5px;
    background: {p["border_default"]};
    border-radius: 2px;
}}

QSlider::sub-page:horizontal {{
    background: {p["accent_primary"]};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: {p["accent_cyan"]};
    width: 13px;
    margin-top: -4px;
    margin-bottom: -4px;
    border-radius: 6px;
}}

QSlider::handle:horizontal:hover {{
    background: {p["accent_primary_hover"]};
}}

/* Menu */
QMenu {{
    background-color: {p["bg_card"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border_default"]};
    border-radius: 6px;
    padding: 4px;
}}

QMenu::item {{
    padding: 6px 20px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {p["accent_primary"]};
    color: #ffffff;
}}

/* Tooltips */
QToolTip {{
    background-color: {p["bg_card_elevated"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border_default"]};
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 12px;
}}
"""


DARK_THEME_QSS = build_qss(DARK_THEME_PALETTE)
LIGHT_THEME_QSS = build_qss(LIGHT_THEME_PALETTE)


def get_theme_qss(theme: str = "dark") -> str:
    """Returns the QSS stylesheet for the given theme ('dark' or 'light')."""
    if theme.lower() == "light":
        return LIGHT_THEME_QSS
    return DARK_THEME_QSS


def get_theme_palette(theme: str = "dark") -> dict:
    """Returns the color token dictionary for the given theme ('dark' or 'light')."""
    if theme.lower() == "light":
        return LIGHT_THEME_PALETTE
    return DARK_THEME_PALETTE

