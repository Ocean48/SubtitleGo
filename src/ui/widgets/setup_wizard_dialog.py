import os
import sys
import threading
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QRadioButton, QButtonGroup, QFrame, QMessageBox,
    QStackedWidget
)
from PySide6.QtCore import QThread, Signal, Qt

from ...core.hardware_detector import detect_hardware_capabilities
from ...core.runtime_manager import (
    is_runtime_installed,
    install_ai_runtime,
    get_installed_runtime_info
)
from ...core.model_manager import (
    is_model_downloaded,
    download_model_weights,
    get_model_dir
)


import os
import sys
import time
import threading
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QRadioButton, QButtonGroup, QFrame, QMessageBox,
    QStackedWidget, QPlainTextEdit, QApplication
)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QTextCursor

from ...core.hardware_detector import detect_hardware_capabilities
from ...core.runtime_manager import (
    is_runtime_installed,
    install_ai_runtime,
    get_installed_runtime_info
)
from ...core.model_manager import (
    is_model_downloaded,
    download_model_weights,
    get_model_dir
)


class SetupWorker(QThread):
    sig_progress = Signal(str, float)
    sig_log = Signal(str)
    sig_stage_changed = Signal(str)
    sig_finished = Signal()
    sig_error = Signal(str)

    def __init__(self, target_runtime: str, need_runtime: bool, need_model: bool, parent=None):
        super().__init__(parent)
        self.target_runtime = target_runtime
        self.need_runtime = need_runtime
        self.need_model = need_model
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def _emit_log(self, text: str):
        timestamp = time.strftime("%H:%M:%S")
        self.sig_log.emit(f"[{timestamp}] {text}")

    def run(self):
        try:
            self._emit_log("Setup process initiated.")
            self._emit_log(f"Runtime needed: {self.need_runtime} | Model needed: {self.need_model}")

            # Stage 1: Runtime installation
            if self.need_runtime:
                self.sig_stage_changed.emit("Stage 1/2: Installing AI Engine & PyTorch Runtime...")
                self._emit_log(f"Starting Stage 1: Installing PyTorch ({self.target_runtime.upper()})...")

                def rt_progress_cb(msg, pct):
                    # Map to 0-50%
                    self.sig_progress.emit(msg, pct * 0.5)

                def rt_log_cb(msg):
                    self._emit_log(msg)

                install_ai_runtime(
                    target_type=self.target_runtime,
                    progress_callback=rt_progress_cb,
                    log_callback=rt_log_cb,
                    cancel_event=self.cancel_event
                )
                self._emit_log("Stage 1 completed: AI runtime configured successfully.")

            if self.cancel_event.is_set():
                self._emit_log("Setup cancelled by user.")
                return

            # Stage 2: Model download
            if self.need_model:
                stage_label = "Stage 2/2: Downloading Qwen3-ASR Model Weights..." if self.need_runtime else "Downloading Qwen3-ASR Model Weights..."
                self.sig_stage_changed.emit(stage_label)
                self._emit_log("Starting Stage 2: Downloading Qwen3-ASR speech recognition weights (~3.4 GB)...")

                def model_progress_cb(msg, pct):
                    # Map to 50-100% or 0-100%
                    start_base = 50.0 if self.need_runtime else 0.0
                    scale = 0.5 if self.need_runtime else 1.0
                    self.sig_progress.emit(msg, start_base + (pct * scale))

                def model_log_cb(msg):
                    self._emit_log(msg)

                download_model_weights(
                    progress_callback=model_progress_cb,
                    log_callback=model_log_cb
                )
                self._emit_log("Stage 2 completed: Model weights verified successfully.")

            if self.cancel_event.is_set():
                self._emit_log("Setup cancelled by user.")
                return

            self._emit_log("All installation steps finished successfully.")
            self.sig_finished.emit()

        except Exception as e:
            self._emit_log(f"ERROR: {str(e)}")
            self.sig_error.emit(str(e))


class SetupWizardDialog(QDialog):
    """
    First-Launch Setup Wizard for hardware detection, PyTorch AI runtime installation,
    and Qwen3-ASR speech model downloading.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SubtitleGo - AI Engine Setup")
        self.setMinimumSize(620, 520)
        self.resize(640, 540)
        self.setWindowModality(Qt.ApplicationModal)

        self.hw_info = detect_hardware_capabilities()
        self.need_runtime = not is_runtime_installed()
        self.need_model = not is_model_downloaded()
        self.worker: Optional[SetupWorker] = None

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 22, 22, 22)
        main_layout.setSpacing(14)

        # Header Title
        self.lbl_title = QLabel("Initial Setup & AI Configuration")
        self.lbl_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #38bdf8;")
        main_layout.addWidget(self.lbl_title)

        # Stacked Pages
        self.stack = QStackedWidget()

        # Page 0: Hardware Discovery & Runtime Selection
        self.page_selection = QWidget()
        page_sel_layout = QVBoxLayout(self.page_selection)
        page_sel_layout.setContentsMargins(0, 0, 0, 0)
        page_sel_layout.setSpacing(12)

        lbl_desc = QLabel(
            "To keep the application download lightweight, AI components and speech models "
            "are set up on first launch tailored to your hardware."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #94a3b8; font-size: 12px;")
        page_sel_layout.addWidget(lbl_desc)

        # Hardware detection card
        card_hw = QFrame()
        card_hw.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px;")
        card_layout = QVBoxLayout(card_hw)
        card_layout.setSpacing(6)

        lbl_hw_header = QLabel("Detected Hardware:")
        lbl_hw_header.setStyleSheet("font-weight: 600; color: #f8fafc; font-size: 12px;")
        card_layout.addWidget(lbl_hw_header)

        lbl_hw_detail = QLabel(f"Device: {self.hw_info.get('hardware_summary', 'Standard CPU')}")
        lbl_hw_detail.setStyleSheet("color: #38bdf8; font-size: 13px; font-weight: 600;")
        card_layout.addWidget(lbl_hw_detail)

        lbl_ram = QLabel(f"System RAM: {self.hw_info.get('total_ram_gb', 8.0)} GB")
        lbl_ram.setStyleSheet("color: #94a3b8; font-size: 11px;")
        card_layout.addWidget(lbl_ram)

        page_sel_layout.addWidget(card_hw)

        # Option selection
        lbl_choose = QLabel("Select AI Acceleration Runtime:")
        lbl_choose.setStyleSheet("font-weight: 600; color: #f8fafc; font-size: 12px; margin-top: 4px;")
        page_sel_layout.addWidget(lbl_choose)

        self.btn_group = QButtonGroup(self)

        is_macos = (sys.platform == "darwin")
        rec_rt = self.hw_info.get("recommended_runtime", "cpu")
        is_apple_silicon = is_macos and (rec_rt == "mps")

        if is_macos:
            if is_apple_silicon:
                self.rb_primary = QRadioButton("Apple Silicon GPU Acceleration (Metal / MPS) (~250 MB)")
                self.rb_primary.setStyleSheet("color: #f8fafc; font-size: 12px;")
                self.btn_group.addButton(self.rb_primary, 1)
                page_sel_layout.addWidget(self.rb_primary)
                self.rb_primary.setChecked(True)

                self.rb_secondary = QRadioButton("CPU Mode - Standard Compatibility (~250 MB)")
                self.rb_secondary.setStyleSheet("color: #f8fafc; font-size: 12px;")
                self.btn_group.addButton(self.rb_secondary, 2)
                page_sel_layout.addWidget(self.rb_secondary)
            else:
                self.rb_primary = QRadioButton("macOS Intel CPU Mode (~250 MB)")
                self.rb_primary.setStyleSheet("color: #f8fafc; font-size: 12px;")
                self.btn_group.addButton(self.rb_primary, 1)
                page_sel_layout.addWidget(self.rb_primary)
                self.rb_primary.setChecked(True)

                self.rb_secondary = None
        else:
            # Windows and Linux
            is_rtx_50 = self.hw_info.get("is_rtx_50_series", False)
            cuda_title = "NVIDIA GPU Acceleration (CUDA 12.8 / RTX 50-Series Blackwell) (~2.0 GB)" if is_rtx_50 else "NVIDIA GPU Acceleration (CUDA 12.4) - Recommended for RTX / GTX GPUs (~2.0 GB)"
            self.rb_primary = QRadioButton(cuda_title)
            self.rb_primary.setStyleSheet("color: #f8fafc; font-size: 12px;")
            self.btn_group.addButton(self.rb_primary, 1)
            page_sel_layout.addWidget(self.rb_primary)

            self.rb_secondary = QRadioButton("CPU Mode - Standard Compatibility (Smallest Download ~250 MB)")
            self.rb_secondary.setStyleSheet("color: #f8fafc; font-size: 12px;")
            self.btn_group.addButton(self.rb_secondary, 2)
            page_sel_layout.addWidget(self.rb_secondary)

            # Select recommendation based on hardware
            if self.hw_info.get("recommended_runtime") == "cuda" and self.hw_info.get("has_nvidia_gpu"):
                self.rb_primary.setChecked(True)
            else:
                self.rb_secondary.setChecked(True)
                if not self.hw_info.get("has_nvidia_gpu"):
                    self.rb_primary.setEnabled(False)
                    self.rb_primary.setText("NVIDIA GPU Acceleration (No supported NVIDIA GPU detected)")

        page_sel_layout.addStretch()
        self.stack.addWidget(self.page_selection)

        # Page 1: Progress & Download + Live Log
        self.page_progress = QWidget()
        page_prog_layout = QVBoxLayout(self.page_progress)
        page_prog_layout.setContentsMargins(0, 0, 0, 0)
        page_prog_layout.setSpacing(10)

        self.lbl_stage = QLabel("Setting up AI runtime...")
        self.lbl_stage.setStyleSheet("font-weight: 600; font-size: 14px; color: #38bdf8;")
        page_prog_layout.addWidget(self.lbl_stage)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        page_prog_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Initializing...")
        self.lbl_status.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self.lbl_status.setWordWrap(True)
        page_prog_layout.addWidget(self.lbl_status)

        # Log Header Row
        log_hdr_layout = QHBoxLayout()
        lbl_log_title = QLabel("Installation Log:")
        lbl_log_title.setStyleSheet("font-weight: 600; font-size: 12px; color: #cbd5e1;")
        log_hdr_layout.addWidget(lbl_log_title)
        log_hdr_layout.addStretch()

        self.btn_copy_log = QPushButton("Copy Log")
        self.btn_copy_log.setStyleSheet("font-size: 11px; padding: 3px 8px;")
        self.btn_copy_log.clicked.connect(self._copy_log_to_clipboard)
        log_hdr_layout.addWidget(self.btn_copy_log)

        page_prog_layout.addLayout(log_hdr_layout)

        # Log Console Box
        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet(
            "background-color: #0f172a; "
            "color: #a5f3fc; "
            "border: 1px solid #334155; "
            "border-radius: 6px; "
            "font-family: 'Consolas', 'Courier New', monospace; "
            "font-size: 11px; "
            "padding: 6px;"
        )
        page_prog_layout.addWidget(self.txt_log, stretch=1)

        self.stack.addWidget(self.page_progress)

        main_layout.addWidget(self.stack, stretch=1)

        # Bottom Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_action = QPushButton("Start Download & Setup")
        self.btn_action.setProperty("class", "btnPrimary")
        self.btn_action.clicked.connect(self._on_action_clicked)
        btn_layout.addWidget(self.btn_action)

        main_layout.addLayout(btn_layout)

    def _on_action_clicked(self):
        if self.stack.currentIndex() == 0:
            is_macos = (sys.platform == "darwin")
            if is_macos:
                if self.hw_info.get("recommended_runtime") == "mps":
                    target_runtime = "mps" if self.rb_primary.isChecked() else "cpu"
                else:
                    target_runtime = "cpu"
            else:
                target_runtime = "cuda" if self.rb_primary.isChecked() else "cpu"

            self.stack.setCurrentIndex(1)
            self.btn_action.setEnabled(False)
            self.btn_cancel.setText("Cancel Setup")

            # Check if runtime needs installation or reinstallation to match target mode
            rt_info = get_installed_runtime_info()
            need_rt = (
                not is_runtime_installed()
                or (target_runtime == "cuda" and not rt_info.get("cuda_available", False))
                or (target_runtime == "mps" and not rt_info.get("mps_available", False))
                or (target_runtime == "cpu" and (rt_info.get("cuda_available", False) or rt_info.get("mps_available", False)))
            )

            self.worker = SetupWorker(
                target_runtime=target_runtime,
                need_runtime=need_rt,
                need_model=self.need_model,
                parent=self
            )
            self.worker.sig_progress.connect(self._on_progress)
            self.worker.sig_log.connect(self._append_log)
            self.worker.sig_stage_changed.connect(self._on_stage_changed)
            self.worker.sig_finished.connect(self._on_finished)
            self.worker.sig_error.connect(self._on_error)
            self.worker.start()

    def _append_log(self, text: str):
        self.txt_log.appendPlainText(text)
        self.txt_log.moveCursor(QTextCursor.End)

    def _copy_log_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.txt_log.toPlainText())
        self._append_log("[System] Log copied to clipboard.")

    def _on_stage_changed(self, stage_text: str):
        self.lbl_stage.setText(stage_text)

    def _on_progress(self, msg: str, pct: float):
        self.lbl_status.setText(msg)
        self.progress_bar.setValue(int(pct))

    def _on_finished(self):
        self.progress_bar.setValue(100)
        self.lbl_stage.setText("Setup Completed Successfully!")
        self.lbl_status.setText("All AI components and speech models are ready.")
        self._append_log("[System] Setup successfully completed.")
        QMessageBox.information(
            self,
            "Setup Complete",
            "AI runtime and speech models were successfully configured."
        )
        self.accept()

    def _on_error(self, err_msg: str):
        self.lbl_stage.setText("Setup Encountered an Error")
        self.lbl_status.setText(f"Error: {err_msg}")
        self._append_log(f"[System Error] {err_msg}")
        self.btn_action.setEnabled(True)
        self.btn_action.setText("Retry")
        self.btn_cancel.setEnabled(True)
        QMessageBox.critical(self, "Setup Error", f"Failed to complete setup:\n{err_msg}")

    def reject(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.quit()
            self.worker.wait(1000)
        super().reject()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.quit()
            self.worker.wait(1000)
        super().closeEvent(event)

    def _on_error(self, err_msg: str):
        self.lbl_stage.setText("Setup Encountered an Error")
        self.lbl_status.setText(f"Error: {err_msg}")
        self.btn_action.setEnabled(True)
        self.btn_action.setText("Retry")
        self.btn_cancel.setEnabled(True)
        QMessageBox.critical(self, "Setup Error", f"Failed to complete setup:\n{err_msg}")

    def reject(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.quit()
            self.worker.wait(1000)
        super().reject()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.quit()
            self.worker.wait(1000)
        super().closeEvent(event)
