"""Speech recognition module"""

import re
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class Segment:
    """Subtitle segment"""
    start: float      # Start time (seconds)
    end: float        # End time (seconds)
    text: str         # Original text
    translated: str = ""  # Translated text


def merge_segments_by_sentence(segments: List[Segment], max_duration: float = 8.0) -> List[Segment]:
    """
    Merge segments to form complete sentences.

    Strategy:
    1. Merge segments that don't end with sentence-ending punctuation
    2. Keep merged segments under max_duration seconds
    3. Preserve original timing boundaries

    Args:
        segments: List of transcribed segments
        max_duration: Maximum duration for a merged segment (seconds)

    Returns:
        List of merged segments
    """
    if not segments:
        return segments

    # Sentence ending patterns (for various languages)
    sentence_end_pattern = re.compile(r'[.!?。！？…]$')

    merged = []
    current = None

    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue

        if current is None:
            current = Segment(
                start=seg.start,
                end=seg.end,
                text=text
            )
        else:
            # Check if we should merge
            potential_duration = seg.end - current.start
            current_ends_sentence = sentence_end_pattern.search(current.text)

            if current_ends_sentence or potential_duration > max_duration:
                # Current segment is complete, start new one
                merged.append(current)
                current = Segment(
                    start=seg.start,
                    end=seg.end,
                    text=text
                )
            else:
                # Merge with current
                current.end = seg.end
                current.text = current.text + " " + text

    # Don't forget the last segment
    if current is not None:
        merged.append(current)

    return merged


def transcribe_audio(audio_path: Path, config: Dict[str, Any]) -> List[Segment]:
    """
    Transcribe audio using speech recognition

    Args:
        audio_path: Path to audio file
        config: Configuration dictionary

    Returns:
        List of subtitle segments
    """
    whisper_config = config.get('whisper', {})
    provider = whisper_config.get('provider', 'local')

    if provider == 'local':
        segments = _transcribe_local(audio_path, config)
    elif provider == 'mlx':
        segments = _transcribe_mlx(audio_path, config)
    elif provider == 'openai':
        segments = _transcribe_openai(audio_path, config)
    elif provider == 'groq':
        segments = _transcribe_groq(audio_path, config)
    else:
        raise ValueError(f"Unsupported Whisper provider: {provider}")

    # Post-process: merge segments by sentence boundaries
    merge_sentences = config.get('advanced', {}).get('merge_sentences', True)
    max_segment_duration = config.get('advanced', {}).get('max_segment_duration', 8.0)

    if merge_sentences:
        segments = merge_segments_by_sentence(segments, max_duration=max_segment_duration)

    return segments


def _transcribe_local(audio_path: Path, config: Dict[str, Any]) -> List[Segment]:
    """Transcribe using local faster-whisper"""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError(
            "Local Whisper requires faster-whisper:\n"
            "pip install faster-whisper"
        )

    model_name = config['whisper'].get('local_model', 'large-v3')
    device = config['whisper'].get('device', 'cuda')
    source_lang = config['whisper'].get('source_language', None)

    # Select compute type based on device
    compute_type = "float16" if device == "cuda" else "int8"

    # Load model
    model = WhisperModel(model_name, device=device, compute_type=compute_type)

    # Transcription options
    transcribe_opts = {
        "word_timestamps": True,
        "vad_filter": True,  # Use VAD to filter silence
    }

    # Add language parameter if source language specified
    if source_lang and source_lang != 'auto':
        transcribe_opts["language"] = source_lang

    # Transcribe
    segments_iter, info = model.transcribe(str(audio_path), **transcribe_opts)

    segments = []
    for seg in segments_iter:
        segments.append(Segment(
            start=seg.start,
            end=seg.end,
            text=seg.text.strip()
        ))

    return segments


def _transcribe_mlx(audio_path: Path, config: Dict[str, Any]) -> List[Segment]:
    """Transcribe using mlx-whisper (Apple Silicon optimized)"""
    try:
        import mlx_whisper
    except ImportError:
        raise ImportError(
            "MLX Whisper requires mlx-whisper (Apple Silicon only):\n"
            "pip install mlx-whisper"
        )

    # Model mapping to MLX community repos
    model_map = {
        "tiny": "mlx-community/whisper-tiny-mlx",
        "base": "mlx-community/whisper-base-mlx",
        "small": "mlx-community/whisper-small-mlx",
        "medium": "mlx-community/whisper-medium-mlx",
        "large": "mlx-community/whisper-large-v3-mlx",
        "large-v2": "mlx-community/whisper-large-v2-mlx",
        "large-v3": "mlx-community/whisper-large-v3-mlx",
        "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
    }

    model_name = config['whisper'].get('local_model', 'large-v3')
    mlx_model = model_map.get(model_name, model_name)  # Allow direct HF repo path

    source_lang = config['whisper'].get('source_language', None)

    # Build transcribe options
    transcribe_opts = {
        "path_or_hf_repo": mlx_model,
        "word_timestamps": True,
    }

    # Add language parameter if source language specified
    if source_lang and source_lang != 'auto':
        transcribe_opts["language"] = source_lang

    # Transcribe
    result = mlx_whisper.transcribe(str(audio_path), **transcribe_opts)

    segments = []
    for seg in result.get("segments", []):
        segments.append(Segment(
            start=seg["start"],
            end=seg["end"],
            text=seg["text"].strip()
        ))

    return segments


def _transcribe_openai(audio_path: Path, config: Dict[str, Any]) -> List[Segment]:
    """Transcribe using OpenAI Whisper API"""
    from openai import OpenAI
    import os

    api_key = config['whisper'].get('openai_key', '')
    if not api_key:
        api_key = os.environ.get('OPENAI_API_KEY', '')

    if not api_key:
        raise ValueError("OpenAI API Key not configured")

    source_lang = config['whisper'].get('source_language', None)

    client = OpenAI(api_key=api_key)

    # OpenAI Whisper API has 25MB file size limit
    file_size = audio_path.stat().st_size
    if file_size > 25 * 1024 * 1024:
        raise ValueError(
            f"Audio file ({file_size / 1024 / 1024:.1f}MB) exceeds OpenAI's 25MB limit. "
            "Please use local Whisper or split the audio."
        )

    # Build API parameters
    api_params = {
        "model": "whisper-1",
        "response_format": "verbose_json",
        "timestamp_granularities": ["segment"]
    }

    # Add language parameter if source language specified
    if source_lang and source_lang != 'auto':
        api_params["language"] = source_lang

    with open(audio_path, 'rb') as f:
        api_params["file"] = f
        response = client.audio.transcriptions.create(**api_params)

    segments = []
    # OpenAI SDK v1+ returns object attributes, not dict
    for seg in response.segments:
        segments.append(Segment(
            start=seg.start,
            end=seg.end,
            text=seg.text.strip()
        ))

    return segments


def _transcribe_groq(audio_path: Path, config: Dict[str, Any]) -> List[Segment]:
    """Transcribe using Groq API (super fast)"""
    try:
        from groq import Groq
    except ImportError:
        raise ImportError(
            "Groq API requires groq package:\n"
            "pip install groq"
        )

    import os

    api_key = config['whisper'].get('groq_key', '')
    if not api_key:
        api_key = os.environ.get('GROQ_API_KEY', '')

    if not api_key:
        raise ValueError("Groq API Key not configured")

    source_lang = config['whisper'].get('source_language', None)

    # Groq also has 25MB file size limit
    file_size = audio_path.stat().st_size
    if file_size > 25 * 1024 * 1024:
        raise ValueError(
            f"Audio file ({file_size / 1024 / 1024:.1f}MB) exceeds Groq's 25MB limit. "
            "Please use local Whisper or split the audio."
        )

    client = Groq(api_key=api_key)

    # Build API parameters
    api_params = {
        "model": "whisper-large-v3",
        "response_format": "verbose_json",
        "timestamp_granularities": ["segment"],
    }

    # Add language parameter if source language specified
    if source_lang and source_lang != 'auto':
        api_params["language"] = source_lang

    with open(audio_path, 'rb') as f:
        api_params["file"] = f
        response = client.audio.transcriptions.create(**api_params)

    segments = []
    # Check if response has segments attribute
    if not hasattr(response, 'segments') or not response.segments:
        # Fallback: if no segments, use entire text as one segment
        if hasattr(response, 'text') and response.text:
            return [Segment(start=0.0, end=0.0, text=response.text.strip())]
        return []

    for seg in response.segments:
        segments.append(Segment(
            start=seg.start,
            end=seg.end,
            text=seg.text.strip()
        ))

    return segments
