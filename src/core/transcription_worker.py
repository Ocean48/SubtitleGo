import os
import time
import tempfile
from typing import Optional, Dict, Any, List
from PySide6.QtCore import QThread, Signal

from .audio_processor import (
    extract_audio_to_wav,
    get_audio_duration_seconds,
    segment_audio_smart
)
from .subtitle_formatter import (
    refine_subtitles_for_pacing,
    build_srt_content,
    build_vtt_content,
    build_txt_content,
    format_timestamp_srt
)
from .model_manager import ModelManager


class TranscriptionWorker(QThread):
    """
    Background worker thread for running audio extraction, speech recognition,
    and subtitle alignment for a single media file.
    """
    sig_started = Signal(str, str)                      # file_id, filename
    sig_progress = Signal(str, int, str, float)         # file_id, stage (1,2,3), stage_msg, percentage (0-100)
    sig_cues_updated = Signal(str, list)                # file_id, current_cue_list
    sig_completed = Signal(str, dict)                   # file_id, full_result_data
    sig_error = Signal(str, str)                        # file_id, error_message

    def __init__(
        self,
        file_id: str,
        media_path: str,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        max_segment_length: float = 4.5,
        min_segment_length: float = 0.25,
        silence_thresh_db: float = -36.0,
        batch_size: Optional[int] = None,
        parent=None
    ):
        super().__init__(parent)
        self.file_id = file_id
        self.media_path = media_path
        self.filename = os.path.basename(media_path)
        self.language = None if (not language or language.lower() in ["auto", "auto detect", "none", ""]) else language
        self.prompt = prompt or None
        self.max_segment_length = max_segment_length
        self.min_segment_length = min_segment_length
        self.silence_thresh_db = silence_thresh_db
        self.batch_size = batch_size
        self._is_cancelled = False

    def cancel(self):
        """Requests worker cancellation."""
        self._is_cancelled = True

    def run(self):
        start_time = time.time()
        self.sig_started.emit(self.file_id, self.filename)

        converted_wav = None
        chunk_files: List[str] = []

        try:
            # Stage 1: Audio Extraction & Silence Detection
            self.sig_progress.emit(self.file_id, 1, "1/3 Extracting audio & speech detection", 5.0)

            if not os.path.isfile(self.media_path):
                raise FileNotFoundError(f"Media file not found: {self.media_path}")

            with tempfile.NamedTemporaryFile(delete=False, suffix=".extracted.wav") as twav:
                converted_wav = twav.name

            extract_ok = extract_audio_to_wav(self.media_path, converted_wav, sample_rate=16000)
            if not extract_ok or not os.path.exists(converted_wav):
                raise RuntimeError("Failed to extract audio track from media file.")

            if self._is_cancelled:
                return

            duration = get_audio_duration_seconds(converted_wav)
            if duration <= 0:
                raise RuntimeError("Extracted audio is empty or unreadable.")

            self.sig_progress.emit(self.file_id, 1, "1/3 Detecting speech pauses & silence intervals", 20.0)

            time_intervals = segment_audio_smart(
                converted_wav,
                max_segment_duration=self.max_segment_length,
                min_segment_duration=self.min_segment_length,
                silence_thresh_db=self.silence_thresh_db
            )
            if not time_intervals:
                time_intervals = [(0.0, duration)]

            if self._is_cancelled:
                return

            # Stage 2: Qwen3-ASR Inference
            self.sig_progress.emit(self.file_id, 2, "2/3 Running Qwen3-ASR model inference", 35.0)

            # Load audio using soundfile (fast C libsndfile binding, robust across torch versions)
            import soundfile as sf
            audio_data, sr = sf.read(converted_wav, dtype="float32")
            total_samples = len(audio_data)

            prepared_chunks: List[Dict[str, Any]] = []
            for idx, (s_sec, e_sec) in enumerate(time_intervals, start=1):
                s_sample = max(0, int(s_sec * sr))
                e_sample = min(total_samples, int(e_sec * sr))
                if e_sample - s_sample < 100:
                    continue

                chunk_wave = audio_data[s_sample:e_sample]
                with tempfile.NamedTemporaryFile(delete=False, suffix=f"_cue_{idx}.wav") as cfile:
                    cpath = cfile.name
                    sf.write(cpath, chunk_wave, sr, subtype="PCM_16")
                    chunk_files.append(cpath)

                prepared_chunks.append({
                    "id": idx,
                    "cpath": cpath,
                    "start": s_sec,
                    "end": e_sec,
                    "start_time": format_timestamp_srt(s_sec),
                    "end_time": format_timestamp_srt(e_sec)
                })

            if not prepared_chunks:
                raise RuntimeError("No valid speech audio chunks were found to transcribe.")

            model_mgr = ModelManager.get_instance()
            if not model_mgr.model:
                self.sig_progress.emit(self.file_id, 2, "2/3 Initializing Qwen3-ASR model...", 38.0)
                model_mgr.load_model(max_batch_size=self.batch_size)

            if self._is_cancelled:
                return

            # Determine inference batch size: respect user override or fallback to dynamic recommendation
            from .model_manager import get_recommended_settings
            rec = get_recommended_settings()
            batch_size = self.batch_size if (self.batch_size and self.batch_size > 0) else rec["recommended_batch_size"]

            raw_segments: List[Dict[str, Any]] = []
            detected_languages: List[str] = []
            total_chunks = len(prepared_chunks)

            for b_idx in range(0, total_chunks, batch_size):
                if self._is_cancelled:
                    return

                batch = prepared_chunks[b_idx: b_idx + batch_size]
                b_paths = [b["cpath"] for b in batch]
                b_ctx = [self.prompt or "" for _ in batch]
                b_langs = [self.language for _ in batch]

                results = model_mgr.transcribe_batch(b_paths, b_ctx, b_langs)

                for chunk_meta, (text, lang) in zip(batch, results):
                    cue_text = text.strip()
                    if cue_text:
                        chunk_meta["text"] = cue_text
                        chunk_meta["language"] = lang
                        raw_segments.append(chunk_meta)
                        if lang:
                            detected_languages.append(lang)

                progress_val = 35.0 + ((b_idx + len(batch)) / total_chunks) * 30.0
                self.sig_progress.emit(
                    self.file_id, 2,
                    f"2/3 Transcribing chunk {min(b_idx + len(batch), total_chunks)}/{total_chunks}",
                    progress_val
                )

            if self._is_cancelled:
                return

            # Stage 3: Subtitle Alignment & Pacing Refinement
            self.sig_progress.emit(self.file_id, 3, "3/3 Aligning timestamps & subtitle pacing", 70.0)

            primary_lang = "Unknown"
            if detected_languages:
                primary_lang = max(set(detected_languages), key=detected_languages.count)
            elif self.language:
                primary_lang = self.language

            refined_segments = refine_subtitles_for_pacing(
                raw_segments,
                max_chars_latin=42,
                max_chars_cjk=18,
                max_duration=self.max_segment_length or 4.5,
                min_duration=0.3
            )

            srt_content = build_srt_content(refined_segments)
            vtt_content = build_vtt_content(refined_segments)
            txt_content = build_txt_content(refined_segments)

            elapsed_time = time.time() - start_time

            result_data = {
                "file_id": self.file_id,
                "media_path": self.media_path,
                "filename": self.filename,
                "duration": round(duration, 2),
                "language": primary_lang,
                "segments_count": len(refined_segments),
                "segments": refined_segments,
                "srt": srt_content,
                "vtt": vtt_content,
                "txt": txt_content,
                "processing_time": f"{elapsed_time:.2f}s"
            }

            self.sig_progress.emit(self.file_id, 3, "Complete", 100.0)
            self.sig_completed.emit(self.file_id, result_data)

        except Exception as e:
            if not self._is_cancelled:
                import traceback
                print(f"\n[TranscriptionWorker] Error processing {self.filename}: {e}")
                traceback.print_exc()

                err_str = str(e)
                if any(k in err_str.lower() for k in ["insufficient memory", "out of memory", "command buffer", "kiogpucommandbuffercallbackerroroutofmemory"]):
                    formatted_err = "GPU Out of Memory (Metal MPS). Please reduce concurrency to 1 or switch to CPU mode in Settings."
                else:
                    formatted_err = f"{type(e).__name__}: {err_str}" if err_str else type(e).__name__

                self.sig_error.emit(self.file_id, formatted_err)
        finally:
            # Clean up temporary WAV files
            if converted_wav and os.path.exists(converted_wav):
                try:
                    os.unlink(converted_wav)
                except Exception:
                    pass
            for cpath in chunk_files:
                if os.path.exists(cpath):
                    try:
                        os.unlink(cpath)
                    except Exception:
                        pass
