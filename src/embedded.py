"""
Embedded subtitle detection and extraction from video files.
"""

import subprocess
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from .logger import debug


@dataclass
class SubtitleTrack:
    """Represents an embedded subtitle track."""
    index: int           # Stream index in the container
    stream_index: int    # Subtitle stream index (0, 1, 2...)
    codec: str           # subrip, ass, hdmv_pgs_subtitle, dvd_subtitle, etc.
    language: Optional[str]  # Language code (eng, jpn, chi, etc.)
    title: Optional[str]     # Track title if available
    is_text: bool        # True for SRT/ASS/VTT, False for PGS/VobSub
    is_default: bool     # Default track flag
    is_forced: bool      # Forced subtitle flag


# Language code mapping (ISO 639-2 to our codes)
LANG_CODE_MAP = {
    'eng': 'en', 'en': 'en',
    'jpn': 'ja', 'ja': 'ja', 'jap': 'ja',
    'chi': 'zh', 'zh': 'zh', 'zho': 'zh', 'cmn': 'zh',
    'kor': 'ko', 'ko': 'ko',
    'fra': 'fr', 'fr': 'fr', 'fre': 'fr',
    'deu': 'de', 'de': 'de', 'ger': 'de',
    'spa': 'es', 'es': 'es',
    'ita': 'it', 'it': 'it',
    'por': 'pt', 'pt': 'pt',
    'rus': 'ru', 'ru': 'ru',
    'ara': 'ar', 'ar': 'ar',
    'hin': 'hi', 'hi': 'hi',
    'tha': 'th', 'th': 'th',
    'vie': 'vi', 'vi': 'vi',
    'ind': 'id', 'id': 'id',
    'msa': 'ms', 'ms': 'ms', 'may': 'ms',
    'und': None,  # Undefined
}

# Text-based subtitle codecs (can be directly used)
TEXT_CODECS = {'subrip', 'srt', 'ass', 'ssa', 'webvtt', 'vtt', 'mov_text', 'text'}

# Image-based subtitle codecs (need OCR)
IMAGE_CODECS = {'hdmv_pgs_subtitle', 'dvd_subtitle', 'dvdsub', 'pgssub', 'pgs'}


def normalize_language(lang: Optional[str]) -> Optional[str]:
    """Normalize language code to our standard (en, zh, ja, etc.)."""
    if not lang:
        return None
    lang = lang.lower().strip()
    return LANG_CODE_MAP.get(lang, lang[:2] if len(lang) >= 2 else None)


def detect_subtitle_tracks(video_path: Path) -> List[SubtitleTrack]:
    """
    Detect all subtitle tracks in a video file using ffprobe.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        List of SubtitleTrack objects
    """
    try:
        result = subprocess.run(
            [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                '-select_streams', 's',  # Only subtitle streams
                str(video_path)
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            debug("ffprobe failed: %s", result.stderr)
            return []
        
        data = json.loads(result.stdout)
        streams = data.get('streams', [])
        
        tracks = []
        sub_index = 0
        
        for stream in streams:
            codec = stream.get('codec_name', '').lower()
            tags = stream.get('tags', {})
            disposition = stream.get('disposition', {})
            
            # Get language from tags
            language = tags.get('language') or tags.get('LANGUAGE')
            
            track = SubtitleTrack(
                index=stream.get('index', 0),
                stream_index=sub_index,
                codec=codec,
                language=normalize_language(language),
                title=tags.get('title') or tags.get('TITLE'),
                is_text=codec in TEXT_CODECS,
                is_default=disposition.get('default', 0) == 1,
                is_forced=disposition.get('forced', 0) == 1,
            )
            tracks.append(track)
            sub_index += 1
            
            debug("Found subtitle track: index=%d, codec=%s, lang=%s, text=%s",
                  track.stream_index, track.codec, track.language, track.is_text)
        
        return tracks
        
    except subprocess.TimeoutExpired:
        debug("ffprobe timed out")
        return []
    except json.JSONDecodeError as e:
        debug("ffprobe JSON parse error: %s", e)
        return []
    except FileNotFoundError:
        debug("ffprobe not found")
        return []
    except Exception as e:
        debug("Error detecting subtitles: %s", e)
        return []


def extract_subtitle_track(
    video_path: Path,
    track: SubtitleTrack,
    output_path: Optional[Path] = None
) -> Optional[Path]:
    """
    Extract a subtitle track from a video file.
    
    Args:
        video_path: Path to the video file
        track: SubtitleTrack to extract
        output_path: Output path (default: video_path with .srt extension)
        
    Returns:
        Path to extracted subtitle file, or None if failed
    """
    if not track.is_text:
        debug("Cannot extract image-based subtitle (codec=%s)", track.codec)
        return None
    
    if output_path is None:
        output_path = video_path.parent / f"{video_path.stem}_extracted.srt"
    
    try:
        result = subprocess.run(
            [
                'ffmpeg',
                '-y',  # Overwrite
                '-i', str(video_path),
                '-map', f'0:s:{track.stream_index}',
                '-c:s', 'srt',  # Convert to SRT
                str(output_path)
            ],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            debug("ffmpeg extraction failed: %s", result.stderr)
            return None
        
        if output_path.exists() and output_path.stat().st_size > 0:
            debug("Extracted subtitle to: %s", output_path)
            return output_path
        else:
            debug("Extraction produced empty file")
            return None
            
    except subprocess.TimeoutExpired:
        debug("ffmpeg extraction timed out")
        return None
    except FileNotFoundError:
        debug("ffmpeg not found")
        return None
    except Exception as e:
        debug("Error extracting subtitle: %s", e)
        return None


def detect_video_language(video_path: Path) -> Optional[str]:
    """
    Try to detect the primary language of the video from audio track metadata.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        Language code (en, zh, ja, etc.) or None
    """
    try:
        result = subprocess.run(
            [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                '-select_streams', 'a',  # Audio streams
                str(video_path)
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return None
        
        data = json.loads(result.stdout)
        streams = data.get('streams', [])
        
        # Look for default audio track language
        for stream in streams:
            tags = stream.get('tags', {})
            disposition = stream.get('disposition', {})
            
            if disposition.get('default', 0) == 1:
                lang = tags.get('language') or tags.get('LANGUAGE')
                if lang:
                    return normalize_language(lang)
        
        # Fallback to first audio track
        if streams:
            tags = streams[0].get('tags', {})
            lang = tags.get('language') or tags.get('LANGUAGE')
            if lang:
                return normalize_language(lang)
        
        return None
        
    except Exception as e:
        debug("Error detecting video language: %s", e)
        return None


def find_best_subtitle_track(
    tracks: List[SubtitleTrack],
    source_lang: Optional[str] = None,
    target_lang: Optional[str] = None
) -> Tuple[Optional[SubtitleTrack], str]:
    """
    Find the best subtitle track to use based on language preferences.
    
    Args:
        tracks: List of available subtitle tracks
        source_lang: Expected source language (e.g., 'en', 'ja')
        target_lang: Target translation language (e.g., 'zh')
        
    Returns:
        Tuple of (best_track, reason) where reason is one of:
        - 'target_exists': Target language subtitle already exists
        - 'source_match': Found source language subtitle
        - 'single_track': Only one track available
        - 'default_track': Using default track
        - 'first_text': Using first text-based track
        - 'none': No usable track found
    """
    if not tracks:
        return None, 'none'
    
    # Filter to text-based subtitles only
    text_tracks = [t for t in tracks if t.is_text]
    
    if not text_tracks:
        debug("No text-based subtitle tracks found (only image-based)")
        return None, 'none'
    
    # 1. Check if target language subtitle already exists
    if target_lang:
        for track in text_tracks:
            if track.language == target_lang:
                debug("Found target language subtitle: %s", track.language)
                return track, 'target_exists'
    
    # 2. If only one text track, use it
    if len(text_tracks) == 1:
        debug("Only one text subtitle track available")
        return text_tracks[0], 'single_track'
    
    # 3. Find source language match
    if source_lang:
        for track in text_tracks:
            if track.language == source_lang:
                debug("Found source language subtitle: %s", track.language)
                return track, 'source_match'
    
    # 4. Try default track
    for track in text_tracks:
        if track.is_default:
            debug("Using default subtitle track")
            return track, 'default_track'
    
    # 5. Use first text track
    debug("Using first text subtitle track")
    return text_tracks[0], 'first_text'


def check_embedded_subtitles(
    video_path: Path,
    source_lang: Optional[str],
    target_lang: str
) -> Dict[str, Any]:
    """
    Check for embedded subtitles and determine the best action.
    
    Args:
        video_path: Path to video file
        source_lang: Source language (or 'auto')
        target_lang: Target translation language
        
    Returns:
        Dict with keys:
        - 'action': 'use_target' | 'use_source' | 'transcribe'
        - 'track': SubtitleTrack to use (if action != 'transcribe')
        - 'reason': Human-readable explanation
        - 'tracks': All detected tracks
    """
    tracks = detect_subtitle_tracks(video_path)
    
    if not tracks:
        return {
            'action': 'transcribe',
            'track': None,
            'reason': 'No embedded subtitles found',
            'tracks': []
        }
    
    # Detect video language if source is auto
    detected_source = None
    if source_lang == 'auto' or not source_lang:
        detected_source = detect_video_language(video_path)
        debug("Detected video language: %s", detected_source)
    
    effective_source = source_lang if source_lang != 'auto' else detected_source
    
    best_track, reason = find_best_subtitle_track(tracks, effective_source, target_lang)
    
    if reason == 'target_exists':
        return {
            'action': 'use_target',
            'track': best_track,
            'reason': f'Target language subtitle ({target_lang}) already exists',
            'tracks': tracks
        }
    elif reason in ('source_match', 'single_track', 'default_track', 'first_text'):
        return {
            'action': 'use_source',
            'track': best_track,
            'reason': f'Using embedded subtitle ({best_track.language or "unknown"}) as source',
            'tracks': tracks
        }
    else:
        return {
            'action': 'transcribe',
            'track': None,
            'reason': 'No usable text subtitles found',
            'tracks': tracks
        }
