# 🔑 API Providers Setup

How to get API keys for each service.

---

## Speech Recognition (Whisper)

### OpenAI Whisper API

**Recommendation**: ⭐⭐⭐⭐⭐ (Most stable)

**Price**: $0.006/minute (2-hour movie ≈ $0.72)

**Steps**:
1. Visit [OpenAI Platform](https://platform.openai.com/)
2. Sign up / Log in
3. Go to [API Keys](https://platform.openai.com/api-keys) page
4. Click "Create new secret key"
5. Copy the key (starts with `sk-`)

**Configuration**:
```yaml
whisper:
  provider: "openai"
  openai_key: "sk-..."
```

---

### Groq API

**Recommendation**: ⭐⭐⭐⭐⭐ (Free tier + super fast)

**Price**: Free tier available, pay-as-you-go after

**Steps**:
1. Visit [Groq Console](https://console.groq.com/)
2. Sign up (Google login supported)
3. Go to [API Keys](https://console.groq.com/keys) page
4. Click "Create API Key"
5. Copy the key (starts with `gsk_`)

**Configuration**:
```yaml
whisper:
  provider: "groq"
  groq_key: "gsk_..."
```

**Features**:
- Extremely fast (2-hour movie in tens of seconds)
- Free tier available, great for trying out
- Uses whisper-large-v3 model

---

### Local Whisper (faster-whisper)

**Recommendation**: ⭐⭐⭐⭐ (Free, requires GPU)

**Price**: Free

**Requirements**:
- NVIDIA GPU (4GB+ VRAM)
- CUDA installed

**Installation**:
```bash
pip install faster-whisper torch
```

**Configuration**:
```yaml
whisper:
  provider: "local"
  local_model: "large-v3"  # or medium/small
  device: "cuda"
```

**VRAM Requirements**:

| Model | VRAM | Quality |
|-------|------|---------|
| tiny | ~1GB | Basic |
| base | ~1GB | Fair |
| small | ~2GB | Good |
| medium | ~5GB | Better |
| large-v3 | ~10GB | Best |

---

## Translation (LLM)

### OpenAI GPT

**Recommendation**: ⭐⭐⭐⭐⭐

**Price**:
- gpt-4o-mini: ~$0.15/M input tokens (recommended)
- gpt-4o: ~$2.5/M input tokens (best quality)

**Steps**: Same as OpenAI Whisper API

**Configuration**:
```yaml
translation:
  provider: "openai"
  model: "gpt-4o-mini"  # or gpt-4o
  api_key: "sk-..."
```

---

### Anthropic Claude

**Recommendation**: ⭐⭐⭐⭐

**Price**:
- claude-3-haiku: ~$0.25/M input tokens
- claude-3-sonnet: ~$3/M input tokens

**Steps**:
1. Visit [Anthropic Console](https://console.anthropic.com/)
2. Sign up
3. Go to [API Keys](https://console.anthropic.com/settings/keys) page
4. Create new key

**Configuration**:
```yaml
translation:
  provider: "claude"
  model: "claude-3-haiku-20240307"
  api_key: "sk-ant-..."
```

---

### DeepSeek

**Recommendation**: ⭐⭐⭐⭐⭐ (Best for Chinese translation)

**Price**: ~¥1/M tokens (very cheap)

**Steps**:
1. Visit [DeepSeek Platform](https://platform.deepseek.com/)
2. Sign up
3. Go to API Keys page
4. Create new key

**Configuration**:
```yaml
translation:
  provider: "deepseek"
  model: "deepseek-chat"
  api_key: "sk-..."
```

**Features**:
- Excellent Chinese output
- Very low cost
- OpenAI-compatible API

---

### Ollama (Local LLM)

**Recommendation**: ⭐⭐⭐⭐ (Completely free)

**Price**: Free

**Requirements**:
- 16GB+ VRAM (14B model)
- 8GB+ VRAM (7B model)

**Installation**:
```bash
# macOS/Linux
curl -fsSL https://ollama.com/install.sh | sh

# Download model
ollama pull qwen2.5:14b
```

**Configuration**:
```yaml
translation:
  provider: "ollama"
  ollama_host: "http://localhost:11434"
  ollama_model: "qwen2.5:14b"
```

**Recommended Models**:

| Model | VRAM | Chinese Quality |
|-------|------|-----------------|
| qwen2.5:7b | ~8GB | Good |
| qwen2.5:14b | ~16GB | Very good |
| llama3:8b | ~8GB | Fair |

---

## Cost Comparison

Translating a 2-hour movie:

| Setup | Whisper Cost | Translation Cost | Total |
|-------|--------------|------------------|-------|
| OpenAI + GPT-4o-mini | $0.72 | ~$0.05 | **~$0.77** |
| Groq + GPT-4o-mini | Free tier | ~$0.05 | **~$0.05** |
| Local + DeepSeek | Free | ~¥0.1 | **~¥0.1** |
| Local + Ollama | Free | Free | **Free** |

---

## Recommended Combinations

| Use Case | Whisper | Translation | Reason |
|----------|---------|-------------|--------|
| First-time user | Groq | GPT-4o-mini | Free + cheap |
| Daily use | Local | GPT-4o-mini | Low cost |
| Quality focus | Local | GPT-4o | Best translation |
| Completely free | Local | Ollama | Zero cost |
| Chinese optimized | Local | DeepSeek | Great Chinese output |
