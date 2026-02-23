# 🎬 SubGen - AI 字幕生成器

> 本地 AI 字幕生成：视频 → 语音识别 → 翻译 → 字幕

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/lgezyxr/subgen/actions/workflows/test.yml/badge.svg)](https://github.com/lgezyxr/subgen/actions/workflows/test.yml)

[English](README.md)

## ✨ 功能特性

- 🎯 **一键生成**：丢进视频，输出字幕
- 🔊 **多种 Whisper 后端**：本地 GPU、MLX（苹果芯片）、OpenAI、Groq
- 🌍 **多种翻译服务**：OpenAI、Claude、DeepSeek、Ollama、ChatGPT Plus、Copilot
- 🎯 **句子感知翻译**：按完整句子分组，词级时间戳对齐
- 📝 **AI 校对**：全剧情上下文审校，确保一致性和准确性
- 🔒 **OAuth 登录**：直接用 ChatGPT Plus 或 GitHub Copilot 订阅（无需 API Key！）
- 💾 **智能缓存**：转写结果缓存，重复运行秒出
- 💰 **费用透明**：用自己的 API Key，花多少一目了然

## 🚀 快速开始

### 安装

```bash
git clone https://github.com/lgezyxr/subgen.git
cd subgen
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 配置

```bash
python subgen.py init
```

### 基本用法

```bash
# 简单翻译（英文 → 中文）
python subgen.py run video.mp4 --to zh

# 句子感知翻译（推荐，质量更好）
python subgen.py run video.mp4 -s --to zh

# 带校对（最佳质量）
python subgen.py run video.mp4 -s --proofread --to zh
```

## 📖 命令参考

### `subgen run` - 生成字幕

```bash
python subgen.py run <视频> [选项]
```

#### 翻译选项

| 选项 | 简写 | 说明 |
|------|------|------|
| `--to LANG` | | 目标语言 (zh, en, ja 等) |
| `--from LANG` | | 源语言（默认自动检测） |
| `--sentence-aware` | `-s` | 启用句子分组 + 词级时间戳 |
| `--proofread` | `-p` | 翻译后进行 AI 校对 |
| `--proofread-only` | | 只运行校对（需要已缓存的翻译） |
| `--no-translate` | | 只转写，不翻译 |
| `--bilingual` | | 输出原文+译文双语字幕 |

#### 服务商选项

| 选项 | 说明 |
|------|------|
| `--whisper-provider` | local / mlx / openai / groq |
| `--llm-provider` | openai / claude / deepseek / ollama / chatgpt / copilot |

#### 其他选项

| 选项 | 说明 |
|------|------|
| `-o, --output` | 输出文件路径 |
| `--force-transcribe` | 忽略缓存，强制重新转写 |
| `--debug` | 显示详细调试日志 |
| `--config` | 使用自定义配置文件 |

### `subgen auth` - OAuth 登录

```bash
# 用 ChatGPT Plus/Pro 登录（会打开浏览器）
python subgen.py auth login chatgpt

# 用 GitHub Copilot 登录
python subgen.py auth login copilot

# 查看登录状态
python subgen.py auth status

# 登出
python subgen.py auth logout chatgpt
```

## 🎯 翻译模式

### 基本模式

```bash
python subgen.py run video.mp4 --to zh
```
- 逐条翻译每个字幕片段
- 速度快，但可能丢失上下文

### 句子感知模式（推荐）

```bash
python subgen.py run video.mp4 -s --to zh
```
- 将字幕片段组合成完整句子
- 使用词级时间戳实现精确对齐
- LLM 决定目标语言的自然断句点
- **适合对话密集的内容**

### 带校对（最佳质量）

```bash
python subgen.py run video.mp4 -s --proofread --to zh
```
- 增加第二轮 AI 审校，带有完整剧情上下文
- 检查人名、术语、语气的一致性
- 修复依赖上下文的翻译错误
- **适合电影、电视剧**

### 仅校对模式

```bash
# 先：生成翻译
python subgen.py run video.mp4 -s --to zh

# 后：只校对现有翻译
python subgen.py run video.mp4 --proofread-only --to zh
```
- 使用已缓存的翻译结果
- 只运行校对流程
- 输出：`video_zh.proofread.srt`

## 📂 输出文件

| 命令 | 输出文件 |
|------|----------|
| `--to zh` | `video_zh.srt` |
| `--to zh --proofread-only` | `video_zh.proofread.srt` |
| `--no-translate` | `video.srt` |
| `-o custom.srt` | `custom.srt` |

## 🔧 支持的服务商

### 语音识别 (Whisper)

| 服务商 | 平台 | 费用 | 说明 |
|--------|------|------|------|
| `mlx` | 苹果芯片 | 免费 | **M1/M2/M3 Mac 首选** |
| `local` | NVIDIA GPU | 免费 | 需要 CUDA，4GB+ 显存 |
| `groq` | 任意 | 有免费额度 | 云端，非常快 |
| `openai` | 任意 | $0.006/分钟 | 最稳定 |

### 翻译 (LLM)

| 服务商 | 认证方式 | 费用 | 说明 |
|--------|----------|------|------|
| `chatgpt` | OAuth | 订阅费 | **用你的 ChatGPT Plus！** |
| `copilot` | OAuth | 订阅费 | 用你的 GitHub Copilot |
| `deepseek` | API Key | ~¥1/百万 token | 中文优化 |
| `openai` | API Key | ~$0.15/百万 token | gpt-4o-mini |
| `claude` | API Key | ~$0.25/百万 token | 快速 |
| `ollama` | 本地 | 免费 | 完全离线 |

## 💡 示例

### 最佳质量配置

```bash
# 苹果芯片
python subgen.py run movie.mkv -s --proofread \
  --whisper-provider mlx \
  --llm-provider chatgpt \
  --to zh

# NVIDIA GPU
python subgen.py run movie.mkv -s --proofread \
  --whisper-provider local \
  --llm-provider chatgpt \
  --to zh
```

### 批量处理

```bash
# 处理文件夹中所有视频
for f in ./videos/*.mp4; do
  python subgen.py run "$f" -s --to zh
done
```

### 调试模式

```bash
# 显示详细日志用于排查问题
python subgen.py run video.mp4 -s --to zh --debug
```

## 📖 文档

- [安装指南](docs/installation.md)
- [配置说明](docs/configuration.md)
- [API 服务商](docs/providers.md)
- [常见问题](docs/faq.md)

## 🤝 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

---

**⭐ 如果这个项目对你有帮助，请给个 Star！**
