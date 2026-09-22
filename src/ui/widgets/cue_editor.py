from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Signal, Qt

from ...core.subtitle_formatter import format_timestamp_srt, parse_timestamp_to_seconds


class CueEditorWidget(QWidget):
    """
    Interactive table editor for subtitle cues.
    Supports in-place editing, real-time search filtering, and seek-on-click.
    """
    sig_seek_requested = Signal(float)
    sig_cues_modified = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cues: List[Dict[str, Any]] = []
        self._current_filter = ""
        self._active_row = -1
        self._is_updating = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Search / Filter Bar
        search_bar = QHBoxLayout()
        search_bar.setSpacing(8)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search within subtitles...")
        self.txt_search.textChanged.connect(self._on_search_changed)
        search_bar.addWidget(self.txt_search, stretch=1)

        self.lbl_count = QLabel("0 cues")
        self.lbl_count.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 500;")
        search_bar.addWidget(self.lbl_count)

        layout.addLayout(search_bar)

        # Cue Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["#", "Time", "Subtitle Text"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)

        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.cellChanged.connect(self._on_cell_changed)

        layout.addWidget(self.table)

    def set_cues(self, cues: List[Dict[str, Any]]):
        """Populates the cue editor table."""
        self.cues = cues
        self._rebuild_table()

    def _rebuild_table(self):
        self._is_updating = True
        self.table.setRowCount(0)

        query = self._current_filter.lower()
        visible_count = 0

        for i, cue in enumerate(self.cues):
            text = str(cue.get("text", ""))
            if query and query not in text.lower():
                continue

            row = self.table.rowCount()
            self.table.insertRow(row)

            # Index Item
            item_id = QTableWidgetItem(str(cue.get("id", i + 1)))
            item_id.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item_id.setData(Qt.UserRole, cue)
            item_id.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, item_id)

            # Time Item
            start_s = float(cue.get("start", 0.0))
            end_s = float(cue.get("end", 0.0))
            time_str = f"{format_timestamp_srt(start_s)} -> {format_timestamp_srt(end_s)}"
            item_time = QTableWidgetItem(time_str)
            item_time.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item_time.setData(Qt.UserRole, start_s)
            item_time.setForeground(Qt.GlobalColor.darkCyan)
            self.table.setItem(row, 1, item_time)

            # Editable Text Item
            item_text = QTableWidgetItem(text)
            item_text.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            self.table.setItem(row, 2, item_text)

            visible_count += 1

        total = len(self.cues)
        self.lbl_count.setText(f"{visible_count} / {total} cues" if query else f"{total} cues")
        self._is_updating = False

    def _on_search_changed(self, text: str):
        self._current_filter = text.strip()
        self._rebuild_table()

    def _on_cell_clicked(self, row: int, column: int):
        item_time = self.table.item(row, 1)
        if item_time:
            start_s = item_time.data(Qt.UserRole)
            if start_s is not None:
                self.sig_seek_requested.emit(float(start_s))

    def _on_cell_changed(self, row: int, column: int):
        if self._is_updating or column != 2:
            return

        item_id = self.table.item(row, 0)
        item_text = self.table.item(row, 2)
        if item_id and item_text:
            cue = item_id.data(Qt.UserRole)
            if cue:
                new_txt = item_text.text().strip()
                cue["text"] = new_txt
                self.sig_cues_modified.emit(self.cues)

    def highlight_active_time(self, current_sec: float):
        """Highlights the cue corresponding to the active player timestamp."""
        active_row = -1
        for row in range(self.table.rowCount()):
            item_id = self.table.item(row, 0)
            if not item_id:
                continue
            cue = item_id.data(Qt.UserRole)
            if not cue:
                continue

            start = float(cue.get("start", 0.0))
            end = float(cue.get("end", 0.0))
            if start <= current_sec <= end:
                active_row = row
                break

        if active_row != self._active_row:
            self._active_row = active_row
            if active_row >= 0:
                self.table.selectRow(active_row)
                self.table.scrollToItem(self.table.item(active_row, 0))
            else:
                self.table.clearSelection()
