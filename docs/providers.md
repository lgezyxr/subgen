# 🔑 API 提供商设置

如何获取各服务的 API Key。

---

## 语音识别 (Whisper)

### OpenAI Whisper API

**推荐度**: ⭐⭐⭐⭐⭐ (最稳定)

**价格**: $0.006/分钟 (2小时电影 ≈ $0.72)

**获取步骤**:
1. 访问 [OpenAI Platform](https://platform.openai.com/)
2. 注册/登录账号
3. 进入 [API Keys](https://platform.openai.com/api-keys) 页面
4. 点击 "Create new secret key"
5. 复制 Key (以 `sk-` 开头)

**配置**:
```yaml
whisper:
  provider: "openai"
  openai_key: "sk-..."
```

---

### Groq API

**推荐度**: ⭐⭐⭐⭐⭐ (免费额度 + 超快)

**价格**: 有免费额度，超出后按量计费

**获取步骤**:
1. 访问 [Groq Console](https://console.groq.com/)
2. 注册账号 (支持 Google 登录)
3. 进入 [API Keys](https://console.groq.com/keys) 页面
4. 点击 "Create API Key"
5. 复制 Key (以 `gsk_` 开头)

**配置**:
```yaml
whisper:
  provider: "groq"
  groq_key: "gsk_..."
```

**特点**:
- 速度极快（2小时电影几十秒完成）
- 有免费额度，适合尝试
- 使用 whisper-large-v3 模型

---

### 本地 Whisper (faster-whisper)

**推荐度**: ⭐⭐⭐⭐ (免费，需要 GPU)

**价格**: 免费

**要求**:
- NVIDIA GPU (4GB+ 显存)
- CUDA 安装

**安装**:
```bash
pip install faster-whisper torch
```

**配置**:
```yaml
whisper:
  provider: "local"
  local_model: "large-v3"  # 或 medium/small
  device: "cuda"
```

**显存需求**:

| 模型 | 显存 | 效果 |
|------|------|------|
| tiny | ~1GB | 凑合 |
| base | ~1GB | 一般 |
| small | ~2GB | 够用 |
| medium | ~5GB | 不错 |
| large-v3 | ~10GB | 最好 |

---

## 翻译 (LLM)

### OpenAI GPT

**推荐度**: ⭐⭐⭐⭐⭐

**价格**:
- gpt-4o-mini: ~$0.15/百万输入 token (推荐)
- gpt-4o: ~$2.5/百万输入 token (最佳质量)

**获取步骤**: 同 OpenAI Whisper API

**配置**:
```yaml
translation:
  provider: "openai"
  model: "gpt-4o-mini"  # 或 gpt-4o
  api_key: "sk-..."
```

---

### Anthropic Claude

**推荐度**: ⭐⭐⭐⭐

**价格**:
- claude-3-haiku: ~$0.25/百万输入 token
- claude-3-sonnet: ~$3/百万输入 token

**获取步骤**:
1. 访问 [Anthropic Console](https://console.anthropic.com/)
2. 注册账号
3. 进入 [API Keys](https://console.anthropic.com/settings/keys) 页面
4. 创建新 Key

**配置**:
```yaml
translation:
  provider: "claude"
  model: "claude-3-haiku-20240307"
  api_key: "sk-ant-..."
```

---

### DeepSeek

**推荐度**: ⭐⭐⭐⭐⭐ (中文翻译首选)

**价格**: ~¥1/百万 token (超便宜)

**获取步骤**:
1. 访问 [DeepSeek Platform](https://platform.deepseek.com/)
2. 注册账号
3. 进入 API Keys 页面
4. 创建新 Key

**配置**:
```yaml
translation:
  provider: "deepseek"
  model: "deepseek-chat"
  api_key: "sk-..."
```

**特点**:
- 中文效果很好
- 价格极低
- 兼容 OpenAI 接口

---

### Ollama (本地 LLM)

**推荐度**: ⭐⭐⭐⭐ (完全免费)

**价格**: 免费

**要求**:
- 16GB+ 显存 (14B 模型)
- 8GB+ 显存 (7B 模型)

**安装**:
```bash
# macOS/Linux
curl -fsSL https://ollama.com/install.sh | sh

# 下载模型
ollama pull qwen2.5:14b
```

**配置**:
```yaml
translation:
  provider: "ollama"
  ollama_host: "http://localhost:11434"
  ollama_model: "qwen2.5:14b"
```

**推荐模型**:

| 模型 | 显存 | 中文效果 |
|------|------|----------|
| qwen2.5:7b | ~8GB | 好 |
| qwen2.5:14b | ~16GB | 很好 |
| llama3:8b | ~8GB | 一般 |

---

## 费用对比

翻译一部 2 小时电影：

| 方案 | Whisper 费用 | 翻译费用 | 总计 |
|------|--------------|----------|------|
| OpenAI + GPT-4o-mini | $0.72 | ~$0.05 | **~$0.77** |
| Groq + GPT-4o-mini | 免费额度 | ~$0.05 | **~$0.05** |
| 本地 + DeepSeek | 免费 | ~¥0.1 | **~¥0.1** |
| 本地 + Ollama | 免费 | 免费 | **免费** |

---

## 推荐组合

| 场景 | Whisper | 翻译 | 理由 |
|------|---------|------|------|
| 新手尝试 | Groq | GPT-4o-mini | 免费 + 便宜 |
| 日常使用 | 本地 | GPT-4o-mini | 低成本 |
| 追求质量 | 本地 | GPT-4o | 翻译最准 |
| 完全免费 | 本地 | Ollama | 零成本 |
| 中文优化 | 本地 | DeepSeek | 中文效果好 |
