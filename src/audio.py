"""音频提取模块"""

import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any


def extract_audio(video_path: Path, config: Dict[str, Any]) -> Path:
    """
    从视频文件中提取音频
    
    Args:
        video_path: 视频文件路径
        config: 配置字典
        
    Returns:
        提取的音频文件路径 (WAV 格式)
    """
    temp_dir = Path(config['advanced']['temp_dir'])
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    audio_path = temp_dir / f"{video_path.stem}_audio.wav"
    
    # 使用 FFmpeg 提取音频
    # -vn: 不处理视频
    # -acodec pcm_s16le: 16-bit PCM 编码
    # -ar 16000: 采样率 16kHz (Whisper 推荐)
    # -ac 1: 单声道
    cmd = [
        'ffmpeg',
        '-i', str(video_path),
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        '-y',  # 覆盖已存在的文件
        str(audio_path)
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 音频提取失败: {result.stderr}")
    
    return audio_path


def get_audio_duration(audio_path: Path) -> float:
    """获取音频时长（秒）"""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(audio_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"无法获取音频时长: {result.stderr}")
    
    return float(result.stdout.strip())
