"""
Transcription cache for SubGen.

Caches Whisper transcription results to avoid re-processing when only
translation parameters change.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .logger import debug

CACHE_VERSION = 1
CACHE_SUFFIX = ".subgen-cache.json"


def get_cache_path(video_path: Path) -> Path:
    """Get cache file path for a video file."""
    return video_path.with_suffix(video_path.suffix + CACHE_SUFFIX)


def get_file_metadata(file_path: Path) -> Dict[str, Any]:
    """Get file metadata for validation."""
    stat = file_path.stat()
    return {
        "file_size": stat.st_size,
        "file_mtime": stat.st_mtime,
    }


def save_cache(
    video_path: Path,
    segments: List[Dict[str, Any]],
    word_segments: Optional[List[Dict[str, Any]]],
    whisper_provider: str,
    whisper_model: str,
    source_lang: str,
) -> Path:
    """
    Save transcription results to cache.
    
    Args:
        video_path: Path to the source video file
        segments: Transcription segments from Whisper
        word_segments: Word-level segments (if available)
        whisper_provider: Provider used (local, mlx, openai, groq)
        whisper_model: Model used (large-v3, etc.)
        source_lang: Detected/specified source language
        
    Returns:
        Path to the cache file
    """
    cache_path = get_cache_path(video_path)
    metadata = get_file_metadata(video_path)
    
    cache_data = {
        "version": CACHE_VERSION,
        "source_file": video_path.name,
        "file_size": metadata["file_size"],
        "file_mtime": metadata["file_mtime"],
        "created_at": time.time(),
        "whisper_provider": whisper_provider,
        "whisper_model": whisper_model,
        "source_lang": source_lang,
        "segment_count": len(segments),
        "segments": segments,
        "word_segments": word_segments,
    }
    
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)
    
    debug("cache: saved %d segments to %s", len(segments), cache_path)
    return cache_path


def load_cache(video_path: Path, strict: bool = True) -> Optional[Dict[str, Any]]:
    """
    Load and validate cached transcription.
    
    Args:
        video_path: Path to the source video file
        strict: If True, validate file size and mtime match
        
    Returns:
        Cache data dict if valid, None otherwise
    """
    cache_path = get_cache_path(video_path)
    
    if not cache_path.exists():
        debug("cache: no cache file found at %s", cache_path)
        return None
    
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        debug("cache: failed to read cache file: %s", e)
        return None
    
    # Version check
    if cache_data.get("version") != CACHE_VERSION:
        debug("cache: version mismatch (got %s, expected %s)", 
              cache_data.get("version"), CACHE_VERSION)
        return None
    
    # File validation
    if strict:
        try:
            metadata = get_file_metadata(video_path)
        except FileNotFoundError:
            debug("cache: source file not found")
            return None
        
        if cache_data.get("file_size") != metadata["file_size"]:
            debug("cache: file size mismatch")
            return None
        
        # Allow 1 second tolerance for mtime (filesystem precision varies)
        cached_mtime = cache_data.get("file_mtime", 0)
        if abs(cached_mtime - metadata["file_mtime"]) > 1.0:
            debug("cache: file mtime mismatch (cached=%.1f, actual=%.1f)", 
                  cached_mtime, metadata["file_mtime"])
            return None
    
    # Validate required fields
    required_fields = ["segments", "source_lang", "whisper_provider"]
    for field in required_fields:
        if field not in cache_data:
            debug("cache: missing required field: %s", field)
            return None
    
    debug("cache: loaded valid cache with %d segments", len(cache_data["segments"]))
    return cache_data


def format_cache_info(cache_data: Dict[str, Any]) -> str:
    """Format cache info for display."""
    created_at = cache_data.get("created_at", 0)
    age_seconds = time.time() - created_at
    
    if age_seconds < 60:
        age_str = f"{int(age_seconds)} sec ago"
    elif age_seconds < 3600:
        age_str = f"{int(age_seconds / 60)} min ago"
    elif age_seconds < 86400:
        age_str = f"{int(age_seconds / 3600)} hours ago"
    else:
        age_str = f"{int(age_seconds / 86400)} days ago"
    
    provider = cache_data.get("whisper_provider", "unknown")
    model = cache_data.get("whisper_model", "unknown")
    lang = cache_data.get("source_lang", "unknown")
    segments = cache_data.get("segment_count", len(cache_data.get("segments", [])))
    
    return f"Whisper: {provider}/{model}, Language: {lang}, {segments} segments ({age_str})"


def delete_cache(video_path: Path) -> bool:
    """Delete cache file for a video."""
    cache_path = get_cache_path(video_path)
    if cache_path.exists():
        cache_path.unlink()
        debug("cache: deleted %s", cache_path)
        return True
    return False
