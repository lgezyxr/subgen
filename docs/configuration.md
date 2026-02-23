# ⚙️ Configuration

SubGen uses `config.yaml` for all settings. Run `python subgen.py init` to create one interactively.

## Config File Location

Default: `./config.yaml` in current directory.

```bash
# Use custom config
python subgen.py run video.mp4 --config /path/to/config.yaml
```

---

## Complete Configuration Reference

### Whisper (Speech Recognition)

```yaml
whisper:
  # Provider: local | mlx | openai | groq
  provider: "local"
  
  # Local/MLX model: tiny | base | small | medium | large-v3
  local_model: "large-v3"
  
  # Device for local provider: cuda | cpu
  device: "cuda"
  
  # Compute type for local provider (auto-detected if not set)
  # float16: Fast, requires modern GPU (RTX series)
  # float32: Compatible with older GPUs (GTX 10xx)
  # int8: Smallest memory footprint
  compute_type: "float16"
  
  # API keys (if using cloud providers)
  openai_key: "sk-..."
  groq_key: "gsk_..."
```

### Translation (LLM)

```yaml
translation:
  # Provider: openai | claude | deepseek | ollama | chatgpt | copilot
  provider: "chatgpt"
  
  # Model selection
  # ChatGPT: gpt-5.3-codex (default, has reasoning) | gpt-5.1-codex-mini
  # OpenAI: gpt-4o-mini | gpt-4o
  # Claude: claude-sonnet-4-20250514 | claude-3-haiku-20240307
  # DeepSeek: deepseek-chat
  # Ollama: qwen2.5:14b | llama3:8b
  model: "gpt-5.3-codex"
  
  # API keys (required for non-OAuth providers)
  api_key: "sk-..."
  
  # Ollama settings
  ollama_url: "http://localhost:11434"
```

### Output

```yaml
output:
  # Subtitle format: srt | ass | vtt
  format: "srt"
  
  # Source language (auto = auto-detect)
  source_language: "auto"
  
  # Target language
  target_language: "zh"
  
  # Show both original + translation
  bilingual: false
  
  # Max characters per subtitle line
  max_chars_per_line: 42
```

### Advanced

```yaml
advanced:
  # --- Transcription ---
  
  # Auto-split long segments using word timestamps
  split_long_segments: true
  max_segment_duration: 15.0
  
  # Filter music/noise by no_speech_prob (disabled by default)
  filter_music: false
  no_speech_threshold: 0.6
  
  # Filter by speech density (disabled by default)
  validate_segments: false
  min_words_per_sec: 0.3
  
  # --- Translation ---
  
  # Batch size (subtitles per API call)
  translation_batch_size: 20
  
  # Context window (surrounding subtitles for reference)
  translation_context_size: 5
  
  # Max segments per sentence group (prevents runaway grouping)
  max_group_size: 10
  
  # --- Proofreading ---
  
  # Override batch size for proofreading
  proofread_batch_size: 50
  
  # Max context chars for proofreading
  proofread_context_chars: 15000
  
  # --- Other ---
  
  temp_dir: "./temp"
  keep_temp_files: false
  log_level: "INFO"
```

---

## Configuration Examples

### ChatGPT Plus User (Recommended)

```yaml
whisper:
  provider: "local"  # or "mlx" for Apple Silicon
  local_model: "large-v3"
  device: "cuda"

translation:
  provider: "chatgpt"
  model: "gpt-5.3-codex"

output:
  target_language: "zh"
```

First run `python subgen.py auth login chatgpt` to authenticate.

### Cheapest Cloud Setup

```yaml
whisper:
  provider: "groq"
  groq_key: "gsk_..."

translation:
  provider: "deepseek"
  api_key: "sk-..."

output:
  target_language: "zh"
```

### Fully Offline

```yaml
whisper:
  provider: "local"
  local_model: "large-v3"
  device: "cuda"

translation:
  provider: "ollama"
  ollama_url: "http://localhost:11434"
  model: "qwen2.5:14b"

output:
  target_language: "zh"
```

### Apple Silicon Optimized

```yaml
whisper:
  provider: "mlx"
  local_model: "large-v3"

translation:
  provider: "chatgpt"
  model: "gpt-5.3-codex"

output:
  target_language: "zh"
```

### Best Quality (GPU + Proofreading)

```yaml
whisper:
  provider: "local"
  local_model: "large-v3"
  device: "cuda"

translation:
  provider: "chatgpt"
  model: "gpt-5.3-codex"

output:
  target_language: "zh"

advanced:
  proofread_batch_size: 50
  proofread_context_chars: 20000
```

---

## Environment Variables

API keys can be set via environment variables (config file takes precedence):

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GROQ_API_KEY="gsk_..."
export DEEPSEEK_API_KEY="sk-..."
```

---

## Translation Rules

SubGen uses language-specific translation rules to improve quality.

### Rules Files

Located in `rules/` directory:

```
rules/
├── default.md   # Fallback rules
├── zh.md        # Chinese-specific rules
├── ja.md        # Japanese-specific rules
└── ko.md        # Korean-specific rules
```

### Rule Loading Order

1. Exact match: `zh-TW.md`
2. Language fallback: `zh.md`
3. Default: `default.md`

### Custom Rules

Create your own rules file in Markdown format:

```markdown
# Translation Rules for [Language]

## Style
- Use conversational tone
- Keep sentences concise

## Terminology
- "AI" → "人工智能" (not "AI")
- Character names: keep original
```

### Rules Search Path

1. `./rules/` (project directory)
2. `~/.subgen/rules/` (user directory)

---

## Model-Specific Settings

Proofreading automatically adjusts batch size based on model:

| Model | Batch Size | Context Chars |
|-------|------------|---------------|
| gpt-4o | 50 | 15000 |
| gpt-5.3-codex | 50 | 15000 |
| claude-sonnet-4 | 60 | 20000 |
| deepseek-chat | 40 | 10000 |
| ollama | 15 | 3000 |

Override in config:
```yaml
advanced:
  proofread_batch_size: 30
  proofread_context_chars: 10000
```
