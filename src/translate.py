"""翻译模块"""

from typing import Dict, Any, List, Callable, Optional
from .transcribe import Segment


# 翻译系统提示词
TRANSLATION_SYSTEM_PROMPT = """你是一个专业的字幕翻译员。你的任务是将字幕翻译成{target_lang}。

翻译要求：
1. 保持原意，但表达要自然流畅
2. 字幕要简洁，适合屏幕显示（每行不超过{max_chars}个字符）
3. 保持前后文连贯性
4. 人名、地名等专有名词保持一致
5. 口语化表达，避免书面语

输出格式：
- 只输出翻译结果，每行对应一条字幕
- 不要添加序号或额外说明
"""

TRANSLATION_USER_PROMPT = """请翻译以下字幕（每行一条）：

{subtitles}
"""


def translate_segments(
    segments: List[Segment],
    config: Dict[str, Any],
    progress_callback: Optional[Callable[[int], None]] = None
) -> List[Segment]:
    """
    翻译字幕片段
    
    Args:
        segments: 字幕片段列表
        config: 配置字典
        progress_callback: 进度回调函数
        
    Returns:
        翻译后的字幕片段列表
    """
    provider = config['translation']['provider']
    target_lang = config['output']['target_language']
    max_chars = config['output']['max_chars_per_line']
    batch_size = config['advanced']['translation_batch_size']
    
    # 获取翻译函数
    if provider == 'openai':
        translate_fn = _translate_openai
    elif provider == 'claude':
        translate_fn = _translate_claude
    elif provider == 'deepseek':
        translate_fn = _translate_deepseek
    elif provider == 'ollama':
        translate_fn = _translate_ollama
    else:
        raise ValueError(f"不支持的翻译提供商: {provider}")
    
    # 分批翻译
    translated_segments = []
    for i in range(0, len(segments), batch_size):
        batch = segments[i:i + batch_size]
        batch_texts = [seg.text for seg in batch]
        
        # 调用翻译
        translations = translate_fn(
            batch_texts,
            target_lang,
            max_chars,
            config
        )
        
        # 更新字幕
        for seg, trans in zip(batch, translations):
            seg.translated = trans
            translated_segments.append(seg)
        
        # 更新进度
        if progress_callback:
            progress_callback(len(batch))
    
    return translated_segments


def _translate_openai(
    texts: List[str],
    target_lang: str,
    max_chars: int,
    config: Dict[str, Any]
) -> List[str]:
    """使用 OpenAI API 翻译"""
    from openai import OpenAI
    import os
    
    api_key = config['translation'].get('api_key', '') or os.environ.get('OPENAI_API_KEY', '')
    base_url = config['translation'].get('base_url', None)
    model = config['translation'].get('model', 'gpt-4o-mini')
    
    if not api_key:
        raise ValueError("OpenAI API Key 未配置")
    
    client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)
    
    system_prompt = TRANSLATION_SYSTEM_PROMPT.format(
        target_lang=_get_lang_name(target_lang),
        max_chars=max_chars
    )
    
    user_prompt = TRANSLATION_USER_PROMPT.format(
        subtitles="\n".join(texts)
    )
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,  # 低温度，更稳定的翻译
    )
    
    # 解析结果
    result_text = response.choices[0].message.content.strip()
    translations = result_text.split('\n')
    
    # 确保数量匹配
    while len(translations) < len(texts):
        translations.append("")
    
    return translations[:len(texts)]


def _translate_claude(
    texts: List[str],
    target_lang: str,
    max_chars: int,
    config: Dict[str, Any]
) -> List[str]:
    """使用 Claude API 翻译"""
    import anthropic
    import os
    
    api_key = config['translation'].get('api_key', '') or os.environ.get('ANTHROPIC_API_KEY', '')
    model = config['translation'].get('model', 'claude-3-haiku-20240307')
    
    if not api_key:
        raise ValueError("Anthropic API Key 未配置")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    system_prompt = TRANSLATION_SYSTEM_PROMPT.format(
        target_lang=_get_lang_name(target_lang),
        max_chars=max_chars
    )
    
    user_prompt = TRANSLATION_USER_PROMPT.format(
        subtitles="\n".join(texts)
    )
    
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt}
        ]
    )
    
    result_text = response.content[0].text.strip()
    translations = result_text.split('\n')
    
    while len(translations) < len(texts):
        translations.append("")
    
    return translations[:len(texts)]


def _translate_deepseek(
    texts: List[str],
    target_lang: str,
    max_chars: int,
    config: Dict[str, Any]
) -> List[str]:
    """使用 DeepSeek API 翻译（OpenAI 兼容接口）"""
    from openai import OpenAI
    import os
    
    api_key = config['translation'].get('api_key', '') or os.environ.get('DEEPSEEK_API_KEY', '')
    model = config['translation'].get('model', 'deepseek-chat')
    
    if not api_key:
        raise ValueError("DeepSeek API Key 未配置")
    
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com/v1"
    )
    
    system_prompt = TRANSLATION_SYSTEM_PROMPT.format(
        target_lang=_get_lang_name(target_lang),
        max_chars=max_chars
    )
    
    user_prompt = TRANSLATION_USER_PROMPT.format(
        subtitles="\n".join(texts)
    )
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,
    )
    
    result_text = response.choices[0].message.content.strip()
    translations = result_text.split('\n')
    
    while len(translations) < len(texts):
        translations.append("")
    
    return translations[:len(texts)]


def _translate_ollama(
    texts: List[str],
    target_lang: str,
    max_chars: int,
    config: Dict[str, Any]
) -> List[str]:
    """使用本地 Ollama 翻译"""
    import httpx
    
    host = config['translation'].get('ollama_host', 'http://localhost:11434')
    model = config['translation'].get('ollama_model', 'qwen2.5:14b')
    
    system_prompt = TRANSLATION_SYSTEM_PROMPT.format(
        target_lang=_get_lang_name(target_lang),
        max_chars=max_chars
    )
    
    user_prompt = TRANSLATION_USER_PROMPT.format(
        subtitles="\n".join(texts)
    )
    
    response = httpx.post(
        f"{host}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
        },
        timeout=120.0
    )
    response.raise_for_status()
    
    result = response.json()
    result_text = result['message']['content'].strip()
    translations = result_text.split('\n')
    
    while len(translations) < len(texts):
        translations.append("")
    
    return translations[:len(texts)]


def _get_lang_name(lang_code: str) -> str:
    """语言代码转语言名称"""
    lang_map = {
        'zh': '中文',
        'en': 'English',
        'ja': '日本語',
        'ko': '한국어',
        'fr': 'Français',
        'de': 'Deutsch',
        'es': 'Español',
        'pt': 'Português',
        'ru': 'Русский',
        'ar': 'العربية',
    }
    return lang_map.get(lang_code, lang_code)
