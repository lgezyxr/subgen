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
    whisper_config = config.get('whisper', {})
    provider = whisper_config.get('provider', 'local')

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

    # 根据设备选择计算类型
    compute_type = "float16" if device == "cuda" else "int8"

    # 加载模型
    model = WhisperModel(model_name, device=device, compute_type=compute_type)

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
    import os

    api_key = config['whisper'].get('openai_key', '')
    if not api_key:
        api_key = os.environ.get('OPENAI_API_KEY', '')

    if not api_key:
        raise ValueError("OpenAI API Key 未配置")

    client = OpenAI(api_key=api_key)

    # OpenAI Whisper API 有 25MB 文件大小限制
    file_size = audio_path.stat().st_size
    if file_size > 25 * 1024 * 1024:
        raise ValueError(
            f"音频文件 ({file_size / 1024 / 1024:.1f}MB) 超过 OpenAI 25MB 限制。"
            "请使用本地 Whisper 或分割音频。"
        )

    with open(audio_path, 'rb') as f:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["segment"]
        )

    segments = []
    # OpenAI SDK v1+ 返回的是对象属性，不是字典
    for seg in response.segments:
        segments.append(Segment(
            start=seg.start,
            end=seg.end,
            text=seg.text.strip()
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

    import os

    api_key = config['whisper'].get('groq_key', '')
    if not api_key:
        api_key = os.environ.get('GROQ_API_KEY', '')

    if not api_key:
        raise ValueError("Groq API Key 未配置")

    # Groq 也有文件大小限制 (25MB)
    file_size = audio_path.stat().st_size
    if file_size > 25 * 1024 * 1024:
        raise ValueError(
            f"音频文件 ({file_size / 1024 / 1024:.1f}MB) 超过 Groq 25MB 限制。"
            "请使用本地 Whisper 或分割音频。"
        )

    client = Groq(api_key=api_key)

    with open(audio_path, 'rb') as f:
        response = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["segment"],  # 确保返回 segments
        )

    segments = []
    # 检查 response 是否有 segments 属性
    if not hasattr(response, 'segments') or not response.segments:
        # 回退：如果没有 segments，用整个文本作为一个片段
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
