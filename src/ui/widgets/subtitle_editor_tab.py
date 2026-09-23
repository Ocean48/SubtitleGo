import os
from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QFrame, QCheckBox, QMessageBox, QSplitter
)
from PySide6.QtCore import Signal, Qt, QMimeData
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QShortcut, QKeySequence

from ...core.subtitle_formatter import (
    parse_srt_content,
    parse_vtt_content,
    build_srt_content,
    build_vtt_content
)
from .cue_editor import CueEditorWidget
from .video_player import VideoPlayerWidget


SUPPORTED_SUBTITLE_EXTS = {".srt", ".vtt"}
SUPPORTED_MEDIA_EXTS = {
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv",
    ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"
}


class SubtitleEditorTab(QWidget):
    """
    Dedicated Subtitle Editor workspace.
    Allows opening existing .srt / .vtt files, editing cues with full undo/redo,
    optional video reference preview, and automatic dual-format (.srt & .vtt) synchronization on save.
    """
    sig_status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

        self.current_subtitle_path: Optional[str] = None
        self.companion_subtitle_path: Optional[str] = None
        self.current_video_path: Optional[str] = None
        self.cues: List[Dict[str, Any]] = []

        self._init_ui()
        self._setup_shortcuts()
        self._connect_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Top Control & File Management Card
        self.top_card = QFrame()
        self.top_card.setProperty("class", "cardFrame")
        top_layout = QVBoxLayout(self.top_card)
        top_layout.setContentsMargins(12, 10, 12, 10)
        top_layout.setSpacing(8)

        # Action Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_open_subtitle = QPushButton("Open Subtitle (.srt / .vtt)...")
        self.btn_open_subtitle.setProperty("class", "btnPrimary")
        self.btn_open_subtitle.setToolTip("Open an existing SRT or WebVTT subtitle file")
        self.btn_open_subtitle.clicked.connect(self._browse_subtitle)
        btn_row.addWidget(self.btn_open_subtitle)

        self.btn_open_video = QPushButton("Load Video Reference...")
        self.btn_open_video.setProperty("class", "btnSecondary")
        self.btn_open_video.setToolTip("Load a video file to synchronize playback while editing")
        self.btn_open_video.clicked.connect(self._browse_video)
        btn_row.addWidget(self.btn_open_video)

        btn_row.addStretch()

        self.btn_save_sync = QPushButton("Save & Sync (Ctrl+S)")
        self.btn_save_sync.setProperty("class", "btnSuccess")
        self.btn_save_sync.setToolTip("Save subtitle changes and automatically synchronize companion .srt / .vtt file")
        self.btn_save_sync.setEnabled(False)
        self.btn_save_sync.clicked.connect(self.save_and_sync)
        btn_row.addWidget(self.btn_save_sync)

        self.btn_export_as = QPushButton("Export As...")
        self.btn_export_as.setProperty("class", "btnOutline")
        self.btn_export_as.setToolTip("Export subtitles to a new file or directory")
        self.btn_export_as.setEnabled(False)
        self.btn_export_as.clicked.connect(self._export_as)
        btn_row.addWidget(self.btn_export_as)

        self.btn_clear = QPushButton("Clear All")
        self.btn_clear.setProperty("class", "btnGhost")
        self.btn_clear.setToolTip("Clear all loaded subtitle cues and media reference")
        self.btn_clear.setEnabled(False)
        self.btn_clear.clicked.connect(self.clear_all)
        btn_row.addWidget(self.btn_clear)

        top_layout.addLayout(btn_row)

        # Status & Sync Options Row
        status_row = QHBoxLayout()
        status_row.setSpacing(10)

        self.lbl_file_info = QLabel("No subtitle file loaded. Drop .srt / .vtt here or click 'Open Subtitle'.")
        self.lbl_file_info.setStyleSheet("font-size: 12px; font-weight: 500;")
        status_row.addWidget(self.lbl_file_info, stretch=1)

        self.lbl_companion_badge = QLabel("[No Companion File]")
        self.lbl_companion_badge.setStyleSheet(
            "background-color: rgba(148, 163, 184, 0.12); color: #94a3b8; "
            "border: 1px solid #475569; border-radius: 4px; padding: 2px 8px; font-size: 11px;"
        )
        self.lbl_companion_badge.setVisible(False)
        status_row.addWidget(self.lbl_companion_badge)

        self.chk_sync_companion = QCheckBox("Auto-sync companion format on save")
        self.chk_sync_companion.setChecked(True)
        self.chk_sync_companion.setStyleSheet("font-size: 11px; font-weight: 500;")
        self.chk_sync_companion.setToolTip(
            "When enabled, saving an .srt automatically updates/creates the matching .vtt file (and vice versa)"
        )
        status_row.addWidget(self.chk_sync_companion)

        top_layout.addLayout(status_row)
        layout.addWidget(self.top_card)

        # Main Splitter (Optional Video Preview on top, Cue Editor on bottom)
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setHandleWidth(5)

        # Video Player (Collapsible / Hidden until video loaded)
        self.video_player = VideoPlayerWidget(self)
        self.video_player.setVisible(False)
        self.splitter.addWidget(self.video_player)

        # Interactive Cue Editor
        self.editor_card = QFrame()
        self.editor_card.setProperty("class", "cardFrame")
        editor_layout = QVBoxLayout(self.editor_card)
        editor_layout.setContentsMargins(10, 10, 10, 10)
        editor_layout.setSpacing(8)

        self.cue_editor = CueEditorWidget(self)
        editor_layout.addWidget(self.cue_editor)
        self.splitter.addWidget(self.editor_card)

        layout.addWidget(self.splitter, stretch=1)

    def _setup_shortcuts(self):
        shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
        shortcut_save.activated.connect(self.save_and_sync)

    def _connect_signals(self):
        self.cue_editor.sig_cues_modified.connect(self._on_cues_modified)
        self.cue_editor.sig_seek_requested.connect(self.video_player.seek_to_seconds)
        self.video_player.sig_position_changed.connect(self.cue_editor.highlight_active_time)

    def _on_cues_modified(self, cues: List[Dict[str, Any]]):
        self.cues = cues
        self.video_player.set_cues(cues)
        self.btn_save_sync.setEnabled(True)
        self.btn_export_as.setEnabled(len(cues) > 0)
        self.btn_clear.setEnabled(True)

    def _browse_subtitle(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Subtitle File",
            "",
            "Subtitle Files (*.srt *.vtt);;SubRip Subtitle (*.srt);;WebVTT Subtitle (*.vtt);;All Files (*)"
        )
        if path:
            self.load_subtitle_file(path)

    def _browse_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Reference Video",
            "",
            "Media Files (*.mp4 *.mkv *.avi *.mov *.webm *.mp3 *.wav *.m4a *.flac *.ogg *.aac);;All Files (*)"
        )
        if path:
            self.load_reference_video(path)

    def load_subtitle_file(self, file_path: str):
        """Loads and parses an .srt or .vtt subtitle file."""
        if not os.path.isfile(file_path):
            QMessageBox.warning(self, "Error", f"File not found: {file_path}")
            return

        ext = os.path.splitext(file_path)[1].lower()
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            if ext == ".srt":
                cues = parse_srt_content(content)
            elif ext == ".vtt":
                cues = parse_vtt_content(content)
            else:
                # Try SRT first, then VTT
                cues = parse_srt_content(content) or parse_vtt_content(content)

            if not cues:
                QMessageBox.warning(self, "Empty Subtitle", "No valid subtitle cues found in file.")
                return

            self.current_subtitle_path = os.path.abspath(file_path)
            self.cues = cues
            self.cue_editor.set_cues(cues, record_history=False)
            self.video_player.set_cues(cues)

            self.btn_save_sync.setEnabled(True)
            self.btn_export_as.setEnabled(True)
            self.btn_clear.setEnabled(True)

            self._detect_companion_file()
            self._detect_companion_video()

            fn = os.path.basename(file_path)
            self.lbl_file_info.setText(f"Active Subtitle: {fn} ({len(cues)} cues)")

        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to open subtitle file:\n{e}")

    def _detect_companion_file(self):
        """Detects if matching companion format (.srt <-> .vtt) exists in same folder."""
        if not self.current_subtitle_path:
            self.lbl_companion_badge.setVisible(False)
            return

        base, ext = os.path.splitext(self.current_subtitle_path)
        ext = ext.lower()
        other_ext = ".vtt" if ext == ".srt" else ".srt"
        companion_candidate = base + other_ext

        self.lbl_companion_badge.setVisible(True)
        if os.path.isfile(companion_candidate):
            self.companion_subtitle_path = companion_candidate
            c_name = os.path.basename(companion_candidate)
            self.lbl_companion_badge.setText(f"[Companion {c_name} detected]")
            self.lbl_companion_badge.setStyleSheet(
                "background-color: rgba(34, 197, 94, 0.15); color: #22c55e; "
                "border: 1px solid #166534; border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 600;"
            )
        else:
            self.companion_subtitle_path = companion_candidate
            c_name = os.path.basename(companion_candidate)
            self.lbl_companion_badge.setText(f"[Companion {c_name} will be created]")
            self.lbl_companion_badge.setStyleSheet(
                "background-color: rgba(56, 189, 248, 0.15); color: #38bdf8; "
                "border: 1px solid #0369a1; border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 500;"
            )

    def _detect_companion_video(self):
        """Checks if a media file with the same base name exists in the folder."""
        if not self.current_subtitle_path or self.current_video_path:
            return

        base, _ = os.path.splitext(self.current_subtitle_path)
        for ext in SUPPORTED_MEDIA_EXTS:
            v_candidate = base + ext
            if os.path.isfile(v_candidate):
                self.load_reference_video(v_candidate)
                break

    def load_reference_video(self, video_path: str):
        """Loads video reference into the video preview widget."""
        if os.path.isfile(video_path):
            self.current_video_path = os.path.abspath(video_path)
            self.video_player.load_media(self.current_video_path)
            self.video_player.setVisible(True)
            self.video_player.set_cues(self.cues)
            self.splitter.setSizes([260, 420])
            self.btn_open_video.setText(f"Video: {os.path.basename(video_path)}")
            self.btn_clear.setEnabled(True)

    def load_cues_from_generator(
        self,
        cues: List[Dict[str, Any]],
        source_media_path: Optional[str] = None
    ):
        """Handoff method called when sending generated subtitles to the editor."""
        self.cues = cues
        self.cue_editor.set_cues(cues, record_history=False)
        self.video_player.set_cues(cues)
        self.btn_save_sync.setEnabled(True)
        self.btn_export_as.setEnabled(True)
        self.btn_clear.setEnabled(True)

        if source_media_path and os.path.isfile(source_media_path):
            self.load_reference_video(source_media_path)
            base, _ = os.path.splitext(source_media_path)
            self.current_subtitle_path = base + ".srt"
            self._detect_companion_file()
            self.lbl_file_info.setText(f"Active Subtitle: {os.path.basename(base)}.srt ({len(cues)} cues)")
        else:
            self.lbl_file_info.setText(f"Generated Subtitles ({len(cues)} cues loaded)")

    def clear_all(self):
        """Clears all loaded subtitle cues, companion paths, and media references."""
        if self.cues or self.current_subtitle_path or self.current_video_path:
            res = QMessageBox.question(
                self,
                "Clear Subtitle Editor",
                "Are you sure you want to clear all loaded subtitle cues and media?",
                QMessageBox.Yes | QMessageBox.No
            )
            if res != QMessageBox.Yes:
                return

        self.current_subtitle_path = None
        self.companion_subtitle_path = None
        self.current_video_path = None
        self.cues = []

        self.cue_editor.set_cues([], record_history=False)
        if hasattr(self.video_player, "player"):
            self.video_player.player.stop()
        self.video_player.set_cues([])
        self.video_player.setVisible(False)

        self.btn_open_video.setText("Load Video Reference...")
        self.btn_save_sync.setEnabled(False)
        self.btn_export_as.setEnabled(False)
        self.btn_clear.setEnabled(False)
        self.lbl_file_info.setText("No subtitle file loaded. Drop .srt / .vtt here or click 'Open Subtitle'.")
        self.lbl_companion_badge.setVisible(False)

    def save_and_sync(self):
        """
        Saves current subtitle cues to disk.
        If companion sync is enabled, writes both .srt and .vtt formats.
        """
        if not self.cues:
            return

        if not self.current_subtitle_path:
            self._export_as()
            return

        try:
            srt_content = build_srt_content(self.cues)
            vtt_content = build_vtt_content(self.cues)

            ext = os.path.splitext(self.current_subtitle_path)[1].lower()
            primary_content = srt_content if ext == ".srt" else vtt_content

            # Write Primary File
            with open(self.current_subtitle_path, "w", encoding="utf-8") as f:
                f.write(primary_content)

            saved_files = [os.path.basename(self.current_subtitle_path)]

            # Write Companion File if sync enabled
            if self.chk_sync_companion.isChecked():
                base, _ = os.path.splitext(self.current_subtitle_path)
                companion_path = base + (".vtt" if ext == ".srt" else ".srt")
                companion_content = vtt_content if ext == ".srt" else srt_content

                with open(companion_path, "w", encoding="utf-8") as f:
                    f.write(companion_content)

                self.companion_subtitle_path = companion_path
                saved_files.append(os.path.basename(companion_path))
                self._detect_companion_file()

            msg = " & ".join(saved_files)
            QMessageBox.information(
                self,
                "Saved & Synchronized",
                f"Successfully saved and synchronized:\n• " + "\n• ".join(saved_files)
            )

        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save subtitle files:\n{e}")

    def _export_as(self):
        """Allows exporting to a custom path."""
        if not self.cues:
            return

        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Subtitles As",
            self.current_subtitle_path or "subtitles.srt",
            "SubRip Subtitle (*.srt);;WebVTT Subtitle (*.vtt)"
        )
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()
        content = build_vtt_content(self.cues) if ext == ".vtt" else build_srt_content(self.cues)

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.current_subtitle_path = os.path.abspath(path)
            self._detect_companion_file()
            QMessageBox.information(self, "Exported", f"Saved subtitles to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export subtitle file:\n{e}")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        for url in urls:
            path = url.toLocalFile()
            if os.path.isfile(path):
                ext = os.path.splitext(path)[1].lower()
                if ext in SUPPORTED_SUBTITLE_EXTS:
                    self.load_subtitle_file(path)
                    break
                elif ext in SUPPORTED_MEDIA_EXTS:
                    self.load_reference_video(path)
                    break
