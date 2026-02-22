# 🔑 API 提供商设置

本指南帮助你获取和配置各服务的 API Key。

---

## 语音识别 (Whisper)

### OpenAI Whisper API

**获取 API Key**:
1. 访问 [OpenAI Platform](https://platform.openai.com/)
2. 注册/登录账号
3. 进入 [API Keys](https://platform.openai.com/api-keys)
4. 点击 "Create new secret key"
5. 复制 Key（以 `sk-` 开头）

**配置**:
```yaml
whisper:
  provider: "openai"
  openai_key: "sk-your-key-here"
```

**价格**: $0.006/分钟（约 ¥0.04/分钟）

---

### Groq API（推荐！）

Groq 提供**免费额度**且速度极快（比 OpenAI 快 10 倍以上）。

**获取 API Key**:
1. 访问 [Groq Console](https://console.groq.com/)
2. 注册/登录（支持 Google 账号）
3. 进入 [API Keys](https://console.groq.com/keys)
4. 创建新 Key

**配置**:
```yaml
whisper:
  provider: "groq"
  groq_key: "gsk_your-key-here"
```

**价格**: 有大量免费额度，超出后约 $0.005/分钟

---

### 本地 Whisper（免费）

无需 API Key，在本地 GPU 运行。

**要求**:
- NVIDIA GPU (4GB+ 显存)
- 安装 `faster-whisper`

**配置**:
```yaml
whisper:
  provider: "local"
  local_model: "large-v3"
  device: "cuda"
```

---

## 翻译 (LLM)

### OpenAI GPT

**获取 API Key**: 同上（OpenAI Whisper）

**配置**:
```yaml
translation:
  provider: "openai"
  model: "gpt-4o-mini"  # 或 "gpt-4o"
  api_key: "sk-your-key-here"
```

**推荐模型**:
| 模型 | 价格 | 适用场景 |
|------|------|----------|
| gpt-4o-mini | $0.15/1M tokens | 日常使用，性价比高 |
| gpt-4o | $2.5/1M tokens | 高质量要求 |

---

### Anthropic Claude

**获取 API Key**:
1. 访问 [Anthropic Console](https://console.anthropic.com/)
2. 注册账号（需要邀请码或等待）
3. 进入 [API Keys](https://console.anthropic.com/settings/keys)
4. 创建 Key

**配置**:
```yaml
translation:
  provider: "claude"
  model: "claude-3-haiku-20240307"
  api_key: "sk-ant-your-key-here"
```

**推荐模型**:
| 模型 | 价格 | 特点 |
|------|------|------|
| claude-3-haiku | $0.25/1M | 快速，便宜 |
| claude-3-sonnet | $3/1M | 平衡 |
| claude-3-opus | $15/1M | 最强 |

---

### DeepSeek（中文优化）

**获取 API Key**:
1. 访问 [DeepSeek Platform](https://platform.deepseek.com/)
2. 注册账号
3. 进入 API Keys 页面
4. 创建 Key

**配置**:
```yaml
translation:
  provider: "deepseek"
  model: "deepseek-chat"
  api_key: "sk-your-key-here"
```

**价格**: ¥1/百万 tokens（非常便宜）

**特点**: 中文翻译质量很好

---

### Ollama（本地免费）

无需 API Key，完全本地运行。

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
| 模型 | 显存需求 | 特点 |
|------|----------|------|
| qwen2.5:7b | ~8GB | 快速 |
| qwen2.5:14b | ~16GB | 质量好 |
| llama3:8b | ~8GB | 通用 |

---

### GitHub Copilot（如果你有订阅）

如果你已经订阅了 GitHub Copilot，可以复用它的额度。

**配置**:
```yaml
translation:
  provider: "openai"
  model: "gpt-4o"
  api_key: "your-copilot-token"
  base_url: "https://api.individual.githubcopilot.com"
```

注意：需要先通过 OAuth 获取 token，参考 OpenClaw 的实现。

---

## 费用估算

**翻译一部 2 小时电影**：

| 方案 | 成本 |
|------|------|
| Groq + GPT-4o-mini | ~¥0.5 |
| OpenAI Whisper + GPT-4o-mini | ~¥5.5 |
| OpenAI Whisper + GPT-4o | ~¥11 |
| 全本地 | ¥0 |

---

## 安全建议

1. **不要提交 API Key 到 Git**
   ```bash
   # .gitignore
   config.yaml
   ```

2. **使用环境变量**
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

3. **设置使用限额**
   - OpenAI: [Usage limits](https://platform.openai.com/account/limits)
   - 其他平台类似

4. **定期轮换 Key**
