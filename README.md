# 🎬 SubGen - AI Subtitle Generator

> Local AI subtitle generator: Video → Speech Recognition → Translation → Subtitles

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/lgezyxr/subgen/actions/workflows/test.yml/badge.svg)](https://github.com/lgezyxr/subgen/actions/workflows/test.yml)

[中文文档](README.zh.md)

## ✨ Features

- 🎯 **One-click subtitle generation**: Drop in a video, get SRT subtitles
- 🔊 **Speech recognition**: Local Whisper or cloud APIs (OpenAI, Groq)
- 🌍 **Smart translation**: Multiple LLMs (OpenAI, Claude, DeepSeek, Ollama)
- 📝 **Bilingual subtitles**: Optional original + translated dual output
- 🔄 **Language switching**: Easy source/target language switching via CLI
- 📋 **Translation rules**: Language-specific professional translation rules (see `rules/`)
- 🔒 **Privacy-friendly**: Video files never leave your machine
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

# (Optional) Install local Whisper support
pip install faster-whisper
```

### Configuration

Copy the config template and add your API keys:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml`:

```yaml
whisper:
  provider: "openai"  # local | openai | groq
  openai_key: "sk-your-key-here"

translation:
  provider: "openai"
  model: "gpt-4o-mini"
  api_key: "sk-your-key-here"
```

### Usage

```bash
# Basic usage (auto-detect source, translate to Chinese)
python subgen.py video.mp4

# Specify source and target language
python subgen.py video.mp4 --from en --to zh

# Spanish to Japanese
python subgen.py video.mp4 -f es -t ja

# Generate bilingual subtitles
python subgen.py video.mp4 --from en --to zh --bilingual

# Use local Whisper
python subgen.py video.mp4 --whisper-provider local

# View all options
python subgen.py --help
```

## 📖 Documentation

- [Installation Guide](docs/installation.md)
- [Configuration](docs/configuration.md)
- [API Providers Setup](docs/providers.md)
- [Roadmap](docs/roadmap.md)
- [FAQ](docs/faq.md)

## 🔧 Supported Services

### Speech Recognition (Whisper)

| Provider | Cost | Speed | Notes |
|----------|------|-------|-------|
| Local (faster-whisper) | Free | Depends on GPU | Requires 4GB+ VRAM |
| OpenAI Whisper API | $0.006/min | Fast | Most stable |
| Groq | Free tier available | **Very fast** | Recommended |

### Translation (LLM)

| Provider | Recommended Model | Cost | Notes |
|----------|-------------------|------|-------|
| OpenAI | gpt-4o-mini | ~$0.15/M tokens | Best value |
| OpenAI | gpt-4o | ~$2.5/M tokens | Highest quality |
| Claude | claude-3-haiku | ~$0.25/M tokens | Fast |
| DeepSeek | deepseek-chat | ~¥1/M tokens | Chinese optimized |
| Ollama | qwen2.5:14b | Free | Requires local deployment |

## 💡 Examples

### Translate a Movie

```bash
# 2-hour movie using cloud services
python subgen.py "Inception.2010.mkv" --from en --to zh --bilingual

# Estimated cost:
# - Whisper API: 120 min × $0.006 = $0.72
# - GPT-4o-mini: ~$0.05
# - Total: ~$0.77
```

### Batch Processing

```bash
# Process entire folder
python subgen.py ./videos/ --to zh
```

## 🏗️ Project Structure

```
subgen/
├── subgen.py           # Main entry point
├── config.yaml         # User config
├── config.example.yaml # Config template
├── requirements.txt    # Python dependencies
├── rules/              # Translation rules by language
│   ├── zh.md           # Chinese translation rules
│   ├── ja.md           # Japanese translation rules
│   └── default.md      # Default rules for other languages
│
├── src/
│   ├── __init__.py
│   ├── audio.py        # Audio extraction
│   ├── config.py       # Config loading
│   ├── transcribe.py   # Speech recognition
│   ├── translate.py    # Translation
│   └── subtitle.py     # Subtitle generation
│
├── docs/               # Documentation
│   ├── installation.md
│   ├── configuration.md
│   ├── providers.md
│   ├── roadmap.md
│   └── faq.md
│
└── tests/              # Unit tests
    └── ...
```

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE)

## 🙏 Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) - Speech recognition model
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) - Efficient Whisper implementation
- All API providers

---

**⭐ If this project helps you, please give it a Star!**
