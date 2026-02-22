# ⚙️ 配置说明

SubGen 使用 YAML 配置文件管理所有设置。

## 配置文件位置

默认读取当前目录的 `config.yaml`，也可以用 `--config` 参数指定：

```bash
python subgen.py video.mp4 --config /path/to/my-config.yaml
```

---

## 完整配置项

### Whisper 语音识别

```yaml
whisper:
  # 提供商选择
  # - local: 本地运行 (需要 GPU)
  # - openai: OpenAI Whisper API ($0.006/分钟)
  # - groq: Groq API (有免费额度，超快)
  provider: "openai"
  
  # 本地模型选择 (仅 provider: local 时有效)
  # tiny (39M) → base (74M) → small (244M) → medium (769M) → large-v3 (1.5B)
  # 模型越大越准，但需要更多显存
  local_model: "large-v3"
  
  # 设备选择 (仅 provider: local 时有效)
  # cuda: NVIDIA GPU (推荐)
  # cpu: CPU (很慢，不推荐)
  device: "cuda"
  
  # API Keys
  openai_key: "sk-..."      # OpenAI API Key
  groq_key: "gsk_..."       # Groq API Key
```

### LLM 翻译

```yaml
translation:
  # 提供商选择
  # - openai: OpenAI GPT 系列
  # - claude: Anthropic Claude
  # - deepseek: DeepSeek (中文优化，便宜)
  # - ollama: 本地 LLM (完全免费)
  provider: "openai"
  
  # 模型选择
  # OpenAI: gpt-4o-mini (便宜) | gpt-4o (最好)
  # Claude: claude-3-haiku (快) | claude-3-sonnet (平衡)
  # DeepSeek: deepseek-chat
  # Ollama: qwen2.5:14b | llama3:8b
  model: "gpt-4o-mini"
  
  # API Key (openai/claude/deepseek)
  api_key: "sk-..."
  
  # 自定义 API 地址 (可选，用于代理或兼容接口)
  base_url: ""
  
  # Ollama 配置
  ollama_host: "http://localhost:11434"
  ollama_model: "qwen2.5:14b"
```

### 输出设置

```yaml
output:
  # 字幕格式
  # - srt: 最通用，所有播放器支持
  # - ass: 支持样式，字幕组常用
  # - vtt: Web 视频标准
  format: "srt"
  
  # 目标翻译语言
  # zh: 中文 | en: English | ja: 日本語 | ko: 한국어
  # fr: Français | de: Deutsch | es: Español
  target_language: "zh"
  
  # 双语字幕
  # true: 显示原文 + 译文
  # false: 只显示译文
  bilingual: false
  
  # 每行最大字符数
  # 控制字幕换行，避免一行太长
  max_chars_per_line: 42
  
  # 烧录字幕到视频
  # true: 输出带字幕的新视频 (硬字幕)
  # false: 只输出字幕文件
  embed_in_video: false
```

### 高级设置

```yaml
advanced:
  # 翻译批次大小
  # 每次 API 调用翻译多少条字幕
  # 太大可能超出 token 限制，太小效率低
  translation_batch_size: 20
  
  # 翻译上下文大小
  # 翻译时提供前后多少条字幕作为上下文
  # 帮助保持翻译连贯性
  translation_context_size: 5
  
  # 临时文件目录
  temp_dir: "./temp"
  
  # 保留临时文件 (调试用)
  keep_temp_files: false
  
  # 日志级别
  # DEBUG | INFO | WARNING | ERROR
  log_level: "INFO"
```

---

## 环境变量

API Keys 也可以通过环境变量设置（优先级低于配置文件）：

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GROQ_API_KEY="gsk_..."
export DEEPSEEK_API_KEY="sk-..."
```

---

## 配置示例

### 最便宜方案 (本地 Whisper + GPT-4o-mini)

```yaml
whisper:
  provider: "local"
  local_model: "large-v3"
  device: "cuda"

translation:
  provider: "openai"
  model: "gpt-4o-mini"
  api_key: "sk-..."
```

### 最快方案 (Groq + GPT-4o)

```yaml
whisper:
  provider: "groq"
  groq_key: "gsk_..."

translation:
  provider: "openai"
  model: "gpt-4o"
  api_key: "sk-..."
```

### 完全离线方案 (本地 Whisper + Ollama)

```yaml
whisper:
  provider: "local"
  local_model: "large-v3"
  device: "cuda"

translation:
  provider: "ollama"
  ollama_host: "http://localhost:11434"
  ollama_model: "qwen2.5:14b"
```

### 中文优化方案 (DeepSeek)

```yaml
whisper:
  provider: "openai"
  openai_key: "sk-..."

translation:
  provider: "deepseek"
  model: "deepseek-chat"
  api_key: "sk-..."
```

---

## 翻译规则自定义

SubGen 支持为不同目标语言配置专门的翻译规则。

### 规则文件位置

规则文件位于 `rules/` 目录：

```
subgen/
├── rules/
│   ├── zh.md          # 中文规则
│   ├── ja.md          # 日语规则
│   ├── ko.md          # 韩语规则
│   └── default.md     # 默认规则（兜底）
```

### 规则加载顺序

1. 精确匹配：`zh-TW.md`
2. 语言族匹配：`zh.md`（从 `zh-TW` 回退）
3. 默认规则：`default.md`

### 规则文件格式

使用 Markdown 格式，便于阅读和编辑：

```markdown
# 中文字幕翻译规则

## 标点符号
- 使用半角标点符号
- 书名用《》

## 数字翻译
- 1-9 用中文：一、二、三
- 10+ 用阿拉伯数字
```

### 添加新语言规则

1. 在 `rules/` 目录创建 `{语言代码}.md` 文件
2. 使用 Markdown 格式编写规则
3. 规则会自动注入到翻译 prompt 中

### 自定义规则目录

规则文件按以下顺序查找：
1. 项目目录 `./rules/`
2. 当前工作目录 `./rules/`
3. 用户目录 `~/.subgen/rules/`

可以在用户目录创建全局规则，或在项目目录创建项目特定规则。
