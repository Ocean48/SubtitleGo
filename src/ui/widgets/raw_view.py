from typing import List, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QPlainTextEdit, QApplication, QLabel
)
from PySide6.QtCore import Signal, QTimer, Qt
from PySide6.QtGui import QFont

from ...core.subtitle_formatter import (
    build_srt_content, build_vtt_content, build_txt_content,
    parse_srt_content, parse_vtt_content
)


class RawSubtitleView(QWidget):
    """
    Inspector view displaying raw SRT, WebVTT, or transcript content with copy and edit capabilities.
    """
    sig_raw_text_modified = Signal(list)  # Emits parsed cues

    def __init__(self, mode: str = "srt", parent=None):
        super().__init__(parent)
        self.mode = mode.lower()  # "srt", "vtt", or "txt"
        self._is_programmatic_update = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header with Copy Button
        header = QHBoxLayout()
        header.setSpacing(8)

        title_map = {"srt": "Formatted SRT", "vtt": "Formatted WebVTT", "txt": "Plain Transcript"}
        lbl_title = QLabel(title_map.get(self.mode, f"Raw {self.mode.upper()} Content"))
        lbl_title.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 600;")
        header.addWidget(lbl_title)

        header.addStretch()

        btn_label = f"Copy {self.mode.upper()}" if self.mode != "txt" else "Copy Transcript"
        self.btn_copy = QPushButton(btn_label)
        self.btn_copy.setProperty("class", "btnOutline")
        self.btn_copy.setStyleSheet("font-size: 11px; padding: 3px 10px;")
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        header.addWidget(self.btn_copy)

        layout.addLayout(header)

        # Editor
        self.editor = QPlainTextEdit()
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        self.editor.setFont(font)
        self.editor.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.editor.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.editor)

    def set_cues(self, cues: List[Dict[str, Any]]):
        """Generates and sets raw text from structured cue list."""
        self._is_programmatic_update = True
        if self.mode == "srt":
            content = build_srt_content(cues)
        elif self.mode == "txt":
            content = build_txt_content(cues)
        else:
            content = build_vtt_content(cues)
        self.editor.setPlainText(content)
        self._is_programmatic_update = False

    def get_text(self) -> str:
        return self.editor.toPlainText()

    def _copy_to_clipboard(self):
        txt = self.editor.toPlainText()
        if txt:
            QApplication.clipboard().setText(txt)
            orig_text = self.btn_copy.text()
            self.btn_copy.setText("Copied!")
            QTimer.singleShot(1500, lambda: self.btn_copy.setText(orig_text))

    def _on_text_changed(self):
        if self._is_programmatic_update:
            return

        txt = self.editor.toPlainText().strip()
        if not txt:
            return

        if self.mode == "srt":
            cues = parse_srt_content(txt)
        else:
            cues = parse_vtt_content(txt)

        if cues:
            self.sig_raw_text_modified.emit(cues)
