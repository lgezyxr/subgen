# 🎬 SubGen - AI Subtitle Generator

> Local AI subtitle generator: Video → Speech Recognition → Translation → Subtitles

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/lgezyxr/subgen/actions/workflows/test.yml/badge.svg)](https://github.com/lgezyxr/subgen/actions/workflows/test.yml)

[中文文档](README.zh.md)

## ✨ Features

- 🎯 **One-click generation**: Video in, subtitles out
- 🔊 **Multiple Whisper backends**: Local GPU, MLX (Apple Silicon), OpenAI, Groq
- 🌍 **Multiple LLM providers**: OpenAI, Claude, DeepSeek, Ollama, ChatGPT Plus, Copilot
- 🎯 **Sentence-aware translation**: Groups sentences for context, word-level timing alignment
- 📝 **AI proofreading**: Full-story context review for consistency and accuracy
- 🔒 **OAuth support**: Use ChatGPT Plus or GitHub Copilot subscriptions (no API key needed!)
- 💾 **Smart caching**: Transcription results cached for fast re-runs
- 💰 **Transparent costs**: Use your own API keys

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/lgezyxr/subgen.git
cd subgen
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Setup

```bash
python subgen.py init
```

### Basic Usage

```bash
# Simple translation (English → Chinese)
python subgen.py run video.mp4 --to zh

# Sentence-aware translation (recommended, better quality)
python subgen.py run video.mp4 -s --to zh

# With proofreading pass (best quality)
python subgen.py run video.mp4 -s --proofread --to zh
```

## 📖 Command Reference

### `subgen run` - Generate Subtitles

```bash
python subgen.py run <video> [options]
```

#### Translation Options

| Option | Short | Description |
|--------|-------|-------------|
| `--to LANG` | | Target language (zh, en, ja, etc.) |
| `--from LANG` | | Source language (default: auto-detect) |
| `--sentence-aware` | `-s` | Enable sentence grouping + word-level timing |
| `--proofread` | `-p` | Add AI proofreading pass after translation |
| `--proofread-only` | | Run only proofreading (requires cached translation) |
| `--no-translate` | | Transcription only, no translation |
| `--bilingual` | | Output both original and translated text |

#### Provider Options

| Option | Description |
|--------|-------------|
| `--whisper-provider` | local / mlx / openai / groq |
| `--llm-provider` | openai / claude / deepseek / ollama / chatgpt / copilot |

#### Other Options

| Option | Description |
|--------|-------------|
| `-o, --output` | Output file path |
| `--force-transcribe` | Ignore cache, re-transcribe |
| `--debug` | Show detailed debug logs |
| `--config` | Use custom config file |

### `subgen auth` - OAuth Login

```bash
# Login with ChatGPT Plus/Pro (opens browser)
python subgen.py auth login chatgpt

# Login with GitHub Copilot
python subgen.py auth login copilot

# Check login status
python subgen.py auth status

# Logout
python subgen.py auth logout chatgpt
```

### `subgen init` - Setup Wizard

```bash
python subgen.py init
```

Interactive wizard for configuring providers and API keys.

## 🎯 Translation Modes

### Basic Mode

```bash
python subgen.py run video.mp4 --to zh
```
- Translates each subtitle segment independently
- Fast, but may miss context

### Sentence-Aware Mode (Recommended)

```bash
python subgen.py run video.mp4 -s --to zh
```
- Groups segments into complete sentences
- Uses word-level timestamps for precise timing
- LLM decides natural break points in target language
- **Best for dialogue-heavy content**

### With Proofreading (Best Quality)

```bash
python subgen.py run video.mp4 -s --proofread --to zh
```
- Adds a second AI pass with full story context
- Reviews for consistency in names, terms, tone
- Fixes context-dependent translation errors
- **Best for movies, TV series**

### Proofread-Only Mode

```bash
# First: generate translation
python subgen.py run video.mp4 -s --to zh

# Later: proofread existing translation
python subgen.py run video.mp4 --proofread-only --to zh
```
- Uses cached translation results
- Only runs proofreading pass
- Output: `video_zh.proofread.srt`

## 📂 Output Files

| Command | Output File |
|---------|-------------|
| `--to zh` | `video_zh.srt` |
| `--to zh --proofread-only` | `video_zh.proofread.srt` |
| `--no-translate` | `video.srt` |
| `-o custom.srt` | `custom.srt` |

## 💾 Caching

SubGen caches transcription results to avoid re-processing:

```bash
# Uses cache if available
python subgen.py run video.mp4 -s --to zh

# Force re-transcription
python subgen.py run video.mp4 -s --to zh --force-transcribe
```

Cache file: `.subgen-cache.json` (same directory as video)

## 🔧 Supported Providers

### Speech Recognition (Whisper)

| Provider | Platform | Cost | Notes |
|----------|----------|------|-------|
| `mlx` | Apple Silicon | Free | **Best for M1/M2/M3 Macs** |
| `local` | NVIDIA GPU | Free | Requires CUDA, 4GB+ VRAM |
| `groq` | Any | Free tier | Very fast cloud API |
| `openai` | Any | $0.006/min | Most stable |

### Translation (LLM)

| Provider | Auth | Cost | Notes |
|----------|------|------|-------|
| `chatgpt` | OAuth | Subscription | **Use your ChatGPT Plus!** |
| `copilot` | OAuth | Subscription | Use your GitHub Copilot |
| `deepseek` | API key | ~¥1/M tokens | Great for Chinese |
| `openai` | API key | ~$0.15/M tokens | gpt-4o-mini |
| `claude` | API key | ~$0.25/M tokens | Fast |
| `ollama` | Local | Free | Fully offline |

## 💡 Examples

### Best Quality Setup

```bash
# Apple Silicon
python subgen.py run movie.mkv -s --proofread \
  --whisper-provider mlx \
  --llm-provider chatgpt \
  --to zh

# NVIDIA GPU
python subgen.py run movie.mkv -s --proofread \
  --whisper-provider local \
  --llm-provider chatgpt \
  --to zh
```

### Batch Processing

```bash
# Process all videos in folder
for f in ./videos/*.mp4; do
  python subgen.py run "$f" -s --to zh
done
```

### Debug Mode

```bash
# Show detailed logs for troubleshooting
python subgen.py run video.mp4 -s --to zh --debug
```

## 📖 Documentation

- [Installation Guide](docs/installation.md) - Platform-specific setup
- [Configuration](docs/configuration.md) - All config options
- [API Providers](docs/providers.md) - How to get API keys
- [FAQ](docs/faq.md) - Common questions

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

## 📄 License

MIT License - see [LICENSE](LICENSE)

---

**⭐ Star this project if it helps you!**
