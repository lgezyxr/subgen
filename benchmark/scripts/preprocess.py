"""Benchmark preprocessor: ASS/SRT → normalized segment dicts.

Reads subtitle files produced by SubGen (clean) or fansub groups (noisy)
and outputs a flat list of segment dicts suitable for ASR / translation
evaluation.

Output format per segment::

    {"start": 12.3, "end": 15.6, "source": "Hello", "translation": "你好",
     "type": "dialogue", "style": "Default"}
"""

from __future__ import annotations

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def preprocess(path: str | Path, source_lang: str = "auto") -> list[dict]:
    """Parse an ASS or SRT file and return normalised segment dicts.

    Parameters
    ----------
    path : str | Path
        Path to the subtitle file (.ass or .srt).
    source_lang : str
        ISO-639-1 code for the source language, or ``"auto"`` to detect
        from the script type of the text.

    Returns
    -------
    list[dict]
        Each dict has keys: ``start``, ``end``, ``source``, ``translation``,
        ``type``, ``style``.
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".ass":
        raw = _parse_ass(path)
    elif suffix == ".srt":
        raw = _parse_srt(path)
    else:
        raise ValueError(f"Unsupported subtitle format: {suffix}")

    # Detect main / lyrics styles (ASS only – SRT has no style info)
    main_style = _detect_main_style(raw) if suffix == ".ass" else None
    lyrics_styles = _detect_lyrics_styles(raw) if suffix == ".ass" else set()

    # Filter noise
    filtered = _filter_noise(raw, main_style, lyrics_styles)

    # Assign type, strip tags, split bilingual
    segments: list[dict] = []
    for seg in filtered:
        text = _strip_ass_tags(seg["text"])
        if not text.strip():
            continue

        style = seg.get("style", "Default")

        # Determine segment type
        if style in lyrics_styles:
            seg_type = "lyrics"
        else:
            seg_type = "dialogue"

        # Detect source language if auto
        lang = source_lang
        if lang == "auto":
            lang = _classify_script(text)

        # Try splitting bilingual lines
        source, translation = _split_bilingual(text, lang)

        segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "source": source,
            "translation": translation,
            "type": seg_type,
            "style": style,
        })

    return segments


# ---------------------------------------------------------------------------
# ASS parser
# ---------------------------------------------------------------------------

def _parse_ass(path: Path) -> list[dict]:
    """Parse an ASS file into raw segment dicts.

    Reads the ``Format:`` line under ``[Events]`` to determine column order,
    then splits each ``Dialogue:`` line by ``,`` with the correct maxsplit
    (since the Text field may contain commas).
    """
    content = path.read_text(encoding="utf-8-sig")
    lines = content.splitlines()

    field_order: list[str] = []
    segments: list[dict] = []
    in_events = False

    for line in lines:
        stripped = line.strip()

        # Section headers
        if stripped.startswith("[") and stripped.endswith("]"):
            in_events = stripped.lower() == "[events]"
            continue

        if not in_events:
            continue

        # Format line
        if stripped.lower().startswith("format:"):
            raw_fields = stripped.split(":", 1)[1]
            field_order = [f.strip().lower() for f in raw_fields.split(",")]
            continue

        # Dialogue / Comment lines
        if ":" not in stripped:
            continue

        line_type_str, _, rest = stripped.partition(":")
        line_type_str = line_type_str.strip().lower()

        if line_type_str not in ("dialogue", "comment"):
            continue

        if not field_order:
            continue

        # Split with maxsplit = len(field_order) - 1
        # so the last field (Text) keeps its commas
        parts = rest.split(",", maxsplit=len(field_order) - 1)
        if len(parts) < len(field_order):
            continue

        fields = {}
        for i, name in enumerate(field_order):
            fields[name] = parts[i].strip()

        start = _parse_ass_timestamp(fields.get("start", "0:00:00.00"))
        end = _parse_ass_timestamp(fields.get("end", "0:00:00.00"))
        text = fields.get("text", "")
        style = fields.get("style", "Default")

        segments.append({
            "start": start,
            "end": end,
            "text": text,
            "style": style,
            "line_type": line_type_str,
        })

    return segments


def _parse_ass_timestamp(ts: str) -> float:
    """Convert ASS timestamp ``H:MM:SS.cc`` to seconds."""
    ts = ts.strip()
    parts = ts.split(":")
    if len(parts) != 3:
        return 0.0
    try:
        h = int(parts[0])
        m = int(parts[1])
        s = float(parts[2])
        return h * 3600 + m * 60 + s
    except (ValueError, IndexError):
        return 0.0


# ---------------------------------------------------------------------------
# SRT parser
# ---------------------------------------------------------------------------

_SRT_TS_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
    r"\s*-->\s*"
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)


def _parse_srt(path: Path) -> list[dict]:
    """Parse an SRT file into raw segment dicts."""
    content = path.read_text(encoding="utf-8-sig")
    blocks = re.split(r"\n\n+", content.strip())

    segments: list[dict] = []
    for block in blocks:
        lines = block.strip().splitlines()
        if not lines:
            continue

        # Find the timestamp line
        ts_line_idx = None
        for i, ln in enumerate(lines):
            if _SRT_TS_RE.search(ln):
                ts_line_idx = i
                break

        if ts_line_idx is None:
            continue

        m = _SRT_TS_RE.search(lines[ts_line_idx])
        if not m:
            continue

        start = (
            int(m.group(1)) * 3600
            + int(m.group(2)) * 60
            + int(m.group(3))
            + int(m.group(4)) / 1000
        )
        end = (
            int(m.group(5)) * 3600
            + int(m.group(6)) * 60
            + int(m.group(7))
            + int(m.group(8)) / 1000
        )

        text_lines = lines[ts_line_idx + 1:]
        text = "\n".join(text_lines)

        segments.append({
            "start": start,
            "end": end,
            "text": text,
            "style": "Default",
            "line_type": "dialogue",
        })

    return segments


# ---------------------------------------------------------------------------
# Noise filtering
# ---------------------------------------------------------------------------

def _filter_noise(
    segments: list[dict],
    main_style: str | None,
    lyrics_styles: set[str],
) -> list[dict]:
    """Remove noisy segments that should not be evaluated.

    Noise criteria:
    - Comment lines (line_type == "comment")
    - Vector drawings (``\\p1`` tag)
    - Duration > 600 s (watermarks / static signs)
    - Pure-tag lines (only ``{...}`` blocks, no visible text)
    - Credits at boundaries (first/last 5 s of the file with short text)
    """
    if not segments:
        return []

    # Determine file boundaries for credits detection
    all_starts = [s["start"] for s in segments]
    all_ends = [s["end"] for s in segments]
    file_start = min(all_starts)
    file_end = max(all_ends)

    keep_styles = set()
    if main_style:
        keep_styles.add(main_style)
    keep_styles.update(lyrics_styles)

    result: list[dict] = []
    for seg in segments:
        # Skip comments
        if seg.get("line_type") == "comment":
            continue

        text = seg.get("text", "")

        # Skip vector drawings
        if r"\p1" in text or r"\p2" in text:
            continue

        # Skip very long duration (watermarks)
        duration = seg["end"] - seg["start"]
        if duration > 600:
            continue

        # Skip pure-tag lines (only {...} blocks, no visible text)
        stripped_text = _strip_ass_tags(text).strip()
        if not stripped_text:
            continue

        # Skip credits at file boundaries
        if _is_credits(seg, stripped_text, file_start, file_end):
            continue

        # If we know the main style, filter out non-main, non-lyrics styles
        # (e.g. signs, title cards)
        if keep_styles and seg.get("style") not in keep_styles:
            continue

        result.append(seg)

    return result


def _is_credits(
    seg: dict, text: str, file_start: float, file_end: float
) -> bool:
    """Detect credit lines at the beginning or end of the file.

    Heuristic: within 5 s of file boundaries, text ≤ 30 chars, and matches
    common credit patterns (Translator, Timer, Encoder, etc.).
    """
    CREDIT_RE = re.compile(
        r"(?i)(translat|timer|typeset|encod|edit|qc|kfx|karaoke|"
        r"subtitle[sd]?\s*by|字幕|翻译|校对|时间轴|压制|特效)"
    )

    at_start = seg["start"] < file_start + 5
    at_end = seg["end"] > file_end - 5

    if (at_start or at_end) and len(text) <= 50 and CREDIT_RE.search(text):
        return True
    return False


# ---------------------------------------------------------------------------
# Style detection
# ---------------------------------------------------------------------------

def _detect_main_style(segments: list[dict]) -> str | None:
    """Return the most frequently used style (= main dialogue style).

    Only considers non-comment Dialogue lines.  Styles whose names match
    lyrics keywords are excluded so that OP/ED styles don't compete with
    the actual dialogue style.
    """
    # First pass: identify lyrics-style names to exclude
    lyrics = _detect_lyrics_styles(segments)

    style_counts: dict[str, int] = {}
    for seg in segments:
        if seg.get("line_type") == "comment":
            continue
        style = seg.get("style", "Default")
        if style in lyrics:
            continue
        style_counts[style] = style_counts.get(style, 0) + 1

    if not style_counts:
        return None

    return max(style_counts, key=style_counts.get)  # type: ignore[arg-type]


_LYRICS_KEYWORDS = re.compile(
    r"(?i)(^op$|^ed$|^op\d|^ed\d|opening|ending|"
    r"lyric|song|insert|歌词|歌|片头|片尾|"
    r"romaji|roma(?:ji)?$|ruby|karaoke|kfx)",
)


def _detect_lyrics_styles(segments: list[dict]) -> set[str]:
    """Return styles whose names match lyrics-related keywords."""
    styles: set[str] = set()
    seen: set[str] = set()
    for seg in segments:
        style = seg.get("style", "Default")
        if style in seen:
            continue
        seen.add(style)
        if _LYRICS_KEYWORDS.search(style):
            styles.add(style)
    return styles


# ---------------------------------------------------------------------------
# Tag stripping
# ---------------------------------------------------------------------------

_ASS_TAG_RE = re.compile(r"\{[^}]*\}")


def _strip_ass_tags(text: str) -> str:
    """Remove ASS override tag blocks ``{...}`` from *text*."""
    return _ASS_TAG_RE.sub("", text)


# ---------------------------------------------------------------------------
# Bilingual splitting
# ---------------------------------------------------------------------------

def _split_bilingual(text: str, source_lang: str) -> tuple[str, str]:
    r"""Split a potentially bilingual line on ``\N`` separator.

    If the text contains ``\N``, split into two parts and classify each
    by script type.  The part matching *source_lang* becomes ``source``;
    the other becomes ``translation``.

    If the text is monolingual, ``source`` gets the full text and
    ``translation`` is empty.

    Parameters
    ----------
    text : str
        Visible text (tags already stripped).
    source_lang : str
        ``"cjk"`` or ``"latin"`` (or an ISO code — we map ``ja``/``zh``/``ko``
        to CJK, everything else to Latin).

    Returns
    -------
    tuple[str, str]
        ``(source, translation)``
    """
    # Normalise source_lang to "cjk" or "latin"
    source_script = _lang_to_script(source_lang)

    # Check for \N separator (literal backslash-N in ASS)
    if r"\N" in text:
        parts = text.split(r"\N")
        # Take the first two meaningful parts
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) >= 2:
            script_a = _classify_script(parts[0])
            script_b = _classify_script(parts[1])

            # If scripts differ → bilingual
            if script_a != script_b:
                if _lang_to_script(script_a) == source_script:
                    return parts[0], parts[1]
                else:
                    return parts[1], parts[0]

            # Same script or can't distinguish — first is source
            return parts[0], parts[1]

        if len(parts) == 1:
            return parts[0], ""

    # Also check for literal newlines (SRT bilingual)
    if "\n" in text:
        parts = text.split("\n")
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) >= 2:
            script_a = _classify_script(parts[0])
            script_b = _classify_script(parts[1])

            if script_a != script_b:
                if _lang_to_script(script_a) == source_script:
                    return parts[0], parts[1]
                else:
                    return parts[1], parts[0]

            return parts[0], parts[1]

        if len(parts) == 1:
            return parts[0], ""

    return text.strip(), ""


def _lang_to_script(lang: str) -> str:
    """Map a language code or script label to ``"cjk"`` or ``"latin"``."""
    lang = lang.lower().strip()
    if lang in ("cjk", "ja", "zh", "ko", "jp", "cn", "chinese", "japanese", "korean"):
        return "cjk"
    return "latin"


# ---------------------------------------------------------------------------
# Script classification
# ---------------------------------------------------------------------------

# Unicode ranges for CJK characters
_CJK_RANGES = (
    (0x4E00, 0x9FFF),    # CJK Unified Ideographs
    (0x3400, 0x4DBF),    # CJK Unified Ideographs Extension A
    (0x3000, 0x303F),    # CJK Symbols and Punctuation
    (0x3040, 0x309F),    # Hiragana
    (0x30A0, 0x30FF),    # Katakana
    (0xAC00, 0xD7AF),    # Hangul Syllables
    (0xFF00, 0xFFEF),    # Halfwidth and Fullwidth Forms
    (0x1100, 0x11FF),    # Hangul Jamo
    (0x20000, 0x2A6DF),  # CJK Unified Ideographs Extension B
)


def _classify_script(text: str) -> str:
    """Classify text as ``"cjk"`` or ``"latin"`` by Unicode block counting.

    Returns ``"cjk"`` if more than 30 % of non-whitespace, non-punctuation
    characters fall in CJK Unicode ranges; otherwise ``"latin"``.
    """
    cjk_count = 0
    total = 0

    for ch in text:
        if ch.isspace():
            continue
        cp = ord(ch)
        total += 1
        for lo, hi in _CJK_RANGES:
            if lo <= cp <= hi:
                cjk_count += 1
                break

    if total == 0:
        return "latin"

    return "cjk" if cjk_count / total > 0.3 else "latin"
