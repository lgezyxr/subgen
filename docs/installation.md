# 📦 Installation Guide

## Requirements

- **Python**: 3.9+
- **FFmpeg**: Required for audio extraction
- **GPU** (optional): NVIDIA GPU or Apple Silicon for local Whisper

---

## Quick Install

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

---

## Install FFmpeg

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

MLX Whisper is **highly recommended** - fast and free:

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

### 🖥️ Windows without GPU

Use cloud APIs:

```yaml
whisper:
  provider: "groq"  # Free tier, very fast
  groq_key: "gsk_..."
```

---

### 🐧 Linux + NVIDIA GPU

```bash
# Install CUDA toolkit first (if not installed)
# Then:
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install faster-whisper
```

---

## OAuth Setup (Recommended)

Use your existing subscriptions - no API keys needed!

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

## Verify Installation

```bash
# Check everything works
python subgen.py init

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
