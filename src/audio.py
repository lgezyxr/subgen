"""音频提取模块"""

import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any


def check_ffmpeg() -> bool:
    """检查 FFmpeg 是否可用"""
    return shutil.which('ffmpeg') is not None


def check_ffprobe() -> bool:
    """检查 FFprobe 是否可用"""
    return shutil.which('ffprobe') is not None


def extract_audio(video_path: Path, config: Dict[str, Any]) -> Path:
    """
    从视频文件中提取音频
    
    Args:
        video_path: 视频文件路径
        config: 配置字典
        
    Returns:
        提取的音频文件路径 (WAV 格式)
    """
    if not check_ffmpeg():
        raise RuntimeError(
            "FFmpeg 未安装或不在 PATH 中。\n"
            "请安装 FFmpeg:\n"
            "  macOS: brew install ffmpeg\n"
            "  Ubuntu: sudo apt install ffmpeg\n"
            "  Windows: https://ffmpeg.org/download.html"
        )
    
    if not video_path.exists():
        raise FileNotFoundError(f"视频文件不存在: {video_path}")
    
    temp_dir = Path(config.get('advanced', {}).get('temp_dir', '/tmp/subgen'))
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
        '-loglevel', 'error',  # 只显示错误
        str(audio_path)
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 音频提取失败: {result.stderr}")
    
    if not audio_path.exists():
        raise RuntimeError("音频提取失败：输出文件未生成")
    
    return audio_path


def get_audio_duration(audio_path: Path) -> float:
    """获取音频时长（秒）"""
    if not check_ffprobe():
        raise RuntimeError(
            "FFprobe 未安装或不在 PATH 中。\n"
            "FFprobe 通常随 FFmpeg 一起安装。"
        )
    
    if not audio_path.exists():
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")
    
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
    
    duration_str = result.stdout.strip()
    if not duration_str or duration_str == 'N/A':
        raise RuntimeError("无法解析音频时长：文件可能已损坏")
    
    try:
        return float(duration_str)
    except ValueError:
        raise RuntimeError(f"无法解析音频时长: '{duration_str}'")


def cleanup_temp_files(config: Dict[str, Any]) -> None:
    """清理临时文件"""
    if config.get('advanced', {}).get('keep_temp_files', False):
        return
    
    temp_dir = Path(config.get('advanced', {}).get('temp_dir', '/tmp/subgen'))
    if temp_dir.exists():
        for f in temp_dir.glob('*_audio.wav'):
            try:
                f.unlink()
            except OSError:
                pass
