# 🔑 API Providers Setup

How to set up each provider for SubGen.

---

## 🔐 OAuth Providers (No API Key!)

### ChatGPT Plus/Pro (Recommended)

**Cost**: Your existing subscription  
**Quality**: ⭐⭐⭐⭐⭐ (gpt-5.3-codex has reasoning capabilities)

If you have a ChatGPT Plus ($20/mo) or Pro subscription, you can use it directly!

**Setup**:
```bash
python subgen.py auth login chatgpt
```

A browser window opens → Log in with your OpenAI account → Done!

**Config**:
```yaml
translation:
  provider: "chatgpt"
  model: "gpt-5.3-codex"  # Best model with reasoning
```

**Available Models**:
| Model | Description |
|-------|-------------|
| `gpt-5.3-codex` | Best quality, has reasoning (default) |
| `gpt-5.2-codex` | Previous version |
| `gpt-5.1-codex-mini` | Faster, less capable |

---

### GitHub Copilot

**Cost**: Your existing subscription  
**Quality**: ⭐⭐⭐⭐

If you have GitHub Copilot Individual or Business subscription:

**Setup**:
```bash
python subgen.py auth login copilot
```

Follow the device code flow to authenticate.

**Config**:
```yaml
translation:
  provider: "copilot"
  model: "gpt-4o-mini"
```

---

## 🔊 Speech Recognition (Whisper)

### Local (faster-whisper)

**Cost**: Free  
**Requirements**: NVIDIA GPU with 4GB+ VRAM, CUDA installed

```bash
pip install faster-whisper
```

**Config**:
```yaml
whisper:
  provider: "local"
  device: "cuda"
  local_model: "large-v3"
```

**VRAM Requirements**:
| Model | VRAM | Accuracy |
|-------|------|----------|
| tiny | ~1GB | ★★☆☆☆ |
| base | ~1GB | ★★★☆☆ |
| small | ~2GB | ★★★★☆ |
| medium | ~5GB | ★★★★☆ |
| large-v3 | ~10GB | ★★★★★ |

**Older GPUs (GTX 10xx series)**:
```yaml
whisper:
  provider: "local"
  device: "cuda"
  compute_type: "float32"  # Required for Pascal GPUs
```

---

### MLX (Apple Silicon)

**Cost**: Free  
**Requirements**: M1/M2/M3 Mac

```bash
pip install mlx-whisper
```

**Config**:
```yaml
whisper:
  provider: "mlx"
  local_model: "large-v3"
```

**Recommended for all Apple Silicon Macs** - native performance, no cloud needed.

---

### Groq API

**Cost**: Free tier available, then pay-as-you-go  
**Speed**: ⭐⭐⭐⭐⭐ (extremely fast)

1. Visit [Groq Console](https://console.groq.com/)
2. Sign up (Google login supported)
3. Go to [API Keys](https://console.groq.com/keys)
4. Create API Key (starts with `gsk_`)

**Config**:
```yaml
whisper:
  provider: "groq"
  groq_key: "gsk_..."
```

---

### OpenAI Whisper API

**Cost**: $0.006/minute (~$0.72 for 2-hour movie)  
**Stability**: ⭐⭐⭐⭐⭐

1. Visit [OpenAI Platform](https://platform.openai.com/)
2. Go to [API Keys](https://platform.openai.com/api-keys)
3. Create new secret key (starts with `sk-`)

**Config**:
```yaml
whisper:
  provider: "openai"
  openai_key: "sk-..."
```

---

## 🌍 Translation (LLM)

### DeepSeek

**Cost**: ~¥1/M tokens (very cheap)  
**Best for**: Chinese translation

1. Visit [DeepSeek Platform](https://platform.deepseek.com/)
2. Sign up and get API key

**Config**:
```yaml
translation:
  provider: "deepseek"
  model: "deepseek-chat"
  api_key: "sk-..."
```

---

### OpenAI API

**Cost**: gpt-4o-mini ~$0.15/M tokens, gpt-4o ~$2.5/M tokens

Same API key as Whisper.

**Config**:
```yaml
translation:
  provider: "openai"
  model: "gpt-4o-mini"  # or "gpt-4o" for best quality
  api_key: "sk-..."
```

---

### Anthropic Claude

**Cost**: claude-3-haiku ~$0.25/M tokens, claude-3-sonnet ~$3/M tokens

1. Visit [Anthropic Console](https://console.anthropic.com/)
2. Go to [API Keys](https://console.anthropic.com/settings/keys)
3. Create new key (starts with `sk-ant-`)

**Config**:
```yaml
translation:
  provider: "claude"
  model: "claude-sonnet-4-20250514"
  api_key: "sk-ant-..."
```

---

### Ollama (Local LLM)

**Cost**: Free  
**Requirements**: 8-16GB+ VRAM

1. Install Ollama:
   ```bash
   # macOS/Linux
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Windows: download from ollama.com
   ```

2. Download a model:
   ```bash
   ollama pull qwen2.5:14b   # Chinese optimized
   ollama pull llama3:8b     # General purpose
   ```

**Config**:
```yaml
translation:
  provider: "ollama"
  model: "qwen2.5:14b"
  ollama_url: "http://localhost:11434"
```

---

## 💰 Cost Comparison

For a 2-hour movie:

| Setup | Whisper | Translation | Total |
|-------|---------|-------------|-------|
| Local + ChatGPT | Free | Subscription | **$0** |
| Groq + ChatGPT | Free | Subscription | **$0** |
| Local + DeepSeek | Free | ~¥0.1 | **~¥0.1** |
| Local + Ollama | Free | Free | **$0** |
| OpenAI + GPT-4o-mini | $0.72 | ~$0.05 | **~$0.77** |

---

## 🏆 Recommended Setups

### Best Quality
```yaml
whisper:
  provider: "local"  # or "mlx"
translation:
  provider: "chatgpt"
  model: "gpt-5.3-codex"
```

### Best Value
```yaml
whisper:
  provider: "groq"
translation:
  provider: "deepseek"
```

### Fully Offline
```yaml
whisper:
  provider: "local"
translation:
  provider: "ollama"
  model: "qwen2.5:14b"
```

### Apple Silicon
```yaml
whisper:
  provider: "mlx"
translation:
  provider: "chatgpt"
```
