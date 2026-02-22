# ⚙️ 配置说明

SubGen 使用 YAML 配置文件。首次使用请复制 `config.example.yaml` 为 `config.yaml`。

---

## 配置文件结构

```yaml
# config.yaml

whisper:        # 语音识别配置
translation:    # 翻译配置
output:         # 输出配置
advanced:       # 高级配置
```

---

## 语音识别配置 (whisper)

```yaml
whisper:
  # 提供商选择
  provider: "openai"  # local | openai | groq
  
  # 本地模式配置
  local_model: "large-v3"  # tiny | base | small | medium | large-v3
  device: "cuda"           # cuda | cpu
  
  # API Keys
  openai_key: "sk-..."     # OpenAI API Key
  groq_key: "gsk_..."      # Groq API Key
```

### 提供商对比

| 提供商 | 价格 | 速度 | 质量 | 备注 |
|--------|------|------|------|------|
| `local` | 免费 | 依赖 GPU | 最好 | 需要显卡 |
| `openai` | $0.006/分钟 | 快 | 很好 | 最稳定 |
| `groq` | 有免费额度 | **极快** | 很好 | 推荐尝试 |

### 本地模型选择

| 模型 | 显存需求 | 质量 | 速度 |
|------|----------|------|------|
| `tiny` | ~1GB | ⭐ | 最快 |
| `base` | ~1GB | ⭐⭐ | 很快 |
| `small` | ~2GB | ⭐⭐⭐ | 快 |
| `medium` | ~5GB | ⭐⭐⭐⭐ | 中等 |
| `large-v3` | ~10GB | ⭐⭐⭐⭐⭐ | 较慢 |

---

## 翻译配置 (translation)

```yaml
translation:
  # 提供商选择
  provider: "openai"  # openai | claude | deepseek | ollama
  
  # 模型选择
  model: "gpt-4o-mini"
  
  # API 配置
  api_key: "sk-..."
  base_url: ""  # 自定义 API 地址（可选）
  
  # Ollama 配置（本地 LLM）
  ollama_host: "http://localhost:11434"
  ollama_model: "qwen2.5:14b"
```

### 提供商对比

| 提供商 | 推荐模型 | 价格 | 质量 | 备注 |
|--------|----------|------|------|------|
| `openai` | gpt-4o-mini | $0.15/1M | ⭐⭐⭐⭐ | 性价比高 |
| `openai` | gpt-4o | $2.5/1M | ⭐⭐⭐⭐⭐ | 质量最好 |
| `claude` | claude-3-haiku | $0.25/1M | ⭐⭐⭐⭐ | 快速 |
| `deepseek` | deepseek-chat | ¥1/1M | ⭐⭐⭐⭐ | 中文优化 |
| `ollama` | qwen2.5:14b | 免费 | ⭐⭐⭐ | 本地运行 |

---

## 输出配置 (output)

```yaml
output:
  # 字幕格式
  format: "srt"  # srt | ass | vtt
  
  # 目标语言
  target_language: "zh"  # zh | en | ja | ko | ...
  
  # 双语字幕
  bilingual: false
  
  # 每行最大字符数
  max_chars_per_line: 42
  
  # 是否烧录进视频
  embed_in_video: false
```

### 字幕格式说明

| 格式 | 特点 | 适用场景 |
|------|------|----------|
| `srt` | 最通用，纯文本 | 大多数播放器 |
| `ass` | 支持样式、特效 | 高级排版需求 |
| `vtt` | Web 标准 | 网页视频 |

### 语言代码

| 代码 | 语言 |
|------|------|
| `zh` | 中文 |
| `en` | English |
| `ja` | 日本語 |
| `ko` | 한국어 |
| `fr` | Français |
| `de` | Deutsch |
| `es` | Español |

---

## 高级配置 (advanced)

```yaml
advanced:
  # 翻译批次大小（一次翻译多少条）
  translation_batch_size: 20
  
  # 翻译上下文（提供多少条前文）
  translation_context_size: 5
  
  # 临时文件目录
  temp_dir: "./temp"
  
  # 保留临时文件（调试用）
  keep_temp_files: false
  
  # 日志级别
  log_level: "INFO"  # DEBUG | INFO | WARNING | ERROR
```

### 翻译批次说明

- **batch_size 大**：API 调用少，但单次请求大
- **batch_size 小**：API 调用多，但更实时
- **推荐值**：15-25

---

## 环境变量

API Keys 也可以通过环境变量设置（优先级高于配置文件）：

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GROQ_API_KEY="gsk_..."
export DEEPSEEK_API_KEY="sk-..."
```

---

## 配置优先级

1. **命令行参数** (最高)
2. **环境变量**
3. **config.yaml**
4. **默认值** (最低)

示例：
```bash
# 命令行参数会覆盖配置文件
python subgen.py video.mp4 --whisper-provider local --target-lang ja
```

---

## 配置示例

### 最简配置（云端）

```yaml
whisper:
  provider: "openai"
  openai_key: "sk-your-key"

translation:
  provider: "openai"
  model: "gpt-4o-mini"
  api_key: "sk-your-key"
```

### 完全本地（免费）

```yaml
whisper:
  provider: "local"
  local_model: "large-v3"
  device: "cuda"

translation:
  provider: "ollama"
  ollama_model: "qwen2.5:14b"
```

### 高质量配置

```yaml
whisper:
  provider: "local"
  local_model: "large-v3"

translation:
  provider: "openai"
  model: "gpt-4o"
  api_key: "sk-your-key"

output:
  bilingual: true
  format: "ass"
```
