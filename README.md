# 🎬 SubGen - AI Subtitle Generator

> Local AI subtitle generator: Video → Speech Recognition → Translation → Subtitles

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/lgezyxr/subgen/actions/workflows/test.yml/badge.svg)](https://github.com/lgezyxr/subgen/actions/workflows/test.yml)

[中文文档](README.zh.md)

## ✨ Features

- 🎯 **One-click subtitle generation**: Drop in a video, get SRT subtitles
- 🔊 **Speech recognition**: Local Whisper, MLX (Apple Silicon), or cloud APIs
- 🌍 **Smart translation**: Multiple LLMs (OpenAI, Claude, DeepSeek, Ollama, ChatGPT Plus, Copilot)
- 🎯 **Sentence-aware translation**: Groups sentences for better context and timing
- 📝 **Bilingual subtitles**: Optional original + translated dual output
- 🔒 **OAuth support**: Use ChatGPT Plus or GitHub Copilot subscriptions (no API key needed)
- 💰 **Cost transparent**: Use your own API keys, costs are predictable

## 🚀 Quick Start

### Installation

```bash
# Clone the project
git clone https://github.com/lgezyxr/subgen.git
cd subgen

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Setup (Interactive Wizard)

```bash
python subgen.py init
```

This will guide you through:
- Choosing Whisper provider (local/mlx/openai/groq)
- Choosing LLM provider (openai/claude/deepseek/ollama/chatgpt/copilot)
- Setting up API keys or OAuth login

### Usage

```bash
# Basic usage (auto-detect source, translate to Chinese)
python subgen.py run video.mp4 --to zh

# Specify source and target language
python subgen.py run video.mp4 --from en --to zh

# Use sentence-aware translation (recommended for better quality)
python subgen.py run video.mp4 -s --to zh

# Transcription only (no translation)
python subgen.py run video.mp4 --no-translate

# Generate bilingual subtitles
python subgen.py run video.mp4 --from en --to zh --bilingual

# Apple Silicon: use MLX Whisper
python subgen.py run video.mp4 --whisper-provider mlx --to zh

# Use ChatGPT Plus subscription
python subgen.py auth login chatgpt
python subgen.py run video.mp4 --llm-provider chatgpt --to zh

# View all options
python subgen.py run --help
```

## 📖 Documentation

- [Installation Guide](docs/installation.md)
- [Configuration](docs/configuration.md)
- [API Providers Setup](docs/providers.md)
- [Roadmap](docs/roadmap.md)
- [FAQ](docs/faq.md)

## 🔧 Supported Services

### Speech Recognition (Whisper)

| Provider | Platform | Cost | Notes |
|----------|----------|------|-------|
| MLX | Apple Silicon | Free | **Recommended for M1/M2/M3 Macs** |
| Local (faster-whisper) | NVIDIA GPU | Free | Requires 4GB+ VRAM |
| OpenAI Whisper API | Any | $0.006/min | Most stable |
| Groq | Any | Free tier | Very fast |

### Translation (LLM)

| Provider | Auth Method | Cost | Notes |
|----------|-------------|------|-------|
| ChatGPT Plus | OAuth login | Subscription | **Use your existing subscription!** |
| GitHub Copilot | OAuth login | Subscription | Use your existing subscription |
| DeepSeek | API key | ~¥1/M tokens | Chinese optimized, free credits |
| OpenAI | API key | ~$0.15/M tokens | gpt-4o-mini recommended |
| Claude | API key | ~$0.25/M tokens | Fast |
| Ollama | Local | Free | Fully offline |

## 🔐 OAuth Login (No API Key Needed)

If you have ChatGPT Plus/Pro or GitHub Copilot subscription:

```bash
# Login with ChatGPT (browser will open)
python subgen.py auth login chatgpt

# Login with GitHub Copilot
python subgen.py auth login copilot

# Check login status
python subgen.py auth status
```

## 💡 Examples

### Best Quality (Sentence-Aware + Word-Aligned)

```bash
# -s enables sentence-aware translation with word-level timing
python subgen.py run movie.mp4 -s --whisper-provider mlx --to zh
```

This mode:
1. Groups split sentences for coherent translation
2. Uses word-level timestamps for precise subtitle timing
3. Lets LLM decide natural Chinese break points

### Batch Processing

```bash
# Process entire folder
for f in ./videos/*.mp4; do
  python subgen.py run "$f" -s --to zh
done
```

## 🏗️ CLI Structure

```bash
subgen.py
├── run <video>     # Generate subtitles
├── init            # Setup wizard
└── auth
    ├── login       # OAuth login (chatgpt/copilot)
    ├── logout      # Logout
    └── status      # Check auth status
```

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE)

---

**⭐ If this project helps you, please give it a Star!**
