#!/usr/bin/env python3
"""Full benchmark pipeline: run SubGen on a video and compare against reference.

Usage::

    python3 benchmark/scripts/run.py benchmark/corpus/sample-001/
    python3 benchmark/scripts/run.py benchmark/corpus/sample-001/ --whisper-provider cpp --no-translation
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Ensure repo root is on sys.path so ``benchmark.*`` imports work when
# the script is executed directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from benchmark.scripts.compare import main as compare_main


# ---------------------------------------------------------------------------
# Video / reference finders
# ---------------------------------------------------------------------------

_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".webm", ".mov"}
_SUBTITLE_EXTENSIONS = {".ass", ".srt"}


def _find_video(sample_dir: Path) -> Path:
    """Locate the video file inside *sample_dir*.

    Raises ``FileNotFoundError`` if no suitable video is found.
    """
    for f in sorted(sample_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in _VIDEO_EXTENSIONS:
            return f
    raise FileNotFoundError(
        f"No video file ({', '.join(_VIDEO_EXTENSIONS)}) found in {sample_dir}"
    )


def _find_reference(sample_dir: Path) -> Path:
    """Locate the reference subtitle file inside *sample_dir*.

    Prefers ``reference.ass`` / ``reference.srt``, then falls back to the
    first ``*.ass`` or ``*.srt`` file.

    Raises ``FileNotFoundError`` if nothing is found.
    """
    # Preferred names
    for name in ("reference.ass", "reference.srt"):
        candidate = sample_dir / name
        if candidate.exists():
            return candidate

    # Fallback: first subtitle file found
    for f in sorted(sample_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in _SUBTITLE_EXTENSIONS:
            return f

    raise FileNotFoundError(
        f"No reference subtitle file found in {sample_dir}"
    )


# ---------------------------------------------------------------------------
# SubGen invocation
# ---------------------------------------------------------------------------


def _run_subgen(
    video_path: Path,
    output_path: Path,
    *,
    source_lang: str = "en",
    target_lang: str = "zh",
    whisper_provider: str | None = None,
    force_transcribe: bool = False,
) -> None:
    """Run SubGen via subprocess to generate subtitles for *video_path*.

    The generated ASS file is written to *output_path*.
    """
    subgen_script = _REPO_ROOT / "subgen.py"
    if not subgen_script.exists():
        raise FileNotFoundError(f"SubGen entry point not found at {subgen_script}")

    cmd: list[str] = [
        sys.executable,
        str(subgen_script),
        "run",
        str(video_path),
        "--from", source_lang,
        "--to", target_lang,
        "--bilingual",
        "--output", str(output_path),
    ]

    if whisper_provider:
        cmd.extend(["--whisper-provider", whisper_provider])

    if force_transcribe:
        cmd.append("--force-transcribe")

    print(f"Running SubGen: {' '.join(cmd)}")
    print()

    result = subprocess.run(
        cmd,
        cwd=str(_REPO_ROOT),
        capture_output=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"SubGen exited with code {result.returncode}"
        )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def main(
    sample_dir: str,
    *,
    source_lang: str = "en",
    target_lang: str = "zh",
    whisper_provider: str | None = None,
    no_translation: bool = False,
    force_transcribe: bool = False,
) -> dict:
    """Run the full benchmark pipeline on a sample directory.

    Parameters
    ----------
    sample_dir : str
        Path to the corpus sample directory containing a video and reference
        subtitle.
    source_lang : str
        Source language code (default ``"en"``).
    target_lang : str
        Target language code (default ``"zh"``).
    whisper_provider : str | None
        Override the whisper provider.
    no_translation : bool
        Skip translation evaluation.
    force_transcribe : bool
        Force re-transcription even if cache exists.

    Returns
    -------
    dict
        The evaluation report.
    """
    sample_path = Path(sample_dir).resolve()
    if not sample_path.is_dir():
        raise FileNotFoundError(f"Sample directory not found: {sample_path}")

    sample_name = sample_path.name

    # 1. Find video and reference
    print(f"Sample: {sample_name}")
    print(f"Directory: {sample_path}")
    print()

    video_path = _find_video(sample_path)
    print(f"Video: {video_path.name}")

    reference_path = _find_reference(sample_path)
    print(f"Reference: {reference_path.name}")
    print()

    # 2. Determine output path for generated subtitles
    output_ass = sample_path / f"{video_path.stem}_generated.ass"

    # 3. Run SubGen (skip if output already exists and not forcing)
    if output_ass.exists() and not force_transcribe:
        print(f"Generated file already exists: {output_ass.name}")
        print("Use --force-transcribe to re-generate.")
        print()
    else:
        _run_subgen(
            video_path,
            output_ass,
            source_lang=source_lang,
            target_lang=target_lang,
            whisper_provider=whisper_provider,
            force_transcribe=force_transcribe,
        )

    # 4. Verify the generated file exists
    if not output_ass.exists():
        raise FileNotFoundError(
            f"Expected generated subtitle not found at {output_ass}. "
            "SubGen may have produced output with a different name."
        )

    # 5. Compare generated vs reference
    results_dir = _REPO_ROOT / "benchmark" / "results" / sample_name
    results_dir.mkdir(parents=True, exist_ok=True)
    eval_json = results_dir / "eval.json"

    report = compare_main(
        generated_path=str(output_ass),
        reference_path=str(reference_path),
        output_path=str(eval_json),
        no_translation=no_translation,
        source_lang=source_lang,
        target_lang=target_lang,
    )

    print(f"\nResults saved to: {eval_json}")

    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Full benchmark pipeline: run SubGen on a video and compare against reference.",
    )
    parser.add_argument(
        "sample_dir",
        help="Path to the corpus sample directory",
    )
    parser.add_argument(
        "--from", "-f",
        dest="source_lang",
        default="en",
        help="Source language (default: en)",
    )
    parser.add_argument(
        "--to", "-t",
        dest="target_lang",
        default="zh",
        help="Target language (default: zh)",
    )
    parser.add_argument(
        "--whisper-provider",
        default=None,
        help="Override whisper provider (local, mlx, openai, groq, cpp)",
    )
    parser.add_argument(
        "--no-translation",
        action="store_true",
        default=False,
        help="Skip translation evaluation",
    )
    parser.add_argument(
        "--force-transcribe",
        action="store_true",
        default=False,
        help="Force re-transcription even if cache exists",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    try:
        main(
            sample_dir=args.sample_dir,
            source_lang=args.source_lang,
            target_lang=args.target_lang,
            whisper_provider=args.whisper_provider,
            no_translation=args.no_translation,
            force_transcribe=args.force_transcribe,
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
