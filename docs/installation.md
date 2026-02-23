# 📦 Installation Guide

## System Requirements

- **Python**: 3.9 or higher
- **FFmpeg**: Required for audio/video processing
- **GPU** (optional): NVIDIA GPU or Apple Silicon for local Whisper

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
```powershell
# Option 1: Using winget (Windows 10+)
winget install FFmpeg

# Option 2: Using Chocolatey
choco install ffmpeg

# Option 3: Manual installation
# 1. Download from https://www.gyan.dev/ffmpeg/builds/
# 2. Extract to C:\ffmpeg
# 3. Add C:\ffmpeg\bin to system PATH
```

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
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Windows CMD:
venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt
```

### 3. Run Setup Wizard

```bash
python subgen.py init
```

This interactive wizard will help you:
- Choose Whisper provider
- Choose LLM provider
- Set up API keys or OAuth login
- Create your `config.yaml`

---

## Platform-Specific Setup

### Apple Silicon (M1/M2/M3 Mac)

MLX Whisper is **highly recommended** for Apple Silicon - it's fast and free:

```bash
pip install mlx-whisper
```

Configure in `config.yaml`:
```yaml
whisper:
  provider: "mlx"
  local_model: "large-v3"
```

### Windows with NVIDIA GPU

```powershell
# Install PyTorch with CUDA
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install faster-whisper
pip install faster-whisper
```

Configure in `config.yaml`:
```yaml
whisper:
  provider: "local"
  device: "cuda"
  local_model: "large-v3"
```

### Windows without GPU

Use cloud APIs (OpenAI Whisper or Groq):

```yaml
whisper:
  provider: "groq"  # Free tier available, very fast
```

Or use CPU-based local Whisper (slower):
```yaml
whisper:
  provider: "local"
  device: "cpu"
  local_model: "base"  # Use smaller model for CPU
```

---

## OAuth Login (No API Key Needed)

If you have ChatGPT Plus/Pro or GitHub Copilot subscription:

### ChatGPT Plus/Pro

```bash
python subgen.py auth login chatgpt
```
A browser window will open. Log in with your OpenAI account.

### GitHub Copilot

```bash
python subgen.py auth login copilot
```
Follow the device code flow to authenticate.

### Check Status

```bash
python subgen.py auth status
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

### 3. Configure SubGen

In `config.yaml`:
```yaml
translation:
  provider: "ollama"
  model: "qwen2.5:14b"
```

---

## Common Issues

### FFmpeg Not Found

**Error**: `FileNotFoundError: ffmpeg not found`

**Solution**:
1. Confirm FFmpeg is installed: `ffmpeg -version`
2. Confirm FFmpeg is in PATH
3. Restart terminal/PowerShell after adding to PATH

### Windows: PowerShell Execution Policy

**Error**: `cannot be loaded because running scripts is disabled`

**Solution**:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

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

After installation:

```bash
# Run the setup wizard
python subgen.py init

# Generate your first subtitle
python subgen.py run video.mp4 -s --to zh
```

See also:
- [Configuration](configuration.md) - Detailed config options
- [API Providers Setup](providers.md) - How to get API keys
