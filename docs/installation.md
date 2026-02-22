# 📦 Installation Guide

## System Requirements

- **Python**: 3.10 or higher
- **FFmpeg**: Required for audio/video processing
- **GPU** (optional): NVIDIA GPU with 4GB+ VRAM recommended for local Whisper

---

## Basic Installation

### 1. Install FFmpeg

**macOS**:
```bash
brew install ffmpeg
```

**Ubuntu/Debian**:
```bash
sudo apt update
sudo apt install ffmpeg
```

**Windows**:
1. Download [FFmpeg](https://ffmpeg.org/download.html)
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to system PATH

Verify installation:
```bash
ffmpeg -version
```

### 2. Install SubGen

```bash
# Clone the project
git clone https://github.com/lgezyxr/subgen.git
cd subgen

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure

```bash
# Copy config template
cp config.example.yaml config.yaml

# Edit config and add your API keys
nano config.yaml  # or use your preferred editor
```

---

## Optional: Local Whisper

If you have an NVIDIA GPU, you can run Whisper locally (free and faster):

### 1. Install CUDA

Ensure NVIDIA drivers and CUDA are installed. Check:
```bash
nvidia-smi
```

### 2. Install PyTorch

```bash
# CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# CUDA 12.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### 3. Install faster-whisper

```bash
pip install faster-whisper
```

### 4. Verify

```python
from faster_whisper import WhisperModel
model = WhisperModel("base", device="cuda")
print("Local Whisper is working!")
```

---

## Optional: Local LLM (Ollama)

For fully offline translation:

### 1. Install Ollama

**macOS/Linux**:
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows**:
Download [Ollama installer](https://ollama.com/download)

### 2. Download a Model

```bash
# Recommended: Qwen2.5 (Chinese optimized)
ollama pull qwen2.5:14b

# Or: Llama 3
ollama pull llama3:8b
```

### 3. Start the Service

```bash
ollama serve
```

### 4. Configure SubGen

In `config.yaml`:
```yaml
translation:
  provider: "ollama"
  ollama_host: "http://localhost:11434"
  ollama_model: "qwen2.5:14b"
```

---

## Common Issues

### FFmpeg Not Found

**Error**: `FileNotFoundError: ffmpeg not found`

**Solution**:
1. Confirm FFmpeg is installed: `ffmpeg -version`
2. Confirm FFmpeg is in PATH
3. Or specify full path in config

### CUDA Out of Memory

**Error**: `CUDA out of memory`

**Solution**:
1. Use a smaller model: `local_model: "medium"` or `"small"`
2. Close other GPU-intensive programs
3. Use cloud API instead of local

### API Request Failed

**Error**: `APIError: 401 Unauthorized`

**Solution**:
1. Check if API key is correct
2. Check if API key is valid (not expired, has quota)
3. Check network connection

---

## Next Steps

After installation, see:
- [Configuration](configuration.md) - Detailed config options
- [API Providers Setup](providers.md) - How to get API keys for each service
