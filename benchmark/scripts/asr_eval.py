"""ASR evaluation: transcription quality metrics.

Compares generated (hypothesis) subtitle segments against reference segments
using text similarity (WER/CER) and timestamp accuracy metrics.

Corpus-level WER/CER is computed by concatenating all texts first, then
computing once — *not* by averaging per-segment scores.

Lyrics segments (``type == "lyrics"``) are scored separately in a
``lyrics_bonus`` section and excluded from the main ``text_metrics``.
"""

from __future__ import annotations

import difflib
import statistics
from typing import Any

# CJK ranges duplicated from preprocess.py for self-contained script detection.
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

try:
    import jiwer
except ImportError:
    jiwer = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate_asr(
    generated: list[dict],
    reference: list[dict],
) -> dict[str, Any]:
    """Evaluate ASR quality by comparing *generated* segments to *reference*.

    Parameters
    ----------
    generated : list[dict]
        Hypothesis segments with keys ``start``, ``end``, ``source``, ``type``.
    reference : list[dict]
        Reference segments with the same keys.

    Returns
    -------
    dict
        ``text_metrics`` — corpus-level WER or CER (dialogue only).
        ``timestamp_metrics`` — temporal accuracy stats.
        ``lyrics_bonus`` — text metrics for lyrics segments (or ``None``).
    """
    # Separate dialogue and lyrics
    gen_dialogue = [s for s in generated if s.get("type") != "lyrics"]
    ref_dialogue = [s for s in reference if s.get("type") != "lyrics"]
    gen_lyrics = [s for s in generated if s.get("type") == "lyrics"]
    ref_lyrics = [s for s in reference if s.get("type") == "lyrics"]

    # Align dialogue segments
    dialogue_pairs = align_segments(gen_dialogue, ref_dialogue)

    # Text metrics — corpus-level
    text_metrics = _compute_text_metrics(dialogue_pairs)

    # Timestamp metrics
    timestamp_metrics = compute_timestamp_metrics(dialogue_pairs)

    # Lyrics bonus (if any)
    lyrics_bonus: dict[str, Any] | None = None
    if gen_lyrics and ref_lyrics:
        lyrics_pairs = align_segments(gen_lyrics, ref_lyrics)
        lyrics_bonus = _compute_text_metrics(lyrics_pairs)

    return {
        "text_metrics": text_metrics,
        "timestamp_metrics": timestamp_metrics,
        "lyrics_bonus": lyrics_bonus,
    }


# ---------------------------------------------------------------------------
# Segment alignment
# ---------------------------------------------------------------------------


def align_segments(
    generated: list[dict],
    reference: list[dict],
) -> list[tuple[dict, dict]]:
    """Greedy-match generated segments to reference segments.

    Each generated segment is paired with the reference segment that
    maximises a combined score:

        ``0.6 * text_similarity + 0.4 * temporal_overlap``

    Each reference segment is used at most once.

    Returns
    -------
    list[tuple[dict, dict]]
        Pairs of ``(generated_segment, reference_segment)``.
    """
    if not generated or not reference:
        return []

    # Pre-compute all scores
    scores: list[tuple[float, int, int]] = []
    for gi, gseg in enumerate(generated):
        for ri, rseg in enumerate(reference):
            ts = text_similarity(gseg.get("source", ""), rseg.get("source", ""))
            to = temporal_overlap(gseg, rseg)
            combined = 0.6 * ts + 0.4 * to
            scores.append((combined, gi, ri))

    # Sort descending by combined score
    scores.sort(key=lambda x: x[0], reverse=True)

    paired: list[tuple[dict, dict]] = []
    used_gen: set[int] = set()
    used_ref: set[int] = set()

    for score, gi, ri in scores:
        if gi in used_gen or ri in used_ref:
            continue
        paired.append((generated[gi], reference[ri]))
        used_gen.add(gi)
        used_ref.add(ri)

    return paired


# ---------------------------------------------------------------------------
# Similarity helpers
# ---------------------------------------------------------------------------


def temporal_overlap(seg_a: dict, seg_b: dict) -> float:
    """Compute Intersection-over-Union (IoU) of two time intervals.

    Parameters
    ----------
    seg_a, seg_b : dict
        Must have ``start`` and ``end`` float keys.

    Returns
    -------
    float
        IoU in [0, 1].
    """
    a_start, a_end = seg_a["start"], seg_a["end"]
    b_start, b_end = seg_b["start"], seg_b["end"]

    inter_start = max(a_start, b_start)
    inter_end = min(a_end, b_end)
    intersection = max(0.0, inter_end - inter_start)

    union = (a_end - a_start) + (b_end - b_start) - intersection
    if union <= 0:
        return 0.0

    return intersection / union


def text_similarity(text_a: str, text_b: str) -> float:
    """Compute text similarity in [0, 1] using ``difflib.SequenceMatcher``.

    Returns 0.0 if both strings are empty.
    """
    if not text_a and not text_b:
        return 0.0
    return difflib.SequenceMatcher(None, text_a, text_b).ratio()


# ---------------------------------------------------------------------------
# WER / CER
# ---------------------------------------------------------------------------


def compute_wer(hypothesis: str, reference: str) -> float:
    """Compute Word Error Rate.

    Requires the ``jiwer`` package.  Raises ``RuntimeError`` if not installed.
    """
    if jiwer is None:
        raise RuntimeError(
            "jiwer is required for WER computation. Install it with: pip install jiwer"
        )
    if not reference.strip():
        return 0.0 if not hypothesis.strip() else 1.0
    return float(jiwer.wer(reference, hypothesis))


def compute_cer(hypothesis: str, reference: str) -> float:
    """Compute Character Error Rate.

    Requires the ``jiwer`` package.  Raises ``RuntimeError`` if not installed.
    """
    if jiwer is None:
        raise RuntimeError(
            "jiwer is required for CER computation. Install it with: pip install jiwer"
        )
    if not reference.strip():
        return 0.0 if not hypothesis.strip() else 1.0
    return float(jiwer.cer(reference, hypothesis))


def detect_metric_type(text: str) -> str:
    """Decide whether to use ``"wer"`` or ``"cer"`` based on script detection.

    CJK-dominated text uses CER (character-level); Latin text uses WER
    (word-level).
    """
    cjk_count = 0
    total = 0
    for ch in text:
        if ch.isspace():
            continue
        total += 1
        cp = ord(ch)
        for lo, hi in _CJK_RANGES:
            if lo <= cp <= hi:
                cjk_count += 1
                break

    if total == 0:
        return "wer"

    return "cer" if cjk_count / total > 0.3 else "wer"


# ---------------------------------------------------------------------------
# Timestamp metrics
# ---------------------------------------------------------------------------


def compute_timestamp_metrics(pairs: list[tuple[dict, dict]]) -> dict[str, float | None]:
    """Compute temporal accuracy statistics from aligned pairs.

    Parameters
    ----------
    pairs : list[tuple[dict, dict]]
        Each element is ``(generated_segment, reference_segment)``.

    Returns
    -------
    dict
        ``mean_start_offset``, ``median_start_offset``,
        ``mean_end_offset``, ``median_end_offset``,
        ``mean_iou``.
        All ``None`` if *pairs* is empty.
    """
    if not pairs:
        return {
            "mean_start_offset": None,
            "median_start_offset": None,
            "mean_end_offset": None,
            "median_end_offset": None,
            "mean_iou": None,
        }

    start_offsets: list[float] = []
    end_offsets: list[float] = []
    ious: list[float] = []

    for gen, ref in pairs:
        start_offsets.append(abs(gen["start"] - ref["start"]))
        end_offsets.append(abs(gen["end"] - ref["end"]))
        ious.append(temporal_overlap(gen, ref))

    return {
        "mean_start_offset": statistics.mean(start_offsets),
        "median_start_offset": statistics.median(start_offsets),
        "mean_end_offset": statistics.mean(end_offsets),
        "median_end_offset": statistics.median(end_offsets),
        "mean_iou": statistics.mean(ious),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_text_metrics(pairs: list[tuple[dict, dict]]) -> dict[str, Any]:
    """Compute corpus-level text metrics from aligned pairs.

    Concatenates all hypothesis and reference texts, then computes a single
    WER or CER score (depending on script detection).
    """
    if not pairs:
        return {"metric_type": "wer", "score": None, "num_segments": 0}

    # Concatenate all texts for corpus-level computation
    all_hyp = " ".join(gen.get("source", "") for gen, _ref in pairs)
    all_ref = " ".join(ref.get("source", "") for _gen, ref in pairs)

    metric_type = detect_metric_type(all_ref)

    if metric_type == "cer":
        score = compute_cer(all_hyp, all_ref)
    else:
        score = compute_wer(all_hyp, all_ref)

    return {
        "metric_type": metric_type,
        "score": score,
        "num_segments": len(pairs),
    }
