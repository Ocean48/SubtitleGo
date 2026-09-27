import os
import sys
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QFrame, QScrollArea,
    QTabWidget, QApplication, QMessageBox, QLineEdit
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QTextCursor, QFont

from ...core.logger import (
    get_log_file_path,
    get_recent_logs,
    clear_recent_logs,
    open_log_file,
    open_log_directory,
    add_log_listener,
    remove_log_listener
)
from ...core.runtime_manager import diagnose_runtime_environment
from ...core.model_manager import ModelManager
from ...__version__ import __app_name__, __version__


class LogSignalBridge(QObject):
    sig_new_log = Signal(str)


class DiagnosticsDialog(QDialog):
    """
    Dialog for displaying real-time system diagnostics, PyTorch CUDA readiness,
    hardware telemetry, and live application logs from logs/subtitlego.log.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{__app_name__} - System Diagnostics & Logs")
        self.resize(820, 640)
        self.setMinimumSize(680, 480)

        self.bridge = LogSignalBridge()
        self.bridge.sig_new_log.connect(self._on_new_log_line)

        self._init_ui()
        self._load_diagnostics()
        self._load_logs()

        # Register live log listener
        add_log_listener(self._emit_to_bridge)

    def _emit_to_bridge(self, text: str):
        self.bridge.sig_new_log.emit(text)

    def closeEvent(self, event):
        remove_log_listener(self._emit_to_bridge)
        super().closeEvent(event)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header Title
        title_box = QHBoxLayout()
        lbl_title = QLabel("System Diagnostics & Log Viewer")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #38bdf8;")
        title_box.addWidget(lbl_title)

        title_box.addStretch()

        self.btn_refresh = QPushButton("Refresh Status")
        self.btn_refresh.setProperty("class", "btnSecondary")
        self.btn_refresh.clicked.connect(self._refresh_all)
        title_box.addWidget(self.btn_refresh)

        layout.addLayout(title_box)

        # Tabs: Overview Diagnostics | Live Logs
        self.tabs = QTabWidget()

        # Tab 1: Diagnostics Overview
        self.tab_diag = QWidget()
        diag_layout = QVBoxLayout(self.tab_diag)
        diag_layout.setContentsMargins(10, 10, 10, 10)
        diag_layout.setSpacing(10)

        # Scroll Area for Diagnostics content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        diag_content = QWidget()
        self.diag_vbox = QVBoxLayout(diag_content)
        self.diag_vbox.setContentsMargins(0, 0, 0, 0)
        self.diag_vbox.setSpacing(10)

        # 1. Environment & App Card
        self.card_env = QFrame()
        self.card_env.setProperty("class", "cardFrame")
        self.env_layout = QVBoxLayout(self.card_env)
        self.diag_vbox.addWidget(self.card_env)

        # 2. Hardware & GPU Card
        self.card_hw = QFrame()
        self.card_hw.setProperty("class", "cardFrame")
        self.hw_layout = QVBoxLayout(self.card_hw)
        self.diag_vbox.addWidget(self.card_hw)

        # 3. AI Runtime & PyTorch Card
        self.card_rt = QFrame()
        self.card_rt.setProperty("class", "cardFrame")
        self.rt_layout = QVBoxLayout(self.card_rt)
        self.diag_vbox.addWidget(self.card_rt)

        # 4. Log File Info Card
        self.card_log_info = QFrame()
        self.card_log_info.setProperty("class", "cardFrame")
        self.log_info_layout = QVBoxLayout(self.card_log_info)
        self.diag_vbox.addWidget(self.card_log_info)

        self.diag_vbox.addStretch()
        scroll.setWidget(diag_content)
        diag_layout.addWidget(scroll)

        self.tabs.addTab(self.tab_diag, "System Diagnostics")

        # Tab 2: Live Log Stream
        self.tab_logs = QWidget()
        logs_layout = QVBoxLayout(self.tab_logs)
        logs_layout.setContentsMargins(10, 10, 10, 10)
        logs_layout.setSpacing(8)

        # Log filter row
        filter_row = QHBoxLayout()
        lbl_filter = QLabel("Search Logs:")
        lbl_filter.setStyleSheet("font-size: 11px; font-weight: 600;")
        filter_row.addWidget(lbl_filter)

        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filter lines (e.g. CUDA, error, torch)...")
        self.txt_filter.textChanged.connect(self._filter_logs)
        filter_row.addWidget(self.txt_filter)

        self.btn_clear_view = QPushButton("Clear Buffer")
        self.btn_clear_view.setProperty("class", "btnGhost")
        self.btn_clear_view.clicked.connect(self._on_clear_logs)
        filter_row.addWidget(self.btn_clear_view)

        logs_layout.addLayout(filter_row)

        # Log text editor
        self.txt_logs = QPlainTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setLineWrapMode(QPlainTextEdit.NoWrap)
        font = QFont("Consolas" if sys.platform == "win32" else "Courier", 10)
        font.setStyleHint(QFont.Monospace)
        self.txt_logs.setFont(font)
        self.txt_logs.setStyleSheet("background-color: #0f172a; color: #f1f5f9; border: 1px solid #334155; border-radius: 6px; padding: 8px;")
        logs_layout.addWidget(self.txt_logs)

        # Log action buttons
        log_btn_row = QHBoxLayout()
        
        self.btn_copy_logs = QPushButton("Copy All Logs")
        self.btn_copy_logs.setProperty("class", "btnSecondary")
        self.btn_copy_logs.clicked.connect(self._on_copy_logs)
        log_btn_row.addWidget(self.btn_copy_logs)

        self.btn_open_file = QPushButton("Open subtitlego.log")
        self.btn_open_file.setProperty("class", "btnSecondary")
        self.btn_open_file.clicked.connect(open_log_file)
        log_btn_row.addWidget(self.btn_open_file)

        self.btn_open_folder = QPushButton("Open Log Folder")
        self.btn_open_folder.setProperty("class", "btnSecondary")
        self.btn_open_folder.clicked.connect(open_log_directory)
        log_btn_row.addWidget(self.btn_open_folder)

        log_btn_row.addStretch()
        logs_layout.addLayout(log_btn_row)

        self.tabs.addTab(self.tab_logs, "Application Logs (subtitlego.log)")
        layout.addWidget(self.tabs)

        # Bottom Bar
        bottom_bar = QHBoxLayout()
        self.btn_relaunch_setup = QPushButton("Re-run AI Engine Setup...")
        self.btn_relaunch_setup.setProperty("class", "btnSecondary")
        self.btn_relaunch_setup.clicked.connect(self._on_relaunch_setup)
        bottom_bar.addWidget(self.btn_relaunch_setup)

        bottom_bar.addStretch()

        self.btn_close = QPushButton("Close")
        self.btn_close.setProperty("class", "btnPrimary")
        self.btn_close.clicked.connect(self.accept)
        bottom_bar.addWidget(self.btn_close)

        layout.addLayout(bottom_bar)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _load_diagnostics(self):
        diag = diagnose_runtime_environment()
        log_path = get_log_file_path()

        # 1. Environment & App Card
        self._clear_layout(self.env_layout)
        lbl_env_hdr = QLabel("Application & Platform")
        lbl_env_hdr.setStyleSheet("font-size: 13px; font-weight: 700; color: #38bdf8;")
        self.env_layout.addWidget(lbl_env_hdr)

        self.env_layout.addWidget(QLabel(f"Application: {__app_name__} v{__version__}"))
        self.env_layout.addWidget(QLabel(f"Python Executable: {diag.get('python_executable')}"))
        self.env_layout.addWidget(QLabel(f"Python ABI: {diag.get('python_version')} (Frozen: {diag.get('is_frozen')})"))
        self.env_layout.addWidget(QLabel(f"Operating System: {sys.platform} ({os.name})"))

        # 2. Hardware & GPU Card
        self._clear_layout(self.hw_layout)
        lbl_hw_hdr = QLabel("Hardware Telemetry")
        lbl_hw_hdr.setStyleSheet("font-size: 13px; font-weight: 700; color: #38bdf8;")
        self.hw_layout.addWidget(lbl_hw_hdr)

        self.hw_layout.addWidget(QLabel(f"Detected Hardware: {diag.get('hardware_summary')}"))
        self.hw_layout.addWidget(QLabel(f"System RAM: {diag.get('total_ram_gb')} GB"))
        if diag.get("has_nvidia_gpu"):
            self.hw_layout.addWidget(QLabel(f"NVIDIA GPU: {diag.get('gpu_name')} ({diag.get('vram_gb')} GB VRAM)"))
            if diag.get("driver_version"):
                self.hw_layout.addWidget(QLabel(f"NVIDIA Driver Version: {diag.get('driver_version')}"))
        else:
            self.hw_layout.addWidget(QLabel("NVIDIA GPU: None detected"))

        # 3. AI Runtime & PyTorch Card
        self._clear_layout(self.rt_layout)
        lbl_rt_hdr = QLabel("AI Runtime & CUDA Readiness")
        lbl_rt_hdr.setStyleSheet("font-size: 13px; font-weight: 700; color: #38bdf8;")
        self.rt_layout.addWidget(lbl_rt_hdr)

        if diag.get("torch_installed"):
            self.rt_layout.addWidget(QLabel(f"PyTorch Version: {diag.get('torch_version')}"))
            self.rt_layout.addWidget(QLabel(f"PyTorch CUDA Build: {diag.get('torch_cuda_build') or 'None (CPU Build)'}"))
            
            cuda_status_lbl = QLabel(f"CUDA Acceleration Active: {'YES' if diag.get('cuda_available') else 'NO'}")
            cuda_status_lbl.setStyleSheet(
                "color: #4ade80; font-weight: 700;" if diag.get("cuda_available") else "color: #f87171; font-weight: 700;"
            )
            self.rt_layout.addWidget(cuda_status_lbl)

            self.rt_layout.addWidget(QLabel(f"Active Acceleration Device: {diag.get('active_device_name', 'CPU')}"))
        else:
            self.rt_layout.addWidget(QLabel("PyTorch Status: Not Installed / Not Found"))
            if diag.get("import_error"):
                lbl_err = QLabel(f"Import Error:\n{diag.get('import_error')}")
                lbl_err.setStyleSheet("color: #f87171; font-family: monospace; font-size: 11px;")
                lbl_err.setWordWrap(True)
                self.rt_layout.addWidget(lbl_err)

        notes = diag.get("cuda_diagnosis_notes", [])
        if notes:
            for n in notes:
                lbl_note = QLabel(f"Notice: {n}")
                lbl_note.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: 500;")
                lbl_note.setWordWrap(True)
                self.rt_layout.addWidget(lbl_note)

        # 4. Log File Info Card
        self._clear_layout(self.log_info_layout)
        lbl_log_hdr = QLabel("Log File Destination")
        lbl_log_hdr.setStyleSheet("font-size: 13px; font-weight: 700; color: #38bdf8;")
        self.log_info_layout.addWidget(lbl_log_hdr)

        lbl_log_path = QLabel(f"File: {log_path}")
        lbl_log_path.setStyleSheet("font-family: monospace; font-size: 11px; color: #cbd5e1;")
        lbl_log_path.setWordWrap(True)
        self.log_info_layout.addWidget(lbl_log_path)

        exists = os.path.exists(log_path)
        size_kb = (os.path.getsize(log_path) / 1024.0) if exists else 0.0
        self.log_info_layout.addWidget(QLabel(f"Status: {'Active' if exists else 'Not Created Yet'} ({size_kb:.1f} KB)"))

    def _load_logs(self):
        raw = get_recent_logs()
        self.txt_logs.setPlainText(raw)
        self.txt_logs.moveCursor(QTextCursor.End)

    def _filter_logs(self, query: str):
        raw = get_recent_logs()
        if not query.strip():
            self.txt_logs.setPlainText(raw)
        else:
            q_lower = query.lower()
            filtered = [line for line in raw.splitlines() if q_lower in line.lower()]
            self.txt_logs.setPlainText("\n".join(filtered))
        self.txt_logs.moveCursor(QTextCursor.End)

    def _on_new_log_line(self, line: str):
        query = self.txt_filter.text().strip().lower()
        if not query or query in line.lower():
            self.txt_logs.appendPlainText(line)

    def _on_copy_logs(self):
        text = self.txt_logs.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            QMessageBox.information(self, "Logs Copied", "Log entries copied to clipboard.")

    def _on_clear_logs(self):
        clear_recent_logs()
        self.txt_logs.clear()

    def _refresh_all(self):
        self._load_diagnostics()
        self._load_logs()

    def _on_relaunch_setup(self):
        from .setup_wizard_dialog import SetupWizardDialog
        dlg = SetupWizardDialog(self)
        dlg.exec()
        ModelManager.get_instance().refresh_hardware_detection()
        self._refresh_all()
