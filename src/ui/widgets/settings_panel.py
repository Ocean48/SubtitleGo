import os
import tempfile
from typing import Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox,
    QDoubleSpinBox, QSpinBox, QLineEdit, QPushButton, QGroupBox, QMessageBox
)
from PySide6.QtCore import Signal

from ...core.model_manager import SUPPORTED_LANGUAGES, is_model_downloaded
from .model_download_dialog import ModelDownloadDialog


class SettingsPanel(QWidget):
    """
    Panel for configuring transcription parameters, language selection,
    and subtitle pacing.
    """
    sig_settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Spoken Language Selection
        lbl_lang = QLabel("Spoken Language")
        lbl_lang.setStyleSheet("font-weight: 600; color: #94a3b8; font-size: 12px;")
        layout.addWidget(lbl_lang)

        self.cb_language = QComboBox()
        for lang in SUPPORTED_LANGUAGES:
            if lang == "Auto Detect":
                self.cb_language.addItem("Auto Detect (All 52 Languages)", "")
            else:
                self.cb_language.addItem(lang, lang)
        self.cb_language.currentIndexChanged.connect(self.sig_settings_changed)
        layout.addWidget(self.cb_language)

        # Auto-save Checkbox
        self.chk_autosave = QCheckBox("Auto-save .srt & .vtt to source video folder")
        self.chk_autosave.setChecked(True)
        self.chk_autosave.setStyleSheet("font-size: 12px; color: #f8fafc;")
        self.chk_autosave.stateChanged.connect(self.sig_settings_changed)
        layout.addWidget(self.chk_autosave)

        lbl_autosave_hint = QLabel("Automatically writes subtitle files next to media upon completion")
        lbl_autosave_hint.setStyleSheet("color: #64748b; font-size: 11px; margin-left: 24px;")
        layout.addWidget(lbl_autosave_hint)

        # Advanced Settings Group (Collapsible)
        self.grp_advanced = QGroupBox("Advanced Pacing & Audio Settings")
        self.grp_advanced.setCheckable(True)
        self.grp_advanced.setChecked(False)

        adv_main_layout = QVBoxLayout(self.grp_advanced)
        adv_main_layout.setContentsMargins(10, 10, 10, 10)
        adv_main_layout.setSpacing(8)

        # Advanced Content Container
        self.adv_content = QWidget()
        adv_layout = QVBoxLayout(self.adv_content)
        adv_layout.setContentsMargins(0, 0, 0, 0)
        adv_layout.setSpacing(8)

        # Row 1: Max Cue Duration & Pause Sensitivity
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        
        # Max Cue Duration
        col_cue = QVBoxLayout()
        lbl_cue = QLabel("Max Cue Duration (s)")
        lbl_cue.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.spin_max_cue = QDoubleSpinBox()
        self.spin_max_cue.setRange(2.0, 15.0)
        self.spin_max_cue.setSingleStep(0.5)
        self.spin_max_cue.setValue(4.5)
        self.spin_max_cue.setToolTip("Maximum duration for each subtitle cue before splitting (Standard: 3.5s - 4.5s)")
        col_cue.addWidget(lbl_cue)
        col_cue.addWidget(self.spin_max_cue)
        row1.addLayout(col_cue)

        # Pause Sensitivity
        col_silence = QVBoxLayout()
        lbl_silence = QLabel("Pause Sensitivity (dB)")
        lbl_silence.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.spin_silence = QSpinBox()
        self.spin_silence.setRange(-50, -15)
        self.spin_silence.setSingleStep(1)
        self.spin_silence.setValue(-36)
        self.spin_silence.setToolTip("Audio volume threshold for speech pause detection (Default: -36 dB)")
        col_silence.addWidget(lbl_silence)
        col_silence.addWidget(self.spin_silence)
        row1.addLayout(col_silence)

        adv_layout.addLayout(row1)

        # Row 2: Vocabulary / Hotwords & Concurrency
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        col_prompt = QVBoxLayout()
        lbl_prompt = QLabel("Vocabulary / Hotwords")
        lbl_prompt.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.txt_prompt = QLineEdit()
        self.txt_prompt.setPlaceholderText("Names, acronyms, terms")
        self.txt_prompt.setToolTip("Keywords passed to speech recognition model to improve domain accuracy")
        col_prompt.addWidget(lbl_prompt)
        col_prompt.addWidget(self.txt_prompt)
        row2.addLayout(col_prompt, stretch=1)

        col_conc = QVBoxLayout()
        lbl_conc = QLabel("Parallel Workers")
        lbl_conc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.cb_concurrency = QComboBox()
        self.cb_concurrency.addItem("1 worker", 1)
        self.cb_concurrency.addItem("2 parallel", 2)
        self.cb_concurrency.addItem("4 parallel", 4)
        self.cb_concurrency.setCurrentIndex(1)  # Default 2
        col_conc.addWidget(lbl_conc)
        col_conc.addWidget(self.cb_concurrency)
        row2.addLayout(col_conc)

        adv_layout.addLayout(row2)

        # Utility Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        
        self.btn_download_model = QPushButton("Model Weights...")
        self.btn_download_model.setProperty("class", "btnOutline")
        self.btn_download_model.clicked.connect(self._open_model_dialog)
        btn_row.addWidget(self.btn_download_model)

        self.btn_purge_temp = QPushButton("Purge Temp Audio")
        self.btn_purge_temp.setProperty("class", "btnOutline")
        self.btn_purge_temp.clicked.connect(self._purge_temp_cache)
        btn_row.addWidget(self.btn_purge_temp)

        adv_layout.addLayout(btn_row)

        adv_main_layout.addWidget(self.adv_content)
        self.adv_content.setVisible(False)
        self.grp_advanced.toggled.connect(self.adv_content.setVisible)

        layout.addWidget(self.grp_advanced)

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
        return {
            "language": self.cb_language.currentData() or None,
            "auto_save": self.chk_autosave.isChecked(),
            "max_segment_length": self.spin_max_cue.value(),
            "silence_thresh_db": float(self.spin_silence.value()),
            "prompt": self.txt_prompt.text().strip() or None,
            "concurrency": self.cb_concurrency.currentData() or 2
        }
