from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QHBoxLayout, QMessageBox
)
from PySide6.QtCore import QThread, Signal, Qt

from ...core.model_manager import download_model_weights, get_model_dir


class ModelDownloadWorker(QThread):
    sig_progress = Signal(str, float)
    sig_finished = Signal(str)
    sig_error = Signal(str)

    def __init__(self, target_dir=None, parent=None):
        super().__init__(parent)
        self.target_dir = target_dir

    def run(self):
        try:
            def callback(msg, pct):
                self.sig_progress.emit(msg, pct)

            path = download_model_weights(self.target_dir, progress_callback=callback)
            self.sig_finished.emit(path)
        except Exception as e:
            self.sig_error.emit(str(e))


class ModelDownloadDialog(QDialog):
    """
    Dialog for downloading Qwen3-ASR weights from Hugging Face Hub.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download Qwen3-ASR Model Weights")
        self.setFixedSize(480, 220)
        self.setWindowModality(Qt.ApplicationModal)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self.lbl_title = QLabel("Qwen3-ASR-1.7B Model Setup")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #38bdf8;")
        layout.addWidget(self.lbl_title)

        self.lbl_desc = QLabel(
            "Local model weights were not found. Download (~3.5 GB) from Hugging Face Hub to enable offline speech recognition?"
        )
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(self.lbl_desc)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #38bdf8; font-size: 12px;")
        self.lbl_status.setVisible(False)
        layout.addWidget(self.lbl_status)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_download = QPushButton("Start Download")
        self.btn_download.setProperty("class", "btnPrimary")
        self.btn_download.clicked.connect(self.start_download)
        btn_layout.addWidget(self.btn_download)

        layout.addLayout(btn_layout)

        self.worker = None

    def start_download(self):
        self.btn_download.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate while connecting
        self.lbl_status.setVisible(True)
        self.lbl_status.setText("Connecting to Hugging Face Hub...")

        self.worker = ModelDownloadWorker(parent=None)
        self.worker.sig_progress.connect(self._on_progress)
        self.worker.sig_finished.connect(self._on_finished)
        self.worker.sig_error.connect(self._on_error)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_finished(self):
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

    def _on_progress(self, msg: str, pct: float):
        self.lbl_status.setText(msg)
        if pct > 0:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(pct))

    def _on_finished(self, path: str):
        self.lbl_status.setText("Model downloaded successfully!")
        self.progress_bar.setValue(100)
        QMessageBox.information(self, "Success", f"Qwen3-ASR model downloaded to:\n{path}")
        self.accept()

    def _on_error(self, err: str):
        self.lbl_status.setText("Download failed.")
        self.btn_download.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        QMessageBox.critical(self, "Download Error", f"Failed to download model weights:\n{err}")

    def reject(self):
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait(1000)
        super().reject()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait(1000)
        super().closeEvent(event)
