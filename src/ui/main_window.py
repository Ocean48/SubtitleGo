import os
from typing import Optional, Dict, Any, List
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QSplitter, QTabWidget, QFileDialog,
    QMessageBox, QStackedWidget, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut

from .styles import DARK_THEME_QSS
from ..__version__ import __title__, __version__
from ..core.queue_manager import QueueManager
from ..core.subtitle_formatter import build_srt_content, build_vtt_content
from .widgets.header_bar import HeaderBar
from .widgets.settings_panel import SettingsPanel
from .widgets.queue_list import QueueList
from .widgets.video_player import VideoPlayerWidget
from .widgets.cue_editor import CueEditorWidget
from .widgets.raw_view import RawSubtitleView


class MainWindow(QMainWindow):
    """
    Main application window for SubtitleGo.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{__title__} v{__version__}")
        self.resize(1280, 800)
        self.setMinimumSize(800, 520)

        self.queue_mgr = QueueManager(self)
        self.active_file_id: Optional[str] = None
        self.active_cues: List[Dict[str, Any]] = []

        self._init_ui()
        self._setup_shortcuts()
        self._connect_signals()

    def _init_ui(self):
        self.setStyleSheet(DARK_THEME_QSS)

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Header Bar
        self.header_bar = HeaderBar(self)
        root_layout.addWidget(self.header_bar)

        # Main Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setContentsMargins(14, 14, 14, 14)
        splitter.setHandleWidth(8)

        # Left Panel (Source, Settings, Queue in a ScrollArea)
        left_card = QFrame()
        left_card.setProperty("class", "cardFrame")
        left_card_layout = QVBoxLayout(left_card)
        left_card_layout.setContentsMargins(0, 0, 0, 0)
        left_card_layout.setSpacing(0)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        left_content = QWidget()
        left_layout = QVBoxLayout(left_content)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(12)

        # Left Card Header
        left_header = QHBoxLayout()
        lbl_left_title = QLabel("Media Queue & Settings")
        lbl_left_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #f8fafc;")
        left_header.addWidget(lbl_left_title)
        left_header.addStretch()

        self.btn_reset_queue = QPushButton("Reset Queue")
        self.btn_reset_queue.setProperty("class", "btnOutline")
        self.btn_reset_queue.setStyleSheet("font-size: 11px; padding: 3px 8px;")
        self.btn_reset_queue.clicked.connect(self._on_reset_queue)
        left_header.addWidget(self.btn_reset_queue)
        left_layout.addLayout(left_header)

        # Settings Panel
        self.settings_panel = SettingsPanel(self)
        left_layout.addWidget(self.settings_panel)

        # Queue List & Dropzone
        self.queue_list = QueueList(self.queue_mgr, self)
        left_layout.addWidget(self.queue_list, stretch=1)

        left_scroll.setWidget(left_content)
        left_card_layout.addWidget(left_scroll)
        splitter.addWidget(left_card)

        # Right Panel (Inspector, Video Preview, Cue Studio)
        right_card = QFrame()
        right_card.setProperty("class", "cardFrame")
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(10)

        # Right Card Header
        right_header = QHBoxLayout()
        self.lbl_inspector_title = QLabel("Subtitle Preview & Studio")
        self.lbl_inspector_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #f8fafc;")
        right_header.addWidget(self.lbl_inspector_title)

        self.lbl_active_filename = QLabel("No file selected")
        self.lbl_active_filename.setStyleSheet("background-color: #0f172a; color: #38bdf8; border: 1px solid #334155; border-radius: 4px; padding: 2px 8px; font-size: 11px;")
        right_header.addWidget(self.lbl_active_filename)

        right_header.addStretch()

        # Export Buttons
        self.export_group = QWidget()
        exp_layout = QHBoxLayout(self.export_group)
        exp_layout.setContentsMargins(0, 0, 0, 0)
        exp_layout.setSpacing(6)

        self.btn_export_srt = QPushButton("Download .SRT")
        self.btn_export_srt.setProperty("class", "btnOutline")
        self.btn_export_srt.clicked.connect(self._export_active_srt)
        exp_layout.addWidget(self.btn_export_srt)

        self.btn_export_vtt = QPushButton("Download .VTT")
        self.btn_export_vtt.setProperty("class", "btnOutline")
        self.btn_export_vtt.clicked.connect(self._export_active_vtt)
        exp_layout.addWidget(self.btn_export_vtt)

        self.export_group.setVisible(False)
        right_header.addWidget(self.export_group)

        right_layout.addLayout(right_header)

        # Right Content Stack (Empty Placeholder vs Active Studio)
        self.inspector_stack = QStackedWidget()

        # Page 0: Empty Placeholder
        self.placeholder_widget = QWidget()
        ph_layout = QVBoxLayout(self.placeholder_widget)
        ph_layout.setAlignment(Qt.AlignCenter)
        ph_layout.setSpacing(10)

        lbl_ph_title = QLabel("No Media Active")
        lbl_ph_title.setAlignment(Qt.AlignCenter)
        lbl_ph_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #f8fafc;")
        ph_layout.addWidget(lbl_ph_title)

        lbl_ph_desc = QLabel("Drag a video or audio file into the queue to load instant preview and subtitle generation.")
        lbl_ph_desc.setAlignment(Qt.AlignCenter)
        lbl_ph_desc.setStyleSheet("font-size: 12px; color: #94a3b8; max-width: 400px;")
        lbl_ph_desc.setWordWrap(True)
        ph_layout.addWidget(lbl_ph_desc)

        self.inspector_stack.addWidget(self.placeholder_widget)

        # Page 1: Active Studio (Video + Tabs inside a vertical splitter)
        self.studio_widget = QWidget()
        studio_layout = QVBoxLayout(self.studio_widget)
        studio_layout.setContentsMargins(0, 0, 0, 0)
        studio_layout.setSpacing(0)

        studio_splitter = QSplitter(Qt.Vertical)
        studio_splitter.setHandleWidth(6)

        # Video Player
        self.video_player = VideoPlayerWidget(self)
        studio_splitter.addWidget(self.video_player)

        # Bottom Studio Container (Info Bar + Tabs)
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 8, 0, 0)
        bottom_layout.setSpacing(8)

        # Subtitle Info Bar
        self.info_bar = QFrame()
        self.info_bar.setStyleSheet("background-color: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 4px 10px;")
        info_layout = QHBoxLayout(self.info_bar)
        info_layout.setContentsMargins(4, 2, 4, 2)
        info_layout.setSpacing(16)

        self.lbl_meta_lang = QLabel("Language: -")
        self.lbl_meta_lang.setStyleSheet("font-size: 11px; color: #94a3b8;")
        info_layout.addWidget(self.lbl_meta_lang)

        self.lbl_meta_duration = QLabel("Duration: -")
        self.lbl_meta_duration.setStyleSheet("font-size: 11px; color: #94a3b8;")
        info_layout.addWidget(self.lbl_meta_duration)

        self.lbl_meta_cues = QLabel("Cues: -")
        self.lbl_meta_cues.setStyleSheet("font-size: 11px; color: #94a3b8;")
        info_layout.addWidget(self.lbl_meta_cues)

        self.lbl_meta_time = QLabel("Processing: -")
        self.lbl_meta_time.setStyleSheet("font-size: 11px; color: #94a3b8;")
        info_layout.addWidget(self.lbl_meta_time)

        info_layout.addStretch()
        bottom_layout.addWidget(self.info_bar)

        # Tabs for Cue Editor, SRT View, WebVTT View
        self.tabs = QTabWidget()
        
        self.cue_editor = CueEditorWidget(self)
        self.tabs.addTab(self.cue_editor, "Interactive Cues")

        self.srt_view = RawSubtitleView(mode="srt", parent=self)
        self.tabs.addTab(self.srt_view, "SRT View")

        self.vtt_view = RawSubtitleView(mode="vtt", parent=self)
        self.tabs.addTab(self.vtt_view, "WebVTT View")

        bottom_layout.addWidget(self.tabs, stretch=1)
        studio_splitter.addWidget(bottom_container)

        studio_splitter.setSizes([320, 360])
        studio_layout.addWidget(studio_splitter)

        self.inspector_stack.addWidget(self.studio_widget)
        right_layout.addWidget(self.inspector_stack, stretch=1)

        splitter.addWidget(right_card)

        # Set Splitter ratio 35% left, 65% right
        splitter.setSizes([420, 800])
        root_layout.addWidget(splitter, stretch=1)

    def _setup_shortcuts(self):
        # Spacebar toggles video play/pause
        self.shortcut_space = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.shortcut_space.activated.connect(self.video_player.toggle_playback)

        # Ctrl+O opens file dialog
        self.shortcut_open = QShortcut(QKeySequence("Ctrl+O"), self)
        self.shortcut_open.activated.connect(self.queue_list._browse_files)

    def _connect_signals(self):
        # Queue events
        self.queue_list.sig_item_selected.connect(self._on_item_selected)
        self.queue_list.sig_process_batch.connect(self._on_start_batch)
        self.queue_list.sig_retry_item.connect(self._on_retry_item)

        self.queue_mgr.sig_item_completed.connect(self._on_item_completed)

        # Player position syncs to Cue Editor
        self.video_player.sig_position_changed.connect(self.cue_editor.highlight_active_time)

        # Cue Editor click seeks video
        self.cue_editor.sig_seek_requested.connect(self.video_player.seek_to_seconds)

        # Bidirectional Cue updates
        self.cue_editor.sig_cues_modified.connect(self._on_cues_modified_from_table)
        self.srt_view.sig_raw_text_modified.connect(self._on_cues_modified_from_raw)
        self.vtt_view.sig_raw_text_modified.connect(self._on_cues_modified_from_raw)

    def _on_reset_queue(self):
        self.queue_mgr.clear_all()
        self.active_file_id = None
        self.active_cues = []
        self.lbl_active_filename.setText("No file selected")
        self.export_group.setVisible(False)
        self.inspector_stack.setCurrentIndex(0)

    def _on_start_batch(self):
        settings = self.settings_panel.get_settings()
        self.queue_mgr.start_batch(settings)

    def _on_retry_item(self, file_id: str):
        settings = self.settings_panel.get_settings()
        self.queue_mgr.retry_item(file_id, settings)

    def _on_item_selected(self, file_id: str):
        if file_id not in self.queue_mgr.items:
            return

        self.active_file_id = file_id
        item = self.queue_mgr.items[file_id]

        self.lbl_active_filename.setText(item["filename"])
        self.inspector_stack.setCurrentIndex(1)

        # Load video in player
        self.video_player.load_media(item["media_path"])

        # If already completed, load subtitle data
        result = item.get("result")
        if result and result.get("segments"):
            self.active_cues = result["segments"]
            self._display_subtitles(result)
        else:
            self.active_cues = []
            self.video_player.set_cues([])
            self.cue_editor.set_cues([])
            self.srt_view.set_cues([])
            self.vtt_view.set_cues([])
            self.export_group.setVisible(False)
            self.lbl_meta_lang.setText("Language: -")
            self.lbl_meta_duration.setText(f"Duration: {item.get('size_mb', 0):.1f} MB")
            self.lbl_meta_cues.setText("Cues: -")
            self.lbl_meta_time.setText("Status: " + item.get("stage_msg", "Queued"))

    def _on_item_completed(self, file_id: str, result: Dict[str, Any]):
        if self.active_file_id == file_id:
            self.active_cues = result.get("segments", [])
            self._display_subtitles(result)

    def _display_subtitles(self, result: Dict[str, Any]):
        cues = result.get("segments", [])
        self.active_cues = cues
        self.video_player.set_cues(cues)
        self.cue_editor.set_cues(cues)
        self.srt_view.set_cues(cues)
        self.vtt_view.set_cues(cues)
        self.export_group.setVisible(True)

        self.lbl_meta_lang.setText(f"Language: {result.get('language', 'Auto')}")
        self.lbl_meta_duration.setText(f"Duration: {result.get('duration', 0):.1f}s")
        self.lbl_meta_cues.setText(f"Cues: {len(cues)}")
        self.lbl_meta_time.setText(f"Processing: {result.get('processing_time', '-')}")

    def _on_cues_modified_from_table(self, updated_cues: List[Dict[str, Any]]):
        self.active_cues = updated_cues
        self.video_player.set_cues(updated_cues)
        self.srt_view.set_cues(updated_cues)
        self.vtt_view.set_cues(updated_cues)
        self.lbl_meta_cues.setText(f"Cues: {len(updated_cues)}")

    def _on_cues_modified_from_raw(self, updated_cues: List[Dict[str, Any]]):
        self.active_cues = updated_cues
        self.video_player.set_cues(updated_cues)
        self.cue_editor.set_cues(updated_cues)
        self.lbl_meta_cues.setText(f"Cues: {len(updated_cues)}")

    def _export_active_srt(self):
        if not self.active_cues:
            return
        default_name = "subtitles.srt"
        if self.active_file_id and self.active_file_id in self.queue_mgr.items:
            base = os.path.splitext(self.queue_mgr.items[self.active_file_id]["filename"])[0]
            default_name = f"{base}.srt"

        path, _ = QFileDialog.getSaveFileName(self, "Export Subtitles (SRT)", default_name, "SubRip Subtitle (*.srt)")
        if path:
            content = build_srt_content(self.active_cues)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            QMessageBox.information(self, "Exported", f"Successfully saved:\n{path}")

    def _export_active_vtt(self):
        if not self.active_cues:
            return
        default_name = "subtitles.vtt"
        if self.active_file_id and self.active_file_id in self.queue_mgr.items:
            base = os.path.splitext(self.queue_mgr.items[self.active_file_id]["filename"])[0]
            default_name = f"{base}.vtt"

        path, _ = QFileDialog.getSaveFileName(self, "Export Subtitles (WebVTT)", default_name, "WebVTT Subtitle (*.vtt)")
        if path:
            content = build_vtt_content(self.active_cues)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            QMessageBox.information(self, "Exported", f"Successfully saved:\n{path}")

    def closeEvent(self, event):
        self.queue_mgr.stop_all()
        if hasattr(self, "video_player") and hasattr(self.video_player, "player"):
            self.video_player.player.stop()
        super().closeEvent(event)
