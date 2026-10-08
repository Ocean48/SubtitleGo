from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QHBoxLayout, QMessageBox, QCheckBox
)
from PySide6.QtCore import QThread, Signal, Qt

from ...core.model_manager import (
    download_model_weights,
    download_forced_aligner_weights,
    get_model_dir,
    get_forced_aligner_dir,
    is_model_downloaded,
    is_forced_aligner_downloaded
)


class ModelDownloadWorker(QThread):
    sig_progress = Signal(str, float)
    sig_finished = Signal(str)
    sig_error = Signal(str)

    def __init__(self, download_asr=True, download_aligner=False, target_dir=None, parent=None):
        super().__init__(parent)
        self.download_asr = download_asr
        self.download_aligner = download_aligner
        self.target_dir = target_dir

    def run(self):
        try:
            total_tasks = (1 if self.download_asr else 0) + (1 if self.download_aligner else 0)
            if total_tasks == 0:
                self.sig_finished.emit("No models selected.")
                return

            current_task = 0
            res_paths = []

            if self.download_asr:
                current_task += 1
                def cb_asr(msg, pct):
                    base = ((current_task - 1) / total_tasks) * 100.0
                    scale = 100.0 / total_tasks
                    self.sig_progress.emit(f"Qwen3-ASR: {msg}", base + (pct * (scale / 100.0)))

                path_asr = download_model_weights(self.target_dir, progress_callback=cb_asr)
                res_paths.append(f"ASR: {path_asr}")

            if self.download_aligner:
                current_task += 1
                def cb_aligner(msg, pct):
                    base = ((current_task - 1) / total_tasks) * 100.0
                    scale = 100.0 / total_tasks
                    self.sig_progress.emit(f"Aligner: {msg}", base + (pct * (scale / 100.0)))

                path_fa = download_forced_aligner_weights(progress_callback=cb_aligner)
                res_paths.append(f"Aligner: {path_fa}")

            self.sig_finished.emit("\n".join(res_paths))
        except Exception as e:
            self.sig_error.emit(str(e))


class ModelDownloadDialog(QDialog):
    """
    Dialog for downloading Qwen3-ASR and Qwen3-ForcedAligner weights from Hugging Face Hub.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download AI Speech Models")
        self.setFixedSize(500, 280)
        self.setWindowModality(Qt.ApplicationModal)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self.lbl_title = QLabel("AI Model Setup")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #38bdf8;")
        layout.addWidget(self.lbl_title)

        self.lbl_desc = QLabel(
            "Select speech recognition and timestamp alignment models to download from Hugging Face Hub:"
        )
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(self.lbl_desc)

        asr_downloaded = is_model_downloaded()
        fa_downloaded = is_forced_aligner_downloaded()

        self.chk_asr = QCheckBox("Qwen3-ASR-1.7B Speech Model (~3.4 GB) " + ("[Installed]" if asr_downloaded else "[Recommended]"))
        self.chk_asr.setChecked(not asr_downloaded)
        self.chk_asr.setStyleSheet("font-size: 12px; color: #e2e8f0;")
        layout.addWidget(self.chk_asr)

        self.chk_aligner = QCheckBox("Qwen3-ForcedAligner-0.6B (~1.2 GB, Millisecond Token Sync) " + ("[Installed]" if fa_downloaded else "[Optional]"))
        self.chk_aligner.setChecked(not fa_downloaded)
        self.chk_aligner.setStyleSheet("font-size: 12px; color: #e2e8f0;")
        layout.addWidget(self.chk_aligner)

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
        dl_asr = self.chk_asr.isChecked()
        dl_fa = self.chk_aligner.isChecked()

        if not dl_asr and not dl_fa:
            QMessageBox.information(self, "No Selection", "Please select at least one model to download.")
            return

        self.chk_asr.setEnabled(False)
        self.chk_aligner.setEnabled(False)
        self.btn_download.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate while connecting
        self.lbl_status.setVisible(True)
        self.lbl_status.setText("Connecting to Hugging Face Hub...")

        self.worker = ModelDownloadWorker(download_asr=dl_asr, download_aligner=dl_fa, parent=None)
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

    def _on_finished(self, paths: str):
        self.lbl_status.setText("Models downloaded successfully!")
        self.progress_bar.setValue(100)
        QMessageBox.information(self, "Success", f"Downloaded successfully:\n{paths}")
        self.accept()

    def _on_error(self, err: str):
        self.lbl_status.setText("Download failed.")
        self.chk_asr.setEnabled(True)
        self.chk_aligner.setEnabled(True)
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
        super().closeEvent(event)
