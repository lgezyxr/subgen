# ⚙️ Configuration

SubGen uses a YAML configuration file to manage all settings.

## Config File Location

By default, it reads `config.yaml` from the current directory. Use `--config` to specify a different path:

```bash
python subgen.py video.mp4 --config /path/to/my-config.yaml
```

---

## Complete Configuration

### Whisper Speech Recognition

```yaml
whisper:
  # Provider selection
  # - local: Run locally (requires GPU)
  # - openai: OpenAI Whisper API ($0.006/min)
  # - groq: Groq API (free tier available, very fast)
  provider: "openai"
  
  # Source language (optional)
  # Specify to improve accuracy, or leave as "auto" for auto-detection
  # en, es, ja, zh, fr, de, etc.
  source_language: "auto"
  
  # Local model selection (only for provider: local)
  # tiny (39M) → base (74M) → small (244M) → medium (769M) → large-v3 (1.5B)
  # Larger models are more accurate but require more VRAM
  local_model: "large-v3"
  
  # Device selection (only for provider: local)
  # cuda: NVIDIA GPU (recommended)
  # cpu: CPU (very slow, not recommended)
  device: "cuda"
  
  # API Keys
  openai_key: "sk-..."      # OpenAI API Key
  groq_key: "gsk_..."       # Groq API Key
```

### LLM Translation

```yaml
translation:
  # Provider selection
  # - openai: OpenAI GPT series
  # - claude: Anthropic Claude
  # - deepseek: DeepSeek (Chinese optimized, cheap)
  # - ollama: Local LLM (completely free)
  provider: "openai"
  
  # Model selection
  # OpenAI: gpt-4o-mini (cheap) | gpt-4o (best quality)
  # Claude: claude-3-haiku (fast) | claude-3-sonnet (balanced)
  # DeepSeek: deepseek-chat
  # Ollama: qwen2.5:14b | llama3:8b
  model: "gpt-4o-mini"
  
  # API Key (openai/claude/deepseek)
  api_key: "sk-..."
  
  # Custom API endpoint (optional, for proxies or compatible APIs)
  base_url: ""
  
  # Ollama configuration
  ollama_host: "http://localhost:11434"
  ollama_model: "qwen2.5:14b"
```

### Output Settings

```yaml
output:
  # Subtitle format
  # - srt: Most universal, all players support it
  # - ass: Supports styling, commonly used by fansubbers
  # - vtt: Web video standard
  format: "srt"
  
  # Source language (for translation prompt)
  # auto: auto-detect | en: English | ja: 日本語 | etc.
  source_language: "auto"
  
  # Target translation language
  # zh: 中文 | en: English | ja: 日本語 | ko: 한국어
  # fr: Français | de: Deutsch | es: Español
  target_language: "zh"
  
  # Bilingual subtitles
  # true: Show original + translation
  # false: Show translation only
  bilingual: false
  
  # Max characters per line
  # Controls subtitle line breaks
  max_chars_per_line: 42
  
  # Burn subtitles into video
  # true: Output new video with subtitles (hardcoded)
  # false: Output subtitle file only
  embed_in_video: false
```

### Advanced Settings

```yaml
advanced:
  # Translation batch size
  # How many subtitles to translate per API call
  # Too large may exceed token limits, too small is inefficient
  translation_batch_size: 20
  
  # Translation context size
  # How many surrounding subtitles to include as context
  # Helps maintain translation consistency
  translation_context_size: 5
  
  # Temporary files directory
  temp_dir: "./temp"
  
  # Keep temporary files (for debugging)
  keep_temp_files: false
  
  # Log level
  # DEBUG | INFO | WARNING | ERROR
  log_level: "INFO"
```

---

## Environment Variables

API keys can also be set via environment variables (lower priority than config file):

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GROQ_API_KEY="gsk_..."
export DEEPSEEK_API_KEY="sk-..."
```

---

## Configuration Examples

### Cheapest Option (Local Whisper + GPT-4o-mini)

```yaml
whisper:
  provider: "local"
  local_model: "large-v3"
  device: "cuda"

translation:
  provider: "openai"
  model: "gpt-4o-mini"
  api_key: "sk-..."
```

### Fastest Option (Groq + GPT-4o)

```yaml
whisper:
  provider: "groq"
  groq_key: "gsk_..."

translation:
  provider: "openai"
  model: "gpt-4o"
  api_key: "sk-..."
```

### Fully Offline (Local Whisper + Ollama)

```yaml
whisper:
  provider: "local"
  local_model: "large-v3"
  device: "cuda"

translation:
  provider: "ollama"
  ollama_host: "http://localhost:11434"
  ollama_model: "qwen2.5:14b"
```

### Chinese-Optimized (DeepSeek)

```yaml
whisper:
  provider: "openai"
  openai_key: "sk-..."

translation:
  provider: "deepseek"
  model: "deepseek-chat"
  api_key: "sk-..."
```

---

## Custom Translation Rules

SubGen supports language-specific translation rules.

### Rules File Location

Rules files are in the `rules/` directory:

```
subgen/
├── rules/
│   ├── zh.md          # Chinese rules
│   ├── ja.md          # Japanese rules
│   ├── ko.md          # Korean rules
│   └── default.md     # Default rules (fallback)
```

### Rule Loading Order

1. Exact match: `zh-TW.md`
2. Language family: `zh.md` (fallback from `zh-TW`)
3. Default: `default.md`

### Rule File Format

Uses Markdown format for easy reading and editing:

```markdown
# Chinese Subtitle Translation Rules

## Punctuation
- Use half-width punctuation
- Use 《》 for book titles

## Number Translation
- 1-9 use Chinese: 一、二、三
- 10+ use Arabic numerals
```

### Adding New Language Rules

1. Create `{language_code}.md` in the `rules/` directory
2. Write rules in Markdown format
3. Rules are automatically injected into the translation prompt

### Custom Rules Directory

Rules files are searched in this order:
1. Project directory `./rules/`
2. Current working directory `./rules/`
3. User directory `~/.subgen/rules/`

You can create global rules in your user directory or project-specific rules in the project directory.
