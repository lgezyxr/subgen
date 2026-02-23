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

# Sentence-aware translation prompt (legacy, without word alignment)
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

# Word-aligned translation prompt
WORD_ALIGNED_TRANSLATION_PROMPT = """You are a professional subtitle translator. Translate {source_lang} to {target_lang}.

The following sentence has word-level positions. Translate it and split into subtitle segments.
For each segment, indicate which English word position it should END at.

English sentence with word positions:
{words_with_positions}

Requirements:
1. Translate the complete sentence naturally
2. Split into {min_segments}-{max_segments} subtitle segments (fewer is better, but each ≤{max_chars} chars)
3. Each segment should end at a natural break point
4. Choose end positions that align semantically (e.g., "Marty Firestone" = "马蒂·法尔斯通" should be in same segment)

Output format (one segment per line):
translated text | end: N

Example:
现在和我在一起的是 | end: 4
Travel Secure公司总裁马蒂·法尔斯通 | end: 11
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
            
            # Check for error messages in translation response
            translations = _validate_translations(translations, batch_texts)
            
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


def _validate_translations(translations: List[str], originals: List[str]) -> List[str]:
    """
    Validate translations and detect error messages.
    
    If a translation looks like an error message from the LLM,
    fall back to keeping the original text.
    """
    # Common error message patterns (Chinese and English)
    error_patterns = [
        "抱歉", "无法", "对不起", "不能完成", "超过", "太长",
        "sorry", "cannot", "unable", "too long", "exceeds",
        "I cannot", "I'm unable", "I apologize"
    ]
    
    result = []
    for i, trans in enumerate(translations):
        # Check if translation looks like an error message
        is_error = False
        if trans and len(trans) > 50:  # Error messages are usually longer
            trans_lower = trans.lower()
            for pattern in error_patterns:
                if pattern.lower() in trans_lower:
                    is_error = True
                    break
        
        if is_error:
            # Keep original text if translation is an error message
            from .logger import debug
            debug("validate_translations: detected error message, keeping original: %s", trans[:50])
            result.append(originals[i] if i < len(originals) else "")
        else:
            result.append(trans)
    
    return result


def _group_segments_by_sentence(segments: List[Segment], max_group_size: int = 10) -> List[List[Segment]]:
    """
    Group segments by sentence boundaries.
    
    Segments not ending with sentence-ending punctuation are grouped
    with following segments until a sentence end is found.
    
    Args:
        segments: List of segments to group
        max_group_size: Maximum segments per group (prevents runaway grouping)
    
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
        
        # Check if this segment ends a sentence OR group is too large
        if sentence_end.search(text) or not text or len(current_group) >= max_group_size:
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
    translate_fn: Callable = None,
    progress_callback: Optional[Callable[[int], None]] = None
) -> List[Segment]:
    """
    Translate segments with sentence awareness and word-level alignment.
    
    If word-level timestamps are available, uses them to create precise
    subtitle timing based on LLM semantic understanding.
    """
    from .transcribe import Segment, Word
    from .logger import debug, debug_segments
    
    if not segments:
        return segments
    
    source_lang = config.get('output', {}).get('source_language', 'auto')
    target_lang = config.get('output', {}).get('target_language', 'zh')
    max_chars = config.get('output', {}).get('max_chars_per_line', 40)
    
    debug("sentence_aware: source=%s, target=%s, max_chars=%d", source_lang, target_lang, max_chars)
    debug_segments("sentence_aware input", segments)
    
    # Get translate function if not provided
    if translate_fn is None:
        provider = config.get('translation', {}).get('provider', 'openai')
        debug("sentence_aware: using provider=%s", provider)
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
    
    # Check if we have word-level timestamps
    has_word_timestamps = any(seg.words for seg in segments)
    debug("sentence_aware: has_word_timestamps=%s", has_word_timestamps)
    
    # Group segments by sentence
    groups = _group_segments_by_sentence(segments)
    debug("sentence_aware: %d groups from %d segments", len(groups), len(segments))
    
    translated_segments = []
    
    for i, group in enumerate(groups):
        debug("sentence_aware: processing group %d/%d with %d segments", i+1, len(groups), len(group))
        
        # Collect all words from this sentence group
        all_words = []
        for seg in group:
            if seg.words:
                all_words.extend(seg.words)
        
        debug("sentence_aware: group %d has %d words", i+1, len(all_words))
        
        # Use word-aligned translation if we have word data
        if has_word_timestamps and all_words:
            try:
                debug("sentence_aware: using word-aligned translation for group %d", i+1)
                new_segments = _translate_with_word_alignment(
                    group, all_words, source_lang, target_lang, max_chars, config
                )
                debug("sentence_aware: word-aligned produced %d segments", len(new_segments))
                translated_segments.extend(new_segments)
            except Exception as e:
                print(f"Word-aligned translation failed: {e}, falling back...")
                # Fallback to simple translation
                for seg in group:
                    try:
                        translations = translate_fn([seg.text], source_lang, target_lang, max_chars, config)
                        seg.translated = translations[0] if translations else seg.text
                    except:
                        seg.translated = seg.text
                    translated_segments.append(seg)
        else:
            # No word timestamps - use legacy approach
            num_parts = len(group)
            
            if num_parts == 1:
                seg = group[0]
                try:
                    translations = translate_fn([seg.text], source_lang, target_lang, max_chars, config)
                    seg.translated = translations[0] if translations else seg.text
                except Exception as e:
                    print(f"Translation failed: {e}")
                    seg.translated = seg.text
                translated_segments.append(seg)
            else:
                merged_text = " ".join(seg.text.strip() for seg in group)
                prompt = SENTENCE_TRANSLATION_PROMPT.format(
                    source_lang=_get_lang_name(source_lang),
                    target_lang=_get_lang_name(target_lang),
                    num_parts=num_parts,
                    max_chars=max_chars,
                    sentence=merged_text
                )
                
                try:
                    translations = _translate_sentence_group(prompt, num_parts, config)
                    for idx, seg in enumerate(group):
                        if idx < len(translations):
                            seg.translated = translations[idx].strip()
                        else:
                            seg.translated = seg.text
                        translated_segments.append(seg)
                except Exception as e:
                    print(f"Sentence translation failed: {e}")
                    for seg in group:
                        seg.translated = seg.text
                        translated_segments.append(seg)
        
        if progress_callback:
            progress_callback(len(group))
    
    return translated_segments


def _translate_with_word_alignment(
    group: List[Segment],
    all_words: List,  # List[Word]
    source_lang: str,
    target_lang: str,
    max_chars: int,
    config: Dict[str, Any]
) -> List[Segment]:
    """
    Translate a sentence group using word-level alignment.
    
    LLM decides how to split the translation and indicates which word position
    each segment should end at. We then create segments with precise timestamps.
    """
    from .transcribe import Segment, Word
    from .logger import debug
    
    # Build words with positions string
    words_with_positions = " ".join(
        f"[{i}]{w.text}" for i, w in enumerate(all_words)
    )
    
    debug("word_alignment: input words: %s", words_with_positions[:200])
    
    # Calculate reasonable segment count range
    total_words = len(all_words)
    min_segments = 1
    max_segments = max(1, total_words // 3)  # Roughly 3+ words per segment
    
    prompt = WORD_ALIGNED_TRANSLATION_PROMPT.format(
        source_lang=_get_lang_name(source_lang),
        target_lang=_get_lang_name(target_lang),
        words_with_positions=words_with_positions,
        min_segments=min_segments,
        max_segments=max_segments,
        max_chars=max_chars
    )
    
    debug("word_alignment: calling LLM with max_segments=%d", max_segments)
    
    # Call LLM
    result = _translate_sentence_group(prompt, max_segments, config)
    
    debug("word_alignment: LLM returned %d lines: %s", len(result), result)
    
    # Parse result: "translated text | end: N"
    new_segments = []
    prev_end_idx = -1
    
    for line in result:
        line = line.strip()
        if not line:
            continue
        
        debug("word_alignment: parsing line: %s", line)
        
        # Parse "text | end: N" format
        if "|" in line and "end:" in line.lower():
            parts = line.rsplit("|", 1)
            text = parts[0].strip()
            end_part = parts[1].lower()
            
            # Extract end position
            import re
            match = re.search(r'end:\s*(\d+)', end_part)
            if match:
                end_idx = int(match.group(1))
                
                # Clamp to valid range
                end_idx = min(end_idx, len(all_words) - 1)
                end_idx = max(end_idx, prev_end_idx + 1)
                
                # Calculate timestamps from word boundaries
                start_idx = prev_end_idx + 1
                start_time = all_words[start_idx].start if start_idx < len(all_words) else all_words[-1].end
                end_time = all_words[end_idx].end
                
                debug("word_alignment: segment text=%s, start_idx=%d, end_idx=%d, time=%.2f-%.2f", 
                      text[:20], start_idx, end_idx, start_time, end_time)
                
                new_segments.append(Segment(
                    start=start_time,
                    end=end_time,
                    text=" ".join(w.text for w in all_words[start_idx:end_idx+1]),
                    translated=text
                ))
                
                prev_end_idx = end_idx
            else:
                debug("word_alignment: no end position found in: %s", end_part)
        else:
            debug("word_alignment: line doesn't match format: %s", line)
    
    # If no valid segments were parsed, return original segments with translation
    if not new_segments:
        debug("word_alignment: no segments parsed, falling back")
        merged_text = " ".join(seg.text for seg in group)
        merged_translation = " ".join(result) if result else merged_text
        
        # Just return one segment with all the text
        return [Segment(
            start=group[0].start,
            end=group[-1].end,
            text=merged_text,
            translated=merged_translation
        )]
    
    debug("word_alignment: returning %d segments", len(new_segments))
    return new_segments


def _translate_sentence_group(prompt: str, expected_parts: int, config: Dict[str, Any]) -> List[str]:
    """
    Translate a sentence group using the configured LLM provider.
    """
    import requests
    from .logger import debug
    
    provider = config.get('translation', {}).get('provider', 'openai')
    debug("_translate_sentence_group: provider=%s, expected_parts=%d", provider, expected_parts)
    
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
        import uuid
        import platform
        
        access_token, account_id = get_openai_codex_token()
        # Codex API requires gpt-5.x-codex models, not gpt-4o
        model = config.get('translation', {}).get('model', 'gpt-5.3-codex')
        
        debug("chatgpt: using Codex Responses API, model=%s", model)
        
        # Build user agent
        system = platform.system().lower()
        release = platform.release()
        arch = platform.machine()
        user_agent = f"subgen ({system} {release}; {arch})"
        
        response = requests.post(
            "https://chatgpt.com/backend-api/codex/responses",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "chatgpt-account-id": account_id,
                "OpenAI-Beta": "responses=experimental",
                "originator": "subgen",
                "User-Agent": user_agent,
            },
            json={
                "model": model,
                "store": False,
                "stream": True,
                "instructions": "You are a professional subtitle translator.",
                "input": [{"role": "user", "content": prompt}],
            },
            timeout=120,
            stream=True
        )
        
        debug("chatgpt: response status=%d", response.status_code)
        
        if response.status_code == 403:
            # Try to get error details
            try:
                error_body = response.text[:1000]
                debug("chatgpt: 403 error body: %s", error_body)
                print(f"\n[ChatGPT 403 Error] {error_body[:200]}")
            except Exception as e:
                debug("chatgpt: failed to get error body: %s", e)
            raise ValueError("ChatGPT 403 Forbidden - try: subgen auth login chatgpt")
        
        if response.status_code == 401:
            raise ValueError("ChatGPT 401 Unauthorized - token expired. Run: subgen auth login chatgpt")
        
        if not response.ok:
            debug("chatgpt: error response: %s", response.text[:500])
            raise ValueError(f"ChatGPT API error: {response.status_code}")
        
        # Parse Codex Responses API SSE format
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
                    event_type = event.get('type', '')
                    
                    # Handle different event types from Codex Responses API
                    if event_type == 'response.output_text.delta':
                        # Streaming text delta
                        delta = event.get('delta', '')
                        result += delta
                        debug("chatgpt: text delta len=%d", len(delta))
                    elif event_type == 'response.completed':
                        # Final response
                        response_data = event.get('response', {})
                        output = response_data.get('output', [])
                        for item in output:
                            if item.get('type') == 'message':
                                content = item.get('content', [])
                                for part in content:
                                    if part.get('type') == 'output_text':
                                        result = part.get('text', result)
                        debug("chatgpt: response completed, result len=%d", len(result))
                    elif 'message' in event:
                        # Legacy conversation format (fallback)
                        msg = event['message']
                        if msg.get('author', {}).get('role') == 'assistant':
                            parts = msg.get('content', {}).get('parts', [])
                            if parts:
                                result = parts[0]
                except json.JSONDecodeError:
                    continue
        
        debug("chatgpt: final result len=%d, preview=%s", len(result), result[:100] if result else "(empty)")

    elif provider == 'claude':
        import anthropic
        api_key = config.get('translation', {}).get('api_key')
        model = config.get('translation', {}).get('model', 'claude-sonnet-4-20250514')
        
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{'role': 'user', 'content': prompt}]
        )
        result = message.content[0].text

    elif provider == 'ollama':
        import requests
        model = config.get('translation', {}).get('model', 'qwen2.5:14b')
        ollama_url = config.get('translation', {}).get('ollama_url', 'http://localhost:11434')
        
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                'model': model,
                'prompt': prompt,
                'stream': False,
            },
            timeout=120
        )
        response.raise_for_status()
        result = response.json()['response']

    elif provider == 'copilot':
        from .auth.copilot import get_copilot_api_token
        token = get_copilot_api_token()
        model = config.get('translation', {}).get('model', 'gpt-4o-mini')
        
        response = requests.post(
            'https://api.githubcopilot.com/chat/completions',
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'Editor-Version': 'vscode/1.85.0',
                'Copilot-Integration-Id': 'vscode-chat',
            },
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': prompt}],
            },
            timeout=60
        )
        response.raise_for_status()
        result = response.json()['choices'][0]['message']['content']
    
    else:
        raise ValueError(f"Unsupported provider for sentence-aware translation: {provider}")
    
    debug("_translate_sentence_group: raw result=%s", result[:200] if result else "(empty)")
    
    # Parse result into lines
    lines = [line.strip() for line in result.strip().split('\n') if line.strip()]
    
    debug("_translate_sentence_group: parsed %d lines", len(lines))
    
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
    model = config.get('translation', {}).get('model', 'auto')

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


# Proofreading prompt
PROOFREAD_SYSTEM_PROMPT = """You are a professional subtitle proofreader for {source_lang} to {target_lang} translation.

## Your Role
You are reviewing existing translations, NOT translating from scratch. Your job is to:
1. Fix mistranslations that don't match the original meaning
2. Improve unnatural expressions to sound more native in {target_lang}
3. Ensure consistency in names, terms, and tone throughout
4. Make sure translations fit the story context

## Translation Rules
{rules}

## Story Context (for understanding, NOT for translation)
{story_context}

## Critical Output Rules
- Output MUST be in {target_lang} only
- Output exactly {count} lines, one corrected translation per line
- If a translation is already good, output it unchanged
- Do NOT add numbering, explanations, or the original text
- Do NOT output the source language text
- NEVER mix languages in your output
"""

PROOFREAD_USER_PROMPT = """Review these {count} translations from {source_lang} to {target_lang}.
Output {count} lines of corrected {target_lang} translations only.

{pairs}
"""


# Model-specific settings for proofreading
MODEL_SETTINGS = {
    # OpenAI models
    'gpt-4o': {'batch_size': 50, 'context_chars': 15000},
    'gpt-4o-mini': {'batch_size': 50, 'context_chars': 15000},
    'gpt-4-turbo': {'batch_size': 50, 'context_chars': 15000},
    'gpt-4': {'batch_size': 30, 'context_chars': 8000},
    'gpt-3.5-turbo': {'batch_size': 20, 'context_chars': 4000},
    # Claude models
    'claude-3-opus': {'batch_size': 60, 'context_chars': 20000},
    'claude-3-sonnet': {'batch_size': 60, 'context_chars': 20000},
    'claude-3-haiku': {'batch_size': 40, 'context_chars': 12000},
    'claude-sonnet-4': {'batch_size': 60, 'context_chars': 20000},
    # DeepSeek
    'deepseek-chat': {'batch_size': 40, 'context_chars': 10000},
    'deepseek-coder': {'batch_size': 40, 'context_chars': 10000},
    # ChatGPT (Codex API)
    'gpt-5.3-codex': {'batch_size': 50, 'context_chars': 15000},
    # Ollama (conservative defaults)
    'ollama': {'batch_size': 15, 'context_chars': 3000},
    # Default fallback
    'default': {'batch_size': 30, 'context_chars': 8000},
}


def _get_model_settings(config: Dict[str, Any]) -> Dict[str, int]:
    """Get model-specific batch_size and context_chars for proofreading."""
    provider = config.get('translation', {}).get('provider', 'openai')
    
    # Try to get model name from config
    model = None
    if provider == 'openai':
        model = config.get('translation', {}).get('openai_model', 'gpt-4o')
    elif provider == 'claude':
        model = config.get('translation', {}).get('claude_model', 'claude-sonnet-4')
    elif provider == 'deepseek':
        model = config.get('translation', {}).get('deepseek_model', 'deepseek-chat')
    elif provider == 'chatgpt':
        model = config.get('translation', {}).get('model', 'gpt-5.3-codex')
    elif provider == 'ollama':
        model = 'ollama'  # Use conservative defaults for all Ollama models
    elif provider == 'copilot':
        model = 'gpt-4o'  # Copilot uses GPT-4 class models
    
    # Look up settings
    if model and model in MODEL_SETTINGS:
        return MODEL_SETTINGS[model]
    
    # Try provider-level defaults
    provider_defaults = {
        'openai': MODEL_SETTINGS['gpt-4o'],
        'claude': MODEL_SETTINGS['claude-sonnet-4'],
        'deepseek': MODEL_SETTINGS['deepseek-chat'],
        'chatgpt': MODEL_SETTINGS['gpt-5.3-codex'],
        'copilot': MODEL_SETTINGS['gpt-4o'],
        'ollama': MODEL_SETTINGS['ollama'],
    }
    
    return provider_defaults.get(provider, MODEL_SETTINGS['default'])


def proofread_translations(
    segments: List[Segment],
    config: Dict[str, Any],
    progress_callback: Optional[Callable[[int], None]] = None
) -> List[Segment]:
    """
    Proofread translations with full story context.
    
    Sends the LLM the complete source text for context,
    then reviews translations in batches for accuracy.
    
    Args:
        segments: Segments with .text (original) and .translated
        config: Configuration dictionary
        progress_callback: Progress update callback
        
    Returns:
        Segments with proofread translations
    """
    from .logger import debug
    
    if not segments:
        debug("proofread: no segments, returning early")
        return segments
    
    source_lang = config.get('output', {}).get('source_language', 'auto')
    target_lang = config.get('output', {}).get('target_language', 'zh')
    
    # Load translation rules for target language
    rules = load_translation_rules(target_lang) or "No specific rules."
    debug("proofread: loaded rules for %s (%d chars)", target_lang, len(rules))
    
    # Get model-specific settings (can be overridden in config)
    model_settings = _get_model_settings(config)
    batch_size = config.get('advanced', {}).get('proofread_batch_size') or model_settings['batch_size']
    max_context_chars = config.get('advanced', {}).get('proofread_context_chars') or model_settings['context_chars']
    
    # Build story context (all original text, no timestamps)
    story_lines = [seg.text for seg in segments if seg.text.strip()]
    story_context = '\n'.join(story_lines)
    
    # Truncate if too long (keep first and last parts for context)
    if len(story_context) > max_context_chars:
        half = max_context_chars // 2
        story_context = story_context[:half] + "\n...[truncated]...\n" + story_context[-half:]
    
    debug("proofread: %d segments, context=%d chars, batch_size=%d (model settings)", 
          len(segments), len(story_context), batch_size)
    
    # Check provider is supported
    provider = config.get('translation', {}).get('provider', 'openai')
    debug("proofread: provider=%s", provider)
    
    supported_providers = ['openai', 'claude', 'deepseek', 'chatgpt']
    if provider not in supported_providers:
        debug("proofread: unsupported provider %s, skipping", provider)
        print(f"[SubGen] Warning: Unsupported provider '{provider}' for proofreading (supported: {supported_providers})")
        return segments
    
    # Save raw translations before proofreading (for comparison)
    for seg in segments:
        if seg.translated and not seg.translated_raw:
            seg.translated_raw = seg.translated
    
    # Process in batches
    proofread_segments = []
    
    for i in range(0, len(segments), batch_size):
        batch = segments[i:i + batch_size]
        
        # Build pairs for review: "Original: xxx | Translation: yyy"
        pairs = []
        for j, seg in enumerate(batch):
            pairs.append(f"{j+1}. [{seg.text}] → [{seg.translated}]")
        pairs_text = '\n'.join(pairs)
        
        # Build prompt with rules and language info
        system_prompt = PROOFREAD_SYSTEM_PROMPT.format(
            source_lang=_get_lang_name(source_lang),
            target_lang=_get_lang_name(target_lang),
            rules=rules,
            story_context=story_context,
            count=len(batch)
        )
        
        user_prompt = PROOFREAD_USER_PROMPT.format(
            source_lang=_get_lang_name(source_lang),
            target_lang=_get_lang_name(target_lang),
            count=len(batch),
            pairs=pairs_text
        )
        
        try:
            debug("proofread: calling LLM for batch %d/%d (%d segments)", 
                  i // batch_size + 1, (len(segments) + batch_size - 1) // batch_size, len(batch))
            
            # Call LLM with custom prompts
            result = _call_llm_for_proofread(system_prompt, user_prompt, config)
            
            # Parse corrections (one per line)
            if result:
                correction_lines = result.strip().split('\n')
                # Clean up: remove numbering if present
                cleaned = []
                for line in correction_lines:
                    line = line.strip()
                    # Remove patterns like "1. ", "1) ", etc.
                    import re
                    line = re.sub(r'^\d+[\.\)]\s*', '', line)
                    if line:
                        cleaned.append(line)
                correction_lines = cleaned
                
                debug("proofread: batch %d got %d corrections", i // batch_size + 1, len(correction_lines))
                
                # Apply corrections
                for j, seg in enumerate(batch):
                    if j < len(correction_lines) and correction_lines[j].strip():
                        new_trans = correction_lines[j].strip()
                        if new_trans != seg.translated:
                            debug("proofread: corrected [%s] → [%s]", 
                                  seg.translated[:20], new_trans[:20])
                        seg.translated = new_trans
            
        except Exception as e:
            debug("proofread: batch %d failed: %s", i // batch_size + 1, e)
            # Keep original translations on error
        
        proofread_segments.extend(batch)
        
        if progress_callback:
            progress_callback(len(batch))
    
    return proofread_segments


def _call_llm_for_proofread(
    system_prompt: str,
    user_prompt: str,
    config: Dict[str, Any]
) -> str:
    """Call LLM with custom prompts for proofreading."""
    import requests
    from .logger import debug
    
    provider = config.get('translation', {}).get('provider', 'openai')
    debug("_call_llm_for_proofread: provider=%s", provider)
    
    if provider == 'chatgpt':
        from .auth.openai_codex import get_openai_codex_token, OpenAICodexAuthError, openai_codex_login
        
        try:
            access_token, account_id = get_openai_codex_token()
        except OpenAICodexAuthError as e:
            print(f"\n⚠️  {e}")
            print("Starting ChatGPT login...\n")
            openai_codex_login()
            access_token, account_id = get_openai_codex_token()
        
        model = config.get('translation', {}).get('model', 'gpt-5.3-codex')
        debug("_call_llm_for_proofread: chatgpt model=%s", model)
        
        response = requests.post(
            "https://chatgpt.com/backend-api/codex/responses",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "OpenAI-Beta": "responses=experimental",
                "chatgpt-account-id": account_id,
                "originator": "pi",
            },
            json={
                "model": model,
                "store": False,
                "stream": True,
                "instructions": system_prompt,
                "input": [{"role": "user", "content": user_prompt}]
            },
            timeout=180,
            stream=True
        )
        
        debug("_call_llm_for_proofread: chatgpt response status=%d", response.status_code)
        
        if not response.ok:
            error_text = response.text[:200] if hasattr(response, 'text') else str(response.content[:200])
            raise ValueError(f"ChatGPT API error: {response.status_code} - {error_text}")
        
        # Parse SSE stream
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
                    # Handle different event types
                    event_type = event.get('type', '')
                    if event_type == 'response.output_text.delta':
                        delta = event.get('delta', '')
                        result_text += delta
                    elif event_type == 'response.completed':
                        # Final response - extract full text
                        output = event.get('response', {}).get('output', [])
                        if output:
                            for item in output:
                                if item.get('type') == 'message':
                                    content = item.get('content', [])
                                    for c in content:
                                        if c.get('type') == 'output_text':
                                            result_text = c.get('text', result_text)
                except json.JSONDecodeError:
                    continue
        
        return result_text
    
    elif provider == 'openai':
        api_key = config.get('translation', {}).get('openai_api_key', '')
        if not api_key:
            raise ValueError("OpenAI API key not configured")
        
        model = config.get('translation', {}).get('openai_model', 'gpt-4o')
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3
            },
            timeout=180
        )
        
        if not response.ok:
            raise ValueError(f"OpenAI API error: {response.status_code}")
        
        return response.json()['choices'][0]['message']['content']
    
    elif provider == 'claude':
        api_key = config.get('translation', {}).get('claude_api_key', '')
        if not api_key:
            raise ValueError("Claude API key not configured")
        
        model = config.get('translation', {}).get('claude_model', 'claude-sonnet-4-20250514')
        
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": model,
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}]
            },
            timeout=180
        )
        
        if not response.ok:
            raise ValueError(f"Claude API error: {response.status_code}")
        
        return response.json()['content'][0]['text']
    
    elif provider == 'deepseek':
        api_key = config.get('translation', {}).get('deepseek_api_key', '')
        if not api_key:
            raise ValueError("DeepSeek API key not configured")
        
        model = config.get('translation', {}).get('deepseek_model', 'deepseek-chat')
        
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3
            },
            timeout=180
        )
        
        if not response.ok:
            raise ValueError(f"DeepSeek API error: {response.status_code}")
        
        return response.json()['choices'][0]['message']['content']
    
    else:
        raise ValueError(f"Unsupported provider for proofreading: {provider}")
