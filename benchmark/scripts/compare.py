#!/usr/bin/env python3
"""Compare two subtitle files and produce an evaluation report.

Usage::

    python3 benchmark/scripts/compare.py generated.ass reference.ass -o eval.json
    python3 benchmark/scripts/compare.py generated.ass reference.ass --no-translation
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure repo root is on sys.path so ``benchmark.*`` imports work when
# the script is executed directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from benchmark.scripts.preprocess import preprocess
from benchmark.scripts.asr_eval import align_segments, evaluate_asr
from benchmark.scripts.translation_eval import evaluate_translation


# ---------------------------------------------------------------------------
# Core logic (importable by run.py)
# ---------------------------------------------------------------------------


def main(
    generated_path: str,
    reference_path: str,
    *,
    output_path: str | None = None,
    no_translation: bool = False,
    source_lang: str | None = None,
    target_lang: str | None = None,
) -> dict:
    """Compare two subtitle files and return an evaluation report dict.

    Parameters
    ----------
    generated_path : str
        Path to the generated (hypothesis) subtitle file.
    reference_path : str
        Path to the reference subtitle file.
    output_path : str | None
        If provided, write the JSON report to this path.
    no_translation : bool
        Skip translation evaluation when ``True``.
    source_lang, target_lang : str | None
        Override automatic language detection.

    Returns
    -------
    dict
        Combined evaluation report.
    """
    gen_path = Path(generated_path)
    ref_path = Path(reference_path)

    if not gen_path.exists():
        raise FileNotFoundError(f"Generated file not found: {gen_path}")
    if not ref_path.exists():
        raise FileNotFoundError(f"Reference file not found: {ref_path}")

    # 1. Preprocess both files
    preprocess_source_lang = source_lang if source_lang else "auto"
    gen_segments = preprocess(gen_path, source_lang=preprocess_source_lang)
    ref_segments = preprocess(ref_path, source_lang=preprocess_source_lang)

    if not gen_segments:
        print("WARNING: No segments found in generated file.")
    if not ref_segments:
        print("WARNING: No segments found in reference file.")

    # 2. Separate dialogue from lyrics
    gen_dialogue = [s for s in gen_segments if s.get("type") != "lyrics"]
    ref_dialogue = [s for s in ref_segments if s.get("type") != "lyrics"]
    gen_lyrics = [s for s in gen_segments if s.get("type") == "lyrics"]
    ref_lyrics = [s for s in ref_segments if s.get("type") == "lyrics"]

    # 3. Align dialogue segments
    aligned_pairs = align_segments(gen_dialogue, ref_dialogue)

    # 4. ASR evaluation (full segments — evaluate_asr handles dialogue/lyrics
    #    separation internally)
    asr_scores = evaluate_asr(gen_segments, ref_segments)

    # 5. Translation evaluation (unless skipped)
    translation_scores: dict | None = None
    if not no_translation:
        trans_source = source_lang if source_lang else "auto"
        trans_target = target_lang if target_lang else "auto"
        translation_scores = evaluate_translation(
            aligned_pairs,
            source_lang=trans_source,
            target_lang=trans_target,
        )

    # 6. Build report
    report: dict = {
        "generated_file": str(gen_path),
        "reference_file": str(ref_path),
        "segment_counts": {
            "generated_total": len(gen_segments),
            "reference_total": len(ref_segments),
            "generated_dialogue": len(gen_dialogue),
            "reference_dialogue": len(ref_dialogue),
            "generated_lyrics": len(gen_lyrics),
            "reference_lyrics": len(ref_lyrics),
            "aligned_pairs": len(aligned_pairs),
        },
        "asr": asr_scores,
        "translation": translation_scores,
    }

    # 7. Write JSON if requested
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Report written to {out}")

    # 8. Print summary
    _print_summary(report)

    return report


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------


def _print_summary(report: dict) -> None:
    """Print a human-readable summary table to stdout."""
    counts = report.get("segment_counts", {})
    asr = report.get("asr", {})
    translation = report.get("translation")

    print()
    print("=" * 60)
    print("  BENCHMARK EVALUATION SUMMARY")
    print("=" * 60)

    # --- Segment counts ---
    print()
    print("  Segments")
    print("  " + "-" * 40)
    print(f"  {'Generated total:':<30} {counts.get('generated_total', 0)}")
    print(f"  {'Reference total:':<30} {counts.get('reference_total', 0)}")
    print(f"  {'Generated dialogue:':<30} {counts.get('generated_dialogue', 0)}")
    print(f"  {'Reference dialogue:':<30} {counts.get('reference_dialogue', 0)}")
    print(f"  {'Aligned pairs:':<30} {counts.get('aligned_pairs', 0)}")

    # --- ASR text metrics ---
    text_metrics = asr.get("text_metrics", {})
    print()
    print("  ASR Text Metrics")
    print("  " + "-" * 40)
    metric_type = text_metrics.get("metric_type", "wer")
    score = text_metrics.get("score")
    score_str = f"{score:.4f}" if score is not None else "N/A"
    print(f"  {metric_type.upper() + ':':<30} {score_str}")
    print(f"  {'Segments evaluated:':<30} {text_metrics.get('num_segments', 0)}")

    # --- Timestamp metrics ---
    ts = asr.get("timestamp_metrics", {})
    print()
    print("  Timestamp Metrics")
    print("  " + "-" * 40)
    for key in ("mean_start_offset", "median_start_offset",
                "mean_end_offset", "median_end_offset", "mean_iou"):
        val = ts.get(key)
        label = key.replace("_", " ").title() + ":"
        val_str = f"{val:.4f}" if val is not None else "N/A"
        print(f"  {label:<30} {val_str}")

    # --- Lyrics bonus ---
    lyrics = asr.get("lyrics_bonus")
    if lyrics:
        print()
        print("  Lyrics Bonus")
        print("  " + "-" * 40)
        lm_type = lyrics.get("metric_type", "wer")
        lm_score = lyrics.get("score")
        lm_str = f"{lm_score:.4f}" if lm_score is not None else "N/A"
        print(f"  {lm_type.upper() + ':':<30} {lm_str}")
        print(f"  {'Segments evaluated:':<30} {lyrics.get('num_segments', 0)}")

    # --- Translation ---
    if translation is not None:
        print()
        print("  Translation Quality (LLM Judge)")
        print("  " + "-" * 40)
        for key in ("accuracy", "naturalness", "terminology",
                    "cultural_adaptation", "composite"):
            val = translation.get(key)
            label = key.replace("_", " ").title() + ":"
            val_str = f"{val:.2f}" if val is not None else "N/A"
            print(f"  {label:<30} {val_str}")
    elif report.get("translation") is None:
        print()
        print("  Translation: skipped")

    print()
    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare two subtitle files and produce an evaluation report.",
    )
    parser.add_argument(
        "generated_path",
        help="Path to the generated (hypothesis) subtitle file",
    )
    parser.add_argument(
        "reference_path",
        help="Path to the reference subtitle file",
    )
    parser.add_argument(
        "--output", "-o",
        dest="output_path",
        default=None,
        help="Path to write JSON evaluation report",
    )
    parser.add_argument(
        "--no-translation",
        action="store_true",
        default=False,
        help="Skip translation evaluation",
    )
    parser.add_argument(
        "--source-lang",
        default=None,
        help="Override source language detection (e.g. en, ja, zh)",
    )
    parser.add_argument(
        "--target-lang",
        default=None,
        help="Override target language detection (e.g. zh, en, ja)",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    try:
        main(
            generated_path=args.generated_path,
            reference_path=args.reference_path,
            output_path=args.output_path,
            no_translation=args.no_translation,
            source_lang=args.source_lang,
            target_lang=args.target_lang,
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
