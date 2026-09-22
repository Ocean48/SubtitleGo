import math
import os
import re
import subprocess
import wave
from typing import List, Tuple, Optional

from .ffmpeg_helper import get_ffmpeg_path, run_ffmpeg

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
    Falls back to torchaudio / soundfile if ffmpeg is unavailable.
    """
    ffmpeg_bin = get_ffmpeg_path()
    try:
        args = [
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
        res = run_ffmpeg(args)
        if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True
    except Exception:
        pass

    # Fallback via torchaudio / soundfile
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

    sf = _get_soundfile()
    if sf and torch and torchaudio:
        try:
            data, sr = sf.read(input_path, dtype="float32")
            waveform = torch.from_numpy(data)
            if waveform.ndim == 1:
                waveform = waveform.unsqueeze(0)
            else:
                waveform = waveform.t()
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)
            if sr != sample_rate:
                resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=sample_rate)
                waveform = resampler(waveform)
            torchaudio.save(output_path, waveform, sample_rate)
            return True
        except Exception as final_e:
            raise RuntimeError(f"Failed to extract audio from {input_path}: {final_e}")

    raise RuntimeError(f"Failed to extract audio using FFmpeg and fallback libraries from {input_path}")


def detect_silence_intervals(wav_path: str, silence_thresh_db: float = -36.0, min_silence_duration: float = 0.25) -> List[Tuple[float, float]]:
    """
    Detects silence intervals in audio using ffmpeg silencedetect filter.
    Returns a list of (silence_start, silence_end) in seconds.
    """
    silences = []
    try:
        args = [
            "-i", wav_path,
            "-af", f"silencedetect=noise={silence_thresh_db}dB:d={min_silence_duration}",
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
    except Exception:
        pass
    return silences


def segment_audio_smart(
    wav_path: str,
    max_segment_duration: float = 4.5,
    min_segment_duration: float = 0.25,
    silence_thresh_db: float = -36.0,
    boundary_padding_s: float = 0.08
) -> List[Tuple[float, float]]:
    """
    Segments long audio into speech segments with start and end timestamps.
    Uses silence detection to split at natural speech pauses for optimal subtitle cadence.
    Adds boundary padding to avoid clipping consonant onsets and tail word decays.
    If speech segments exceed max_segment_duration, splits them with small overlap to protect words.
    """
    duration = get_audio_duration_seconds(wav_path)
    if duration <= 0:
        return []

    # If audio is shorter than max segment duration, treat as single segment
    if duration <= max_segment_duration:
        return [(0.0, duration)]

    silences = detect_silence_intervals(wav_path, silence_thresh_db=silence_thresh_db, min_silence_duration=0.25)

    segments = []
    current_pos = 0.0
    overlap_s = 0.1

    for s_start, s_end in silences:
        if s_start > current_pos:
            speech_len = s_start - current_pos
            if speech_len >= min_segment_duration:
                if speech_len > max_segment_duration:
                    num_sub = math.ceil(speech_len / max_segment_duration)
                    sub_len = speech_len / num_sub
                    for k in range(num_sub):
                        sub_s = max(0.0, current_pos + k * sub_len - (overlap_s if k > 0 else boundary_padding_s))
                        sub_e = min(duration, min(current_pos + (k + 1) * sub_len + (overlap_s if k < num_sub - 1 else boundary_padding_s), s_start + boundary_padding_s))
                        segments.append((round(sub_s, 3), round(sub_e, 3)))
                else:
                    pad_s = max(0.0, current_pos - boundary_padding_s)
                    pad_e = min(duration, s_start + boundary_padding_s)
                    segments.append((round(pad_s, 3), round(pad_e, 3)))
        current_pos = s_end

    # Handle remaining speech at the end
    if current_pos < duration:
        speech_len = duration - current_pos
        if speech_len >= min_segment_duration:
            if speech_len > max_segment_duration:
                num_sub = math.ceil(speech_len / max_segment_duration)
                sub_len = speech_len / num_sub
                for k in range(num_sub):
                    sub_s = max(0.0, current_pos + k * sub_len - (overlap_s if k > 0 else boundary_padding_s))
                    sub_e = min(duration, current_pos + (k + 1) * sub_len + (overlap_s if k < num_sub - 1 else boundary_padding_s))
                    segments.append((round(sub_s, 3), round(sub_e, 3)))
            else:
                pad_s = max(0.0, current_pos - boundary_padding_s)
                segments.append((round(pad_s, 3), round(duration, 3)))

    # If no silence detected or empty segments, fallback to uniform slicing with slight overlap
    if not segments:
        num_chunks = math.ceil(duration / max_segment_duration)
        chunk_len = duration / num_chunks
        for i in range(num_chunks):
            s = max(0.0, i * chunk_len - (overlap_s if i > 0 else 0.0))
            e = min(duration, (i + 1) * chunk_len + (overlap_s if i < num_chunks - 1 else 0.0))
            segments.append((round(s, 3), round(e, 3)))

    return segments
