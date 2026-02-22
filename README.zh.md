# 🎬 SubGen - AI 字幕生成工具

> 本地运行的 AI 字幕生成器：视频 → 语音识别 → 翻译 → 字幕

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/lgezyxr/subgen/actions/workflows/test.yml/badge.svg)](https://github.com/lgezyxr/subgen/actions/workflows/test.yml)

[English](README.md)

## ✨ 特性

- 🎯 **一键生成字幕**：拖入视频，自动输出 SRT 字幕
- 🔊 **语音识别**：支持本地 Whisper 或云端 API（OpenAI、Groq）
- 🌍 **智能翻译**：支持多种 LLM（OpenAI、Claude、DeepSeek、Ollama）
- 📝 **双语字幕**：可选原文+译文双语输出
- 🔄 **语言切换**：通过 CLI 轻松切换源语言和目标语言
- 📋 **多语言规则**：为不同目标语言配置专业翻译规则（详见 `rules/` 目录）
- 🔒 **隐私友好**：视频文件不离开本地
- 💰 **成本透明**：使用自己的 API，费用可控

## 🚀 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/lgezyxr/subgen.git
cd subgen

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# （可选）安装本地 Whisper 支持
pip install faster-whisper
```

### 配置

复制配置模板并填入你的 API Keys：

```bash
cp config.example.yaml config.yaml
```

编辑 `config.yaml`：

```yaml
whisper:
  provider: "openai"  # local | openai | groq
  openai_key: "sk-your-key-here"

translation:
  provider: "openai"
  model: "gpt-4o-mini"
  api_key: "sk-your-key-here"
```

### 使用

```bash
# 基础用法（自动检测源语言，翻译成中文）
python subgen.py video.mp4

# 指定源语言和目标语言
python subgen.py video.mp4 --from en --to zh

# 西班牙语翻译成日语
python subgen.py video.mp4 -f es -t ja

# 生成双语字幕
python subgen.py video.mp4 --from en --to zh --bilingual

# 使用本地 Whisper
python subgen.py video.mp4 --whisper-provider local

# 查看所有选项
python subgen.py --help
```

## 📖 详细文档

- [安装指南](docs/zh/installation.md)
- [配置说明](docs/zh/configuration.md)
- [API 提供商设置](docs/zh/providers.md)
- [开发计划](docs/zh/roadmap.md)
- [常见问题](docs/zh/faq.md)

## 🔧 支持的服务

### 语音识别 (Whisper)

| 提供商 | 价格 | 速度 | 备注 |
|--------|------|------|------|
| 本地 (faster-whisper) | 免费 | 取决于 GPU | 需要 4GB+ 显存 |
| OpenAI Whisper API | $0.006/分钟 | 快 | 最稳定 |
| Groq | 有免费额度 | **极快** | 推荐尝试 |

### 翻译 (LLM)

| 提供商 | 推荐模型 | 价格 | 备注 |
|--------|----------|------|------|
| OpenAI | gpt-4o-mini | ~$0.15/百万token | 性价比高 |
| OpenAI | gpt-4o | ~$2.5/百万token | 质量最好 |
| Claude | claude-3-haiku | ~$0.25/百万token | 快速 |
| DeepSeek | deepseek-chat | ~¥1/百万token | 中文优化 |
| Ollama | qwen2.5:14b | 免费 | 需要本地部署 |

## 💡 示例

### 翻译一部电影

```bash
# 2小时电影，使用云端服务
python subgen.py "Inception.2010.mkv" --from en --to zh --bilingual

# 预估成本：
# - Whisper API: 120分钟 × $0.006 = $0.72
# - GPT-4o-mini: ~$0.05
# - 总计: ~$0.77 (约 ¥5.5)
```

### 批量处理

```bash
# 处理整个文件夹
python subgen.py ./videos/ --to zh
```

## 🏗️ 项目结构

```
subgen/
├── subgen.py           # 主程序入口
├── config.yaml         # 用户配置
├── config.example.yaml # 配置模板
├── requirements.txt    # Python 依赖
├── rules/              # 翻译规则（按语言）
│   ├── zh.md           # 中文翻译规则
│   ├── ja.md           # 日语翻译规则
│   └── default.md      # 其他语言默认规则
│
├── src/
│   ├── __init__.py
│   ├── audio.py        # 音频提取
│   ├── config.py       # 配置加载
│   ├── transcribe.py   # 语音识别
│   ├── translate.py    # 翻译
│   └── subtitle.py     # 字幕生成
│
├── docs/               # 英文文档
│   └── zh/             # 中文文档
│
└── tests/              # 单元测试
    └── ...
```

## 🤝 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解如何参与。

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

## 🙏 致谢

- [OpenAI Whisper](https://github.com/openai/whisper) - 语音识别模型
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) - 高效 Whisper 实现
- 所有 API 提供商

---

**⭐ 如果这个项目对你有帮助，请给个 Star！**
