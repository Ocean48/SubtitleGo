import os
from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QFrame, QScrollArea, QProgressBar, QMessageBox
)
from PySide6.QtCore import Signal, Qt, QMimeData
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from ...core.queue_manager import QueueManager

SUPPORTED_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv",
    ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma"
}


class DropZoneWidget(QFrame):
    sig_files_dropped = Signal(list)
    sig_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(4)

        lbl_title = QLabel("Drag & Drop Video or Audio Files")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("font-weight: 600; font-size: 13px; color: #f8fafc; background: transparent;")
        layout.addWidget(lbl_title)

        lbl_sub = QLabel("or click to browse from computer")
        lbl_sub.setAlignment(Qt.AlignCenter)
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent;")
        layout.addWidget(lbl_sub)

        lbl_tags = QLabel("MP4 · MKV · MOV · WEBM · MP3 · WAV · M4A")
        lbl_tags.setAlignment(Qt.AlignCenter)
        lbl_tags.setStyleSheet("font-size: 10px; color: #64748b; margin-top: 2px; background: transparent;")
        layout.addWidget(lbl_tags)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.sig_clicked.emit()
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        paths = []
        for url in urls:
            path = url.toLocalFile()
            if os.path.isfile(path):
                ext = os.path.splitext(path)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    paths.append(path)
            elif os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for f in files:
                        ext = os.path.splitext(f)[1].lower()
                        if ext in SUPPORTED_EXTENSIONS:
                            paths.append(os.path.join(root, f))
        if paths:
            self.sig_files_dropped.emit(paths)


class QueueItemWidget(QFrame):
    sig_selected = Signal(str)
    sig_removed = Signal(str)
    sig_retry = Signal(str)

    def __init__(self, item_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.file_id = item_data["file_id"]
        self.is_selected = False
        self._init_ui(item_data)

    def _init_ui(self, item_data: Dict[str, Any]):
        self.setStyleSheet("""
            QueueItemWidget {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px;
            }
            QueueItemWidget:hover {
                border-color: #475569;
                background-color: #24344d;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Top row: Filename, size, status badge, buttons
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.lbl_name = QLabel(item_data["filename"])
        self.lbl_name.setStyleSheet("font-weight: 600; font-size: 12px; color: #f8fafc;")
        self.lbl_name.setToolTip(item_data["filename"])
        self.lbl_name.setWordWrap(True)
        top_row.addWidget(self.lbl_name, stretch=1)

        self.lbl_size = QLabel(f"{item_data.get('size_mb', 0):.1f} MB")
        self.lbl_size.setStyleSheet("font-size: 11px; color: #64748b;")
        top_row.addWidget(self.lbl_size)

        self.lbl_badge = QLabel(item_data.get("status", "queued").upper())
        self.lbl_badge.setStyleSheet(self._get_badge_style(item_data.get("status", "queued")))
        top_row.addWidget(self.lbl_badge)

        self.btn_retry = QPushButton("↺")
        self.btn_retry.setToolTip("Retry transcription")
        self.btn_retry.setFixedSize(24, 24)
        self.btn_retry.setStyleSheet("font-size: 14px; padding: 0;")
        self.btn_retry.setVisible(item_data.get("status") == "error")
        self.btn_retry.clicked.connect(lambda: self.sig_retry.emit(self.file_id))
        top_row.addWidget(self.btn_retry)

        self.btn_remove = QPushButton("✕")
        self.btn_remove.setToolTip("Remove from queue")
        self.btn_remove.setFixedSize(24, 24)
        self.btn_remove.setStyleSheet("font-size: 11px; padding: 0;")
        self.btn_remove.clicked.connect(lambda: self.sig_removed.emit(self.file_id))
        top_row.addWidget(self.btn_remove)

        layout.addLayout(top_row)

        # Bottom row: Stage message and Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(int(item_data.get("progress", 0.0)))
        layout.addWidget(self.progress_bar)

        self.lbl_stage = QLabel(item_data.get("stage_msg", "Queued"))
        self.lbl_stage.setStyleSheet("font-size: 11px; color: #94a3b8;")
        layout.addWidget(self.lbl_stage)

    def _get_badge_style(self, status: str) -> str:
        if status == "completed":
            return "background-color: rgba(34, 197, 94, 0.15); color: #22c55e; border: 1px solid #166534; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: 600;"
        elif status == "processing":
            return "background-color: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid #0369a1; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: 600;"
        elif status == "error":
            return "background-color: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid #991b1b; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: 600;"
        return "background-color: #0f172a; color: #94a3b8; border: 1px solid #334155; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: 600;"

    def update_state(self, status: str, stage_msg: str, progress: float):
        self.lbl_badge.setText(status.upper())
        self.lbl_badge.setStyleSheet(self._get_badge_style(status))
        self.lbl_stage.setText(stage_msg)
        self.progress_bar.setValue(int(progress))
        self.btn_retry.setVisible(status == "error")

    def set_selected(self, selected: bool):
        self.is_selected = selected
        if selected:
            self.setStyleSheet("""
                QueueItemWidget {
                    background-color: #24344d;
                    border: 2px solid #38bdf8;
                    border-radius: 6px;
                    padding: 7px;
                }
            """)
        else:
            self.setStyleSheet("""
                QueueItemWidget {
                    background-color: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    padding: 8px;
                }
                QueueItemWidget:hover {
                    border-color: #475569;
                    background-color: #24344d;
                }
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.sig_selected.emit(self.file_id)
        super().mousePressEvent(event)


class QueueList(QWidget):
    """
    Queue container with dropzone, folder ingestion, action buttons, and progress list.
    """
    sig_item_selected = Signal(str)
    sig_process_batch = Signal()
    sig_retry_item = Signal(str)

    def __init__(self, queue_manager: QueueManager, parent=None):
        super().__init__(parent)
        self.queue_mgr = queue_manager
        self.item_widgets: Dict[str, QueueItemWidget] = {}
        self.selected_file_id: Optional[str] = None
        self._init_ui()

        self.queue_mgr.sig_queue_updated.connect(self._rebuild_list)
        self.queue_mgr.sig_item_status_changed.connect(self._on_item_status_changed)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Dropzone
        self.dropzone = DropZoneWidget(self)
        self.dropzone.sig_files_dropped.connect(self._on_files_dropped)
        self.dropzone.sig_clicked.connect(self._browse_files)
        layout.addWidget(self.dropzone)

        # Folder Picker Bar
        btn_folder = QPushButton("Open Video Folder (Batch Auto-Save)")
        btn_folder.setProperty("class", "btnOutline")
        btn_folder.clicked.connect(self._browse_folder)
        layout.addWidget(btn_folder)

        # Action Bar: Process All Button
        self.btn_process = QPushButton("Generate Subtitles")
        self.btn_process.setProperty("class", "btnPrimary")
        self.btn_process.setEnabled(False)
        self.btn_process.clicked.connect(self.sig_process_batch)
        layout.addWidget(self.btn_process)

        # Queue Summary Bar
        self.summary_frame = QFrame()
        self.summary_frame.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 6px 10px;")
        sum_layout = QHBoxLayout(self.summary_frame)
        sum_layout.setContentsMargins(4, 2, 4, 2)

        self.lbl_stats = QLabel("0 files · 0 done · 0 MB")
        self.lbl_stats.setStyleSheet("font-size: 11px; color: #94a3b8;")
        sum_layout.addWidget(self.lbl_stats)

        sum_layout.addStretch()

        self.btn_zip = QPushButton("Download All (ZIP)")
        self.btn_zip.setProperty("class", "btnOutline")
        self.btn_zip.setEnabled(False)
        self.btn_zip.setStyleSheet("font-size: 11px; padding: 4px 8px;")
        self.btn_zip.clicked.connect(self._on_export_zip)
        sum_layout.addWidget(self.btn_zip)

        layout.addWidget(self.summary_frame)

        # Scrollable File Queue Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: transparent; border: none;")

        self.queue_container = QWidget()
        self.queue_layout = QVBoxLayout(self.queue_container)
        self.queue_layout.setContentsMargins(0, 0, 0, 0)
        self.queue_layout.setSpacing(6)
        self.queue_layout.addStretch()

        self.scroll_area.setWidget(self.queue_container)
        layout.addWidget(self.scroll_area, stretch=1)

    def _browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Media Files",
            "",
            "Media Files (*.mp4 *.mkv *.avi *.mov *.webm *.mp3 *.wav *.m4a *.flac *.ogg *.aac);;All Files (*)"
        )
        if files:
            self._on_files_dropped(files)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Video Folder")
        if folder:
            paths = []
            for root, _, files in os.walk(folder):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in SUPPORTED_EXTENSIONS:
                        paths.append(os.path.join(root, f))
            if paths:
                self._on_files_dropped(paths)

    def _on_files_dropped(self, paths: List[str]):
        added = self.queue_mgr.add_files(paths)
        if added and not self.selected_file_id:
            self.select_item(added[0])

    def _rebuild_list(self):
        # Clear existing item widgets
        for w in self.item_widgets.values():
            w.setParent(None)
            w.deleteLater()
        self.item_widgets.clear()

        # Re-populate
        items = list(self.queue_mgr.items.values())
        total_count = len(items)
        completed_count = sum(1 for it in items if it["status"] == "completed")
        total_size = sum(it.get("size_mb", 0) for it in items)

        self.lbl_stats.setText(f"{total_count} files · {completed_count} done · {total_size:.1f} MB")
        self.btn_process.setEnabled(total_count > 0)
        self.btn_zip.setEnabled(completed_count > 0)

        # Re-add items before stretch
        while self.queue_layout.count() > 0:
            it = self.queue_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        for item in items:
            fid = item["file_id"]
            w = QueueItemWidget(item)
            w.sig_selected.connect(self.select_item)
            w.sig_removed.connect(self.queue_mgr.remove_item)
            w.sig_retry.connect(lambda fid=fid: self.sig_retry_item.emit(fid))
            if fid == self.selected_file_id:
                w.set_selected(True)
            self.queue_layout.addWidget(w)
            self.item_widgets[fid] = w

        self.queue_layout.addStretch()

    def _on_item_status_changed(self, file_id: str, status: str, stage_msg: str, progress: float):
        if file_id in self.item_widgets:
            self.item_widgets[file_id].update_state(status, stage_msg, progress)

        items = list(self.queue_mgr.items.values())
        completed_count = sum(1 for it in items if it["status"] == "completed")
        self.btn_zip.setEnabled(completed_count > 0)

    def select_item(self, file_id: str):
        self.selected_file_id = file_id
        for fid, w in self.item_widgets.items():
            w.set_selected(fid == file_id)
        self.sig_item_selected.emit(file_id)

    def _on_export_zip(self):
        zip_path, _ = QFileDialog.getSaveFileName(
            self, "Save All Subtitles as ZIP", "subtitles_export.zip", "ZIP Archive (*.zip)"
        )
        if zip_path:
            ok = self.queue_mgr.export_zip(zip_path)
            if ok:
                QMessageBox.information(self, "Export Successful", f"Saved all subtitles to:\n{zip_path}")
            else:
                QMessageBox.warning(self, "Export Failed", "No completed subtitles found to export.")
