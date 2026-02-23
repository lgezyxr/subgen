"""Speech recognition module"""

import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from .logger import debug


@dataclass
class Word:
    """Word with timestamp"""
    text: str
    start: float
    end: float


@dataclass
class Segment:
    """Subtitle segment"""
    start: float      # Start time (seconds)
    end: float        # End time (seconds)
    text: str         # Original text
    translated: str = ""  # Translated text
    words: List[Word] = field(default_factory=list)  # Word-level timestamps
    no_speech_prob: float = 0.0  # Probability of no speech (0-1)
    avg_logprob: float = 0.0  # Average log probability


def split_long_segments(segments: List[Segment], max_duration: float = 15.0) -> List[Segment]:
    """
    Split segments that are too long using word boundaries.
    
    Args:
        segments: List of transcribed segments
        max_duration: Maximum duration for a segment (seconds)
        
    Returns:
        List of segments with long ones split
    """
    result = []
    
    for seg in segments:
        duration = seg.end - seg.start
        
        # If segment is within limit, keep as-is
        if duration <= max_duration:
            result.append(seg)
            continue
        
        # If no word-level data, keep as-is (can't split accurately)
        if not seg.words:
            debug("split_long_segments: segment [%.1f-%.1f] too long (%.1fs) but no word data, keeping",
                  seg.start, seg.end, duration)
            result.append(seg)
            continue
        
        # Split using word boundaries
        debug("split_long_segments: splitting segment [%.1f-%.1f] (%.1fs, %d words)",
              seg.start, seg.end, duration, len(seg.words))
        
        current_words = []
        current_start = seg.words[0].start if seg.words else seg.start
        
        for word in seg.words:
            current_words.append(word)
            current_duration = word.end - current_start
            
            # Split at natural boundaries (punctuation) or when duration exceeded
            is_sentence_end = word.text.rstrip().endswith(('.', '!', '?', '。', '！', '？', '…'))
            should_split = (current_duration >= max_duration * 0.8) or \
                          (current_duration >= max_duration * 0.5 and is_sentence_end)
            
            if should_split and len(current_words) >= 2:
                # Create new segment from accumulated words
                new_seg = Segment(
                    start=current_start,
                    end=word.end,
                    text=' '.join(w.text for w in current_words).strip(),
                    words=current_words.copy(),
                    no_speech_prob=seg.no_speech_prob,
                    avg_logprob=seg.avg_logprob
                )
                result.append(new_seg)
                debug("split_long_segments: created sub-segment [%.1f-%.1f] %s",
                      new_seg.start, new_seg.end, new_seg.text[:30])
                
                # Reset for next segment
                current_words = []
                current_start = word.end
        
        # Handle remaining words
        if current_words:
            new_seg = Segment(
                start=current_start,
                end=seg.words[-1].end,
                text=' '.join(w.text for w in current_words).strip(),
                words=current_words,
                no_speech_prob=seg.no_speech_prob,
                avg_logprob=seg.avg_logprob
            )
            result.append(new_seg)
    
    return result


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
    
    debug("transcribe: provider=%s, audio=%s", provider, audio_path)

    if provider == 'local':
        segments = _transcribe_local(audio_path, config)
        debug("transcribe: _transcribe_local returned")
    elif provider == 'mlx':
        segments = _transcribe_mlx(audio_path, config)
    elif provider == 'openai':
        segments = _transcribe_openai(audio_path, config)
    elif provider == 'groq':
        segments = _transcribe_groq(audio_path, config)
    else:
        raise ValueError(f"Unsupported Whisper provider: {provider}")

    debug("transcribe: got %d segments", len(segments))

    # Validate: filter out low-density segments (likely music/noise)
    validate = config.get('advanced', {}).get('validate_segments', True)
    if validate:
        original_count = len(segments)
        segments = validate_segments(segments, config)
        if len(segments) != original_count:
            debug("transcribe: validated, %d -> %d segments", original_count, len(segments))

    # Post-process: split long segments using word boundaries
    max_segment_duration = config.get('advanced', {}).get('max_segment_duration', 15.0)
    split_long = config.get('advanced', {}).get('split_long_segments', True)
    
    debug("transcribe: split_long=%s, max_duration=%.1f", split_long, max_segment_duration)
    
    if split_long:
        original_count = len(segments)
        debug("transcribe: calling split_long_segments...")
        segments = split_long_segments(segments, max_duration=max_segment_duration)
        debug("transcribe: split_long_segments done")
        if len(segments) != original_count:
            debug("transcribe: split long segments, %d -> %d", original_count, len(segments))

    # Post-process: merge segments by sentence boundaries (disabled by default)
    merge_sentences = config.get('advanced', {}).get('merge_sentences', False)

    if merge_sentences:
        segments = merge_segments_by_sentence(segments, max_duration=max_segment_duration)
        debug("transcribe: after merge, %d segments", len(segments))

    debug("transcribe: returning %d segments", len(segments))

    return segments


def validate_segments(segments: List[Segment], config: Dict[str, Any]) -> List[Segment]:
    """
    Validate and filter segments based on speech density.
    
    Segments with very low words-per-second are likely music or noise
    that Whisper incorrectly transcribed.
    
    Args:
        segments: List of transcribed segments
        config: Configuration dictionary
        
    Returns:
        Filtered list of segments
    """
    min_words_per_sec = config.get('advanced', {}).get('min_words_per_sec', 0.3)
    min_duration_for_check = config.get('advanced', {}).get('min_duration_for_density_check', 20.0)
    
    result = []
    skipped = 0
    
    for seg in segments:
        duration = seg.end - seg.start
        word_count = len(seg.words) if seg.words else len(seg.text.split())
        
        # Only check density for long segments
        if duration >= min_duration_for_check:
            words_per_sec = word_count / duration if duration > 0 else 0
            
            if words_per_sec < min_words_per_sec:
                debug("validate_segments: skipping [%.1f-%.1f] (%.1fs, %d words, %.2f w/s): %s",
                      seg.start, seg.end, duration, word_count, words_per_sec,
                      seg.text[:30] if seg.text else "")
                skipped += 1
                continue
        
        result.append(seg)
    
    if skipped > 0:
        debug("validate_segments: skipped %d low-density segments (likely music)", skipped)
    
    return result


# Global reference to keep model alive and prevent crash on garbage collection
_model_ref = None


def _transcribe_local(audio_path: Path, config: Dict[str, Any]) -> List[Segment]:
    """Transcribe using local faster-whisper"""
    global _model_ref
    
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError(
            "Local Whisper requires faster-whisper:\n"
            "pip install faster-whisper"
        )
    
    import gc
    try:
        import torch
        has_torch = True
    except ImportError:
        has_torch = False

    model_name = config['whisper'].get('local_model', 'large-v3')
    device = config['whisper'].get('device', 'cuda')
    source_lang = config['whisper'].get('source_language', None)

    debug("transcribe_local: model=%s, device=%s, lang=%s", model_name, device, source_lang)

    # Select compute type (can be overridden in config)
    # float16 is fastest but not supported on older GPUs (Pascal/GTX 10xx)
    compute_type = config['whisper'].get('compute_type', None)
    
    if compute_type is None:
        if device == "cpu":
            compute_type = "int8"
        else:
            # Try float16 first, fallback to float32 for older GPUs
            compute_type = "float16"

    debug("transcribe_local: loading model with compute_type=%s", compute_type)

    # Load model with fallback for older GPUs
    try:
        model = WhisperModel(model_name, device=device, compute_type=compute_type)
    except ValueError as e:
        if "float16" in str(e) and compute_type == "float16":
            print("  ⚠️  GPU doesn't support float16, using float32...")
            compute_type = "float32"
            debug("transcribe_local: fallback to compute_type=%s", compute_type)
            model = WhisperModel(model_name, device=device, compute_type=compute_type)
        else:
            raise
    
    debug("transcribe_local: model loaded, starting transcription...")

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
    
    debug("transcribe_local: detected language=%s, probability=%.2f", 
          info.language, info.language_probability)

    # Config for filtering
    filter_music = config.get('advanced', {}).get('filter_music', True)
    no_speech_threshold = config.get('advanced', {}).get('no_speech_threshold', 0.6)
    max_no_speech_duration = config.get('advanced', {}).get('max_no_speech_duration', 30.0)

    segments = []
    segment_count = 0
    skipped_count = 0
    
    for seg in segments_iter:
        segment_count += 1
        duration = seg.end - seg.start
        no_speech_prob = getattr(seg, 'no_speech_prob', 0.0)
        avg_logprob = getattr(seg, 'avg_logprob', 0.0)
        
        # Debug logging for first few and every 50th segment
        if segment_count <= 3 or segment_count % 50 == 0:
            debug("transcribe_local: segment %d: [%.1f-%.1f] no_speech=%.2f logprob=%.2f %s", 
                  segment_count, seg.start, seg.end, no_speech_prob, avg_logprob,
                  seg.text[:40] if seg.text else "")
        
        # Filter likely music/noise segments
        if filter_music:
            # High no_speech_prob = likely not speech
            if no_speech_prob > no_speech_threshold:
                # For short segments, skip if very high no_speech_prob
                # For long segments (likely OP/ED), also skip with moderate no_speech_prob
                if no_speech_prob > 0.8 or (duration > max_no_speech_duration and no_speech_prob > 0.5):
                    skipped_count += 1
                    debug("transcribe_local: skipping segment %d (no_speech=%.2f, duration=%.1fs): %s",
                          segment_count, no_speech_prob, duration, seg.text[:30] if seg.text else "")
                    continue
        
        # Extract word-level timestamps
        words = []
        if seg.words:
            for w in seg.words:
                words.append(Word(
                    text=w.word.strip(),
                    start=w.start,
                    end=w.end
                ))
        
        segments.append(Segment(
            start=seg.start,
            end=seg.end,
            text=seg.text.strip(),
            words=words,
            no_speech_prob=no_speech_prob,
            avg_logprob=avg_logprob
        ))
    
    debug("transcribe_local: completed, total %d segments (%d skipped as music/noise)", 
          len(segments), skipped_count)

    # GPU memory cleanup (disabled - causes crash on some systems)
    # The memory will be released naturally when the function returns
    # and the model goes out of scope
    # 
    # If you want to enable manual cleanup, uncomment below:
    # debug("transcribe_local: releasing GPU memory...")
    # try:
    #     del model
    #     gc.collect()
    #     if has_torch and device == 'cuda' and torch.cuda.is_available():
    #         torch.cuda.empty_cache()
    # except Exception as e:
    #     debug("transcribe_local: cleanup error: %s", e)

    # Keep model reference alive to prevent crash during garbage collection
    # The model will be cleaned up on next transcription or program exit
    _model_ref = model
    
    debug("transcribe_local: about to return %d segments", len(segments))
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
        # Extract word-level timestamps
        words = []
        for w in seg.get("words", []):
            words.append(Word(
                text=w.get("word", "").strip(),
                start=w.get("start", 0),
                end=w.get("end", 0)
            ))
        
        segments.append(Segment(
            start=seg["start"],
            end=seg["end"],
            text=seg["text"].strip(),
            words=words
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
