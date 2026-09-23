from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QMessageBox, QDialog
)
from PySide6.QtCore import Signal, Qt, QThread

from ...core.model_manager import ModelManager, is_model_downloaded
from .model_download_dialog import ModelDownloadDialog


class ModelLoaderWorker(QThread):
    """Background worker for initializing and loading Qwen3-ASR weights."""
    sig_finished = Signal(bool, str)
    sig_error = Signal(str)

    def run(self):
        try:
            mgr = ModelManager.get_instance()
            ok = mgr.load_model()
            self.sig_finished.emit(ok, mgr.device)
        except Exception as e:
            self.sig_error.emit(str(e))


class HeaderBar(QFrame):
    """
    Top header bar showing application branding, subtitle description,
    model start/end control, live hardware indicator, and theme / help controls.
    """
    sig_refresh_hardware = Signal()
    sig_theme_toggled = Signal(str)  # "dark" or "light"
    sig_shortcuts_clicked = Signal()
    sig_model_status_changed = Signal(bool)  # True if model loaded, False if unloaded

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "headerFrame")
        self._current_theme = "dark"
        self._loader_thread = None
        self._init_ui()
        self.sync_model_state()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        # Left Branding
        title_box = QVBoxLayout()
        title_box.setSpacing(1)

        self.lbl_title = QLabel("SubtitleGo")
        self.lbl_title.setObjectName("appTitle")
        title_box.addWidget(self.lbl_title)

        self.lbl_subtitle = QLabel("AI-Powered Transcription, Pacing & Precision Subtitle Studio")
        self.lbl_subtitle.setObjectName("appSubtitle")
        self.lbl_subtitle.setWordWrap(True)
        title_box.addWidget(self.lbl_subtitle)

        layout.addLayout(title_box, stretch=1)

        # Right Controls: Model Toggle + Hardware Status + Theme Toggle + Shortcuts
        right_layout = QHBoxLayout()
        right_layout.setSpacing(8)

        # Start / End Qwen Model Button
        self.btn_model_toggle = QPushButton("Start Qwen Model")
        self.btn_model_toggle.setProperty("class", "btnPrimary")
        self.btn_model_toggle.setToolTip("Load Qwen3-ASR model into GPU/CPU memory for instant speech recognition")
        self.btn_model_toggle.clicked.connect(self._on_toggle_model)
        right_layout.addWidget(self.btn_model_toggle)

        # Hardware & Model Status Badge
        self.lbl_status = QLabel("Checking Hardware...")
        self.lbl_status.setObjectName("statusBadge")
        right_layout.addWidget(self.lbl_status)

        self.btn_shortcuts = QPushButton("Shortcuts")
        self.btn_shortcuts.setProperty("class", "btnGhost")
        self.btn_shortcuts.setToolTip("View keyboard shortcuts (Ctrl+/)")
        self.btn_shortcuts.clicked.connect(self.sig_shortcuts_clicked)
        right_layout.addWidget(self.btn_shortcuts)

        self.btn_theme = QPushButton("Theme: Dark")
        self.btn_theme.setProperty("class", "btnSecondary")
        self.btn_theme.setToolTip("Toggle Dark / Light Theme")
        self.btn_theme.clicked.connect(self._toggle_theme)
        right_layout.addWidget(self.btn_theme)

        layout.addLayout(right_layout)

    def _on_toggle_model(self):
        """Starts (loads) or Ends (unloads) the Qwen model in memory."""
        mgr = ModelManager.get_instance()
        if mgr.model is not None:
            # End / Unload Model
            mgr.unload_model()
            self.sync_model_state()
            self.sig_model_status_changed.emit(False)
        else:
            # Check if model weights are downloaded
            if not is_model_downloaded():
                dlg = ModelDownloadDialog(self)
                if dlg.exec() != QDialog.Accepted:
                    return

            self.btn_model_toggle.setText("Starting Qwen...")
            self.btn_model_toggle.setEnabled(False)
            self.lbl_status.setText("[Loading Model Weights...]")

            self._loader_thread = ModelLoaderWorker(self)
            self._loader_thread.sig_finished.connect(self._on_model_loaded)
            self._loader_thread.sig_error.connect(self._on_model_load_error)
            self._loader_thread.start()

    def _on_model_loaded(self, ok: bool, device: str):
        self.sync_model_state()
        self.sig_model_status_changed.emit(True)

    def _on_model_load_error(self, err_msg: str):
        self.sync_model_state()
        QMessageBox.warning(self, "Model Load Error", f"Failed to load Qwen3-ASR model:\n{err_msg}")

    def sync_model_state(self):
        """Synchronizes model button and status badge with current model instance."""
        mgr = ModelManager.get_instance()
        info = mgr.get_hardware_status()
        is_loaded = info.get("model_loaded", False)

        self.btn_model_toggle.setEnabled(True)
        if is_loaded:
            self.btn_model_toggle.setText("End Qwen Model")
            self.btn_model_toggle.setProperty("class", "btnDanger")
            self.btn_model_toggle.setToolTip("Unload Qwen3-ASR model from memory to free VRAM/RAM")
        else:
            self.btn_model_toggle.setText("Start Qwen Model")
            self.btn_model_toggle.setProperty("class", "btnPrimary")
            self.btn_model_toggle.setToolTip("Load Qwen3-ASR model into GPU/CPU memory for instant speech recognition")

        self.btn_model_toggle.style().unpolish(self.btn_model_toggle)
        self.btn_model_toggle.style().polish(self.btn_model_toggle)
        self.update_hardware_status()

    def _toggle_theme(self):
        if self._current_theme == "dark":
            self._current_theme = "light"
            self.btn_theme.setText("Theme: Light")
        else:
            self._current_theme = "dark"
            self.btn_theme.setText("Theme: Dark")
        self.sig_theme_toggled.emit(self._current_theme)

    def set_theme(self, theme: str):
        self._current_theme = theme.lower()
        if self._current_theme == "light":
            self.btn_theme.setText("Theme: Light")
        else:
            self.btn_theme.setText("Theme: Dark")

    def update_hardware_status(self):
        """Refreshes hardware and GPU availability badge."""
        try:
            mgr = ModelManager.get_instance()
            info = mgr.get_hardware_status()
            is_loaded = info.get("model_loaded", False)

            if info.get("cuda_available"):
                gpu_desc = f"GPU: {info['gpu_name']} {info['vram_gb']:.1f}GB" if info.get('vram_gb') else f"GPU: {info['gpu_name']}"
                if is_loaded:
                    self.lbl_status.setText(f"[Active | {gpu_desc}]")
                    self.lbl_status.setProperty("class", "gpu")
                else:
                    self.lbl_status.setText(f"[Standby | {gpu_desc}]")
                    self.lbl_status.setProperty("class", "")
            elif info.get("mps_available"):
                ram_str = f" ({info['total_ram_gb']:.0f} GB Unified RAM)" if info.get('total_ram_gb') else ""
                gpu_desc = f"Apple Silicon GPU{ram_str}"
                if is_loaded:
                    self.lbl_status.setText(f"[Active | {gpu_desc}]")
                    self.lbl_status.setProperty("class", "gpu")
                else:
                    self.lbl_status.setText(f"[Standby | {gpu_desc}]")
                    self.lbl_status.setProperty("class", "")
            else:
                ram_str = f" ({info['total_ram_gb']:.0f} GB RAM)" if info.get('total_ram_gb') else ""
                if is_loaded:
                    self.lbl_status.setText(f"[Active | CPU Mode{ram_str}]")
                    self.lbl_status.setProperty("class", "cpu")
                else:
                    self.lbl_status.setText(f"[Standby | CPU Mode{ram_str}]")
                    self.lbl_status.setProperty("class", "")
        except Exception:
            self.lbl_status.setText("[Offline / Initializing]")
            self.lbl_status.setProperty("class", "")

        self.lbl_status.style().unpolish(self.lbl_status)
        self.lbl_status.style().polish(self.lbl_status)


