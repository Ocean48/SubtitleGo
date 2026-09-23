import os
import uuid
import zipfile
from typing import Dict, Any, List, Optional
from PySide6.QtCore import QObject, Signal

from .transcription_worker import TranscriptionWorker


class QueueManager(QObject):
    """
    Manages batch transcription tasks, concurrency limits, and auto-saving.
    """
    sig_queue_updated = Signal()                        # General list change
    sig_item_status_changed = Signal(str, str, str, float)  # file_id, status, stage_msg, progress
    sig_item_completed = Signal(str, dict)              # file_id, result_dict
    sig_item_error = Signal(str, str)                   # file_id, error_msg
    sig_batch_finished = Signal()                       # All items completed
    sig_batch_stopped = Signal()                        # Batch processing stopped

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: Dict[str, Dict[str, Any]] = {}
        self.active_workers: Dict[str, TranscriptionWorker] = {}
        self.concurrency = 2
        self.auto_save = True
        self._is_processing_batch = False
        self._current_settings: Dict[str, Any] = {}

    def add_files(self, file_paths: List[str]) -> List[str]:
        """Adds media files to the queue. Returns list of newly added file_ids."""
        added_ids = []
        for fp in file_paths:
            if not os.path.isfile(fp):
                continue
            
            # Check for duplicate
            if any(item["media_path"] == fp for item in self.items.values()):
                continue

            fid = str(uuid.uuid4())[:8]
            size_mb = 0.0
            try:
                size_mb = round(os.path.getsize(fp) / (1024 * 1024), 2)
            except Exception:
                pass

            self.items[fid] = {
                "file_id": fid,
                "media_path": fp,
                "filename": os.path.basename(fp),
                "size_mb": size_mb,
                "status": "queued",       # 'queued', 'processing', 'completed', 'error'
                "stage_msg": "Queued",
                "progress": 0.0,
                "result": None,
                "error": None
            }
            added_ids.append(fid)

        if added_ids:
            self.sig_queue_updated.emit()
            if self._is_processing_batch:
                self._schedule_next()
        return added_ids

    def remove_item(self, file_id: str):
        """Removes an item and aborts worker if running."""
        if file_id in self.active_workers:
            worker = self.active_workers.pop(file_id)
            worker.cancel()
            worker.quit()
            if worker.isRunning():
                worker.wait(2000)
            worker.deleteLater()
        if file_id in self.items:
            del self.items[file_id]
            self.sig_queue_updated.emit()
            if self._is_processing_batch:
                self._schedule_next()

    def stop_item(self, file_id: str):
        """Cancels a single running worker without removing the item from the queue."""
        if file_id in self.active_workers:
            worker = self.active_workers.pop(file_id)
            worker.cancel()
            worker.quit()
            if worker.isRunning():
                worker.wait(2000)
            worker.deleteLater()

        if file_id in self.items:
            self.items[file_id]["status"] = "cancelled"
            self.items[file_id]["stage_msg"] = "Stopped"
            self.sig_item_status_changed.emit(file_id, "cancelled", "Stopped", self.items[file_id].get("progress", 0.0))
            self.sig_queue_updated.emit()

        if self._is_processing_batch:
            self._schedule_next()

    def move_item(self, file_id: str, direction: int):
        """Moves an item up (-1) or down (+1) in the queue order."""
        keys = list(self.items.keys())
        if file_id not in keys:
            return
        idx = keys.index(file_id)
        target_idx = idx + direction
        if target_idx < 0 or target_idx >= len(keys):
            return
        keys[idx], keys[target_idx] = keys[target_idx], keys[idx]
        self.items = {k: self.items[k] for k in keys}
        self.sig_queue_updated.emit()

    def clear_all(self):
        """Cancels all active tasks and clears queue."""
        self.stop_all()
        self.items.clear()
        self.sig_queue_updated.emit()

    def clear_completed(self):
        """Removes all completed items from the queue."""
        to_remove = [fid for fid, it in self.items.items() if it["status"] == "completed"]
        for fid in to_remove:
            del self.items[fid]
        if to_remove:
            self.sig_queue_updated.emit()

    def clear_failed(self):
        """Removes all error or cancelled items from the queue."""
        to_remove = [fid for fid, it in self.items.items() if it["status"] in ["error", "cancelled"]]
        for fid in to_remove:
            del self.items[fid]
        if to_remove:
            self.sig_queue_updated.emit()

    def stop_all(self):
        """Aborts all active workers and resets in-flight items."""
        self._is_processing_batch = False
        workers_to_stop = list(self.active_workers.values())
        self.active_workers.clear()
        for worker in workers_to_stop:
            worker.cancel()
            worker.quit()
        for worker in workers_to_stop:
            if worker.isRunning():
                worker.wait(3000)
            worker.deleteLater()

        for item in self.items.values():
            if item["status"] == "processing":
                item["status"] = "cancelled"
                item["stage_msg"] = "Stopped"
                self.sig_item_status_changed.emit(item["file_id"], "cancelled", "Stopped", item.get("progress", 0.0))

        self.sig_queue_updated.emit()
        self.sig_batch_stopped.emit()

    def is_processing(self) -> bool:
        """Returns True if a batch is active or workers are running."""
        return self._is_processing_batch or bool(self.active_workers)

    def start_batch(self, settings: Dict[str, Any]):
        """Starts batch processing for all queued, cancelled, or errored items."""
        self._current_settings = settings
        self.concurrency = int(settings.get("concurrency", 2))
        self.auto_save = bool(settings.get("auto_save", True))
        self._is_processing_batch = True

        for item in self.items.values():
            if item["status"] in ["error", "cancelled"]:
                item["status"] = "queued"
                item["stage_msg"] = "Queued"
                item["progress"] = 0.0
                item["error"] = None
                self.sig_item_status_changed.emit(item["file_id"], "queued", "Queued", 0.0)

        self._schedule_next()

    def retry_item(self, file_id: str, settings: Dict[str, Any]):
        """Retries a specific item."""
        if file_id not in self.items:
            return
        self.items[file_id]["status"] = "queued"
        self.items[file_id]["stage_msg"] = "Queued"
        self.items[file_id]["progress"] = 0.0
        self.items[file_id]["error"] = None
        self.sig_item_status_changed.emit(file_id, "queued", "Queued", 0.0)

        self._current_settings = settings
        self.concurrency = int(settings.get("concurrency", 2))
        self.auto_save = bool(settings.get("auto_save", True))
        self._is_processing_batch = True
        self._schedule_next()

    def _schedule_next(self):
        """Pulls next queued items up to concurrency limit."""
        if not self._is_processing_batch:
            return

        running_count = sum(1 for item in self.items.values() if item["status"] == "processing")
        while running_count < self.concurrency:
            next_id = None
            for fid, item in self.items.items():
                if item["status"] == "queued" and fid not in self.active_workers:
                    next_id = fid
                    break

            if not next_id:
                break

            self._start_worker(next_id)
            running_count += 1

        # Check if all items finished or aborted
        if not self.active_workers:
            all_done = all(item["status"] in ["completed", "error", "cancelled"] for item in self.items.values())
            if all_done and self._is_processing_batch:
                self._is_processing_batch = False
                self.sig_batch_finished.emit()

    def _start_worker(self, file_id: str):
        item = self.items[file_id]
        item["status"] = "processing"
        item["stage_msg"] = "Starting..."
        item["progress"] = 0.0

        self.sig_item_status_changed.emit(file_id, "processing", "Starting...", 0.0)

        worker = TranscriptionWorker(
            file_id=file_id,
            media_path=item["media_path"],
            language=self._current_settings.get("language"),
            prompt=self._current_settings.get("prompt"),
            max_segment_length=float(self._current_settings.get("max_segment_length", 4.5)),
            silence_thresh_db=float(self._current_settings.get("silence_thresh_db", -36.0)),
            batch_size=self._current_settings.get("batch_size"),
        )

        worker.sig_progress.connect(self._on_worker_progress)
        worker.sig_completed.connect(self._on_worker_completed)
        worker.sig_error.connect(self._on_worker_error)
        worker.finished.connect(lambda fid=file_id, w=worker: self._on_worker_finished(fid, w))

        self.active_workers[file_id] = worker
        worker.start()

    def _on_worker_progress(self, file_id: str, stage: int, stage_msg: str, progress: float):
        if file_id in self.items:
            self.items[file_id]["stage_msg"] = stage_msg
            self.items[file_id]["progress"] = progress
            self.sig_item_status_changed.emit(file_id, "processing", stage_msg, progress)

    def _on_worker_completed(self, file_id: str, result: Dict[str, Any]):
        if file_id in self.items:
            self.items[file_id]["status"] = "completed"
            self.items[file_id]["stage_msg"] = "Completed"
            self.items[file_id]["progress"] = 100.0
            self.items[file_id]["result"] = result
            self.items[file_id]["error"] = None

            # Auto-save to source video directory
            if self.auto_save:
                self._auto_save_subtitles(self.items[file_id]["media_path"], result)

            self.sig_item_status_changed.emit(file_id, "completed", "Completed", 100.0)
            self.sig_item_completed.emit(file_id, result)

        self.sig_queue_updated.emit()
        self._schedule_next()

    def _on_worker_error(self, file_id: str, error_msg: str):
        if file_id in self.items:
            self.items[file_id]["status"] = "error"
            self.items[file_id]["stage_msg"] = f"Error: {error_msg}"
            self.items[file_id]["progress"] = 0.0
            self.items[file_id]["error"] = error_msg
            self.sig_item_status_changed.emit(file_id, "error", f"Error: {error_msg}", 0.0)
            self.sig_item_error.emit(file_id, error_msg)

        self.sig_queue_updated.emit()
        self._schedule_next()

    def _on_worker_finished(self, file_id: str, worker: TranscriptionWorker):
        if file_id in self.active_workers and self.active_workers[file_id] is worker:
            del self.active_workers[file_id]
        worker.deleteLater()

        if not self.active_workers:
            all_done = all(item["status"] in ["completed", "error", "cancelled"] for item in self.items.values())
            if all_done and self._is_processing_batch:
                self._is_processing_batch = False
                self.sig_batch_finished.emit()

    def _auto_save_subtitles(self, media_path: str, result: Dict[str, Any]):
        """Writes .srt and .vtt directly adjacent to media file."""
        try:
            base_dir = os.path.dirname(media_path)
            base_name = os.path.splitext(os.path.basename(media_path))[0]
            
            srt_path = os.path.join(base_dir, f"{base_name}.srt")
            vtt_path = os.path.join(base_dir, f"{base_name}.vtt")

            if result.get("srt"):
                with open(srt_path, "w", encoding="utf-8") as f:
                    f.write(result["srt"])
            if result.get("vtt"):
                with open(vtt_path, "w", encoding="utf-8") as f:
                    f.write(result["vtt"])
        except Exception as e:
            print(f"Auto-save warning: failed to write subtitles for {media_path}: {e}")

    def export_zip(self, zip_path: str) -> bool:
        """Exports all completed subtitles into a single ZIP file."""
        completed_items = [it for it in self.items.values() if it["status"] == "completed" and it.get("result")]
        if not completed_items:
            return False

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for it in completed_items:
                res = it["result"]
                base_name = os.path.splitext(it["filename"])[0]
                if res.get("srt"):
                    zf.writestr(f"{base_name}.srt", res["srt"])
                if res.get("vtt"):
                    zf.writestr(f"{base_name}.vtt", res["vtt"])
                if res.get("txt"):
                    zf.writestr(f"{base_name}.txt", res["txt"])
        return True
