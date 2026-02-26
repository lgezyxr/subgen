# 📦 Installation Guide

[中文版](zh/installation.md)

## Requirements

- **FFmpeg**: Required for audio extraction (auto-downloaded by `subgen init`)
- **GPU** (optional): NVIDIA GPU or Apple Silicon for local Whisper

---

## Option 1: Download Executable (Recommended)

Download the latest release for your platform from [GitHub Releases](https://github.com/lgezyxr/subgen/releases):

| Platform | File |
|----------|------|
| Windows | `subgen-windows-x64.exe` |
| macOS (Intel) | `subgen-macos-x64` |
| macOS (Apple Silicon) | `subgen-macos-arm64` |
| Linux | `subgen-linux-x64` |

```bash
# macOS / Linux: add execute permission
chmod +x subgen-macos-arm64

# Run setup wizard (downloads FFmpeg, whisper.cpp, models as needed)
./subgen init

# Start generating subtitles
./subgen run movie.mp4 --to zh
```

No Python, pip, or virtual environment needed.

---

## Option 2: Install from Source

```bash
# Clone
git clone https://github.com/lgezyxr/subgen.git
cd subgen

# Create virtual environment
python -m venv venv

# Activate
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate         # Windows CMD
.\venv\Scripts\Activate.ps1   # Windows PowerShell

# Install dependencies
pip install -r requirements.txt

# Run setup wizard
python subgen.py init
```

### Python Version

Python 3.9 or higher is required.

---

## Setup Wizard: `subgen init`

The `init` command is a one-stop setup wizard that configures everything you need:

1. **Hardware detection** — Detects GPU, CUDA, Apple Silicon
2. **Speech recognition** — Choose cloud (Groq, free) or local (whisper.cpp with auto-download)
3. **Translation** — Choose LLM provider and authenticate (OAuth for Copilot/ChatGPT)
4. **FFmpeg** — Auto-downloads if not found in PATH
5. **Defaults** — Language, format, style preset

After `init` completes, you're ready to `subgen run`.

You can re-run `subgen init` at any time to reconfigure.

---

## Install FFmpeg

FFmpeg can be auto-downloaded by `subgen init`. To install manually:

### macOS
```bash
brew install ffmpeg
```

### Ubuntu/Debian
```bash
sudo apt update && sudo apt install ffmpeg
```

### Windows
```powershell
# Option 1: winget (Windows 10+)
winget install FFmpeg

# Option 2: Chocolatey
choco install ffmpeg

# Option 3: Manual
# Download from https://www.gyan.dev/ffmpeg/builds/
# Extract to C:\ffmpeg
# Add C:\ffmpeg\bin to PATH
```

Verify:
```bash
ffmpeg -version
```

---

## Platform-Specific Setup

### 🍎 Apple Silicon (M1/M2/M3)

**Exe users**: `subgen init` will offer whisper.cpp with Metal acceleration.

**Source users**: MLX Whisper is highly recommended — fast and free:

```bash
pip install mlx-whisper
```

```yaml
whisper:
  provider: "mlx"
  local_model: "large-v3"
```

---

### 🖥️ Windows + NVIDIA GPU

**Exe users**: `subgen init` will offer whisper.cpp with CUDA acceleration.

**Source users**:

```powershell
# Install PyTorch with CUDA
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install faster-whisper
pip install faster-whisper
```

```yaml
whisper:
  provider: "local"
  device: "cuda"
  local_model: "large-v3"
```

**Older GPUs (GTX 10xx/Pascal)**: Add `compute_type: "float32"`

---

### 🖥️ Without GPU

Use cloud APIs:

```yaml
whisper:
  provider: "groq"  # Free tier, very fast
  groq_key: "gsk_..."
```

---

### 🐧 Linux + NVIDIA GPU

**Source users**:

```bash
# Install CUDA toolkit first (if not installed)
# Then:
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install faster-whisper
```

---

## OAuth Setup (Recommended)

Use your existing subscriptions — no API keys needed!

### ChatGPT Plus/Pro

```bash
python subgen.py auth login chatgpt
```

Browser opens → Log in → Done!

### GitHub Copilot

```bash
python subgen.py auth login copilot
```

Follow device code flow.

### Check Status

```bash
python subgen.py auth status
```

---

## Optional: Ollama (Offline LLM)

For fully offline translation:

### 1. Install Ollama

```bash
# macOS/Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows: download from ollama.com
```

### 2. Download Model

```bash
ollama pull qwen2.5:14b   # Best for Chinese (16GB VRAM)
ollama pull qwen2.5:7b    # Smaller (8GB VRAM)
ollama pull llama3:8b     # General purpose
```

### 3. Configure

```yaml
translation:
  provider: "ollama"
  model: "qwen2.5:14b"
```

---

## Environment Check: `subgen doctor`

Run `subgen doctor` to verify your setup:

```bash
python subgen.py doctor
```

This checks config, FFmpeg, Whisper backend, LLM, GPU, and disk usage, showing what's ready and what needs fixing.

---

## Verify Installation

```bash
# Check everything works
python subgen.py doctor

# Test with a short video
python subgen.py run test.mp4 -s --to zh --debug
```

---

## Troubleshooting

### PowerShell Execution Policy (Windows)

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### CUDA Not Found

1. Verify CUDA installation: `nvcc --version`
2. Verify PyTorch sees GPU: `python -c "import torch; print(torch.cuda.is_available())"`
3. Install correct PyTorch version for your CUDA

### Package Conflicts (Anaconda)

If using Anaconda, create a conda environment instead:

```bash
conda create -n subgen python=3.11
conda activate subgen
pip install -r requirements.txt
```

---

## Next Steps

1. Run `python subgen.py init` to configure
2. Try: `python subgen.py run video.mp4 -s --to zh`
3. See [Configuration](configuration.md) for all options
