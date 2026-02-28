"""Translation evaluation: LLM-as-judge scoring via copilot-api.

Sends aligned (source, reference-translation, generated-translation) triples
to Claude for quality assessment.  Scores four dimensions:

- **accuracy** — semantic faithfulness to the source
- **naturalness** — fluency in the target language
- **terminology** — domain-specific term handling
- **cultural_adaptation** — cultural references and idioms

Composite = 0.4 * accuracy + 0.3 * naturalness
            + 0.15 * terminology + 0.15 * cultural_adaptation

Only dialogue segments are evaluated (lyrics are excluded).

If the copilot-api endpoint is unavailable the functions degrade gracefully
and return ``None`` with a log message.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Copilot-API settings
_API_URL = "http://localhost:4141/v1/messages"
_MODEL = "claude-opus-4.6"

# CJK ranges for language detection (same as preprocess / asr_eval)
_CJK_RANGES = (
    (0x4E00, 0x9FFF),
    (0x3400, 0x4DBF),
    (0x3000, 0x303F),
    (0x3040, 0x309F),
    (0x30A0, 0x30FF),
    (0xAC00, 0xD7AF),
    (0xFF00, 0xFFEF),
    (0x1100, 0x11FF),
    (0x20000, 0x2A6DF),
)

# Hiragana / Katakana ranges for Japanese detection
_HIRAGANA = (0x3040, 0x309F)
_KATAKANA = (0x30A0, 0x30FF)
_HANGUL_RANGES = ((0xAC00, 0xD7AF), (0x1100, 0x11FF))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate_translation(
    aligned_pairs: list[tuple[dict, dict]],
    source_lang: str = "auto",
    target_lang: str = "auto",
) -> dict[str, Any] | None:
    """Score translation quality using an LLM judge.

    Parameters
    ----------
    aligned_pairs : list[tuple[dict, dict]]
        Pairs of ``(generated_segment, reference_segment)``.  Each segment
        must have ``source``, ``translation``, and ``type`` keys.
    source_lang, target_lang : str
        Language names (e.g. ``"Japanese"``, ``"English"``).  ``"auto"``
        triggers heuristic detection.

    Returns
    -------
    dict | None
        Aggregated scores dict, or ``None`` if the LLM call fails.
    """
    # Filter to dialogue only
    dialogue_pairs = [
        (gen, ref) for gen, ref in aligned_pairs
        if gen.get("type") != "lyrics" and ref.get("type") != "lyrics"
    ]

    if not dialogue_pairs:
        logger.warning("No dialogue pairs to evaluate.")
        return None

    # Build triples: (source_text, reference_translation, generated_translation)
    triples: list[tuple[str, str, str]] = []
    for gen, ref in dialogue_pairs:
        src = ref.get("source", "")
        ref_trans = ref.get("translation", "")
        gen_trans = gen.get("translation", "")
        if src.strip() or ref_trans.strip() or gen_trans.strip():
            triples.append((src, ref_trans, gen_trans))

    if not triples:
        logger.warning("All triples are empty — nothing to evaluate.")
        return None

    # Detect languages if auto
    if source_lang == "auto":
        source_lang = _detect_language(dialogue_pairs, "source")
    if target_lang == "auto":
        target_lang = _detect_language(dialogue_pairs, "translation")

    # Batch and score
    batches = _batch_triples(triples)
    all_scores: list[dict[str, float]] = []

    for batch in batches:
        prompt = _build_prompt(batch, source_lang, target_lang)
        response = _call_llm(prompt)
        if response is None:
            return None
        parsed = _parse_response(response)
        if parsed is not None:
            all_scores.append(parsed)

    if not all_scores:
        logger.warning("No valid scores returned by LLM.")
        return None

    return _aggregate_scores(all_scores)


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


def _build_prompt(
    triples: list[tuple[str, str, str]],
    source_lang: str,
    target_lang: str,
) -> str:
    """Build the evaluation prompt for a batch of triples.

    Parameters
    ----------
    triples : list[tuple[str, str, str]]
        Each element is ``(source_text, reference_translation, generated_translation)``.
    source_lang, target_lang : str
        Human-readable language names.

    Returns
    -------
    str
        The formatted prompt to send to the LLM judge.
    """
    lines: list[str] = []
    lines.append(
        "You are a professional translation quality evaluator. "
        f"Evaluate the following {source_lang} → {target_lang} subtitle translations."
    )
    lines.append("")
    lines.append("For each set of translations below, compare the Generated translation "
                 "against the Reference translation and the original Source text.")
    lines.append("")

    for i, (src, ref_t, gen_t) in enumerate(triples, 1):
        lines.append(f"--- Segment {i} ---")
        lines.append(f"Source ({source_lang}): {src}")
        lines.append(f"Reference ({target_lang}): {ref_t}")
        lines.append(f"Generated ({target_lang}): {gen_t}")
        lines.append("")

    lines.append("Score the Generated translations on these four dimensions (1-10 scale):")
    lines.append("- accuracy: semantic faithfulness to the source")
    lines.append("- naturalness: fluency and readability in the target language")
    lines.append("- terminology: correct handling of domain-specific terms")
    lines.append("- cultural_adaptation: appropriate handling of cultural references and idioms")
    lines.append("")
    lines.append("Return your evaluation as a single JSON object with exactly these keys:")
    lines.append('{"accuracy": <float>, "naturalness": <float>, '
                 '"terminology": <float>, "cultural_adaptation": <float>}')
    lines.append("")
    lines.append("Return ONLY the JSON object, no other text.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM interaction
# ---------------------------------------------------------------------------


def _call_llm(prompt: str) -> str | None:
    """Call Claude via the copilot-api local endpoint.

    Returns the response text, or ``None`` if the call fails.
    """
    if httpx is None:
        logger.error("httpx is required for LLM calls. Install it with: pip install httpx")
        return None

    payload = {
        "model": _MODEL,
        "max_tokens": 1024,
        "messages": [
            {"role": "user", "content": prompt},
        ],
    }

    try:
        response = httpx.post(
            _API_URL,
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()

        # Extract text from Claude's response format
        content = data.get("content", [])
        if isinstance(content, list) and content:
            return content[0].get("text", "")
        return None

    except (httpx.HTTPError, httpx.TimeoutException, ConnectionError, OSError) as exc:
        logger.warning("copilot-api call failed: %s", exc)
        return None
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.warning("Unexpected response format from copilot-api: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

_JSON_RE = re.compile(r"\{[^{}]*\}")


def _parse_response(text: str) -> dict[str, float] | None:
    """Extract score dict from LLM response text.

    Tries to parse the whole text as JSON first.  Falls back to extracting
    the first ``{...}`` block.
    """
    required = {"accuracy", "naturalness", "terminology", "cultural_adaptation"}

    # Try direct parse
    try:
        data = json.loads(text.strip())
        if isinstance(data, dict) and required.issubset(data.keys()):
            return {k: float(data[k]) for k in required}
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Fallback: regex extraction
    match = _JSON_RE.search(text)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, dict) and required.issubset(data.keys()):
                return {k: float(data[k]) for k in required}
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    logger.warning("Could not parse LLM response as score JSON: %.200s", text)
    return None


# ---------------------------------------------------------------------------
# Batching & aggregation
# ---------------------------------------------------------------------------


def _batch_triples(
    triples: list[tuple[str, str, str]],
    batch_size: int = 20,
) -> list[list[tuple[str, str, str]]]:
    """Split *triples* into batches of at most *batch_size*.

    Empty triples (all three strings blank) are filtered out.
    """
    # Filter empties
    filtered = [
        t for t in triples
        if any(s.strip() for s in t)
    ]
    if not filtered:
        return []

    return [filtered[i:i + batch_size] for i in range(0, len(filtered), batch_size)]


def _aggregate_scores(batch_scores: list[dict[str, float]]) -> dict[str, float]:
    """Compute weighted-average composite from per-batch scores.

    Weights: accuracy 0.4, naturalness 0.3, terminology 0.15,
    cultural_adaptation 0.15.

    Returns a dict with the four dimension averages and the composite.
    """
    if not batch_scores:
        return {
            "accuracy": 0.0,
            "naturalness": 0.0,
            "terminology": 0.0,
            "cultural_adaptation": 0.0,
            "composite": 0.0,
        }

    n = len(batch_scores)
    avg: dict[str, float] = {
        "accuracy": sum(s["accuracy"] for s in batch_scores) / n,
        "naturalness": sum(s["naturalness"] for s in batch_scores) / n,
        "terminology": sum(s["terminology"] for s in batch_scores) / n,
        "cultural_adaptation": sum(s["cultural_adaptation"] for s in batch_scores) / n,
    }

    avg["composite"] = (
        0.4 * avg["accuracy"]
        + 0.3 * avg["naturalness"]
        + 0.15 * avg["terminology"]
        + 0.15 * avg["cultural_adaptation"]
    )

    return avg


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------


def _detect_language(
    pairs: list[tuple[dict, dict]],
    field: str,
) -> str:
    """Heuristic language detection from segment text using Unicode blocks.

    Parameters
    ----------
    pairs : list[tuple[dict, dict]]
        Aligned segment pairs.
    field : str
        Which field to inspect (``"source"`` or ``"translation"``).

    Returns
    -------
    str
        A human-readable language name: ``"Japanese"``, ``"Chinese"``,
        ``"Korean"``, or ``"English"``.
    """
    cjk = 0
    hiragana_katakana = 0
    hangul = 0
    total = 0

    # Sample from reference segments (second element)
    for _gen, ref in pairs:
        text = ref.get(field, "")
        for ch in text:
            if ch.isspace():
                continue
            cp = ord(ch)
            total += 1
            for lo, hi in _CJK_RANGES:
                if lo <= cp <= hi:
                    cjk += 1
                    break
            # Sub-classify
            if _HIRAGANA[0] <= cp <= _HIRAGANA[1] or _KATAKANA[0] <= cp <= _KATAKANA[1]:
                hiragana_katakana += 1
            for lo, hi in _HANGUL_RANGES:
                if lo <= cp <= hi:
                    hangul += 1
                    break

    if total == 0:
        return "English"

    cjk_ratio = cjk / total
    if cjk_ratio <= 0.3:
        return "English"

    # Among CJK characters, distinguish Japanese / Korean / Chinese
    if hiragana_katakana > 0:
        return "Japanese"
    if hangul > 0:
        return "Korean"
    return "Chinese"
