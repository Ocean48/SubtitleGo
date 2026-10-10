import re
from typing import List, Dict, Any, Optional


def format_timestamp_srt(seconds: float) -> str:
    """Format seconds into SRT timestamp format: HH:MM:SS,mmm"""
    if seconds < 0:
        seconds = 0.0
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        secs += 1
        millis = 0
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def format_timestamp_vtt(seconds: float) -> str:
    """Format seconds into WebVTT timestamp format: HH:MM:SS.mmm"""
    if seconds < 0:
        seconds = 0.0
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        secs += 1
        millis = 0
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{millis:03d}"


def parse_timestamp_to_seconds(ts_str: str) -> float:
    """Parses SRT or VTT timestamp string to float seconds."""
    ts_str = ts_str.strip().replace(",", ".")
    parts = ts_str.split(":")
    if len(parts) == 3:
        hrs = float(parts[0])
        mins = float(parts[1])
        secs = float(parts[2])
        return hrs * 3600 + mins * 60 + secs
    elif len(parts) == 2:
        mins = float(parts[0])
        secs = float(parts[1])
        return mins * 60 + secs
    return 0.0


def build_srt_content(segments: List[Dict[str, Any]]) -> str:
    """Convert segment list into standard SubRip (.srt) subtitle string."""
    entries = []
    idx = 1
    for seg in segments:
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        start_ts = format_timestamp_srt(float(seg["start"]))
        end_ts = format_timestamp_srt(float(seg["end"]))
        entries.append(f"{idx}\n{start_ts} --> {end_ts}\n{text}\n")
        idx += 1
    return "\n".join(entries)


def build_vtt_content(segments: List[Dict[str, Any]]) -> str:
    """Convert segment list into standard WebVTT (.vtt) subtitle string."""
    entries = ["WEBVTT\n"]
    idx = 1
    for seg in segments:
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        start_ts = format_timestamp_vtt(float(seg["start"]))
        end_ts = format_timestamp_vtt(float(seg["end"]))
        entries.append(f"{idx}\n{start_ts} --> {end_ts}\n{text}\n")
        idx += 1
    return "\n".join(entries)


def build_txt_content(segments: List[Dict[str, Any]]) -> str:
    """Convert segment list into plain transcript text with timestamps."""
    lines = []
    for seg in segments:
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        start_ts = format_timestamp_srt(float(seg["start"]))
        end_ts = format_timestamp_srt(float(seg["end"]))
        lines.append(f"[{start_ts} --> {end_ts}] {text}")
    return "\n".join(lines)


def parse_srt_content(srt_text: str) -> List[Dict[str, Any]]:
    """Parses raw SRT content into structured cue dictionaries."""
    segments = []
    blocks = srt_text.strip().replace("\r\n", "\n").split("\n\n")
    cue_id = 1
    for block in blocks:
        lines = block.strip().split("\n")
        if not lines or len(lines) < 2:
            continue
        
        # Check if first line is index or timestamp
        ts_line_idx = 1 if "-->" in lines[1] else (0 if "-->" in lines[0] else -1)
        if ts_line_idx == -1:
            continue
            
        ts_line = lines[ts_line_idx]
        text = "\n".join(lines[ts_line_idx + 1:]).strip()
        if not text:
            continue
            
        m = re.match(r"([0-9:,\.]+)\s*-->\s*([0-9:,\.]+)", ts_line)
        if m:
            start_s = parse_timestamp_to_seconds(m.group(1))
            end_s = parse_timestamp_to_seconds(m.group(2))
            segments.append({
                "id": cue_id,
                "start": start_s,
                "end": end_s,
                "start_time": format_timestamp_srt(start_s),
                "end_time": format_timestamp_srt(end_s),
                "text": text,
                "language": "Unknown"
            })
            cue_id += 1
    return segments


def parse_vtt_content(vtt_text: str) -> List[Dict[str, Any]]:
    """Parses raw WebVTT content into structured cue dictionaries."""
    segments = []
    cleaned = vtt_text.replace("WEBVTT", "").strip().replace("\r\n", "\n")
    blocks = cleaned.split("\n\n")
    cue_id = 1
    for block in blocks:
        lines = block.strip().split("\n")
        if not lines:
            continue
        ts_line_idx = -1
        for i, l in enumerate(lines):
            if "-->" in l:
                ts_line_idx = i
                break
        if ts_line_idx == -1:
            continue

        ts_line = lines[ts_line_idx]
        text = "\n".join(lines[ts_line_idx + 1:]).strip()
        if not text:
            continue

        m = re.match(r"([0-9:,\.]+)\s*-->\s*([0-9:,\.]+)", ts_line)
        if m:
            start_s = parse_timestamp_to_seconds(m.group(1))
            end_s = parse_timestamp_to_seconds(m.group(2))
            segments.append({
                "id": cue_id,
                "start": start_s,
                "end": end_s,
                "start_time": format_timestamp_srt(start_s),
                "end_time": format_timestamp_srt(end_s),
                "text": text,
                "language": "Unknown"
            })
            cue_id += 1
    return segments


def _is_cjk(text: str) -> bool:
    """Detect if text contains significant Chinese, Japanese, or Korean characters."""
    cjk_count = len(re.findall(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', text))
    return cjk_count > (len(text.replace(" ", "")) * 0.3)


def remove_repetition_loops(text: str) -> str:
    """
    Suppresses ASR repetition loops (e.g. 'Thank you. Thank you. Thank you.' or '好的好的好的')
    that occur when ASR hallucinates on silence, music, or low-confidence audio.
    """
    if not text:
        return ""
    text = text.strip()

    # 1. Collapse identical consecutive sentences/clauses
    parts = re.split(r'([.!?，。、！？\n]+)', text)
    if len(parts) > 2:
        new_clauses = []
        last_norm = None
        for i in range(0, len(parts), 2):
            clause = parts[i].strip()
            punct = parts[i + 1] if i + 1 < len(parts) else ""
            norm = re.sub(r'[^\w]', '', clause.lower())
            if norm and norm == last_norm:
                continue
            if clause:
                new_clauses.append(clause + punct)
                last_norm = norm
        text = " ".join(new_clauses).strip()

    # 2. CJK character repetition (e.g. 好的好的好的 -> 好的)
    text = re.sub(r'([\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]{1,4})(?:\1){2,}', r'\1', text)

    # 3. Repeated word patterns in Latin (e.g. "word word word" -> "word")
    text = re.sub(r'\b([A-Za-z0-9\'-]+)(?:\s+\1\b){2,}', r'\1', text, flags=re.IGNORECASE)

    return text.strip()


def _normalize_token_for_match(token: str) -> str:
    """Strip punctuation and lowercase for comparison."""
    return re.sub(r'[^\w]', '', token.lower())


def deduplicate_chunk_boundary(prev_text: str, curr_text: str, is_cjk: bool = False) -> str:
    """
    Detects and strips duplicate words/characters occurring across adjacent chunk boundaries
    caused by acoustic padding overlap or contiguous speech between consecutive audio windows.
    Returns cleaned curr_text, or empty string if curr_text is fully redundant.
    """
    if not prev_text or not curr_text:
        return curr_text.strip()

    prev_clean = prev_text.strip()
    curr_clean = curr_text.strip()

    if prev_clean == curr_clean:
        return ""

    if is_cjk:
        p_chars = [c for c in prev_clean if not re.match(r'[\s\W_]', c)]
        c_chars = [c for c in curr_clean if not re.match(r'[\s\W_]', c)]
        if not p_chars or not c_chars:
            return curr_clean

        max_check = min(len(p_chars), len(c_chars), 14)
        best_overlap_len = 0
        for k in range(max_check, 1, -1):
            if p_chars[-k:] == c_chars[:k]:
                best_overlap_len = k
                break

        if best_overlap_len > 0:
            matched_count = 0
            cut_idx = len(curr_clean)
            for idx, ch in enumerate(curr_clean):
                if not re.match(r'[\s\W_]', ch):
                    matched_count += 1
                    if matched_count == best_overlap_len:
                        cut_idx = idx + 1
                        break
            while cut_idx < len(curr_clean) and curr_clean[cut_idx] in ' ，。、！？!?,.;:':
                cut_idx += 1
            return curr_clean[cut_idx:].strip()

        return curr_clean

    # Latin-based scripts: match word n-grams
    prev_words = prev_clean.split()
    curr_words = curr_clean.split()

    if not prev_words or not curr_words:
        return curr_clean

    norm_prev = [_normalize_token_for_match(w) for w in prev_words]
    norm_curr = [_normalize_token_for_match(w) for w in curr_words]

    p_nonempty = [(i, w) for i, w in enumerate(norm_prev) if w]
    c_nonempty = [(i, w) for i, w in enumerate(norm_curr) if w]

    if not p_nonempty or not c_nonempty:
        return curr_clean

    max_k = min(len(p_nonempty), len(c_nonempty), 8)
    best_k = 0
    for k in range(max_k, 0, -1):
        if [w for _, w in p_nonempty[-k:]] == [w for _, w in c_nonempty[:k]]:
            best_k = k
            break

    if best_k > 0:
        word_cut_idx = c_nonempty[best_k - 1][0] + 1
        remaining_words = curr_words[word_cut_idx:]
        return " ".join(remaining_words).strip()

    return curr_clean


def deduplicate_raw_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Cleans up ASR repetition loops and removes boundary duplicate text across consecutive raw segments.
    """
    if not segments:
        return []

    cleaned: List[Dict[str, Any]] = []
    prev_text = ""

    for seg in segments:
        text = str(seg.get("text", "")).strip()
        if not text:
            continue

        lang = seg.get("language", "Unknown")
        is_cjk_lang = _is_cjk(text) or (isinstance(lang, str) and any(c in lang.lower() for c in ["chinese", "cantonese", "japanese", "korean", "wu", "minnan"]))

        # 1. Remove intra-segment repetition loops
        text = remove_repetition_loops(text)
        if not text:
            continue

        # 2. Deduplicate cross-chunk boundary overlap
        if prev_text:
            text = deduplicate_chunk_boundary(prev_text, text, is_cjk=is_cjk_lang)
            if not text:
                continue

        seg_copy = dict(seg)
        seg_copy["text"] = text
        cleaned.append(seg_copy)
        prev_text = text

    return cleaned


# Common CJK particles and conjunctions after which a line cut is natural
CJK_BREAK_AFTER = [
    # Chinese conjunctions & particles
    "而且", "但是", "所以", "如果", "因为", "虽然", "那么", "并且", "以及",
    "的", "了", "着", "过", "和", "与", "及", "但", "而", "在", "向", "从", "到",
    # Japanese particles & auxiliaries
    "から", "ので", "けど", "して", "ても", "たら", "れば", "なら",
    "は", "が", "を", "に", "で", "と", "へ", "も", "や", "ね", "よ"
]

# Weak trailing words in Latin that should not be orphaned at line ends
LATIN_WEAK_ENDINGS = {
    "the", "a", "an", "to", "in", "on", "at", "for", "of", "by",
    "my", "your", "his", "her", "our", "their", "its",
    "i", "he", "she", "we", "they"
}


def _split_cjk_phrase(text: str, max_chars: int) -> List[str]:
    """Splits a long CJK phrase cleanly without cutting compound words or characters mid-concept."""
    if len(text) <= max_chars:
        return [text] if text else []

    chunks: List[str] = []
    rem = text.strip()

    while len(rem) > max_chars:
        min_cut = max(2, int(max_chars * 0.45))
        window = rem[:max_chars]

        best_cut = -1
        # 1. Look for punctuation in window
        punct_matches = [m.end() for m in re.finditer(r'[\s，、；：,;:]', window) if m.end() >= min_cut]
        if punct_matches:
            best_cut = punct_matches[-1]

        # 2. Look for natural CJK particles / conjunctions
        if best_cut == -1:
            for p in CJK_BREAK_AFTER:
                pos = window.rfind(p)
                if pos != -1:
                    cut_pos = pos + len(p)
                    if min_cut <= cut_pos <= max_chars:
                        if cut_pos > best_cut:
                            best_cut = cut_pos

        # 3. Fallback: hard cut at max_chars
        if best_cut == -1 or best_cut < min_cut:
            best_cut = max_chars

        chunk = rem[:best_cut].strip()
        if chunk:
            chunks.append(chunk)
        rem = rem[best_cut:].strip()

    if rem:
        chunks.append(rem)
    return chunks


def _split_latin_phrase(text: str, max_chars: int) -> List[str]:
    """Splits a long Latin phrase cleanly using syntactic word boundaries."""
    words = text.split()
    if not words:
        return []

    chunks: List[str] = []
    curr: List[str] = []

    for w in words:
        cand = curr + [w]
        cand_str = " ".join(cand)
        if len(cand_str) <= max_chars:
            curr.append(w)
        else:
            if curr:
                # If last word in curr is a weak ending (e.g. "the", "in") and we have > 1 words, roll it over
                if len(curr) > 1 and curr[-1].lower() in LATIN_WEAK_ENDINGS:
                    rollover = curr.pop()
                    chunks.append(" ".join(curr))
                    curr = [rollover, w]
                else:
                    chunks.append(" ".join(curr))
                    curr = [w]
            else:
                chunks.append(w)
                curr = []

    if curr:
        chunks.append(" ".join(curr))

    return chunks


def _split_text_into_chunks(text: str, max_chars: int) -> List[str]:
    """Splits text into readable chunks adhering to character limits and natural linguistic phrasing."""
    text = text.strip()
    if not text or len(text) <= max_chars:
        return [text] if text else []

    is_cjk_text = _is_cjk(text)

    clause_delimiters = r'([。！？!?；;\n]+|[，,、]+\s*)'
    tokens = re.split(clause_delimiters, text)

    chunks = []
    current = ""
    for token in tokens:
        if not token:
            continue
        if len(current) + len(token) <= max_chars:
            current += token
        else:
            if current.strip():
                chunks.append(current.strip())
            current = token
    if current.strip():
        chunks.append(current.strip())

    final_chunks = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            final_chunks.append(chunk)
            continue

        if is_cjk_text:
            cjk_chunks = _split_cjk_phrase(chunk, max_chars)
            final_chunks.extend(cjk_chunks)
        else:
            latin_chunks = _split_latin_phrase(chunk, max_chars)
            final_chunks.extend(latin_chunks)

    return [c for c in final_chunks if c]


def _group_aligned_items_into_cues(
    items: List[Dict[str, Any]],
    max_chars: int,
    max_duration: float = 4.5,
    min_duration: float = 0.3,
    lead_in: float = 0.06,
    lang: str = "Unknown"
) -> List[Dict[str, Any]]:
    """
    Groups word/token forced alignment items into pacing-compliant subtitle cues.
    """
    if not items:
        return []

    is_cjk = any(_is_cjk(it.get("text", "")) for it in items) or any(c in lang.lower() for c in ["chinese", "cantonese", "japanese", "korean", "wu", "minnan"])
    cues = []
    current_tokens: List[Dict[str, Any]] = []

    def flush_cue():
        nonlocal current_tokens
        if not current_tokens:
            return
        if is_cjk:
            cue_text = "".join(it["text"] for it in current_tokens).strip()
        else:
            cue_text = " ".join(it["text"] for it in current_tokens).strip()

        if not cue_text:
            current_tokens = []
            return

        c_start = max(0.0, float(current_tokens[0].get("start", 0.0)) - lead_in)
        c_end = max(float(current_tokens[-1].get("end", c_start + min_duration)), c_start + min_duration)

        cues.append({
            "start": round(c_start, 3),
            "end": round(c_end, 3),
            "start_time": format_timestamp_srt(c_start),
            "end_time": format_timestamp_srt(c_end),
            "text": cue_text,
            "language": lang
        })
        current_tokens = []

    for idx, item in enumerate(items):
        token_txt = str(item.get("text", "")).strip()
        if not token_txt:
            continue

        if not current_tokens:
            current_tokens.append(item)
            continue

        # Check candidate length
        if is_cjk:
            cand_len = sum(len(it.get("text", "")) for it in current_tokens) + len(token_txt)
        else:
            cand_len = sum(len(it.get("text", "")) for it in current_tokens) + len(current_tokens) + len(token_txt)

        first_start = float(current_tokens[0].get("start", 0.0))
        item_end = float(item.get("end", first_start))
        cand_dur = item_end - first_start

        prev_end = float(current_tokens[-1].get("end", 0.0))
        curr_start = float(item.get("start", prev_end))
        gap_s = curr_start - prev_end

        # Split conditions: character overflow, duration overflow, major punctuation, or conversational pause
        prev_txt = str(current_tokens[-1].get("text", ""))
        is_sentence_end = bool(re.search(r"[。！？!?；;\n]$", prev_txt))
        has_turnover_gap = gap_s >= 0.35  # Conversational turnover pause

        if cand_len > max_chars or cand_dur > max_duration or (is_sentence_end and cand_dur >= 1.0) or has_turnover_gap:
            flush_cue()
            current_tokens.append(item)
        else:
            current_tokens.append(item)

    flush_cue()
    return cues


def refine_subtitles_for_pacing(
    segments: List[Dict[str, Any]],
    max_chars_latin: int = 42,
    max_chars_cjk: int = 18,
    max_duration: float = 4.5,
    min_duration: float = 0.3,
    lead_in: float = 0.06
) -> List[Dict[str, Any]]:
    """
    Post-processes subtitle segments to adhere to optimal pacing standards:
    - Automatically deduplicates boundary overlaps and repetition loops across chunks
    - Target 2.0 to 4.5s per cue
    - Max 42 characters per line for Latin scripts, 18 characters for CJK
    - Uses exact token/word timestamps when forced aligner data is present
    - Uses acoustic RMS pause valleys to anchor clause splits when available
    - Proportionally interpolates timestamps across split cues with visual lead-in
    - Re-numbers cues sequentially
    """
    # 1. Clean up repetition loops and cross-chunk boundary duplicates
    deduped_segments = deduplicate_raw_segments(segments)

    refined: List[Dict[str, Any]] = []
    cue_id = 1

    for seg in deduped_segments:
        text = str(seg.get("text", "")).strip()
        if not text:
            continue

        raw_start = float(seg.get("start", 0.0))
        raw_end = float(seg.get("end", raw_start + 1.0))
        # Apply standard broadcast visual cognitive lead-in (60ms)
        start_time = max(0.0, raw_start - lead_in)
        end_time = max(raw_end, start_time + min_duration)
        duration = max(min_duration, end_time - start_time)
        lang = seg.get("language", "Unknown")
        time_stamps = seg.get("time_stamps", [])
        pauses = seg.get("pauses", [])

        is_cjk_lang = _is_cjk(text) or (isinstance(lang, str) and any(c in lang.lower() for c in ["chinese", "cantonese", "japanese", "korean", "wu", "minnan"]))
        max_chars = max_chars_cjk if is_cjk_lang else max_chars_latin

        # 1. Neural Forced Alignment Branch (Highest precision)
        if time_stamps:
            aligned_cues = _group_aligned_items_into_cues(
                items=time_stamps,
                max_chars=max_chars,
                max_duration=max_duration,
                min_duration=min_duration,
                lead_in=lead_in,
                lang=lang
            )
            if aligned_cues:
                for c in aligned_cues:
                    c["id"] = cue_id
                    refined.append(c)
                    cue_id += 1
                continue

        # 2. Acoustic Energy & Pacing Split Branch
        needs_split = (len(text) > max_chars) or (duration > max_duration)
        if not needs_split:
            refined.append({
                "id": cue_id,
                "start": round(start_time, 3),
                "end": round(end_time, 3),
                "start_time": format_timestamp_srt(start_time),
                "end_time": format_timestamp_srt(end_time),
                "text": text,
                "language": lang
            })
            cue_id += 1
            continue

        chunks = _split_text_into_chunks(text, max_chars)
        if len(chunks) <= 1:
            refined.append({
                "id": cue_id,
                "start": round(start_time, 3),
                "end": round(end_time, 3),
                "start_time": format_timestamp_srt(start_time),
                "end_time": format_timestamp_srt(end_time),
                "text": text,
                "language": lang
            })
            cue_id += 1
            continue

        total_chars = sum(max(1, len(c)) for c in chunks)
        cursor_time = start_time
        cum_chars = 0

        for i, chunk in enumerate(chunks):
            cum_chars += max(1, len(chunk))
            if i == len(chunks) - 1:
                c_start = cursor_time
                c_end = end_time
            else:
                nominal_end = start_time + duration * (cum_chars / total_chars)
                # Energy Pause Snapping: find nearest acoustic pause trough
                best_pause_cut = None
                if pauses:
                    for p_s, p_e in pauses:
                        p_mid = (p_s + p_e) / 2.0
                        if abs(p_mid - nominal_end) <= 1.0:
                            if best_pause_cut is None or abs(p_mid - nominal_end) < abs(best_pause_cut - nominal_end):
                                best_pause_cut = p_mid

                if best_pause_cut is not None:
                    c_end = max(cursor_time + min_duration, min(best_pause_cut, end_time - min_duration))
                else:
                    c_end = nominal_end

                c_start = cursor_time
                c_end = max(c_end, c_start + min_duration)
                if c_end > end_time:
                    c_end = end_time

            refined.append({
                "id": cue_id,
                "start": round(c_start, 3),
                "end": round(c_end, 3),
                "start_time": format_timestamp_srt(c_start),
                "end_time": format_timestamp_srt(c_end),
                "text": chunk,
                "language": lang
            })
            cue_id += 1
            cursor_time = c_end

    return refined
