import math
import os
import re
import subprocess
import wave
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Any, Union

from .ffmpeg_helper import get_ffmpeg_path, run_ffmpeg


@dataclass
class SpeechInterval:
    """
    Structured representation of a speech interval:
    - start: True acoustic speech onset in seconds (unpadded)
    - end: True acoustic speech offset in seconds (unpadded)
    - pad_start: Extended extraction window with acoustic padding for ASR
    - pad_end: Extended extraction window with acoustic padding for ASR
    - pauses: List of intra-segment pause timestamps (start, end) in seconds
    """
    start: float
    end: float
    pad_start: float
    pad_end: float
    pauses: List[Tuple[float, float]] = field(default_factory=list)

    def __iter__(self):
        """Allows unpacking as (start, end) for backwards compatibility."""
        return iter((self.start, self.end))

    def __getitem__(self, index: int) -> float:
        return (self.start, self.end)[index]

    def __len__(self) -> int:
        return 2

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def _get_numpy():
    try:
        import numpy as np
        return np
    except ImportError:
        return None

def _get_torchaudio():
    try:
        import torchaudio
        return torchaudio
    except ImportError:
        return None

def _get_soundfile():
    try:
        import soundfile as sf
        return sf
    except ImportError:
        return None

def _get_torch():
    try:
        import torch
        return torch
    except ImportError:
        return None


def get_audio_duration_seconds(wav_path: str) -> float:
    """Gets duration of a WAV file in seconds using standard library wave or fallback packages."""
    try:
        with wave.open(wav_path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate > 0:
                return float(frames / float(rate))
    except Exception:
        pass

    sf = _get_soundfile()
    if sf:
        try:
            info = sf.info(wav_path)
            return float(info.duration)
        except Exception:
            pass

    torchaudio = _get_torchaudio()
    if torchaudio:
        try:
            waveform, sr = torchaudio.load(wav_path)
            return float(waveform.shape[-1] / sr)
        except Exception:
            pass

    return 0.0


def extract_audio_to_wav(input_path: str, output_path: str, sample_rate: int = 16000) -> bool:
    """
    Extracts audio from video or audio file and converts it to mono 16kHz 16-bit PCM WAV using ffmpeg.
    Applies audio conditioning: PTS sync (aresample), speech bandpass (120Hz-4000Hz),
    and dynamic audio normalization (dynaudnorm) to normalize volume across whispers and loud speech.
    Falls back to unconditioned ffmpeg or torchaudio / soundfile if filters or ffmpeg are unavailable.
    """
    ffmpeg_bin = get_ffmpeg_path()
    try:
        # High quality audio conditioning filter chain
        conditioned_args = [
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", input_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", str(sample_rate),
            "-ac", "1",
            "-af", "aresample=async=1:first_pts=0,highpass=f=120,lowpass=f=4000,dynaudnorm=f=75:g=15:m=10.0",
            output_path
        ]
        res = run_ffmpeg(conditioned_args)
        if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True

        # Fallback to basic extraction without filters if complex filter graph fails
        basic_args = [
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", input_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", str(sample_rate),
            "-ac", "1",
            output_path
        ]
        res = run_ffmpeg(basic_args)
        if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True
    except Exception:
        pass

    # Fallback via soundfile / scipy / torchaudio
    sf = _get_soundfile()
    if sf:
        try:
            data, sr = sf.read(input_path, dtype="float32")
            if data.ndim > 1:
                import numpy as np
                data = np.mean(data, axis=1)
            if sr != sample_rate:
                import scipy.signal
                num_samples = int(len(data) * float(sample_rate) / float(sr))
                data = scipy.signal.resample(data, num_samples)
            import numpy as np
            # Convert float32 [-1, 1] to PCM 16-bit
            scaled = np.int16(np.clip(data, -1.0, 1.0) * 32767)
            sf.write(output_path, scaled, sample_rate, subtype="PCM_16")
            return True
        except Exception:
            pass

    torchaudio = _get_torchaudio()
    torch = _get_torch()
    if torchaudio and torch:
        try:
            waveform, sr = torchaudio.load(input_path)
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)
            if sr != sample_rate:
                resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=sample_rate)
                waveform = resampler(waveform)
            torchaudio.save(output_path, waveform, sample_rate)
            return True
        except Exception:
            pass

    raise RuntimeError(f"Failed to extract audio using FFmpeg and fallback libraries from {input_path}")


def compute_rms_envelope(
    audio: Any,
    sr: int = 16000,
    frame_ms: float = 25.0,
    hop_ms: float = 10.0
) -> Tuple[Any, Any]:
    """
    Computes smoothed short-time RMS energy envelope of mono audio data.
    Returns (rms_values, timestamp_seconds).
    """
    np = _get_numpy()
    if np is None:
        return None, None

    if not isinstance(audio, np.ndarray):
        audio = np.array(audio, dtype=np.float32)

    if audio.ndim > 1:
        audio = np.mean(audio, axis=0)

    frame_len = max(1, int(sr * frame_ms / 1000.0))
    hop_len = max(1, int(sr * hop_ms / 1000.0))

    if len(audio) < frame_len:
        rms_single = np.sqrt(np.mean(audio ** 2) + 1e-9)
        return np.array([rms_single], dtype=np.float32), np.array([0.0], dtype=np.float32)

    num_frames = 1 + (len(audio) - frame_len) // hop_len
    shape = (num_frames, frame_len)
    strides = (audio.strides[0] * hop_len, audio.strides[0])
    try:
        frames = np.lib.stride_tricks.as_strided(audio, shape=shape, strides=strides)
        rms = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-9)
    except Exception:
        # Fallback if strides fail
        rms = np.zeros(num_frames, dtype=np.float32)
        for i in range(num_frames):
            st = i * hop_len
            chunk = audio[st:st + frame_len]
            rms[i] = np.sqrt(np.mean(chunk ** 2) + 1e-9)

    times = np.arange(num_frames, dtype=np.float32) * (hop_ms / 1000.0) + (frame_ms / 2000.0)

    # Apply 5-point moving average smoothing to eliminate transient spike noise
    if len(rms) >= 5:
        kernel = np.ones(5, dtype=np.float32) / 5.0
        smoothed = np.convolve(rms, kernel, mode="same")
        return smoothed, times

    return rms, times


def find_intra_chunk_pauses(
    audio: Any,
    sr: int = 16000,
    offset_s: float = 0.0,
    min_pause_s: float = 0.12,
    silence_thresh_ratio: float = 0.22
) -> List[Tuple[float, float]]:
    """
    Finds intra-utterance breath/pause valleys and conversational turnover micro-pauses
    within an audio segment. Returns list of (pause_start_s, pause_end_s).
    """
    np = _get_numpy()
    if np is None or audio is None or len(audio) == 0:
        return []

    rms, times = compute_rms_envelope(audio, sr=sr, frame_ms=25.0, hop_ms=10.0)
    if rms is None or len(rms) < 5:
        return []

    peak_rms = float(np.percentile(rms, 90))
    floor_rms = float(np.percentile(rms, 10))
    if peak_rms <= 1e-7:
        return []

    # Dynamic silence threshold based on local dynamic range
    dyn_thresh = floor_rms + (peak_rms - floor_rms) * silence_thresh_ratio
    is_silent = rms < dyn_thresh

    pauses: List[Tuple[float, float]] = []
    in_pause = False
    p_start = 0.0

    for idx, (silent, t) in enumerate(zip(is_silent, times)):
        curr_t = offset_s + float(t)
        if silent and not in_pause:
            in_pause = True
            p_start = curr_t
        elif not silent and in_pause:
            in_pause = False
            p_dur = curr_t - p_start
            if p_dur >= min_pause_s:
                pauses.append((round(p_start, 3), round(curr_t, 3)))

    if in_pause:
        last_t = offset_s + float(times[-1])
        if last_t - p_start >= min_pause_s:
            pauses.append((round(p_start, 3), round(last_t, 3)))

    return pauses


def find_energy_valley_in_window(
    audio: Any,
    sr: int,
    chunk_offset_s: float,
    search_start_s: float,
    search_end_s: float
) -> float:
    """
    Scans a time window [search_start_s, search_end_s] in the audio waveform and finds
    the timestamp of the lowest acoustic energy trough (breath, pause, between-word silence).
    """
    np = _get_numpy()
    if np is None or audio is None or len(audio) == 0:
        return (search_start_s + search_end_s) / 2.0

    s_idx = max(0, int((search_start_s - chunk_offset_s) * sr))
    e_idx = min(len(audio), int((search_end_s - chunk_offset_s) * sr))
    if e_idx - s_idx < int(sr * 0.1):
        return (search_start_s + search_end_s) / 2.0

    sub_wave = audio[s_idx:e_idx]
    rms, times = compute_rms_envelope(sub_wave, sr=sr, frame_ms=30.0, hop_ms=10.0)
    if rms is None or len(rms) == 0:
        return (search_start_s + search_end_s) / 2.0

    min_idx = int(np.argmin(rms))
    valley_time = search_start_s + float(times[min_idx])
    return round(valley_time, 3)


def subdivide_speech_by_energy_valleys(
    audio: Any,
    sr: int,
    start_s: float,
    end_s: float,
    max_duration: float = 8.0,
    min_duration: float = 0.25,
    target_duration: float = 6.0
) -> List[Tuple[float, float]]:
    """
    Subdivides long uninterrupted speech into complete sentences and natural clause chunks
    by searching for acoustic energy valleys (pauses/breaths) instead of slicing mid-word.
    """
    total_dur = end_s - start_s
    if total_dur <= max_duration:
        return [(start_s, end_s)]

    results: List[Tuple[float, float]] = []
    curr_start = start_s

    while curr_start < end_s:
        rem_dur = end_s - curr_start
        if rem_dur <= max_duration:
            results.append((round(curr_start, 3), round(end_s, 3)))
            break

        # Ideal target cut point
        nominal_cut = curr_start + min(target_duration, rem_dur / 2.0)
        # Search window around nominal cut (+/- 1.5s) bounded by safety margins
        search_start = max(curr_start + min_duration, nominal_cut - 1.5)
        search_end = min(end_s - min_duration, nominal_cut + 1.5)

        if search_end > search_start and audio is not None:
            valley_cut = find_energy_valley_in_window(
                audio, sr, 0.0, search_start, search_end
            )
            # Ensure cut advances significantly
            if valley_cut <= curr_start + min_duration or valley_cut >= end_s - min_duration:
                valley_cut = nominal_cut
        else:
            valley_cut = nominal_cut

        results.append((round(curr_start, 3), round(valley_cut, 3)))
        curr_start = valley_cut

    return results


def detect_silence_intervals(
    wav_path: str,
    silence_thresh_db: float = -38.0,
    min_silence_duration: float = 0.35
) -> List[Tuple[float, float]]:
    """
    Detects silence intervals in audio using ffmpeg silencedetect filter.
    Default min_silence_duration is 0.35s to capture character conversational turn-taking
    and natural sentence endings without grouping distinct speakers into run-on segments.
    Returns a list of (silence_start, silence_end) in seconds.
    """
    silences = []
    try:
        # Vocal-bandpass filtered silencedetect
        args = [
            "-i", wav_path,
            "-af", f"highpass=f=180,lowpass=f=3500,silencedetect=noise={silence_thresh_db}dB:d={min_silence_duration}",
            "-f", "null",
            "-"
        ]
        res = run_ffmpeg(args)
        output = res.stderr

        start_matches = re.findall(r"silence_start:\s*([0-9\.]+)", output)
        end_matches = re.findall(r"silence_end:\s*([0-9\.]+)", output)

        starts = [float(x) for x in start_matches]
        ends = [float(x) for x in end_matches]

        for i in range(min(len(starts), len(ends))):
            silences.append((starts[i], ends[i]))

        if not silences and res.returncode != 0:
            # Fallback to plain silencedetect if bandpass filter was unsupported
            plain_args = [
                "-i", wav_path,
                "-af", f"silencedetect=noise={silence_thresh_db}dB:d={min_silence_duration}",
                "-f", "null",
                "-"
            ]
            plain_res = run_ffmpeg(plain_args)
            plain_output = plain_res.stderr
            p_starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9\.]+)", plain_output)]
            p_ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9\.]+)", plain_output)]
            for i in range(min(len(p_starts), len(p_ends))):
                silences.append((p_starts[i], p_ends[i]))
    except Exception:
        pass
    return silences


def segment_audio_smart(
    wav_path: str,
    max_segment_duration: float = 8.0,
    min_segment_duration: float = 0.25,
    min_silence_duration: float = 0.30,
    silence_thresh_db: float = -38.0,
    boundary_padding_s: float = 0.20,
    audio_data: Optional[Any] = None,
    sr: int = 16000
) -> List[SpeechInterval]:
    """
    Intelligently segments audio into speech intervals corresponding to complete sentences
    and character dialogue turns:
    1. Uses hierarchical silence detection (0.30s default) to capture character turn-overs.
    2. Uses acoustic energy valley search on long continuous speech to split at natural breaths/pauses.
    3. Retains true speech start/end timestamps separate from acoustic extraction padding.
    4. Computes intra-segment pause timestamps for high-precision clause alignment.
    
    Returns a list of SpeechInterval objects (which unpack as (start, end) tuples for full backward compatibility).
    """
    duration = get_audio_duration_seconds(wav_path)
    if duration <= 0:
        return []

    # If audio data is not provided in memory, load it for acoustic energy valley search
    if audio_data is None:
        sf = _get_soundfile()
        if sf:
            try:
                audio_data, file_sr = sf.read(wav_path, dtype="float32")
                sr = file_sr
            except Exception:
                pass

    # Detect conversational turnover and sentence pauses
    silences = detect_silence_intervals(
        wav_path,
        silence_thresh_db=silence_thresh_db,
        min_silence_duration=min_silence_duration
    )

    # If ffmpeg silencedetect found no silences but audio array is present, try in-memory RMS pause detector
    if not silences and audio_data is not None:
        rms_pauses = find_intra_chunk_pauses(
            audio_data,
            sr=sr,
            offset_s=0.0,
            min_pause_s=min_silence_duration,
            silence_thresh_ratio=0.20
        )
        if rms_pauses:
            silences = rms_pauses

    raw_spans: List[Tuple[float, float]] = []
    current_pos = 0.0

    for s_start, s_end in silences:
        if s_start > current_pos:
            speech_len = s_start - current_pos
            if speech_len >= min_segment_duration:
                raw_spans.append((round(current_pos, 3), round(s_start, 3)))
        current_pos = s_end

    if current_pos < duration:
        speech_len = duration - current_pos
        if speech_len >= min_segment_duration:
            raw_spans.append((round(current_pos, 3), round(duration, 3)))

    if not raw_spans:
        raw_spans = [(0.0, duration)]

    # Subdivide long continuous spans using acoustic energy valley search
    final_intervals: List[SpeechInterval] = []
    for sp_start, sp_end in raw_spans:
        sp_dur = sp_end - sp_start
        if sp_dur > max_segment_duration and audio_data is not None:
            sub_spans = subdivide_speech_by_energy_valleys(
                audio=audio_data,
                sr=sr,
                start_s=sp_start,
                end_s=sp_end,
                max_duration=max_segment_duration,
                min_duration=min_segment_duration,
                target_duration=min(6.0, max_segment_duration)
            )
        elif sp_dur > max_segment_duration:
            num_sub = math.ceil(sp_dur / max_segment_duration)
            sub_len = sp_dur / num_sub
            sub_spans = [(round(sp_start + k * sub_len, 3), round(sp_start + (k + 1) * sub_len, 3)) for k in range(num_sub)]
        else:
            sub_spans = [(sp_start, sp_end)]

        for sub_s, sub_e in sub_spans:
            # Padded bounds for ASR acoustic context
            pad_s = max(0.0, sub_s - boundary_padding_s)
            pad_e = min(duration, sub_e + boundary_padding_s)

            # Find intra-segment micro-pauses for clause alignment
            pauses = []
            if audio_data is not None:
                sub_wave_s = max(0, int(sub_s * sr))
                sub_wave_e = min(len(audio_data), int(sub_e * sr))
                if sub_wave_e > sub_wave_s:
                    pauses = find_intra_chunk_pauses(
                        audio_data[sub_wave_s:sub_wave_e],
                        sr=sr,
                        offset_s=sub_s,
                        min_pause_s=0.10,
                        silence_thresh_ratio=0.20
                    )

            final_intervals.append(SpeechInterval(
                start=round(sub_s, 3),
                end=round(sub_e, 3),
                pad_start=round(pad_s, 3),
                pad_end=round(pad_e, 3),
                pauses=pauses
            ))

    return final_intervals
