"""whisper.cpp backend — calls whisper-cpp binary via subprocess."""

import json
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .transcribe import Segment, Word
from .components import ComponentManager
from .logger import debug


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

    # Build command
    threads = whisper_cfg.get("cpp_threads", 4)
    cmd = [
        str(engine_path),
        "-m", str(model_path),
        "-f", str(audio_path),
        "--output-json",
        "--print-progress",
        "-t", str(threads),
    ]

    source_lang = whisper_cfg.get("source_language")
    if source_lang and source_lang != "auto":
        cmd.extend(["-l", source_lang])

    debug("transcribe_cpp: running %s", " ".join(cmd))

    # Execute
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Read stderr for progress
    stderr_lines: List[str] = []
    for line in process.stderr:  # type: ignore[union-attr]
        stderr_lines.append(line)
        if "progress =" in line and on_progress:
            try:
                pct = int(line.split("=")[1].strip().rstrip("%"))
                on_progress(pct, 100)
            except (ValueError, IndexError):
                pass

    stdout = process.stdout.read()  # type: ignore[union-attr]
    process.wait()

    if process.returncode != 0:
        raise RuntimeError(
            f"whisper.cpp failed (exit {process.returncode}):\n"
            + "".join(stderr_lines[-10:])
        )

    return _parse_whisper_json(stdout)


def _parse_whisper_json(json_str: str) -> List[Segment]:
    """Parse whisper.cpp JSON output into Segment list.

    Args:
        json_str: Raw JSON string from whisper.cpp stdout.

    Returns:
        List of Segment objects.
    """
    data = json.loads(json_str)

    segments: List[Segment] = []
    for item in data.get("transcription", []):
        start = _timestamp_to_seconds(item["timestamps"]["from"])
        end = _timestamp_to_seconds(item["timestamps"]["to"])
        text = item.get("text", "").strip()

        if not text:
            continue

        # Word-level timestamps
        words: List[Word] = []
        for token in item.get("tokens", []):
            if "timestamps" in token and token.get("text", "").strip():
                w_start = _timestamp_to_seconds(token["timestamps"]["from"])
                w_end = _timestamp_to_seconds(token["timestamps"]["to"])
                words.append(Word(
                    text=token["text"].strip(),
                    start=w_start,
                    end=w_end,
                ))

        segments.append(Segment(
            start=start,
            end=end,
            text=text,
            words=words,
            no_speech_prob=item.get("no_speech_prob", 0.0),
        ))

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
    s = float(parts[2])
    return h * 3600 + m * 60 + s
