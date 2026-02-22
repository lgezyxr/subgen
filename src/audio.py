"""Audio extraction module"""

import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any


def check_ffmpeg() -> bool:
    """Check if FFmpeg is available"""
    return shutil.which('ffmpeg') is not None


def check_ffprobe() -> bool:
    """Check if FFprobe is available"""
    return shutil.which('ffprobe') is not None


def extract_audio(video_path: Path, config: Dict[str, Any]) -> Path:
    """
    Extract audio from video file

    Args:
        video_path: Path to video file
        config: Configuration dictionary

    Returns:
        Path to extracted audio file (WAV format)
    """
    if not check_ffmpeg():
        raise RuntimeError(
            "FFmpeg is not installed or not in PATH.\n"
            "Please install FFmpeg:\n"
            "  macOS: brew install ffmpeg\n"
            "  Ubuntu: sudo apt install ffmpeg\n"
            "  Windows: https://ffmpeg.org/download.html"
        )

    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    temp_dir = Path(config.get('advanced', {}).get('temp_dir', '/tmp/subgen'))
    temp_dir.mkdir(parents=True, exist_ok=True)

    audio_path = temp_dir / f"{video_path.stem}_audio.wav"

    # Use FFmpeg to extract audio
    # -vn: disable video
    # -acodec pcm_s16le: 16-bit PCM encoding
    # -ar 16000: 16kHz sample rate (recommended for Whisper)
    # -ac 1: mono channel
    cmd = [
        'ffmpeg',
        '-i', str(video_path),
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        '-y',  # overwrite existing file
        '-loglevel', 'error',  # only show errors
        str(audio_path)
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr}")

    if not audio_path.exists():
        raise RuntimeError("Audio extraction failed: output file not created")

    return audio_path


def get_audio_duration(audio_path: Path) -> float:
    """Get audio duration in seconds"""
    if not check_ffprobe():
        raise RuntimeError(
            "FFprobe is not installed or not in PATH.\n"
            "FFprobe is usually installed with FFmpeg."
        )

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(audio_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Failed to get audio duration: {result.stderr}")

    duration_str = result.stdout.strip()
    if not duration_str or duration_str == 'N/A':
        raise RuntimeError("Failed to parse audio duration: file may be corrupted")

    try:
        return float(duration_str)
    except ValueError:
        raise RuntimeError(f"Failed to parse audio duration: '{duration_str}'")


def cleanup_temp_files(config: Dict[str, Any]) -> None:
    """Clean up temporary files"""
    if config.get('advanced', {}).get('keep_temp_files', False):
        return

    temp_dir = Path(config.get('advanced', {}).get('temp_dir', '/tmp/subgen'))
    if temp_dir.exists():
        for f in temp_dir.glob('*_audio.wav'):
            try:
                f.unlink()
            except OSError:
                pass
