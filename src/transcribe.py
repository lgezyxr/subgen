"""语音识别模块"""

from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class Segment:
    """字幕片段"""
    start: float      # 开始时间（秒）
    end: float        # 结束时间（秒）
    text: str         # 原文文本
    translated: str = ""  # 翻译文本


def transcribe_audio(audio_path: Path, config: Dict[str, Any]) -> List[Segment]:
    """
    对音频进行语音识别
    
    Args:
        audio_path: 音频文件路径
        config: 配置字典
        
    Returns:
        字幕片段列表
    """
    provider = config['whisper']['provider']
    
    if provider == 'local':
        return _transcribe_local(audio_path, config)
    elif provider == 'openai':
        return _transcribe_openai(audio_path, config)
    elif provider == 'groq':
        return _transcribe_groq(audio_path, config)
    else:
        raise ValueError(f"不支持的 Whisper 提供商: {provider}")


def _transcribe_local(audio_path: Path, config: Dict[str, Any]) -> List[Segment]:
    """使用本地 faster-whisper 进行语音识别"""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError(
            "本地 Whisper 需要安装 faster-whisper:\n"
            "pip install faster-whisper"
        )
    
    model_name = config['whisper'].get('local_model', 'large-v3')
    device = config['whisper'].get('device', 'cuda')
    
    # 加载模型
    model = WhisperModel(model_name, device=device, compute_type="float16")
    
    # 转录
    segments_iter, info = model.transcribe(
        str(audio_path),
        word_timestamps=True,
        vad_filter=True,  # 使用 VAD 过滤静音
    )
    
    segments = []
    for seg in segments_iter:
        segments.append(Segment(
            start=seg.start,
            end=seg.end,
            text=seg.text.strip()
        ))
    
    return segments


def _transcribe_openai(audio_path: Path, config: Dict[str, Any]) -> List[Segment]:
    """使用 OpenAI Whisper API 进行语音识别"""
    from openai import OpenAI
    
    api_key = config['whisper'].get('openai_key', '')
    if not api_key:
        import os
        api_key = os.environ.get('OPENAI_API_KEY', '')
    
    if not api_key:
        raise ValueError("OpenAI API Key 未配置")
    
    client = OpenAI(api_key=api_key)
    
    with open(audio_path, 'rb') as f:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["segment"]
        )
    
    segments = []
    for seg in response.segments:
        segments.append(Segment(
            start=seg['start'],
            end=seg['end'],
            text=seg['text'].strip()
        ))
    
    return segments


def _transcribe_groq(audio_path: Path, config: Dict[str, Any]) -> List[Segment]:
    """使用 Groq API 进行语音识别（超快）"""
    try:
        from groq import Groq
    except ImportError:
        raise ImportError(
            "Groq API 需要安装 groq:\n"
            "pip install groq"
        )
    
    api_key = config['whisper'].get('groq_key', '')
    if not api_key:
        import os
        api_key = os.environ.get('GROQ_API_KEY', '')
    
    if not api_key:
        raise ValueError("Groq API Key 未配置")
    
    client = Groq(api_key=api_key)
    
    with open(audio_path, 'rb') as f:
        response = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=f,
            response_format="verbose_json",
        )
    
    segments = []
    for seg in response.segments:
        segments.append(Segment(
            start=seg['start'],
            end=seg['end'],
            text=seg['text'].strip()
        ))
    
    return segments
