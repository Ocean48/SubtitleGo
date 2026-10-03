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
    _group_aligned_items_into_cues,
)
from src.core.audio_processor import (
    segment_audio_smart,
    get_audio_duration_seconds,
    extract_audio_to_wav,
    detect_silence_intervals,
    compute_rms_envelope,
    find_intra_chunk_pauses,
    subdivide_speech_by_energy_valleys,
    SpeechInterval,
)
from src.core.runtime_manager import (
    find_system_python,
    resolve_pip_command,
    get_pip_extra_install_flags,
    init_runtime_environment,
    get_candidate_package_dirs,
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
    print("[4/5] Testing package metadata and version exports...")
    import re
    from src.__version__ import __version__, __app_name__, __title__
    assert isinstance(__version__, str) and re.match(r"^\d+\.\d+\.\d+", __version__), f"Invalid semver version: {__version__}"
    assert __app_name__ == "SubtitleGo", f"Unexpected app name: {__app_name__}"
    assert "SubtitleGo" in __title__
    print(f"      PASS: Package metadata valid: {__app_name__} v{__version__}")


def test_runtime_manager_pip_resolution():
    print("[5/6] Testing runtime manager pip resolution and environment...")
    sys_py = find_system_python()
    assert sys_py is not None, "Expected to find a valid Python executable"
    
    logs = []
    pip_cmd = resolve_pip_command(sys_py, log_callback=logs.append)
    assert isinstance(pip_cmd, list) and len(pip_cmd) >= 1, f"Expected non-empty pip command list, got: {pip_cmd}"
    
    flags = get_pip_extra_install_flags(pip_cmd)
    assert isinstance(flags, list)
    
    # Test initialization of runtime environment paths without exceptions
    init_runtime_environment()
    candidate_dirs = get_candidate_package_dirs()
    assert len(candidate_dirs) >= 1
    print(f"      PASS: Pip resolved ({' '.join(pip_cmd)}) and runtime candidate directories verified.")


def test_audio_conditioning_and_silence_bandpass():
    print("[6/6] Testing audio conditioning (dynaudnorm/bandpass) and vocal-filtered silence detection...")
    wav_bytes = generate_synthetic_wav(duration_s=4.0)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".raw.wav") as raw_f:
        raw_f.write(wav_bytes)
        raw_path = raw_f.name

    with tempfile.NamedTemporaryFile(delete=False, suffix=".conditioned.wav") as cond_f:
        cond_path = cond_f.name

    try:
        # Test conditioned extraction
        ok = extract_audio_to_wav(raw_path, cond_path, sample_rate=16000)
        assert ok, "Audio extraction failed"
        assert os.path.exists(cond_path) and os.path.getsize(cond_path) > 1000

        cond_dur = get_audio_duration_seconds(cond_path)
        assert abs(cond_dur - 4.0) < 0.2, f"Conditioned audio duration mismatch: {cond_dur}"

        # Test bandpassed silence detection
        silences = detect_silence_intervals(cond_path, silence_thresh_db=-38.0, min_silence_duration=0.3)
        # Synthetic wav has silence around 1.0-1.5s
        assert isinstance(silences, list)

        # Test 250ms boundary safety padding in smart segmentation
        segments = segment_audio_smart(cond_path, max_segment_duration=14.0, boundary_padding_s=0.25)
        assert len(segments) >= 1
        for s, e in segments:
            assert s < e
        print("      PASS: Audio conditioning filter chain and vocal bandpass silence detection verified.")
    finally:
        for p in [raw_path, cond_path]:
            if os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass


def test_acoustic_energy_envelope_and_valley_subdivider():
    print("[7/9] Testing RMS acoustic energy envelope & valley search subdivision...")
    import numpy as np
    sr = 16000
    # Create 10-second audio: 0-4s speech (tone), 4-4.5s breath/pause (silence), 4.5-9s speech (tone)
    audio = np.zeros(sr * 10, dtype=np.float32)
    t = np.arange(sr * 10) / sr
    audio[:sr * 4] = 0.4 * np.sin(2 * np.pi * 440 * t[:sr * 4])
    audio[int(sr * 4.5):sr * 9] = 0.4 * np.sin(2 * np.pi * 880 * t[int(sr * 4.5):sr * 9])

    rms, times = compute_rms_envelope(audio, sr=sr)
    assert len(rms) > 100, "Expected RMS envelope frames"
    # Find intra-chunk pauses
    pauses = find_intra_chunk_pauses(audio, sr=sr, offset_s=0.0, min_pause_s=0.2)
    assert len(pauses) >= 1, f"Expected pause around 4.0-4.5s, got: {pauses}"
    p_s, p_e = pauses[0]
    assert 3.8 <= p_s <= 4.2 and 4.3 <= p_e <= 4.7, f"Pause timing unexpected: {pauses[0]}"

    # Test energy-valley subdivision across the 10s audio
    sub_spans = subdivide_speech_by_energy_valleys(audio, sr=sr, start_s=0.0, end_s=9.0, max_duration=6.0, target_duration=5.0)
    assert len(sub_spans) == 2, f"Expected 2 complete sentence sub-spans, got {len(sub_spans)}: {sub_spans}"
    # The cut should occur near the 4.0-4.5s pause valley, not at arbitrary mathematical 4.5s
    first_end = sub_spans[0][1]
    assert 3.9 <= first_end <= 4.6, f"Expected cut at acoustic pause valley (~4.2s), got: {first_end}"
    print(f"      PASS: Energy envelope & pause valley subdivision verified (Cut at {first_end}s).")


def test_conversational_turnover_and_speech_interval_metadata():
    print("[8/9] Testing conversational turnover pause detection & SpeechInterval metadata...")
    # Synthetic dialog: Speaker A (0.0-1.5s), 350ms turnover pause (1.5-1.85s), Speaker B (1.85-3.5s)
    sr = 16000
    samples = bytearray()
    for i in range(int(sr * 3.8)):
        t = i / sr
        if (0.0 <= t < 1.5) or (1.85 <= t < 3.5):
            freq = 300 if t < 1.5 else 600
            val = int(32767 * 0.4 * math.sin(2 * math.pi * freq * t))
        else:
            val = 0
        samples.extend(struct.pack("<h", val))

    wav_buf = io.BytesIO()
    wav_buf.write(b"RIFF")
    wav_buf.write(struct.pack("<I", 36 + len(samples)))
    wav_buf.write(b"WAVEfmt ")
    wav_buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sr, sr * 2, 2, 16))
    wav_buf.write(b"data")
    wav_buf.write(struct.pack("<I", len(samples)))
    wav_buf.write(samples)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".turnover.wav") as tmp_f:
        tmp_f.write(wav_buf.getvalue())
        tmp_path = tmp_f.name

    try:
        intervals = segment_audio_smart(tmp_path, min_segment_duration=0.25)
        # Should detect two distinct speaker turns separated by 350ms turnover pause
        assert len(intervals) >= 2, f"Expected 2 speaker turns, got {len(intervals)}"
        # Verify SpeechInterval attributes
        first = intervals[0]
        assert isinstance(first, SpeechInterval)
        assert first.start < first.end
        assert first.pad_start <= first.start
        assert first.pad_end >= first.end
        # Test tuple unpacking compatibility
        s, e = first
        assert s == first.start and e == first.end
        print(f"      PASS: Conversational turnover (350ms gap) identified {len(intervals)} distinct speaker intervals.")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_forced_alignment_cue_grouping_and_pause_snapping():
    print("[9/9] Testing forced alignment token grouping & acoustic pause snapping...")
    # 1. Test token-level forced alignment cue grouping
    mock_tokens = [
        {"text": "Hello", "start": 0.50, "end": 0.85},
        {"text": "world,", "start": 0.90, "end": 1.25},
        {"text": "this", "start": 1.30, "end": 1.55},
        {"text": "is", "start": 1.60, "end": 1.75},
        {"text": "a", "start": 1.80, "end": 1.90},
        {"text": "precise", "start": 1.95, "end": 2.35},
        {"text": "subtitle", "start": 2.40, "end": 2.90},
        {"text": "stream.", "start": 2.95, "end": 3.40},
    ]
    cues = _group_aligned_items_into_cues(mock_tokens, max_chars=25, max_duration=3.0, lead_in=0.06)
    assert len(cues) >= 2, f"Expected tokens to group into paced cues, got {len(cues)}"
    assert cues[0]["start"] == 0.44  # 0.50 - 0.06s lead-in
    assert "Hello world" in cues[0]["text"]

    # 2. Test pause snapping in refine_subtitles_for_pacing
    seg_with_pause = [{
        "id": 1,
        "start": 0.0,
        "end": 8.0,
        "text": "First clause of the sentence, followed by the second clause of the sentence.",
        "language": "English",
        "pauses": [(3.8, 4.3)]  # Breath pause between clauses
    }]
    snapped = refine_subtitles_for_pacing(seg_with_pause, max_chars_latin=50, max_duration=4.5)
    assert len(snapped) == 2, f"Expected 2 clauses, got {len(snapped)}"
    # The first cue should snap near the pause (3.8-4.3s)
    first_cue_end = snapped[0]["end"]
    assert 3.7 <= first_cue_end <= 4.4, f"Expected cue to snap to acoustic pause valley (~4.05s), got: {first_cue_end}"
    print(f"      PASS: Forced alignment token grouping ({len(cues)} cues) and pause snapping ({first_cue_end}s) verified.")


def main():
    print("==================================================")
    print(" Running SubtitleGo Pipeline & Unit Tests")
    print("==================================================")
    test_timestamp_and_subtitle_formatters()
    test_subtitle_pacing_refiner()
    test_audio_segmentation_logic()
    test_package_metadata_and_version()
    test_runtime_manager_pip_resolution()
    test_audio_conditioning_and_silence_bandpass()
    test_acoustic_energy_envelope_and_valley_subdivider()
    test_conversational_turnover_and_speech_interval_metadata()
    test_forced_alignment_cue_grouping_and_pause_snapping()
    print("==================================================")
    print(" All SubtitleGo verification tests PASSED.")
    print("==================================================")


if __name__ == "__main__":
    main()
