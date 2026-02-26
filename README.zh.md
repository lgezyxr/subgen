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
- 🎨 **样式预设**：内置样式（default/netflix/fansub/minimal），支持完全自定义
- 📁 **项目文件**：保存/加载 `.subgen` 项目文件，支持迭代工作流
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

#### 样式选项

| 选项 | 说明 |
|------|------|
| `--style-preset` | 样式预设：default / netflix / fansub / minimal |
| `--primary-font` | 覆盖主字幕字体 |
| `--primary-color` | 覆盖主字幕颜色（hex 格式，如 `#FFFFFF`） |
| `--secondary-font` | 覆盖副字幕字体 |
| `--secondary-color` | 覆盖副字幕颜色（hex 格式，如 `#AAAAAA`） |

#### 项目选项

| 选项 | 说明 |
|------|------|
| `--save-project PATH` | 处理后保存 `.subgen` 项目文件 |
| `--load-project PATH` | 从 `.subgen` 项目文件加载（跳过转写/翻译） |

#### 其他选项

| 选项 | 说明 |
|------|------|
| `-o, --output` | 输出文件路径 |
| `--force-transcribe` | 忽略缓存，强制重新转写 |
| `--embed` | 烧录字幕到视频 |
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

## 🎨 样式预设

SubGen 内置多种 ASS 字幕渲染样式预设，使用 `--style-preset` 选择：

```bash
# 使用 Netflix 风格字幕
python subgen.py run movie.mp4 --to zh --style-preset netflix

# 字幕组风格 + 自定义主字幕颜色
python subgen.py run movie.mp4 --to zh --style-preset fansub --primary-color "#00FF00"
```

### 可用预设

| 预设 | 主字体 | 主颜色 | 副颜色 | 说明 |
|------|--------|--------|--------|------|
| `default` | Arial | `#FFFFFF` | `#AAAAAA` | 简洁通用样式 |
| `netflix` | Netflix Sans | `#FFFFFF` | `#CCCCCC` | Netflix 风格，轻描边 |
| `fansub` | 方正准圆_GBK | `#00FFFF` | `#FFFFFF` | 字幕组风格，青色主字幕 |
| `minimal` | Helvetica | `#FFFFFF` | `#BBBBBB` | 极简风格，细描边 |

可以在任意预设基础上覆盖单项属性：

```bash
python subgen.py run movie.mp4 --to zh \
  --style-preset netflix \
  --primary-font "Noto Sans CJK SC" \
  --secondary-color "#DDDDDD"
```

样式也可以在 `config.yaml` 中配置，详见 [配置说明](docs/configuration.md)。

## 📁 项目文件

SubGen 支持保存和加载 `.subgen` 项目文件，以 JSON 格式存储所有片段、样式、元数据和处理状态。

```bash
# 生成字幕并保存项目
python subgen.py run movie.mp4 --to zh --save-project movie.subgen

# 之后：加载项目并重新导出（例如使用不同样式）
python subgen.py run movie.mp4 --load-project movie.subgen --style-preset fansub -o movie_fansub.ass
```

项目文件的用途：
- **迭代工作流**：转写一次，反复调整样式和设置
- **状态保存**：无需重新处理即可恢复或重新导出
- **协作共享**：与他人分享转写/翻译成果

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
