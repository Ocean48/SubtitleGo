import copy
from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QPushButton, QInputDialog, QMessageBox, QFrame
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QKeySequence, QShortcut, QColor

from ...core.subtitle_formatter import (
    format_timestamp_srt,
    format_timestamp_vtt,
    parse_timestamp_to_seconds
)


class CueEditorWidget(QWidget):
    """
    Advanced interactive multi-column editor for subtitle cues.
    Supports in-place editing of text and timestamps, add/split/merge/delete operations,
    timestamp shifting, CPS (characters per second) indicator, and full Undo/Redo history.
    """
    sig_seek_requested = Signal(float)
    sig_cues_modified = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cues: List[Dict[str, Any]] = []
        self._current_playback_sec: float = 0.0
        self._current_filter: str = ""
        self._active_row: int = -1
        self._is_updating: bool = False

        # Undo / Redo History Stacks
        self._undo_stack: List[List[Dict[str, Any]]] = []
        self._redo_stack: List[List[Dict[str, Any]]] = []
        self._max_history = 50

        self._init_ui()
        self._setup_shortcuts()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Action Toolbar (Add, Split, Merge, Delete, Shift, Undo, Redo)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self.btn_add = QPushButton("+ Add Cue")
        self.btn_add.setProperty("class", "btnSecondary")
        self.btn_add.setToolTip("Insert a new cue after the selected cue (or at current playhead)")
        self.btn_add.clicked.connect(self._on_add_cue)
        toolbar.addWidget(self.btn_add)

        self.btn_split = QPushButton("Split Cue")
        self.btn_split.setProperty("class", "btnSecondary")
        self.btn_split.setToolTip("Split selected cue at current video playhead timestamp")
        self.btn_split.clicked.connect(self._on_split_cue)
        toolbar.addWidget(self.btn_split)

        self.btn_merge = QPushButton("Merge Cues")
        self.btn_merge.setProperty("class", "btnSecondary")
        self.btn_merge.setToolTip("Merge selected cue with the following cue")
        self.btn_merge.clicked.connect(self._on_merge_cue)
        toolbar.addWidget(self.btn_merge)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setProperty("class", "btnDanger")
        self.btn_delete.setToolTip("Delete selected cue (Del)")
        self.btn_delete.clicked.connect(self._on_delete_cue)
        toolbar.addWidget(self.btn_delete)

        self.btn_shift = QPushButton("Shift Timings...")
        self.btn_shift.setProperty("class", "btnSecondary")
        self.btn_shift.setToolTip("Shift all cues from selection by +/- offset in milliseconds")
        self.btn_shift.clicked.connect(self._on_shift_timings)
        toolbar.addWidget(self.btn_shift)

        toolbar.addStretch()

        self.btn_undo = QPushButton("Undo")
        self.btn_undo.setProperty("class", "btnGhost")
        self.btn_undo.setToolTip("Undo last cue change (Ctrl+Z)")
        self.btn_undo.setEnabled(False)
        self.btn_undo.clicked.connect(self.undo)
        toolbar.addWidget(self.btn_undo)

        self.btn_redo = QPushButton("Redo")
        self.btn_redo.setProperty("class", "btnGhost")
        self.btn_redo.setToolTip("Redo cue change (Ctrl+Y)")
        self.btn_redo.setEnabled(False)
        self.btn_redo.clicked.connect(self.redo)
        toolbar.addWidget(self.btn_redo)

        layout.addLayout(toolbar)

        # Search / Filter Bar
        search_bar = QHBoxLayout()
        search_bar.setSpacing(6)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Filter cues by text... (Ctrl+F)")
        self.txt_search.textChanged.connect(self._on_search_changed)
        search_bar.addWidget(self.txt_search, stretch=1)

        self.btn_prev_match = QPushButton("◀")
        self.btn_prev_match.setProperty("class", "btnGhost")
        self.btn_prev_match.setToolTip("Previous match")
        self.btn_prev_match.setFixedSize(26, 26)
        self.btn_prev_match.clicked.connect(self._on_prev_match)
        search_bar.addWidget(self.btn_prev_match)

        self.btn_next_match = QPushButton("▶")
        self.btn_next_match.setProperty("class", "btnGhost")
        self.btn_next_match.setToolTip("Next match")
        self.btn_next_match.setFixedSize(26, 26)
        self.btn_next_match.clicked.connect(self._on_next_match)
        search_bar.addWidget(self.btn_next_match)

        self.btn_clear_search = QPushButton("✕")
        self.btn_clear_search.setProperty("class", "btnGhost")
        self.btn_clear_search.setToolTip("Clear search")
        self.btn_clear_search.setFixedSize(26, 26)
        self.btn_clear_search.clicked.connect(lambda: self.txt_search.clear())
        search_bar.addWidget(self.btn_clear_search)

        self.lbl_count = QLabel("0 cues")
        self.lbl_count.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 500; min-width: 70px;")
        self.lbl_count.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        search_bar.addWidget(self.lbl_count)

        layout.addLayout(search_bar)

        # Multi-column Cue Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["#", "Start Time", "End Time", "Duration", "CPS", "Subtitle Text"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)

        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.cellChanged.connect(self._on_cell_changed)

        layout.addWidget(self.table)

    def _setup_shortcuts(self):
        shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        shortcut_undo.activated.connect(self.undo)

        shortcut_redo = QShortcut(QKeySequence("Ctrl+Y"), self)
        shortcut_redo.activated.connect(self.redo)

        shortcut_redo_alt = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        shortcut_redo_alt.activated.connect(self.redo)

        shortcut_find = QShortcut(QKeySequence("Ctrl+F"), self)
        shortcut_find.activated.connect(self.txt_search.setFocus)

        shortcut_del = QShortcut(QKeySequence("Delete"), self)
        shortcut_del.activated.connect(self._on_delete_cue)

    def set_cues(self, cues: List[Dict[str, Any]], record_history: bool = True):
        """Populates the cue editor table and optionally initializes history."""
        if record_history and self.cues:
            self._push_undo()
        self.cues = copy.deepcopy(cues)
        if not record_history:
            self._undo_stack.clear()
            self._redo_stack.clear()
            self._update_history_buttons()
        self._rebuild_table()

    def update_playback_position(self, sec: float):
        """Updates internal reference to current playback timestamp."""
        self._current_playback_sec = sec

    def _push_undo(self):
        self._undo_stack.append(copy.deepcopy(self.cues))
        if len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._update_history_buttons()

    def _update_history_buttons(self):
        self.btn_undo.setEnabled(len(self._undo_stack) > 0)
        self.btn_redo.setEnabled(len(self._redo_stack) > 0)

    def undo(self):
        if not self._undo_stack:
            return
        self._redo_stack.append(copy.deepcopy(self.cues))
        self.cues = self._undo_stack.pop()
        self._update_history_buttons()
        self._rebuild_table()
        self.sig_cues_modified.emit(self.cues)

    def redo(self):
        if not self._redo_stack:
            return
        self._undo_stack.append(copy.deepcopy(self.cues))
        self.cues = self._redo_stack.pop()
        self._update_history_buttons()
        self._rebuild_table()
        self.sig_cues_modified.emit(self.cues)

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

            # 0: Index Item
            item_id = QTableWidgetItem(str(cue.get("id", i + 1)))
            item_id.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item_id.setData(Qt.UserRole, i)  # Index in self.cues
            item_id.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, item_id)

            # Timings
            start_s = float(cue.get("start", 0.0))
            end_s = float(cue.get("end", 0.0))
            dur_s = max(0.0, end_s - start_s)

            # 1: Start Time (Editable)
            item_start = QTableWidgetItem(format_timestamp_srt(start_s))
            item_start.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            item_start.setTextAlignment(Qt.AlignCenter)
            item_start.setData(Qt.UserRole, start_s)
            self.table.setItem(row, 1, item_start)

            # 2: End Time (Editable)
            item_end = QTableWidgetItem(format_timestamp_srt(end_s))
            item_end.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            item_end.setTextAlignment(Qt.AlignCenter)
            item_end.setData(Qt.UserRole, end_s)
            self.table.setItem(row, 2, item_end)

            # 3: Duration (Read-only)
            item_dur = QTableWidgetItem(f"{dur_s:.2f}s")
            item_dur.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item_dur.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, item_dur)

            # 4: CPS (Characters Per Second)
            cps = (len(text.replace(" ", "")) / dur_s) if dur_s > 0.05 else 0.0
            item_cps = QTableWidgetItem(f"{cps:.1f}")
            item_cps.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item_cps.setTextAlignment(Qt.AlignCenter)
            if cps > 23.0:
                item_cps.setForeground(QColor("#ef4444"))
                item_cps.setToolTip("Fast speech rate (> 23 CPS) - Consider splitting")
            elif cps > 18.0:
                item_cps.setForeground(QColor("#f59e0b"))
            else:
                item_cps.setForeground(QColor("#22c55e"))
            self.table.setItem(row, 4, item_cps)

            # 5: Editable Text Item
            item_text = QTableWidgetItem(text)
            item_text.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            self.table.setItem(row, 5, item_text)

            visible_count += 1

        total = len(self.cues)
        self.lbl_count.setText(f"{visible_count} / {total} cues" if query else f"{total} cues")
        self._is_updating = False

    def _on_search_changed(self, text: str):
        self._current_filter = text.strip()
        self._rebuild_table()

    def _on_prev_match(self):
        cur = self.table.currentRow()
        if cur > 0:
            self.table.selectRow(cur - 1)
            self.table.scrollToItem(self.table.item(cur - 1, 0))

    def _on_next_match(self):
        cur = self.table.currentRow()
        if cur < self.table.rowCount() - 1:
            self.table.selectRow(cur + 1)
            self.table.scrollToItem(self.table.item(cur + 1, 0))

    def _on_cell_clicked(self, row: int, column: int):
        if column != 5:  # Non-text columns seek video
            item_id = self.table.item(row, 0)
            if item_id:
                cue_idx = item_id.data(Qt.UserRole)
                if cue_idx is not None and 0 <= cue_idx < len(self.cues):
                    self.sig_seek_requested.emit(float(self.cues[cue_idx].get("start", 0.0)))

    def _on_cell_changed(self, row: int, column: int):
        if self._is_updating:
            return

        item_id = self.table.item(row, 0)
        if not item_id:
            return
        cue_idx = item_id.data(Qt.UserRole)
        if cue_idx is None or not (0 <= cue_idx < len(self.cues)):
            return

        cue = self.cues[cue_idx]

        if column == 1:  # Start Time
            new_ts_str = self.table.item(row, 1).text().strip()
            try:
                new_sec = parse_timestamp_to_seconds(new_ts_str)
                if 0 <= new_sec <= float(cue.get("end", 0.0)):
                    self._push_undo()
                    cue["start"] = new_sec
                    self._rebuild_table()
                    self.sig_cues_modified.emit(self.cues)
                else:
                    self._rebuild_table()
            except Exception:
                self._rebuild_table()

        elif column == 2:  # End Time
            new_ts_str = self.table.item(row, 2).text().strip()
            try:
                new_sec = parse_timestamp_to_seconds(new_ts_str)
                if new_sec >= float(cue.get("start", 0.0)):
                    self._push_undo()
                    cue["end"] = new_sec
                    self._rebuild_table()
                    self.sig_cues_modified.emit(self.cues)
                else:
                    self._rebuild_table()
            except Exception:
                self._rebuild_table()

        elif column == 5:  # Text
            new_txt = self.table.item(row, 5).text()
            if new_txt != cue.get("text", ""):
                self._push_undo()
                cue["text"] = new_txt
                # Update CPS without full rebuild
                dur_s = max(0.05, float(cue.get("end", 0.0)) - float(cue.get("start", 0.0)))
                cps = len(new_txt.replace(" ", "")) / dur_s
                item_cps = self.table.item(row, 4)
                if item_cps:
                    item_cps.setText(f"{cps:.1f}")
                self.sig_cues_modified.emit(self.cues)

    def _get_selected_cue_index(self) -> Optional[int]:
        row = self.table.currentRow()
        if row >= 0:
            item_id = self.table.item(row, 0)
            if item_id:
                return item_id.data(Qt.UserRole)
        return None

    def _on_add_cue(self):
        idx = self._get_selected_cue_index()
        self._push_undo()

        if idx is not None and 0 <= idx < len(self.cues):
            prev_end = float(self.cues[idx].get("end", 0.0))
            new_cue = {
                "id": idx + 2,
                "start": prev_end + 0.1,
                "end": prev_end + 2.5,
                "text": "New subtitle cue"
            }
            self.cues.insert(idx + 1, new_cue)
        else:
            cur_pos = self._current_playback_sec
            new_cue = {
                "id": len(self.cues) + 1,
                "start": cur_pos,
                "end": cur_pos + 2.5,
                "text": "New subtitle cue"
            }
            self.cues.append(new_cue)

        self._reindex_cues()
        self._rebuild_table()
        self.sig_cues_modified.emit(self.cues)

    def _on_split_cue(self):
        idx = self._get_selected_cue_index()
        if idx is None or not (0 <= idx < len(self.cues)):
            QMessageBox.information(self, "Split Cue", "Please select a cue in the table to split.")
            return

        target_cue = self.cues[idx]
        start = float(target_cue.get("start", 0.0))
        end = float(target_cue.get("end", 0.0))
        text = target_cue.get("text", "")

        split_sec = self._current_playback_sec
        if not (start + 0.2 < split_sec < end - 0.2):
            split_sec = start + (end - start) / 2.0

        # Split words approx in half
        words = text.split()
        mid = max(1, len(words) // 2)
        txt1 = " ".join(words[:mid]) if words else text
        txt2 = " ".join(words[mid:]) if len(words) > 1 else ""

        self._push_undo()
        target_cue["end"] = split_sec
        target_cue["text"] = txt1

        cue2 = {
            "id": idx + 2,
            "start": split_sec + 0.05,
            "end": end,
            "text": txt2 or "..."
        }
        self.cues.insert(idx + 1, cue2)

        self._reindex_cues()
        self._rebuild_table()
        self.sig_cues_modified.emit(self.cues)

    def _on_merge_cue(self):
        idx = self._get_selected_cue_index()
        if idx is None or idx >= len(self.cues) - 1:
            QMessageBox.information(self, "Merge Cues", "Please select a cue that has a subsequent cue to merge with.")
            return

        self._push_undo()
        cue1 = self.cues[idx]
        cue2 = self.cues[idx + 1]

        cue1["end"] = float(cue2.get("end", 0.0))
        cue1["text"] = f"{cue1.get('text', '').strip()} {cue2.get('text', '').strip()}".strip()

        self.cues.pop(idx + 1)
        self._reindex_cues()
        self._rebuild_table()
        self.sig_cues_modified.emit(self.cues)

    def _on_delete_cue(self):
        idx = self._get_selected_cue_index()
        if idx is None or not (0 <= idx < len(self.cues)):
            return

        self._push_undo()
        self.cues.pop(idx)
        self._reindex_cues()
        self._rebuild_table()
        self.sig_cues_modified.emit(self.cues)

    def _on_shift_timings(self):
        if not self.cues:
            return

        offset_ms, ok = QInputDialog.getInt(
            self,
            "Shift Timings",
            "Enter timing offset in milliseconds (+/- ms):\n(e.g. 500 for +0.5s, -250 for -0.25s)",
            value=0,
            minValue=-60000,
            maxValue=60000,
            step=100
        )
        if ok and offset_ms != 0:
            delta_s = offset_ms / 1000.0
            idx = self._get_selected_cue_index()
            start_idx = idx if idx is not None else 0

            self._push_undo()
            for i in range(start_idx, len(self.cues)):
                c = self.cues[i]
                c["start"] = max(0.0, float(c.get("start", 0.0)) + delta_s)
                c["end"] = max(c["start"] + 0.1, float(c.get("end", 0.0)) + delta_s)

            self._rebuild_table()
            self.sig_cues_modified.emit(self.cues)

    def _reindex_cues(self):
        for i, c in enumerate(self.cues):
            c["id"] = i + 1

    def highlight_active_time(self, current_sec: float):
        """Highlights the cue corresponding to the active player timestamp."""
        self._current_playback_sec = current_sec
        active_row = -1
        for row in range(self.table.rowCount()):
            item_id = self.table.item(row, 0)
            if not item_id:
                continue
            cue_idx = item_id.data(Qt.UserRole)
            if cue_idx is None or not (0 <= cue_idx < len(self.cues)):
                continue

            cue = self.cues[cue_idx]
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

