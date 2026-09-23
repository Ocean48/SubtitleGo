import os
import tempfile
from typing import Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox,
    QDoubleSpinBox, QSpinBox, QLineEdit, QPushButton, QGroupBox, QMessageBox,
    QFrame
)
from PySide6.QtCore import Signal

from ...core.model_manager import (
    SUPPORTED_LANGUAGES,
    is_model_downloaded,
    get_recommended_settings,
    get_system_memory_info
)
from .model_download_dialog import ModelDownloadDialog


class SettingsPanel(QWidget):
    """
    Panel for configuring transcription parameters, language selection,
    and subtitle pacing.
    """
    sig_settings_changed = Signal()
    sig_toggle_model = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rec_settings = get_recommended_settings()
        self._init_ui()
        self.sync_model_state()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(14)

        # Primary Options Card
        card_primary = QFrame()
        card_primary.setProperty("class", "cardFrame")
        cp_layout = QVBoxLayout(card_primary)
        cp_layout.setContentsMargins(12, 12, 12, 12)
        cp_layout.setSpacing(10)

        # Spoken Language Selection
        lbl_lang = QLabel("Spoken Language")
        lbl_lang.setStyleSheet("font-weight: 600; font-size: 12px;")
        cp_layout.addWidget(lbl_lang)

        self.cb_language = QComboBox()
        for lang in SUPPORTED_LANGUAGES:
            if lang == "Auto Detect":
                self.cb_language.addItem("Auto Detect (All 52 Languages)", "")
            else:
                self.cb_language.addItem(lang, lang)
        self.cb_language.currentIndexChanged.connect(self.sig_settings_changed)
        cp_layout.addWidget(self.cb_language)

        # Auto-save Checkbox
        self.chk_autosave = QCheckBox("Auto-save .srt & .vtt to media directory")
        self.chk_autosave.setChecked(True)
        self.chk_autosave.setStyleSheet("font-weight: 500; font-size: 12px;")
        self.chk_autosave.stateChanged.connect(self.sig_settings_changed)
        cp_layout.addWidget(self.chk_autosave)

        lbl_autosave_hint = QLabel("Automatically generates subtitle files alongside source media upon completion.")
        lbl_autosave_hint.setStyleSheet("color: #64748b; font-size: 11px; margin-left: 24px;")
        lbl_autosave_hint.setWordWrap(True)
        cp_layout.addWidget(lbl_autosave_hint)

        layout.addWidget(card_primary)

        # Advanced Settings Group
        self.grp_advanced = QGroupBox("Pacing, Vocabulary & System Settings")
        self.grp_advanced.setCheckable(True)
        self.grp_advanced.setChecked(True)

        adv_main_layout = QVBoxLayout(self.grp_advanced)
        adv_main_layout.setContentsMargins(12, 12, 12, 12)
        adv_main_layout.setSpacing(10)

        self.adv_content = QWidget()
        adv_layout = QVBoxLayout(self.adv_content)
        adv_layout.setContentsMargins(0, 0, 0, 0)
        adv_layout.setSpacing(10)

        # Row 1: Max Cue Duration & Pause Sensitivity
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        
        # Max Cue Duration
        col_cue = QVBoxLayout()
        lbl_cue = QLabel("Max Cue Duration (s)")
        lbl_cue.setStyleSheet("font-size: 11px; font-weight: 500;")
        self.spin_max_cue = QDoubleSpinBox()
        self.spin_max_cue.setRange(1.5, 15.0)
        self.spin_max_cue.setSingleStep(0.5)
        self.spin_max_cue.setValue(4.5)
        self.spin_max_cue.setToolTip("Maximum duration for each subtitle cue before splitting (Standard: 3.5s - 4.5s)")
        col_cue.addWidget(lbl_cue)
        col_cue.addWidget(self.spin_max_cue)
        row1.addLayout(col_cue)

        # Pause Sensitivity
        col_silence = QVBoxLayout()
        lbl_silence = QLabel("Pause Sensitivity (dB)")
        lbl_silence.setStyleSheet("font-size: 11px; font-weight: 500;")
        self.spin_silence = QSpinBox()
        self.spin_silence.setRange(-60, -10)
        self.spin_silence.setSingleStep(1)
        self.spin_silence.setValue(-36)
        self.spin_silence.setToolTip("Audio volume threshold for speech pause detection (Default: -36 dB)")
        col_silence.addWidget(lbl_silence)
        col_silence.addWidget(self.spin_silence)
        row1.addLayout(col_silence)

        adv_layout.addLayout(row1)

        # Row 2: Vocabulary / Hotwords
        col_prompt = QVBoxLayout()
        lbl_prompt = QLabel("Domain Vocabulary / Hotwords")
        lbl_prompt.setStyleSheet("font-size: 11px; font-weight: 500;")
        self.txt_prompt = QLineEdit()
        self.txt_prompt.setPlaceholderText("e.g. PySide6, CUDA, Qwen, specialized terms...")
        self.txt_prompt.setToolTip("Context keywords passed to speech model to improve domain accuracy")
        col_prompt.addWidget(lbl_prompt)
        col_prompt.addWidget(self.txt_prompt)
        adv_layout.addLayout(col_prompt)

        # Row 3: Inference Batch Size & Concurrency
        row3 = QHBoxLayout()
        row3.setSpacing(10)

        # Inference Batch Size
        col_batch = QVBoxLayout()
        lbl_batch = QLabel("Inference Batch Size")
        lbl_batch.setStyleSheet("font-size: 11px; font-weight: 500;")
        self.cb_batch_size = QComboBox()
        rec_bs = self.rec_settings["recommended_batch_size"]
        self.cb_batch_size.addItem(f"Auto (Recommended: {rec_bs} Chunks)", rec_bs)
        self.cb_batch_size.addItem("1 Chunk (Lowest Memory / Safety Mode)", 1)
        self.cb_batch_size.addItem("2 Chunks (8GB Mac Unified / 4GB VRAM / 8GB RAM)", 2)
        self.cb_batch_size.addItem("4 Chunks (12-16GB Mac Unified / 6GB VRAM / 16GB RAM)", 4)
        self.cb_batch_size.addItem("8 Chunks (16-24GB Mac Unified / 8GB VRAM / 16-32GB RAM)", 8)
        self.cb_batch_size.addItem("16 Chunks (24-32GB Mac Unified / 12-16GB VRAM / 32GB RAM)", 16)
        self.cb_batch_size.addItem("32 Chunks (32-64GB Mac Unified / 16-24GB VRAM / 64GB RAM)", 32)
        self.cb_batch_size.addItem("64 Chunks (64GB+ Mac Unified / 24GB+ VRAM / 64GB+ RAM)", 64)
        self.cb_batch_size.setCurrentIndex(0)
        self.cb_batch_size.setToolTip(
            "Batch size determines how many audio chunks are processed simultaneously.\n"
            "• Dedicated GPU VRAM: 4GB -> 2-4 chunks, 8GB -> 8 chunks, 12-16GB -> 16 chunks, 24GB -> 32-64 chunks\n"
            "• Apple Silicon Unified Memory: 8GB -> 2 chunks, 16GB -> 8 chunks, 24-32GB -> 16 chunks, 64GB+ -> 32-64 chunks\n"
            "• CPU Mode: Uses physical system RAM"
        )
        self.cb_batch_size.currentIndexChanged.connect(self.sig_settings_changed)
        col_batch.addWidget(lbl_batch)
        col_batch.addWidget(self.cb_batch_size)
        row3.addLayout(col_batch)

        # Concurrency
        col_conc = QVBoxLayout()
        lbl_conc = QLabel("Parallel Worker Threads")
        lbl_conc.setStyleSheet("font-size: 11px; font-weight: 500;")
        self.cb_concurrency = QComboBox()
        self.cb_concurrency.addItem("1 Worker (Low Memory / Apple Silicon)", 1)
        self.cb_concurrency.addItem("2 Workers (Standard)", 2)
        self.cb_concurrency.addItem("4 Workers (High Performance)", 4)
        
        # Preselect recommended concurrency
        rec_conc = self.rec_settings["recommended_concurrency"]
        conc_idx = 0 if rec_conc == 1 else (1 if rec_conc == 2 else 2)
        self.cb_concurrency.setCurrentIndex(conc_idx)
        self.cb_concurrency.setToolTip("Number of video/audio files transcribed concurrently in the queue")
        self.cb_concurrency.currentIndexChanged.connect(self.sig_settings_changed)
        col_conc.addWidget(lbl_conc)
        col_conc.addWidget(self.cb_concurrency)
        row3.addLayout(col_conc)

        adv_layout.addLayout(row3)

        # Hardware Info Note
        lbl_mem_info = QLabel(f"Hardware Profile: {self.rec_settings['memory_label']}")
        lbl_mem_info.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 500;")
        adv_layout.addWidget(lbl_mem_info)

        # Utility Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_toggle_model = QPushButton("Start Qwen Model")
        self.btn_toggle_model.setProperty("class", "btnPrimary")
        self.btn_toggle_model.setToolTip("Start or end the Qwen3-ASR model in memory")
        self.btn_toggle_model.clicked.connect(self.sig_toggle_model)
        btn_row.addWidget(self.btn_toggle_model)
        
        self.btn_download_model = QPushButton("Model Weights...")
        self.btn_download_model.setProperty("class", "btnSecondary")
        self.btn_download_model.setToolTip("Download or verify local AI model weights")
        self.btn_download_model.clicked.connect(self._open_model_dialog)
        btn_row.addWidget(self.btn_download_model)

        self.btn_purge_temp = QPushButton("Clear Temp Audio")
        self.btn_purge_temp.setProperty("class", "btnSecondary")
        self.btn_purge_temp.setToolTip("Delete temporary extracted WAV segments from disk")
        self.btn_purge_temp.clicked.connect(self._purge_temp_cache)
        btn_row.addWidget(self.btn_purge_temp)

        adv_layout.addLayout(btn_row)

        adv_main_layout.addWidget(self.adv_content)
        self.grp_advanced.toggled.connect(self.adv_content.setVisible)

        layout.addWidget(self.grp_advanced)
        layout.addStretch()

    def sync_model_state(self):
        """Synchronizes model button in settings with current model instance state."""
        from ...core.model_manager import ModelManager
        mgr = ModelManager.get_instance()
        is_loaded = mgr.model is not None
        if is_loaded:
            self.btn_toggle_model.setText("End Qwen Model")
            self.btn_toggle_model.setProperty("class", "btnDanger")
            self.btn_toggle_model.setToolTip("Unload Qwen3-ASR model from memory to free VRAM/RAM")
        else:
            self.btn_toggle_model.setText("Start Qwen Model")
            self.btn_toggle_model.setProperty("class", "btnPrimary")
            self.btn_toggle_model.setToolTip("Load Qwen3-ASR model into GPU/CPU memory for instant speech recognition")

        self.btn_toggle_model.style().unpolish(self.btn_toggle_model)
        self.btn_toggle_model.style().polish(self.btn_toggle_model)

    def _open_model_dialog(self):
        dlg = ModelDownloadDialog(self)
        dlg.exec()

    def _purge_temp_cache(self):
        temp_dir = tempfile.gettempdir()
        deleted = 0
        freed = 0
        try:
            for f in os.listdir(temp_dir):
                if f.endswith(".extracted.wav") or "_cue_" in f or (f.startswith("tmp") and f.endswith(".wav")):
                    full_p = os.path.join(temp_dir, f)
                    try:
                        sz = os.path.getsize(full_p)
                        os.unlink(full_p)
                        deleted += 1
                        freed += sz
                    except Exception:
                        pass
            QMessageBox.information(
                self,
                "Cache Cleared",
                f"Deleted {deleted} temporary audio files.\nFreed {freed / (1024 * 1024):.2f} MB."
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to clean temp files: {e}")

    def get_settings(self) -> Dict[str, Any]:
        """Returns the dictionary of currently configured parameters."""
        raw_bs = self.cb_batch_size.currentData()
        batch_size = int(raw_bs if raw_bs is not None else self.rec_settings["recommended_batch_size"])
        return {
            "language": self.cb_language.currentData() or None,
            "auto_save": self.chk_autosave.isChecked(),
            "max_segment_length": self.spin_max_cue.value(),
            "silence_thresh_db": float(self.spin_silence.value()),
            "prompt": self.txt_prompt.text().strip() or None,
            "batch_size": batch_size,
            "concurrency": self.cb_concurrency.currentData() or 2
        }
