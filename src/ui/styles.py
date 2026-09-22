"""
QSS Stylesheet for SubtitleGo
Dark theme matching #0f172a / #1e293b with #38bdf8 accents.
"""

DARK_THEME_QSS = """
/* Global Base */
QWidget {
    background-color: #0f172a;
    color: #f8fafc;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, "Helvetica Neue", sans-serif;
    font-size: 13px;
    selection-background-color: #0284c7;
    selection-color: #ffffff;
}

/* Main Window & Dialogs */
QMainWindow, QDialog {
    background-color: #0f172a;
}

/* Cards & Frames */
QFrame.cardFrame {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
}

QFrame.headerFrame {
    background-color: #1e293b;
    border-bottom: 1px solid #334155;
    padding: 12px 20px;
}

/* Brand Badge */
QLabel#brandBadge {
    background-color: #0284c7;
    color: #ffffff;
    font-weight: 700;
    font-size: 11px;
    padding: 4px 8px;
    border-radius: 4px;
    letter-spacing: 1px;
}

QLabel#appTitle {
    font-size: 17px;
    font-weight: 600;
    color: #f8fafc;
}

QLabel#appSubtitle {
    font-size: 12px;
    color: #94a3b8;
}

/* Status Badges */
QLabel#statusBadge {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 12px;
    color: #38bdf8;
    font-weight: 500;
}

QLabel#statusBadge.gpu {
    color: #22c55e;
    border-color: #166534;
}

QLabel#statusBadge.cpu {
    color: #f59e0b;
    border-color: #854d0e;
}

/* Buttons */
QPushButton {
    background-color: #334155;
    color: #f8fafc;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #475569;
    border-color: #64748b;
}

QPushButton:pressed {
    background-color: #1e293b;
}

QPushButton:disabled {
    background-color: #1e293b;
    color: #64748b;
    border-color: #334155;
}

/* Primary Action Buttons */
QPushButton.btnPrimary {
    background-color: #0284c7;
    color: #ffffff;
    border: 1px solid #0369a1;
    font-weight: 600;
    font-size: 14px;
    padding: 10px 18px;
    border-radius: 8px;
}

QPushButton.btnPrimary:hover {
    background-color: #0ea5e9;
    border-color: #38bdf8;
}

QPushButton.btnPrimary:pressed {
    background-color: #0369a1;
}

QPushButton.btnPrimary:disabled {
    background-color: #1e293b;
    color: #64748b;
    border-color: #334155;
}

/* Outline Buttons */
QPushButton.btnOutline {
    background-color: transparent;
    color: #38bdf8;
    border: 1px solid #0284c7;
}

QPushButton.btnOutline:hover {
    background-color: rgba(56, 189, 248, 0.1);
    border-color: #38bdf8;
}

/* Text Inputs, Combobox, Spinbox */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {
    background-color: #0f172a;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #38bdf8;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid #334155;
}

QComboBox QAbstractItemView {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    selection-background-color: #0284c7;
    selection-color: #ffffff;
}

/* CheckBox */
QCheckBox {
    color: #f8fafc;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #475569;
    background-color: #0f172a;
}

QCheckBox::indicator:checked {
    background-color: #0284c7;
    border-color: #38bdf8;
}

/* Progress Bar */
QProgressBar {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 4px;
    text-align: center;
    color: #f8fafc;
    font-size: 11px;
    height: 14px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
    border-radius: 3px;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #334155;
    border-top: none;
    background-color: #1e293b;
    border-bottom-left-radius: 8px;
    border-bottom-right-radius: 8px;
}

QTabBar::tab {
    background-color: #0f172a;
    color: #94a3b8;
    border: 1px solid #334155;
    border-bottom: none;
    padding: 8px 18px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 500;
}

QTabBar::tab:selected {
    background-color: #1e293b;
    color: #38bdf8;
    border-bottom: 2px solid #38bdf8;
    font-weight: 600;
}

QTabBar::tab:hover:!selected {
    background-color: #1a2333;
    color: #f8fafc;
}

/* Splitters */
QSplitter::handle {
    background-color: #1e293b;
}

QSplitter::handle:hover {
    background-color: #0284c7;
}

QSplitter::handle:horizontal {
    width: 6px;
}

QSplitter::handle:vertical {
    height: 6px;
}

/* Scroll Areas */
QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

/* ScrollBars */
QScrollBar:vertical {
    background: #0f172a;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #334155;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #475569;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    background: none;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QScrollBar:horizontal {
    background: #0f172a;
    height: 8px;
    margin: 0px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background: #334155;
    min-width: 20px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: #475569;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    background: none;
}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}

/* Group Box */
QGroupBox {
    border: 1px solid #334155;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 14px;
    font-weight: 600;
    color: #94a3b8;
    font-size: 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    background-color: #1e293b;
}

QGroupBox::indicator {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid #475569;
    background-color: #0f172a;
}

QGroupBox::indicator:checked {
    background-color: #0284c7;
    border-color: #38bdf8;
}

/* Drop Zone Frame */
QFrame#dropZone {
    background-color: #0f172a;
    border: 2px dashed #334155;
    border-radius: 8px;
    padding: 20px;
}

QFrame#dropZone:hover {
    border-color: #38bdf8;
    background-color: #131d33;
}

/* Cue List & Table */
QTableWidget, QListWidget {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    gridline-color: #1e293b;
}

QTableWidget::item {
    padding: 6px;
    border-bottom: 1px solid #1e293b;
}

QTableWidget::item:selected {
    background-color: rgba(2, 132, 199, 0.25);
    color: #f8fafc;
}

QHeaderView::section {
    background-color: #1e293b;
    color: #94a3b8;
    border: none;
    border-bottom: 1px solid #334155;
    padding: 6px 10px;
    font-weight: 600;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background: #334155;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #0284c7;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #38bdf8;
    width: 14px;
    margin-top: -4px;
    margin-bottom: -4px;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #7dd3fc;
}

/* Tooltips */
QToolTip {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #475569;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 12px;
}
"""
