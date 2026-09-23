import os
from typing import Optional, Dict, Any, List
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QSplitter, QTabWidget, QFileDialog,
    QMessageBox, QStackedWidget, QScrollArea, QDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut

from .styles import get_theme_qss
from ..__version__ import __title__, __version__
from ..core.queue_manager import QueueManager
from ..core.subtitle_formatter import build_srt_content, build_vtt_content
from .widgets.header_bar import HeaderBar
from .widgets.settings_panel import SettingsPanel
from .widgets.queue_list import QueueList
from .widgets.video_player import VideoPlayerWidget
from .widgets.raw_view import RawSubtitleView
from .widgets.subtitle_editor_tab import SubtitleEditorTab


class ShortcutsDialog(QDialog):
    """Help dialog displaying application keyboard shortcuts."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts Reference")
        self.setFixedSize(500, 440)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        lbl_title = QLabel("Keyboard Shortcuts")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(lbl_title)

        shortcuts = [
            ("Space", "Play / Pause video preview"),
            ("Left / Right", "Step -0.1s / +0.1s in video"),
            ("Shift + Left / Right", "Jump -5.0s / +5.0s in video"),
            ("Ctrl + O", "Open media / subtitle files dialog"),
            ("Ctrl + S", "Save & Sync subtitles (.srt & .vtt) in Editor"),
            ("Ctrl + F", "Focus subtitle search filter"),
            ("Ctrl + Z", "Undo subtitle modification"),
            ("Ctrl + Y / Ctrl+Shift+Z", "Redo subtitle modification"),
            ("Delete", "Delete selected subtitle cue"),
            ("F11 / Double-Click", "Toggle Fullscreen video preview"),
            ("Ctrl + /", "Open this shortcuts reference")
        ]

        card = QFrame()
        card.setProperty("class", "cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        for key, desc in shortcuts:
            row = QHBoxLayout()
            lbl_k = QLabel(key)
            lbl_k.setStyleSheet("font-family: monospace; font-weight: 700; color: #38bdf8; min-width: 170px;")
            lbl_d = QLabel(desc)
            lbl_d.setStyleSheet("color: #94a3b8;")
            row.addWidget(lbl_k)
            row.addWidget(lbl_d, stretch=1)
            card_layout.addLayout(row)

        layout.addWidget(card)

        btn_close = QPushButton("Close")
        btn_close.setProperty("class", "btnPrimary")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)


class MainWindow(QMainWindow):
    """
    Main application window for SubtitleGo.
    Features a dual-workspace architecture:
    1. Subtitle Generator: Fast media transcription, model management, synchronized preview, and instant review.
    2. Subtitle Editor & Sync: Dedicated standalone subtitle editor with companion .srt/.vtt auto-detection and dual-sync.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{__title__} v{__version__}")
        self.resize(1300, 840)
        self.setMinimumSize(880, 580)

        self._current_theme = "dark"
        self.queue_mgr = QueueManager(self)
        self.active_file_id: Optional[str] = None
        self.active_cues: List[Dict[str, Any]] = []

        self._init_ui()
        self._setup_shortcuts()
        self._connect_signals()

    def _init_ui(self):
        self.setStyleSheet(get_theme_qss(self._current_theme))

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Header Bar
        self.header_bar = HeaderBar(self)
        root_layout.addWidget(self.header_bar)

        # Top-level Workspace Tabs (Subtitle Generator | Subtitle Editor & Sync)
        self.workspace_tabs = QTabWidget()
        self.workspace_tabs.setContentsMargins(10, 8, 10, 10)

        # Tab 1: Subtitle Generator Workspace
        self.generator_tab = self._create_generator_workspace()
        self.workspace_tabs.addTab(self.generator_tab, "Subtitle Generator")

        # Tab 2: Subtitle Editor & Dual-Format Sync Workspace
        self.editor_tab = SubtitleEditorTab(self)
        self.workspace_tabs.addTab(self.editor_tab, "Subtitle Editor & Sync (.srt / .vtt)")

        root_layout.addWidget(self.workspace_tabs, stretch=1)

    def _create_generator_workspace(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        # Generator Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(6)

        # Left Panel (Tabbed Sidebar: Media Queue | Settings)
        left_card = QFrame()
        left_card.setProperty("class", "cardFrame")
        left_card_layout = QVBoxLayout(left_card)
        left_card_layout.setContentsMargins(8, 8, 8, 8)
        left_card_layout.setSpacing(6)

        self.sidebar_tabs = QTabWidget()

        # Tab 1: Queue List
        self.queue_list = QueueList(self.queue_mgr, self)
        self.sidebar_tabs.addTab(self.queue_list, "Media Queue")

        # Tab 2: Settings Panel inside scroll area
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.settings_panel = SettingsPanel(self)
        settings_scroll.setWidget(self.settings_panel)
        self.sidebar_tabs.addTab(settings_scroll, "Settings")

        left_card_layout.addWidget(self.sidebar_tabs)
        splitter.addWidget(left_card)

        # Right Panel (Studio Inspector, Video Preview, Subtitle Review)
        right_card = QFrame()
        right_card.setProperty("class", "cardFrame")
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)

        # Right Card Header
        right_header = QHBoxLayout()
        self.lbl_inspector_title = QLabel("Media Studio Preview")
        self.lbl_inspector_title.setStyleSheet("font-size: 14px; font-weight: 700;")
        right_header.addWidget(self.lbl_inspector_title)

        self.lbl_active_filename = QLabel("No file selected")
        self.lbl_active_filename.setStyleSheet("color: #38bdf8; border: 1px solid #334155; border-radius: 4px; padding: 2px 8px; font-size: 11px;")
        right_header.addWidget(self.lbl_active_filename)

        right_header.addStretch()

        # Action Buttons: Export & Open in Editor
        self.export_group = QWidget()
        exp_layout = QHBoxLayout(self.export_group)
        exp_layout.setContentsMargins(0, 0, 0, 0)
        exp_layout.setSpacing(6)

        self.btn_open_in_editor = QPushButton("Open in Subtitle Editor →")
        self.btn_open_in_editor.setProperty("class", "btnPrimary")
        self.btn_open_in_editor.setToolTip("Open generated subtitles in the dedicated Subtitle Editor tab")
        self.btn_open_in_editor.clicked.connect(self._on_open_in_editor)
        exp_layout.addWidget(self.btn_open_in_editor)

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
        ph_layout.setSpacing(12)

        lbl_ph_title = QLabel("Welcome to SubtitleGo")
        lbl_ph_title.setAlignment(Qt.AlignCenter)
        lbl_ph_title.setStyleSheet("font-size: 18px; font-weight: 700;")
        ph_layout.addWidget(lbl_ph_title)

        lbl_ph_desc = QLabel(
            "Drop video or audio files into the queue on the left to begin. "
            "SubtitleGo will provide instant playback preview and one-click speech recognition."
        )
        lbl_ph_desc.setAlignment(Qt.AlignCenter)
        lbl_ph_desc.setStyleSheet("font-size: 12px; color: #94a3b8; max-width: 460px;")
        lbl_ph_desc.setWordWrap(True)
        ph_layout.addWidget(lbl_ph_desc)

        btn_ph_open = QPushButton("Open Media Files...")
        btn_ph_open.setProperty("class", "btnPrimary")
        btn_ph_open.clicked.connect(self.queue_list._browse_files)
        ph_layout.addWidget(btn_ph_open, alignment=Qt.AlignCenter)

        self.inspector_stack.addWidget(self.placeholder_widget)

        # Page 1: Active Studio (Video Player + Review Tabs)
        self.studio_widget = QWidget()
        studio_layout = QVBoxLayout(self.studio_widget)
        studio_layout.setContentsMargins(0, 0, 0, 0)
        studio_layout.setSpacing(0)

        studio_splitter = QSplitter(Qt.Vertical)
        studio_splitter.setHandleWidth(5)

        # Video Player
        self.video_player = VideoPlayerWidget(self)
        studio_splitter.addWidget(self.video_player)

        # Bottom Container (Info Bar + Review Tabs)
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 6, 0, 0)
        bottom_layout.setSpacing(6)

        # Subtitle Metadata Info Bar
        self.info_bar = QFrame()
        self.info_bar.setProperty("class", "cardFrame")
        info_layout = QHBoxLayout(self.info_bar)
        info_layout.setContentsMargins(8, 4, 8, 4)
        info_layout.setSpacing(16)

        self.lbl_meta_lang = QLabel("Language: -")
        self.lbl_meta_lang.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 500;")
        info_layout.addWidget(self.lbl_meta_lang)

        self.lbl_meta_duration = QLabel("Duration: -")
        self.lbl_meta_duration.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 500;")
        info_layout.addWidget(self.lbl_meta_duration)

        self.lbl_meta_cues = QLabel("Cues: -")
        self.lbl_meta_cues.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 500;")
        info_layout.addWidget(self.lbl_meta_cues)

        self.lbl_meta_time = QLabel("Processing: -")
        self.lbl_meta_time.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 500;")
        info_layout.addWidget(self.lbl_meta_time)

        info_layout.addStretch()
        bottom_layout.addWidget(self.info_bar)

        # Formatted Review Tabs (SRT View, WebVTT View, Transcript View)
        self.review_tabs = QTabWidget()

        self.srt_view = RawSubtitleView(mode="srt", parent=self)
        self.review_tabs.addTab(self.srt_view, "SRT Format")

        self.vtt_view = RawSubtitleView(mode="vtt", parent=self)
        self.review_tabs.addTab(self.vtt_view, "WebVTT Format")

        self.txt_view = RawSubtitleView(mode="txt", parent=self)
        self.review_tabs.addTab(self.txt_view, "Transcript")

        bottom_layout.addWidget(self.review_tabs, stretch=1)
        studio_splitter.addWidget(bottom_container)

        studio_splitter.setSizes([320, 360])
        studio_layout.addWidget(studio_splitter)

        self.inspector_stack.addWidget(self.studio_widget)
        right_layout.addWidget(self.inspector_stack, stretch=1)

        splitter.addWidget(right_card)

        # Splitter initial sizes: 32% left, 68% right
        splitter.setSizes([380, 840])
        layout.addWidget(splitter)
        return container

    def _setup_shortcuts(self):
        # Spacebar toggles video play/pause
        self.shortcut_space = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.shortcut_space.activated.connect(self._on_space_pressed)

        # Arrow stepping
        self.shortcut_left = QShortcut(QKeySequence(Qt.Key_Left), self)
        self.shortcut_left.activated.connect(lambda: self._active_video_player().step_seconds(-0.1))

        self.shortcut_right = QShortcut(QKeySequence(Qt.Key_Right), self)
        self.shortcut_right.activated.connect(lambda: self._active_video_player().step_seconds(0.1))

        self.shortcut_shift_left = QShortcut(QKeySequence("Shift+Left"), self)
        self.shortcut_shift_left.activated.connect(lambda: self._active_video_player().step_seconds(-5.0))

        self.shortcut_shift_right = QShortcut(QKeySequence("Shift+Right"), self)
        self.shortcut_shift_right.activated.connect(lambda: self._active_video_player().step_seconds(5.0))

        # Fullscreen preview
        self.shortcut_f11 = QShortcut(QKeySequence(Qt.Key_F11), self)
        self.shortcut_f11.activated.connect(lambda: self._active_video_player().toggle_fullscreen())

        # Open file
        self.shortcut_open = QShortcut(QKeySequence("Ctrl+O"), self)
        self.shortcut_open.activated.connect(self._on_ctrl_o_pressed)

        # Help shortcuts dialog
        self.shortcut_help = QShortcut(QKeySequence("Ctrl+/"), self)
        self.shortcut_help.activated.connect(self._show_shortcuts_dialog)

    def _active_video_player(self) -> VideoPlayerWidget:
        if self.workspace_tabs.currentIndex() == 1 and self.editor_tab.video_player.isVisible():
            return self.editor_tab.video_player
        return self.video_player

    def _on_space_pressed(self):
        player = self._active_video_player()
        player.toggle_playback()

    def _on_ctrl_o_pressed(self):
        if self.workspace_tabs.currentIndex() == 1:
            self.editor_tab._browse_subtitle()
        else:
            self.queue_list._browse_files()

    def _connect_signals(self):
        # Header bar signals
        self.header_bar.sig_theme_toggled.connect(self._on_theme_changed)
        self.header_bar.sig_shortcuts_clicked.connect(self._show_shortcuts_dialog)
        self.header_bar.sig_model_status_changed.connect(lambda _: self.settings_panel.sync_model_state())
        self.settings_panel.sig_toggle_model.connect(self.header_bar._on_toggle_model)

        # Queue events
        self.queue_list.sig_item_selected.connect(self._on_item_selected)
        self.queue_list.sig_process_batch.connect(self._on_start_batch)
        self.queue_list.sig_stop_batch.connect(self._on_stop_batch)
        self.queue_list.sig_retry_item.connect(self._on_retry_item)
        self.queue_list.sig_clear_queue.connect(self._on_clear_queue)

        self.queue_mgr.sig_item_completed.connect(self._on_item_completed)
        self.queue_mgr.sig_item_status_changed.connect(self._on_item_status_updated)

        # Raw views modifications sync
        self.srt_view.sig_raw_text_modified.connect(self._on_cues_modified_from_raw)
        self.vtt_view.sig_raw_text_modified.connect(self._on_cues_modified_from_raw)

    def _on_theme_changed(self, theme: str):
        self._current_theme = theme
        self.setStyleSheet(get_theme_qss(theme))
        self.header_bar.update_hardware_status()

    def _show_shortcuts_dialog(self):
        dlg = ShortcutsDialog(self)
        dlg.exec()

    def _on_clear_queue(self):
        self.active_file_id = None
        self.active_cues = []
        self.lbl_active_filename.setText("No file selected")
        self.export_group.setVisible(False)
        self.inspector_stack.setCurrentIndex(0)

    def _on_start_batch(self):
        settings = self.settings_panel.get_settings()
        self.queue_mgr.start_batch(settings)

    def _on_stop_batch(self):
        self.queue_mgr.stop_all()

    def _on_retry_item(self, file_id: str):
        settings = self.settings_panel.get_settings()
        self.queue_mgr.retry_item(file_id, settings)

    def _on_item_status_updated(self, file_id: str, status: str, stage_msg: str, progress: float):
        if self.active_file_id == file_id and status != "completed":
            self.lbl_meta_time.setText("Status: " + stage_msg)

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
            self.srt_view.set_cues([])
            self.vtt_view.set_cues([])
            self.txt_view.set_cues([])
            self.export_group.setVisible(False)
            self.lbl_meta_lang.setText("Language: -")
            self.lbl_meta_duration.setText(f"Size: {item.get('size_mb', 0):.1f} MB")
            self.lbl_meta_cues.setText("Cues: -")
            self.lbl_meta_time.setText("Status: " + item.get("stage_msg", "Queued"))

    def _on_item_completed(self, file_id: str, result: Dict[str, Any]):
        self.header_bar.sync_model_state()
        self.settings_panel.sync_model_state()
        if self.active_file_id == file_id:
            self.active_cues = result.get("segments", [])
            self._display_subtitles(result)

    def _display_subtitles(self, result: Dict[str, Any]):
        cues = result.get("segments", [])
        self.active_cues = cues
        self.video_player.set_cues(cues)
        self.srt_view.set_cues(cues)
        self.vtt_view.set_cues(cues)
        self.txt_view.set_cues(cues)
        self.export_group.setVisible(True)

        self.lbl_meta_lang.setText(f"Language: {result.get('language', 'Auto')}")
        self.lbl_meta_duration.setText(f"Duration: {result.get('duration', 0):.1f}s")
        self.lbl_meta_cues.setText(f"Cues: {len(cues)}")
        self.lbl_meta_time.setText(f"Processing: {result.get('processing_time', '-')}")

    def _on_cues_modified_from_raw(self, updated_cues: List[Dict[str, Any]]):
        self.active_cues = updated_cues
        self.video_player.set_cues(updated_cues)
        self.lbl_meta_cues.setText(f"Cues: {len(updated_cues)}")

    def _on_open_in_editor(self):
        """Handoff generated subtitles to the dedicated Subtitle Editor tab."""
        if not self.active_cues:
            return

        source_media_path = None
        if self.active_file_id and self.active_file_id in self.queue_mgr.items:
            source_media_path = self.queue_mgr.items[self.active_file_id].get("media_path")

        self.editor_tab.load_cues_from_generator(self.active_cues, source_media_path=source_media_path)
        self.workspace_tabs.setCurrentIndex(1)

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
        if hasattr(self, "editor_tab") and hasattr(self.editor_tab, "video_player"):
            self.editor_tab.video_player.player.stop()
        super().closeEvent(event)

