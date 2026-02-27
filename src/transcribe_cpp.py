"""whisper.cpp backend — calls whisper-cpp binary via subprocess."""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .transcribe import Segment, Word
from .components import ComponentManager
from .logger import debug

# Matches whisper.cpp special tokens like [_BEG_], [_EOT_], [_SOT_], [_TT_250]
_SPECIAL_TOKEN_RE = re.compile(r"^\[_.*\]$")


def transcribe_cpp(
    audio_path: Path,
    config: Dict[str, Any],
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> List[Segment]:
    """Transcribe audio using whisper.cpp binary.

    Args:
        audio_path: Path to audio file (WAV format preferred).
        config: Configuration dictionary with whisper settings.
        on_progress: Optional progress callback(current, total).

    Returns:
        List of transcribed Segment objects.

    Raises:
        RuntimeError: If engine/model not found or whisper-cpp fails.
    """
    cm = ComponentManager()

    # Find engine
    engine_path = cm.find_whisper_engine()
    if not engine_path:
        raise RuntimeError(
            "whisper.cpp engine not found.\n"
            "Run: subgen install whisper\n"
            "Or use cloud Whisper: subgen init"
        )

    # Find model
    whisper_cfg = config.get("whisper", {})
    model_name = whisper_cfg.get("cpp_model") or whisper_cfg.get("local_model", "large-v3")
    model_path = cm.find_whisper_model(model_name)
    if not model_path:
        raise RuntimeError(
            f"Whisper model '{model_name}' not found.\n"
            f"Run: subgen install model {model_name}"
        )

    # Build command — output JSON to a secure temp directory
    import tempfile
    tmp_dir = tempfile.mkdtemp(prefix="subgen_whisper_")
    try:
        output_base = os.path.join(tmp_dir, "output")

        threads = whisper_cfg.get("cpp_threads", 4)
        cmd = [
            str(engine_path),
            "-m", str(model_path),
            "-f", str(audio_path),
            "--output-json-full",
            "--print-progress",
            "--split-on-word",
            "-t", str(threads),
            "-of", output_base,
        ]

        source_lang = whisper_cfg.get("source_language")
        if source_lang and source_lang != "auto":
            cmd.extend(["-l", source_lang])

        debug("transcribe_cpp: running %s", " ".join(cmd))

        # Execute — use communicate() to avoid deadlock from sequential
        # stdout/stderr reads when pipe buffers fill up.
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        stdout, stderr = process.communicate()

        # Parse stderr for progress reporting
        stderr_lines = stderr.splitlines(keepends=True) if stderr else []
        if on_progress:
            for line in stderr_lines:
                if "progress =" in line:
                    try:
                        pct = int(line.split("=")[1].strip().rstrip("%"))
                        on_progress(pct, 100)
                    except (ValueError, IndexError):
                        pass

        if process.returncode != 0:
            raise RuntimeError(
                f"whisper.cpp failed (exit {process.returncode}):\n"
                + "".join(stderr_lines[-10:])
            )

        # Read JSON output file
        json_file = output_base + ".json"
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                json_str = f.read()
        except FileNotFoundError:
            raise RuntimeError(
                f"whisper.cpp did not produce JSON output.\n"
                f"Expected: {json_file}\n"
                f"stdout: {stdout[:500]}"
            )

        return _parse_whisper_json(json_str)
    finally:
        # Cleanup entire temp directory securely
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _parse_whisper_json(json_str: str) -> List[Segment]:
    """Parse whisper.cpp JSON output into Segment list.

    Args:
        json_str: Raw JSON string from whisper.cpp stdout.

    Returns:
        List of Segment objects.

    Raises:
        RuntimeError: If JSON is malformed or has unexpected schema.
    """
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        raise RuntimeError(
            f"Failed to parse whisper.cpp JSON output: {e}\n"
            f"Raw output (first 500 chars): {json_str[:500]}"
        ) from e

    if not isinstance(data, dict):
        raise RuntimeError(
            f"Unexpected whisper.cpp output format: expected JSON object, "
            f"got {type(data).__name__}"
        )

    transcription = data.get("transcription")
    if transcription is None:
        raise RuntimeError(
            "Unexpected whisper.cpp output format: missing 'transcription' key. "
            f"Available keys: {list(data.keys())}"
        )

    if not isinstance(transcription, list):
        raise RuntimeError(
            f"Unexpected whisper.cpp output format: 'transcription' should be a list, "
            f"got {type(transcription).__name__}"
        )

    segments: List[Segment] = []
    for i, item in enumerate(transcription):
        try:
            if not isinstance(item, dict):
                debug("transcribe_cpp: skipping non-dict item at index %d", i)
                continue

            timestamps = item.get("timestamps")
            if not isinstance(timestamps, dict) or "from" not in timestamps or "to" not in timestamps:
                debug("transcribe_cpp: skipping item %d with missing/invalid timestamps", i)
                continue

            start = _timestamp_to_seconds(timestamps["from"])
            end = _timestamp_to_seconds(timestamps["to"])
            text = item.get("text", "").strip()

            if not text:
                continue

            # Word-level timestamps — merge BPE subword fragments into words.
            # Convention: tokens starting with a space begin a new word;
            # tokens without a leading space continue the previous word.
            # Special tokens matching [_..._] (e.g. [_BEG_], [_EOT_]) are skipped.
            words: List[Word] = []

            # Accumulator for the current in-progress word
            cur_text: Optional[str] = None
            cur_start: float = 0.0
            cur_end: float = 0.0

            for token in item.get("tokens", []):
                if not isinstance(token, dict):
                    continue

                token_text = token.get("text", "")

                # Skip special tokens like [_BEG_], [_EOT_], [_TT_*]
                if _SPECIAL_TOKEN_RE.match(token_text):
                    continue

                # Skip tokens without valid timestamps
                token_ts = token.get("timestamps")
                if not isinstance(token_ts, dict) or "from" not in token_ts or "to" not in token_ts:
                    continue

                # Skip tokens with no visible content
                if not token_text.strip():
                    continue

                w_start = _timestamp_to_seconds(token_ts["from"])
                w_end = _timestamp_to_seconds(token_ts["to"])

                # A token that starts with a space begins a new word
                if token_text.startswith(" "):
                    # Flush the accumulated word (if any)
                    if cur_text is not None:
                        words.append(Word(text=cur_text, start=cur_start, end=cur_end))
                    # Start a new word (strip the leading space)
                    cur_text = token_text.lstrip(" ")
                    cur_start = w_start
                    cur_end = w_end
                else:
                    # Continue / start accumulating
                    if cur_text is None:
                        # First token in segment has no leading space — treat as word start
                        cur_text = token_text
                        cur_start = w_start
                    else:
                        cur_text += token_text
                    cur_end = w_end

            # Flush the last accumulated word
            if cur_text is not None:
                words.append(Word(text=cur_text, start=cur_start, end=cur_end))

            segments.append(Segment(
                start=start,
                end=end,
                text=text,
                words=words,
                no_speech_prob=item.get("no_speech_prob", 0.0),
            ))
        except (KeyError, ValueError, TypeError) as e:
            debug("transcribe_cpp: skipping malformed segment at index %d: %s", i, e)
            continue

    return segments


def _timestamp_to_seconds(ts: str) -> float:
    """Convert whisper.cpp timestamp 'HH:MM:SS.mmm' to seconds.

    Args:
        ts: Timestamp string.

    Returns:
        Time in seconds.
    """
    parts = ts.split(":")
    h = int(parts[0])
    m = int(parts[1])
    s = float(parts[2].replace(",", "."))
    return h * 3600 + m * 60 + s
