import io
import math
import os
import struct
import sys
import tempfile
import time
import urllib.request
import urllib.parse
import urllib.error

# Add src to sys.path to test core utility functions directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from src.core.subtitle_formatter import (
    format_timestamp_srt,
    format_timestamp_vtt,
    build_srt_content,
    build_vtt_content,
    refine_subtitles_for_pacing,
)
from src.core.audio_processor import (
    segment_audio_smart,
    get_audio_duration_seconds,
)


def generate_synthetic_wav(duration_s: float = 3.0, sample_rate: int = 16000) -> bytes:
    """Generates a synthetic 16kHz mono WAV file with intermittent tones and silences."""
    num_samples = int(sample_rate * duration_s)
    raw_samples = bytearray()
    
    # 0.0 - 1.0s tone (440Hz)
    # 1.0 - 1.5s silence
    # 1.5 - 2.8s tone (880Hz)
    # 2.8 - 3.0s silence
    for i in range(num_samples):
        t = i / sample_rate
        if (0.0 <= t < 1.0) or (1.5 <= t < 2.8):
            freq = 440 if t < 1.0 else 880
            val = int(32767 * 0.4 * math.sin(2 * math.pi * freq * t))
        else:
            val = 0
        raw_samples.extend(struct.pack("<h", val))

    wav_buffer = io.BytesIO()
    wav_buffer.write(b"RIFF")
    wav_buffer.write(struct.pack("<I", 36 + len(raw_samples)))
    wav_buffer.write(b"WAVEfmt ")
    wav_buffer.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
    wav_buffer.write(b"data")
    wav_buffer.write(struct.pack("<I", len(raw_samples)))
    wav_buffer.write(raw_samples)
    return wav_buffer.getvalue()


def test_timestamp_and_subtitle_formatters():
    print("[1/4] Testing Subtitle timestamp & format utilities...")
    
    # Test SRT timestamp formatting
    ts_srt = format_timestamp_srt(65.432)
    assert ts_srt == "00:01:05,432", f"SRT timestamp mismatch: got {ts_srt}"
    
    # Test VTT timestamp formatting
    ts_vtt = format_timestamp_vtt(3661.050)
    assert ts_vtt == "01:01:01.050", f"VTT timestamp mismatch: got {ts_vtt}"

    # Test subtitle builders
    mock_segments = [
        {
            "id": 1,
            "start": 0.5,
            "end": 3.2,
            "start_time": "00:00:00,500",
            "end_time": "00:00:03,200",
            "text": "Hello and welcome to the video."
        },
        {
            "id": 2,
            "start": 3.5,
            "end": 6.8,
            "start_time": "00:00:03,500",
            "end_time": "00:00:06,800",
            "text": "This subtitle is generated with Qwen3-ASR."
        }
    ]

    srt_out = build_srt_content(mock_segments)
    assert "1\n00:00:00,500 --> 00:00:03,200\nHello and welcome to the video." in srt_out
    assert "2\n00:00:03,500 --> 00:00:06,800\nThis subtitle is generated with Qwen3-ASR." in srt_out

    vtt_out = build_vtt_content(mock_segments)
    assert vtt_out.startswith("WEBVTT\n")
    assert "00:00:00.500 --> 00:00:03.200" in vtt_out

    print("      PASS: Timestamp and subtitle formats (.srt & .vtt) verified.")


def test_subtitle_pacing_refiner():
    print("[2/5] Testing subtitle pacing & length refinement...")

    # Long sentence in English that exceeds 42 chars and 4.5s
    long_english_segment = [
        {
            "id": 1,
            "start": 0.0,
            "end": 8.0,
            "start_time": "00:00:00,000",
            "end_time": "00:00:08,000",
            "text": "Welcome to our in-depth tutorial, today we are going to explore modern speech recognition using neural models.",
            "language": "English"
        }
    ]

    refined = refine_subtitles_for_pacing(long_english_segment, max_chars_latin=42, max_duration=4.5)
    assert len(refined) >= 2, f"Expected long English segment to split, got {len(refined)} cues"
    for cue in refined:
        assert len(cue["text"]) <= 55, f"Cue text too long: {cue['text']}"
        assert cue["start"] < cue["end"], f"Invalid cue timing: {cue}"

    # CJK segment that exceeds 18 chars
    cjk_segment = [
        {
            "id": 1,
            "start": 0.0,
            "end": 6.0,
            "start_time": "00:00:00,000",
            "end_time": "00:00:06,000",
            "text": "欢迎大家收看本期视频，今天我们将详细介绍如何利用语音识别技术生成高质量字幕。",
            "language": "Chinese"
        }
    ]

    cjk_refined = refine_subtitles_for_pacing(cjk_segment, max_chars_cjk=18, max_duration=4.5)
    assert len(cjk_refined) >= 2, f"Expected CJK segment to split into shorter cues, got {len(cjk_refined)}"
    for cue in cjk_refined:
        assert cue["start"] < cue["end"]

    print(f"      PASS: English split into {len(refined)} cues, CJK split into {len(cjk_refined)} cues.")


def test_audio_segmentation_logic():
    print("[3/5] Testing audio segmentation, short utterance retention & duration detection...")
    
    wav_bytes = generate_synthetic_wav(duration_s=4.0)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(wav_bytes)
        tmp_path = tmp.name

    try:
        duration = get_audio_duration_seconds(tmp_path)
        assert abs(duration - 4.0) < 0.1, f"Expected 4.0s duration, got {duration}"
        
        segments = segment_audio_smart(tmp_path, max_segment_duration=2.0, min_segment_duration=0.25)
        assert len(segments) >= 1, "Expected at least 1 segment"
        for s, e in segments:
            assert s < e, f"Invalid segment timing: {s} -> {e}"
        print(f"      PASS: Audio segmented into {len(segments)} intervals (Duration: {duration:.2f}s).")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # Test short speech pulse retention (< 0.8s, e.g. 0.3s)
    short_pulse_samples = bytearray()
    sr = 16000
    # 0.0 - 0.5s silence, 0.5 - 0.8s tone (0.3s short speech), 0.8 - 1.5s silence
    for i in range(int(sr * 1.5)):
        t = i / sr
        if 0.5 <= t < 0.8:
            val = int(32767 * 0.4 * math.sin(2 * math.pi * 440 * t))
        else:
            val = 0
        short_pulse_samples.extend(struct.pack("<h", val))

    short_wav = io.BytesIO()
    short_wav.write(b"RIFF")
    short_wav.write(struct.pack("<I", 36 + len(short_pulse_samples)))
    short_wav.write(b"WAVEfmt ")
    short_wav.write(struct.pack("<IHHIIHH", 16, 1, 1, sr, sr * 2, 2, 16))
    short_wav.write(b"data")
    short_wav.write(struct.pack("<I", len(short_pulse_samples)))
    short_wav.write(short_pulse_samples)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_short:
        tmp_short.write(short_wav.getvalue())
        tmp_short_path = tmp_short.name

    try:
        short_segments = segment_audio_smart(tmp_short_path, min_segment_duration=0.25)
        assert len(short_segments) >= 1, f"Expected short speech (0.3s) to be retained, got {len(short_segments)} segments"
        print(f"      PASS: Short speech pulse (0.3s) successfully retained in {len(short_segments)} segment(s).")
    finally:
        if os.path.exists(tmp_short_path):
            os.unlink(tmp_short_path)


def test_package_metadata_and_version():
    print("[4/4] Testing package metadata and version exports...")
    from src.__version__ import __version__, __app_name__, __title__
    assert __version__ == "1.0.0", f"Unexpected version: {__version__}"
    assert __app_name__ == "SubtitleGo", f"Unexpected app name: {__app_name__}"
    assert "SubtitleGo" in __title__
    print(f"      PASS: Package metadata valid: {__app_name__} v{__version__}")


def main():
    print("==================================================")
    print(" Running SubtitleGo Pipeline & Unit Tests")
    print("==================================================")
    test_timestamp_and_subtitle_formatters()
    test_subtitle_pacing_refiner()
    test_audio_segmentation_logic()
    test_package_metadata_and_version()
    print("==================================================")
    print(" All SubtitleGo verification tests PASSED.")
    print("==================================================")


if __name__ == "__main__":
    main()
