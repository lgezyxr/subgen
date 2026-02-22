"""Translation module"""

import time
import json
from pathlib import Path
from typing import Dict, Any, List, Callable, Optional
from .transcribe import Segment


# Base translation system prompt
TRANSLATION_SYSTEM_PROMPT_BASE = """You are a professional subtitle translator. Your task is to translate {source_lang} subtitles into {target_lang}.

Requirements:
1. Preserve the original meaning while ensuring natural, fluent expression
2. Keep subtitles concise for screen display (max {max_chars} characters per line)
3. Maintain consistency across context
4. Keep proper nouns (names, places) consistent throughout
5. Use colloquial expressions, avoid overly formal language

Output format:
- Output only the translations, one line per subtitle
- Do not add numbering or extra explanations
- Output exactly the same number of lines as input (strict 1:1 correspondence)
"""

# System prompt with rules
TRANSLATION_SYSTEM_PROMPT_WITH_RULES = """You are a professional subtitle translator. Your task is to translate {source_lang} subtitles into {target_lang}.

Requirements:
1. Preserve the original meaning while ensuring natural, fluent expression
2. Keep subtitles concise for screen display (max {max_chars} characters per line)
3. Maintain consistency across context
4. Keep proper nouns (names, places) consistent throughout
5. Use colloquial expressions, avoid overly formal language

{target_lang} Translation Rules (MUST follow strictly):
{rules}

Output format:
- Output only the translations, one line per subtitle
- Do not add numbering or extra explanations
- Output exactly the same number of lines as input (strict 1:1 correspondence)
"""

TRANSLATION_USER_PROMPT = """Please translate the following {count} subtitles (one per line, output must also be {count} lines):

{subtitles}
"""

# Sentence-aware translation prompt
SENTENCE_TRANSLATION_PROMPT = """You are a professional subtitle translator. Translate {source_lang} to {target_lang}.

The following is ONE complete sentence that spans {num_parts} subtitle segments.
Translate it naturally, then split your translation into exactly {num_parts} parts.

Requirements:
1. Translate the COMPLETE sentence first for accuracy
2. Then split into {num_parts} parts at natural break points
3. Each part should be ≤{max_chars} characters
4. Parts should flow naturally when read in sequence

Original sentence (split across {num_parts} segments):
{sentence}

Output exactly {num_parts} lines, one translation part per line:
"""


def _get_rules_dir() -> Path:
    """Get translation rules directory"""
    # Search for rules/ directory in multiple locations
    possible_paths = [
        Path(__file__).parent.parent / 'rules',  # Parent of src/
        Path.cwd() / 'rules',  # Current working directory
        Path.home() / '.subgen' / 'rules',  # User home directory
    ]
    for path in possible_paths:
        if path.exists():
            return path
    return possible_paths[0]  # Return default path even if it doesn't exist


def load_translation_rules(lang_code: str) -> Optional[str]:
    """
    Load translation rules for specified language

    Args:
        lang_code: Language code (e.g., 'zh', 'ja', 'en')

    Returns:
        Rules content string, or None if not found
    """
    rules_dir = _get_rules_dir()

    # Try loading order: exact match -> language family -> default
    # e.g., zh-TW -> zh-TW.md -> zh.md -> default.md
    candidates = [
        rules_dir / f'{lang_code}.md',
        rules_dir / f'{lang_code.split("-")[0]}.md',  # zh-TW -> zh
        rules_dir / 'default.md',
    ]

    for rule_file in candidates:
        if rule_file.exists():
            try:
                content = rule_file.read_text(encoding='utf-8')
                # Remove Markdown title, keep only content
                lines = []
                for line in content.split('\n'):
                    # Skip level-1 headings
                    if line.startswith('# '):
                        continue
                    lines.append(line)
                return '\n'.join(lines).strip()
            except Exception as e:
                print(f"Warning: Failed to read rules file {rule_file}: {e}")
                continue

    return None


def _build_system_prompt(source_lang: str, target_lang: str, max_chars: int, lang_code: str) -> str:
    """
    Build system prompt for translation

    Args:
        source_lang: Source language name
        target_lang: Target language name
        max_chars: Maximum characters per line
        lang_code: Target language code

    Returns:
        Complete system prompt
    """
    rules = load_translation_rules(lang_code)

    if rules:
        return TRANSLATION_SYSTEM_PROMPT_WITH_RULES.format(
            source_lang=source_lang,
            target_lang=target_lang,
            max_chars=max_chars,
            rules=rules
        )
    else:
        return TRANSLATION_SYSTEM_PROMPT_BASE.format(
            source_lang=source_lang,
            target_lang=target_lang,
            max_chars=max_chars
        )


def translate_segments(
    segments: List[Segment],
    config: Dict[str, Any],
    progress_callback: Optional[Callable[[int], None]] = None
) -> List[Segment]:
    """
    Translate subtitle segments

    Args:
        segments: List of subtitle segments
        config: Configuration dictionary
        progress_callback: Progress callback function

    Returns:
        List of translated subtitle segments
    """
    if not segments:
        return []

    provider = config.get('translation', {}).get('provider', 'openai')
    source_lang = config.get('output', {}).get('source_language', 'auto')
    target_lang = config.get('output', {}).get('target_language', 'zh')
    max_chars = config.get('output', {}).get('max_chars_per_line', 40)
    batch_size = config.get('advanced', {}).get('translation_batch_size', 10)

    # Validate batch_size
    if not batch_size or batch_size < 1:
        batch_size = 10  # Default value

    # Get translation function
    if provider == 'openai':
        translate_fn = _translate_openai
    elif provider == 'claude':
        translate_fn = _translate_claude
    elif provider == 'deepseek':
        translate_fn = _translate_deepseek
    elif provider == 'ollama':
        translate_fn = _translate_ollama
    elif provider == 'copilot':
        translate_fn = _translate_copilot
    elif provider == 'chatgpt':
        translate_fn = _translate_chatgpt
    else:
        raise ValueError(f"Unsupported translation provider: {provider}")

    # Translate in batches
    translated_segments = []
    for i in range(0, len(segments), batch_size):
        batch = segments[i:i + batch_size]
        batch_texts = [seg.text for seg in batch]

        # Skip empty batches
        if all(not text.strip() for text in batch_texts):
            for seg in batch:
                seg.translated = ""
                translated_segments.append(seg)
            if progress_callback:
                progress_callback(len(batch))
            continue

        # Call translation
        try:
            translations = translate_fn(
                batch_texts,
                source_lang,
                target_lang,
                max_chars,
                config
            )
        except Exception as e:
            # On translation failure, keep original text
            print(f"Translation batch failed: {e}")
            translations = batch_texts

        # Ensure translations length matches batch
        while len(translations) < len(batch):
            translations.append("")
        translations = translations[:len(batch)]

        # Update subtitles (use index iteration to ensure no loss)
        for idx, seg in enumerate(batch):
            trans = translations[idx] if idx < len(translations) else ""
            seg.translated = trans.strip() if trans else seg.text
            translated_segments.append(seg)

        # Update progress
        if progress_callback:
            progress_callback(len(batch))

    return translated_segments


def _group_segments_by_sentence(segments: List[Segment]) -> List[List[Segment]]:
    """
    Group segments by sentence boundaries.
    
    Segments not ending with sentence-ending punctuation are grouped
    with following segments until a sentence end is found.
    
    Returns:
        List of segment groups, where each group forms a complete sentence
    """
    import re
    sentence_end = re.compile(r'[.!?。！？…][\s"\'）\)]*$')
    
    groups = []
    current_group = []
    
    for seg in segments:
        current_group.append(seg)
        text = seg.text.strip()
        
        # Check if this segment ends a sentence
        if sentence_end.search(text) or not text:
            if current_group:
                groups.append(current_group)
                current_group = []
    
    # Don't forget remaining segments
    if current_group:
        groups.append(current_group)
    
    return groups


def translate_segments_sentence_aware(
    segments: List[Segment],
    config: Dict[str, Any],
    translate_fn: Callable,
    progress_callback: Optional[Callable[[int], None]] = None
) -> List[Segment]:
    """
    Translate segments with sentence awareness.
    
    Groups segments into complete sentences, translates each sentence,
    and lets the LLM decide how to split the translation.
    """
    if not segments:
        return segments
    
    source_lang = config.get('output', {}).get('source_language', 'auto')
    target_lang = config.get('output', {}).get('target_language', 'zh')
    max_chars = config.get('output', {}).get('max_chars_per_line', 40)
    
    # Group segments by sentence
    groups = _group_segments_by_sentence(segments)
    
    translated_segments = []
    
    for group in groups:
        num_parts = len(group)
        
        if num_parts == 1:
            # Single segment - translate normally
            seg = group[0]
            try:
                translations = translate_fn(
                    [seg.text],
                    source_lang,
                    target_lang,
                    max_chars,
                    config
                )
                seg.translated = translations[0] if translations else seg.text
            except Exception as e:
                print(f"Translation failed: {e}")
                seg.translated = seg.text
            translated_segments.append(seg)
        else:
            # Multiple segments - use sentence-aware prompt
            merged_text = " ".join(seg.text.strip() for seg in group)
            
            prompt = SENTENCE_TRANSLATION_PROMPT.format(
                source_lang=_get_lang_name(source_lang),
                target_lang=_get_lang_name(target_lang),
                num_parts=num_parts,
                max_chars=max_chars,
                sentence=merged_text
            )
            
            try:
                # Call LLM with the sentence-aware prompt
                translations = _translate_sentence_group(
                    prompt,
                    num_parts,
                    config
                )
                
                # Assign translations to segments
                for idx, seg in enumerate(group):
                    if idx < len(translations):
                        seg.translated = translations[idx].strip()
                    else:
                        seg.translated = seg.text
                    translated_segments.append(seg)
                    
            except Exception as e:
                print(f"Sentence translation failed: {e}")
                # Fallback: keep original text
                for seg in group:
                    seg.translated = seg.text
                    translated_segments.append(seg)
        
        if progress_callback:
            progress_callback(len(group))
    
    return translated_segments


def _translate_sentence_group(prompt: str, expected_parts: int, config: Dict[str, Any]) -> List[str]:
    """
    Translate a sentence group using the configured LLM provider.
    """
    import requests
    
    provider = config.get('translation', {}).get('provider', 'openai')
    
    if provider == 'openai':
        api_key = config.get('translation', {}).get('api_key')
        model = config.get('translation', {}).get('model', 'gpt-4o-mini')
        
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={'Authorization': f'Bearer {api_key}'},
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.3,
            },
            timeout=60
        )
        response.raise_for_status()
        result = response.json()['choices'][0]['message']['content']
        
    elif provider == 'deepseek':
        api_key = config.get('translation', {}).get('api_key')
        model = config.get('translation', {}).get('model', 'deepseek-chat')
        
        response = requests.post(
            'https://api.deepseek.com/chat/completions',
            headers={'Authorization': f'Bearer {api_key}'},
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.3,
            },
            timeout=60
        )
        response.raise_for_status()
        result = response.json()['choices'][0]['message']['content']
        
    elif provider == 'chatgpt':
        from .auth.openai_codex import get_openai_codex_token
        access_token, account_id = get_openai_codex_token()
        model = config.get('translation', {}).get('model', 'gpt-4o')
        
        response = requests.post(
            "https://chatgpt.com/backend-api/conversation",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "chatgpt-account-id": account_id,
            },
            json={
                "action": "next",
                "messages": [{
                    "id": f"msg-{int(time.time())}",
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": [prompt]}
                }],
                "model": model,
                "history_and_training_disabled": True,
            },
            timeout=120,
            stream=True
        )
        
        result = ""
        for line in response.iter_lines():
            if not line:
                continue
            line = line.decode('utf-8')
            if line.startswith('data: '):
                data = line[6:]
                if data == '[DONE]':
                    break
                try:
                    event = json.loads(data)
                    if 'message' in event:
                        msg = event['message']
                        if msg.get('author', {}).get('role') == 'assistant':
                            parts = msg.get('content', {}).get('parts', [])
                            if parts:
                                result = parts[0]
                except json.JSONDecodeError:
                    continue
    else:
        raise ValueError(f"Sentence-aware translation not yet supported for provider: {provider}")
    
    # Parse result into lines
    lines = [line.strip() for line in result.strip().split('\n') if line.strip()]
    
    # Remove numbering if present (1. xxx, 1) xxx, etc.)
    cleaned = []
    for line in lines:
        if line and line[0].isdigit():
            for sep in ['. ', ') ', ': ', '、', '．']:
                if sep in line[:5]:
                    line = line.split(sep, 1)[-1]
                    break
        cleaned.append(line)
    
    return cleaned[:expected_parts]


def _parse_translations(result_text: str, expected_count: int) -> List[str]:
    """
    Parse LLM translation results

    Handle various edge cases:
    - Line count mismatch
    - Empty lines
    - Extra formatting
    """
    # Split by lines, keep all lines (don't strip overall to avoid losing leading/trailing empty lines)
    lines = result_text.split('\n')

    # Remove possible numbering prefixes (1. 2. etc.)
    translations = []
    for line in lines:
        line_stripped = line.strip()
        # Remove common numbering formats
        if line_stripped and line_stripped[0].isdigit():
            # Check for "1. xxx" or "1) xxx" format
            for sep in ['. ', ') ', ': ', '、']:
                if sep in line_stripped[:5]:
                    line_stripped = line_stripped.split(sep, 1)[-1]
                    break
        translations.append(line_stripped)

    # Filter empty lines but maintain position correspondence
    # If line count matches, return directly
    if len(translations) == expected_count:
        return translations

    # If fewer lines than expected, pad with empty strings
    while len(translations) < expected_count:
        translations.append("")

    # If more lines than expected, truncate
    return translations[:expected_count]


def _translate_openai(
    texts: List[str],
    source_lang: str,
    target_lang: str,
    max_chars: int,
    config: Dict[str, Any]
) -> List[str]:
    """Translate using OpenAI API"""
    from openai import OpenAI
    import os

    api_key = config['translation'].get('api_key', '') or os.environ.get('OPENAI_API_KEY', '')
    base_url = config['translation'].get('base_url', None)
    model = config['translation'].get('model', 'gpt-4o-mini')

    if not api_key:
        raise ValueError("OpenAI API Key not configured")

    client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)

    system_prompt = _build_system_prompt(
        _get_lang_name(source_lang),
        _get_lang_name(target_lang),
        max_chars,
        target_lang
    )

    user_prompt = TRANSLATION_USER_PROMPT.format(
        count=len(texts),
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
    return _parse_translations(result_text, len(texts))


def _translate_claude(
    texts: List[str],
    source_lang: str,
    target_lang: str,
    max_chars: int,
    config: Dict[str, Any]
) -> List[str]:
    """Translate using Claude API"""
    import anthropic
    import os

    api_key = config['translation'].get('api_key', '') or os.environ.get('ANTHROPIC_API_KEY', '')
    model = config['translation'].get('model', 'claude-3-haiku-20240307')

    if not api_key:
        raise ValueError("Anthropic API Key not configured")

    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = _build_system_prompt(
        _get_lang_name(source_lang),
        _get_lang_name(target_lang),
        max_chars,
        target_lang
    )

    user_prompt = TRANSLATION_USER_PROMPT.format(
        count=len(texts),
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
    return _parse_translations(result_text, len(texts))


def _translate_deepseek(
    texts: List[str],
    source_lang: str,
    target_lang: str,
    max_chars: int,
    config: Dict[str, Any]
) -> List[str]:
    """Translate using DeepSeek API (OpenAI-compatible)"""
    from openai import OpenAI
    import os

    api_key = config['translation'].get('api_key', '') or os.environ.get('DEEPSEEK_API_KEY', '')
    model = config['translation'].get('model', 'deepseek-chat')

    if not api_key:
        raise ValueError("DeepSeek API Key not configured")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com/v1"
    )

    system_prompt = _build_system_prompt(
        _get_lang_name(source_lang),
        _get_lang_name(target_lang),
        max_chars,
        target_lang
    )

    user_prompt = TRANSLATION_USER_PROMPT.format(
        count=len(texts),
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
    return _parse_translations(result_text, len(texts))


def _translate_ollama(
    texts: List[str],
    source_lang: str,
    target_lang: str,
    max_chars: int,
    config: Dict[str, Any]
) -> List[str]:
    """Translate using local Ollama"""
    import httpx

    host = config['translation'].get('ollama_host', 'http://localhost:11434')
    model = config['translation'].get('ollama_model', 'qwen2.5:14b')

    system_prompt = _build_system_prompt(
        _get_lang_name(source_lang),
        _get_lang_name(target_lang),
        max_chars,
        target_lang
    )

    user_prompt = TRANSLATION_USER_PROMPT.format(
        count=len(texts),
        subtitles="\n".join(texts)
    )

    try:
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
    except httpx.ConnectError:
        raise ConnectionError(
            f"Cannot connect to Ollama ({host}). Please make sure Ollama is running:\n"
            "ollama serve"
        )

    result = response.json()
    result_text = result['message']['content'].strip()
    return _parse_translations(result_text, len(texts))


def _translate_copilot(
    texts: List[str],
    source_lang: str,
    target_lang: str,
    max_chars: int,
    config: Dict[str, Any]
) -> List[str]:
    """Translate using GitHub Copilot API"""
    import requests
    from .auth.copilot import get_copilot_api_token, CopilotAuthError, copilot_login

    # Get Copilot token (will refresh if needed)
    try:
        token = get_copilot_api_token()
    except CopilotAuthError as e:
        # Not logged in, try interactive login
        print(f"\n⚠️  {e}")
        print("Starting Copilot login...\n")
        try:
            copilot_login()
            token = get_copilot_api_token()
        except CopilotAuthError as e2:
            raise ValueError(f"Copilot authentication failed: {e2}")

    system_prompt = _build_system_prompt(
        _get_lang_name(source_lang),
        _get_lang_name(target_lang),
        max_chars,
        target_lang
    )

    user_prompt = TRANSLATION_USER_PROMPT.format(
        count=len(texts),
        subtitles="\n".join(texts)
    )

    # Call Copilot API (OpenAI-compatible)
    response = requests.post(
        "https://api.githubcopilot.com/chat/completions",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Editor-Version": "vscode/1.85.0",
            "Editor-Plugin-Version": "copilot-chat/0.12.0",
            "Openai-Organization": "github-copilot",
            "Openai-Intent": "conversation-panel",
        },
        json={
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3,
            "n": 1,
            "stream": False,
        },
        timeout=60
    )

    if response.status_code == 401:
        raise ValueError("Copilot token expired. Please run: subgen auth login copilot")

    if response.status_code == 400:
        # Log detailed error for debugging
        try:
            err = response.json()
            err_msg = err.get("error", {}).get("message", response.text[:500])
        except Exception:
            err_msg = response.text[:500]
        raise ValueError(f"Copilot API error (400): {err_msg}")

    response.raise_for_status()

    result = response.json()
    result_text = result['choices'][0]['message']['content'].strip()
    return _parse_translations(result_text, len(texts))


def _translate_chatgpt(
    texts: List[str],
    source_lang: str,
    target_lang: str,
    max_chars: int,
    config: Dict[str, Any]
) -> List[str]:
    """Translate using ChatGPT Plus (via OAuth login)"""
    import requests
    from .auth.openai_codex import get_openai_codex_token, OpenAICodexAuthError, openai_codex_login

    # Get ChatGPT token (will refresh if needed)
    try:
        access_token, account_id = get_openai_codex_token()
    except OpenAICodexAuthError as e:
        # Not logged in, try interactive login
        print(f"\n⚠️  {e}")
        print("Starting ChatGPT login...\n")
        try:
            openai_codex_login()
            access_token, account_id = get_openai_codex_token()
        except OpenAICodexAuthError as e2:
            raise ValueError(f"ChatGPT authentication failed: {e2}")

    system_prompt = _build_system_prompt(
        _get_lang_name(source_lang),
        _get_lang_name(target_lang),
        max_chars,
        target_lang
    )

    user_prompt = TRANSLATION_USER_PROMPT.format(
        count=len(texts),
        subtitles="\n".join(texts)
    )

    # Get model from config, default to gpt-4o
    model = config.get('translation', {}).get('model', 'gpt-4o')

    # Call ChatGPT backend API (Codex/Responses API)
    response = requests.post(
        "https://chatgpt.com/backend-api/conversation",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "chatgpt-account-id": account_id,
            "oai-device-id": account_id,
            "oai-language": "en-US",
        },
        json={
            "action": "next",
            "messages": [
                {
                    "id": f"msg-{int(time.time())}",
                    "author": {"role": "user"},
                    "content": {
                        "content_type": "text",
                        "parts": [f"{system_prompt}\n\n{user_prompt}"]
                    }
                }
            ],
            "model": model,
            "timezone_offset_min": -480,
            "history_and_training_disabled": True,
        },
        timeout=120,
        stream=True  # ChatGPT uses SSE streaming
    )

    if response.status_code == 401:
        raise ValueError("ChatGPT token expired. Please run: subgen auth login chatgpt")

    if response.status_code == 403:
        raise ValueError("ChatGPT access denied. Make sure you have a Plus/Pro subscription.")

    if not response.ok:
        raise ValueError(f"ChatGPT API error: {response.status_code}")

    # Parse SSE stream response
    result_text = ""
    for line in response.iter_lines():
        if not line:
            continue
        line = line.decode('utf-8')
        if line.startswith('data: '):
            data = line[6:]
            if data == '[DONE]':
                break
            try:
                event = json.loads(data)
                if 'message' in event:
                    msg = event['message']
                    if msg.get('author', {}).get('role') == 'assistant':
                        content = msg.get('content', {})
                        parts = content.get('parts', [])
                        if parts:
                            result_text = parts[0]
            except json.JSONDecodeError:
                continue

    if not result_text:
        raise ValueError("Empty response from ChatGPT")

    return _parse_translations(result_text, len(texts))


def _get_lang_name(lang_code: str) -> str:
    """Convert language code to language name"""
    lang_map = {
        'auto': 'source language',  # Display for auto-detect
        'zh': '中文',
        'zh-TW': '繁體中文',
        'en': 'English',
        'ja': '日本語',
        'ko': '한국어',
        'fr': 'Français',
        'de': 'Deutsch',
        'es': 'Español',
        'pt': 'Português',
        'ru': 'Русский',
        'ar': 'العربية',
        'th': 'ภาษาไทย',
        'vi': 'Tiếng Việt',
        'it': 'Italiano',
        'nl': 'Nederlands',
        'pl': 'Polski',
        'tr': 'Türkçe',
        'id': 'Bahasa Indonesia',
        'hi': 'हिन्दी',
    }
    return lang_map.get(lang_code, lang_code)
