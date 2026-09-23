import os
import subprocess
import sys
from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QFrame, QScrollArea, QProgressBar, QMessageBox,
    QMenu
)
from PySide6.QtCore import Signal, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent, QDesktopServices

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
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(4)

        lbl_title = QLabel("Drag and Drop Media Files")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("font-weight: 700; font-size: 13px; background: transparent;")
        layout.addWidget(lbl_title)

        lbl_sub = QLabel("or click to browse files from your computer")
        lbl_sub.setAlignment(Qt.AlignCenter)
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent;")
        layout.addWidget(lbl_sub)

        lbl_tags = QLabel("MP4 · MKV · MOV · WEBM · MP3 · WAV · M4A · FLAC")
        lbl_tags.setAlignment(Qt.AlignCenter)
        lbl_tags.setStyleSheet("font-size: 10px; color: #64748b; margin-top: 3px; background: transparent;")
        layout.addWidget(lbl_tags)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.sig_clicked.emit()
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("dragging", True)
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, event: QDragLeaveEvent):
        self.setProperty("dragging", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event: QDropEvent):
        self.setProperty("dragging", False)
        self.style().unpolish(self)
        self.style().polish(self)
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
    sig_stop = Signal(str)
    sig_move = Signal(str, int)  # file_id, direction (-1 up, +1 down)

    def __init__(self, item_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.file_id = item_data["file_id"]
        self.media_path = item_data.get("media_path", "")
        self.current_status = item_data.get("status", "queued")
        self.is_selected = False
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._init_ui(item_data)

    def _init_ui(self, item_data: Dict[str, Any]):
        self.setProperty("class", "cardFrame")
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Top row: Filename, size, status badge, buttons
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        self.lbl_name = QLabel(item_data["filename"])
        self.lbl_name.setStyleSheet("font-weight: 600; font-size: 12px;")
        self.lbl_name.setToolTip(self.media_path or item_data["filename"])
        top_row.addWidget(self.lbl_name, stretch=1)

        self.lbl_size = QLabel(f"{item_data.get('size_mb', 0):.1f} MB")
        self.lbl_size.setStyleSheet("font-size: 11px; color: #64748b;")
        top_row.addWidget(self.lbl_size)

        self.lbl_badge = QLabel(self.current_status.upper())
        self._apply_badge_style(self.current_status)
        top_row.addWidget(self.lbl_badge)

        # Stop button (visible while processing)
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setToolTip("Stop transcribing this file")
        self.btn_stop.setProperty("class", "btnDanger")
        self.btn_stop.setStyleSheet("font-size: 11px; padding: 2px 8px;")
        self.btn_stop.setVisible(self.current_status == "processing")
        self.btn_stop.clicked.connect(lambda: self.sig_stop.emit(self.file_id))
        top_row.addWidget(self.btn_stop)

        # Retry button (visible on error or cancelled)
        self.btn_retry = QPushButton("Retry")
        self.btn_retry.setToolTip("Retry transcription")
        self.btn_retry.setProperty("class", "btnSecondary")
        self.btn_retry.setStyleSheet("font-size: 11px; padding: 2px 8px;")
        self.btn_retry.setVisible(self.current_status in ["error", "cancelled"])
        self.btn_retry.clicked.connect(lambda: self.sig_retry.emit(self.file_id))
        top_row.addWidget(self.btn_retry)

        # Remove button
        self.btn_remove = QPushButton("✕")
        self.btn_remove.setToolTip("Remove from queue")
        self.btn_remove.setProperty("class", "btnGhost")
        self.btn_remove.setFixedSize(22, 22)
        self.btn_remove.clicked.connect(lambda: self.sig_removed.emit(self.file_id))
        top_row.addWidget(self.btn_remove)

        layout.addLayout(top_row)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(int(item_data.get("progress", 0.0)))
        layout.addWidget(self.progress_bar)

        # Stage message
        self.lbl_stage = QLabel(item_data.get("stage_msg", "Queued"))
        self.lbl_stage.setStyleSheet("font-size: 11px; color: #94a3b8;")
        layout.addWidget(self.lbl_stage)

    def _apply_badge_style(self, status: str):
        self.current_status = status
        self.lbl_badge.setText(status.upper())
        if status == "completed":
            self.lbl_badge.setStyleSheet(
                "background-color: rgba(34, 197, 94, 0.15); color: #22c55e; "
                "border: 1px solid #166534; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: 600;"
            )
        elif status == "processing":
            self.lbl_badge.setStyleSheet(
                "background-color: rgba(56, 189, 248, 0.15); color: #38bdf8; "
                "border: 1px solid #0369a1; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: 600;"
            )
        elif status == "cancelled":
            self.lbl_badge.setStyleSheet(
                "background-color: rgba(245, 158, 11, 0.15); color: #f59e0b; "
                "border: 1px solid #854d0e; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: 600;"
            )
        elif status == "error":
            self.lbl_badge.setStyleSheet(
                "background-color: rgba(239, 68, 68, 0.15); color: #ef4444; "
                "border: 1px solid #991b1b; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: 600;"
            )
        else:
            self.lbl_badge.setStyleSheet(
                "background-color: rgba(148, 163, 184, 0.12); color: #94a3b8; "
                "border: 1px solid #475569; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: 600;"
            )

    def update_state(self, status: str, stage_msg: str, progress: float):
        self._apply_badge_style(status)
        self.lbl_stage.setText(stage_msg)
        self.progress_bar.setValue(int(progress))
        self.btn_stop.setVisible(status == "processing")
        self.btn_retry.setVisible(status in ["error", "cancelled"])

    def set_selected(self, selected: bool):
        self.is_selected = selected
        if selected:
            self.setStyleSheet("""
                QFrame.cardFrame {
                    border: 2px solid #0284c7;
                    background-color: rgba(2, 132, 199, 0.12);
                }
            """)
        else:
            self.setStyleSheet("")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.sig_selected.emit(self.file_id)
        super().mousePressEvent(event)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        act_select = menu.addAction("Select & Preview")
        act_select.triggered.connect(lambda: self.sig_selected.emit(self.file_id))

        if self.media_path and os.path.exists(self.media_path):
            act_folder = menu.addAction("Show in File Explorer")
            act_folder.triggered.connect(self._open_in_explorer)

        menu.addSeparator()

        if self.current_status == "processing":
            act_stop = menu.addAction("Stop Processing")
            act_stop.triggered.connect(lambda: self.sig_stop.emit(self.file_id))
        else:
            act_retry = menu.addAction("Re-transcribe File")
            act_retry.triggered.connect(lambda: self.sig_retry.emit(self.file_id))

        menu.addSeparator()
        act_up = menu.addAction("Move Up")
        act_up.triggered.connect(lambda: self.sig_move.emit(self.file_id, -1))

        act_down = menu.addAction("Move Down")
        act_down.triggered.connect(lambda: self.sig_move.emit(self.file_id, 1))

        menu.addSeparator()
        act_remove = menu.addAction("Remove from Queue")
        act_remove.triggered.connect(lambda: self.sig_removed.emit(self.file_id))

        menu.exec(self.mapToGlobal(pos))

    def _open_in_explorer(self):
        if self.media_path and os.path.exists(self.media_path):
            folder = os.path.dirname(self.media_path)
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", os.path.normpath(self.media_path)])
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(folder))


class QueueList(QWidget):
    """
    Queue container with dropzone, folder ingestion, action buttons, reordering, and progress list.
    """
    sig_item_selected = Signal(str)
    sig_process_batch = Signal()
    sig_stop_batch = Signal()
    sig_retry_item = Signal(str)
    sig_stop_item = Signal(str)
    sig_clear_queue = Signal()

    def __init__(self, queue_manager: QueueManager, parent=None):
        super().__init__(parent)
        self.queue_mgr = queue_manager
        self.item_widgets: Dict[str, QueueItemWidget] = {}
        self.selected_file_id: Optional[str] = None
        self._init_ui()

        self.queue_mgr.sig_queue_updated.connect(self._rebuild_list)
        self.queue_mgr.sig_item_status_changed.connect(self._on_item_status_changed)
        self.queue_mgr.sig_batch_finished.connect(self._on_batch_finished)
        self.queue_mgr.sig_batch_stopped.connect(self._on_batch_stopped)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Dropzone
        self.dropzone = DropZoneWidget(self)
        self.dropzone.sig_files_dropped.connect(self._on_files_dropped)
        self.dropzone.sig_clicked.connect(self._browse_files)
        layout.addWidget(self.dropzone)

        # Buttons row: Add Files & Add Folder
        btn_ingest_row = QHBoxLayout()
        btn_ingest_row.setSpacing(6)

        self.btn_add_files = QPushButton("Add Files...")
        self.btn_add_files.setProperty("class", "btnSecondary")
        self.btn_add_files.clicked.connect(self._browse_files)
        btn_ingest_row.addWidget(self.btn_add_files)

        self.btn_folder = QPushButton("Add Folder...")
        self.btn_folder.setProperty("class", "btnSecondary")
        self.btn_folder.clicked.connect(self._browse_folder)
        btn_ingest_row.addWidget(self.btn_folder)

        layout.addLayout(btn_ingest_row)

        # Action Bar: Process All / Stop CTA Button
        self.btn_process = QPushButton("Generate All Subtitles")
        self.btn_process.setProperty("class", "btnPrimary")
        self.btn_process.setEnabled(False)
        self.btn_process.clicked.connect(self._on_main_action_clicked)
        layout.addWidget(self.btn_process)

        # Queue Summary Bar
        self.summary_frame = QFrame()
        self.summary_frame.setProperty("class", "cardFrame")
        sum_layout = QHBoxLayout(self.summary_frame)
        sum_layout.setContentsMargins(8, 6, 8, 6)
        sum_layout.setSpacing(8)

        self.lbl_stats = QLabel("0 files · 0 done · 0 MB")
        self.lbl_stats.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 500;")
        sum_layout.addWidget(self.lbl_stats)

        sum_layout.addStretch()

        self.btn_clear = QPushButton("Clear ▾")
        self.btn_clear.setProperty("class", "btnGhost")
        self.btn_clear.setToolTip("Clear queue options")
        self.btn_clear.clicked.connect(self._show_clear_menu)
        sum_layout.addWidget(self.btn_clear)

        self.btn_zip = QPushButton("ZIP All")
        self.btn_zip.setProperty("class", "btnOutline")
        self.btn_zip.setEnabled(False)
        self.btn_zip.setToolTip("Export all completed subtitles to a ZIP archive")
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
            "Media Files (*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv *.mp3 *.wav *.m4a *.flac *.ogg *.aac);;All Files (*)"
        )
        if files:
            self._on_files_dropped(files)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Media Folder")
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

    def _on_main_action_clicked(self):
        if self.queue_mgr.is_processing():
            self.queue_mgr.stop_all()
            self.sig_stop_batch.emit()
        else:
            self.sig_process_batch.emit()
            self._update_process_button(is_running=True)

    def _update_process_button(self, is_running: bool):
        if is_running:
            self.btn_process.setText("Stop Batch Processing")
            self.btn_process.setProperty("class", "btnDanger")
            self.btn_process.setEnabled(True)
        else:
            self.btn_process.setText("Generate All Subtitles")
            self.btn_process.setProperty("class", "btnPrimary")
            total_count = len(self.queue_mgr.items)
            self.btn_process.setEnabled(total_count > 0)
        self.btn_process.style().unpolish(self.btn_process)
        self.btn_process.style().polish(self.btn_process)

    def _on_batch_finished(self):
        self._update_process_button(is_running=False)

    def _on_batch_stopped(self):
        self._update_process_button(is_running=False)

    def _show_clear_menu(self):
        if not self.queue_mgr.items:
            return
        menu = QMenu(self)
        act_clear_completed = menu.addAction("Clear Completed Tasks")
        act_clear_completed.triggered.connect(self.queue_mgr.clear_completed)

        act_clear_failed = menu.addAction("Clear Failed / Stopped Tasks")
        act_clear_failed.triggered.connect(self.queue_mgr.clear_failed)

        menu.addSeparator()
        act_clear_all = menu.addAction("Clear All Queue Items")
        act_clear_all.triggered.connect(self._on_clear_all_confirmed)

        menu.exec(self.btn_clear.mapToGlobal(self.btn_clear.rect().bottomLeft()))

    def _on_clear_all_confirmed(self):
        res = QMessageBox.question(
            self, "Clear Queue", "Are you sure you want to remove all items from the queue?",
            QMessageBox.Yes | QMessageBox.No
        )
        if res == QMessageBox.Yes:
            self.queue_mgr.clear_all()
            self.sig_clear_queue.emit()

    def _rebuild_list(self):
        for w in self.item_widgets.values():
            w.setParent(None)
            w.deleteLater()
        self.item_widgets.clear()

        items = list(self.queue_mgr.items.values())
        total_count = len(items)
        completed_count = sum(1 for it in items if it["status"] == "completed")
        total_size = sum(it.get("size_mb", 0) for it in items)

        self.lbl_stats.setText(f"{total_count} files · {completed_count} done · {total_size:.1f} MB")
        self._update_process_button(self.queue_mgr.is_processing())
        self.btn_zip.setEnabled(completed_count > 0)
        self.btn_clear.setEnabled(total_count > 0)

        while self.queue_layout.count() > 0:
            it = self.queue_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        for item in items:
            fid = item["file_id"]
            w = QueueItemWidget(item)
            w.sig_selected.connect(self.select_item)
            w.sig_removed.connect(self._on_item_removed)
            w.sig_retry.connect(lambda fid=fid: self.sig_retry_item.emit(fid))
            w.sig_stop.connect(self.queue_mgr.stop_item)
            w.sig_move.connect(self.queue_mgr.move_item)
            if fid == self.selected_file_id:
                w.set_selected(True)
            self.queue_layout.addWidget(w)
            self.item_widgets[fid] = w

        self.queue_layout.addStretch()

    def _on_item_removed(self, file_id: str):
        self.queue_mgr.remove_item(file_id)
        if self.selected_file_id == file_id:
            remaining_keys = list(self.queue_mgr.items.keys())
            if remaining_keys:
                self.select_item(remaining_keys[0])
            else:
                self.selected_file_id = None
                self.sig_clear_queue.emit()

    def _on_item_status_changed(self, file_id: str, status: str, stage_msg: str, progress: float):
        if file_id in self.item_widgets:
            self.item_widgets[file_id].update_state(status, stage_msg, progress)

        items = list(self.queue_mgr.items.values())
        completed_count = sum(1 for it in items if it["status"] == "completed")
        self.btn_zip.setEnabled(completed_count > 0)
        self._update_process_button(self.queue_mgr.is_processing())

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
