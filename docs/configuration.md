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
  # Provider: local | mlx | cpp | openai | groq
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
  
  # whisper.cpp settings (for provider: cpp)
  cpp_model: "large-v3"     # Model name (must be downloaded via subgen install)
  cpp_threads: 4            # CPU thread count
  cpp_gpu_layers: 0         # GPU acceleration layers (0 = auto)
  
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

### Local whisper.cpp (Exe Users)

```yaml
whisper:
  provider: "cpp"
  cpp_model: "large-v3"
  cpp_threads: 4

translation:
  provider: "copilot"

output:
  target_language: "zh"
```

Install the engine and model first: `subgen install whisper --with-model`

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

## Subtitle Styles

SubGen supports customizable subtitle styles for ASS format output. Styles are configured via the `styles` block in `config.yaml`, CLI options, or a combination of both.

### Configuration

```yaml
styles:
  # Start from a preset: default | netflix | fansub | minimal
  preset: "default"

  # Override primary subtitle (translation) style
  primary:
    font: "Noto Sans CJK SC"
    size: 60
    color: "#FFFFFF"
    bold: false
    outline: 3
    outline_color: "#000000"

  # Override secondary subtitle (original) style
  secondary:
    font: "Arial"
    size: 45
    color: "#AAAAAA"
    bold: false
    outline: 2
```

### Preset Inheritance

You can select a preset and override specific properties. Unspecified properties inherit from the preset:

```yaml
styles:
  preset: "netflix"
  primary:
    font: "Noto Sans CJK SC"  # Override font only; size, color, etc. from netflix preset
```

### Color Format

Colors use standard `#RRGGBB` hex format (e.g., `#FFFFFF` for white, `#00FFFF` for cyan). SubGen automatically converts hex colors to ASS format (`&HAABBGGRR`) internally.

Alpha channel is also supported via `#AARRGGBB` format (e.g., `#80000000` for 50% transparent black).

### Preset Details

#### `default`
| Property | Primary | Secondary |
|----------|---------|-----------|
| Font | Arial | Arial |
| Size | 60 | 45 |
| Color | `#FFFFFF` | `#AAAAAA` |
| Bold | No | No |
| Outline | 3.0 | 2.0 |
| Outline Color | `#000000` | `#000000` |
| Shadow | 1.0 | 1.0 |

#### `netflix`
| Property | Primary | Secondary |
|----------|---------|-----------|
| Font | Netflix Sans | Netflix Sans |
| Size | 55 | 40 |
| Color | `#FFFFFF` | `#CCCCCC` |
| Bold | No | No |
| Outline | 2.0 | 1.5 |
| Shadow | 0.0 | 0.0 |

#### `fansub`
| Property | Primary | Secondary |
|----------|---------|-----------|
| Font | 方正准圆_GBK | Arial |
| Size | 65 | 45 |
| Color | `#00FFFF` | `#FFFFFF` |
| Bold | Yes | No |
| Outline | 3.0 | 2.0 |
| Shadow | 1.5 | 1.0 |

#### `minimal`
| Property | Primary | Secondary |
|----------|---------|-----------|
| Font | Helvetica | Helvetica |
| Size | 50 | 38 |
| Color | `#FFFFFF` | `#BBBBBB` |
| Bold | No | No |
| Outline | 1.0 | 0.5 |
| Shadow | 0.0 | 0.0 |

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
