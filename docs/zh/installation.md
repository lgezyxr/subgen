# 📦 安装指南

[English](../installation.md)

## 系统要求

- **FFmpeg**：音频提取必需（`subgen init` 可自动下载）
- **GPU**（可选）：NVIDIA GPU 或 Apple Silicon，用于本地 Whisper

---

## 方式一：下载可执行文件（推荐）

从 [GitHub Releases](https://github.com/lgezyxr/subgen/releases) 下载适合你平台的最新版本：

| 平台 | 文件 |
|------|------|
| Windows | `subgen-windows-x64.exe` |
| macOS (Intel) | `subgen-macos-x64` |
| macOS (Apple Silicon) | `subgen-macos-arm64` |
| Linux | `subgen-linux-x64` |

```bash
# macOS / Linux：添加执行权限
chmod +x subgen-macos-arm64

# 运行设置向导（按需下载 FFmpeg、whisper.cpp、模型）
./subgen init

# 开始生成字幕
./subgen run movie.mp4 --to zh
```

无需 Python、pip 或虚拟环境。

---

## 方式二：从源码安装

```bash
# 克隆
git clone https://github.com/lgezyxr/subgen.git
cd subgen

# 创建虚拟环境
python -m venv venv

# 激活
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate         # Windows CMD
.\venv\Scripts\Activate.ps1   # Windows PowerShell

# 安装依赖
pip install -r requirements.txt

# 运行设置向导
python subgen.py init
```

### Python 版本

需要 Python 3.9 或更高版本。

---

## 设置向导：`subgen init`

`init` 命令是一站式设置向导，配置你需要的一切：

1. **硬件检测** — 检测 GPU、CUDA、Apple Silicon
2. **语音识别** — 选择云端（Groq，免费）或本地（whisper.cpp，自动下载）
3. **翻译** — 选择 LLM 服务商并认证（Copilot/ChatGPT 支持 OAuth）
4. **FFmpeg** — 未在 PATH 中找到时自动下载
5. **默认设置** — 语言、格式、样式预设

`init` 完成后即可直接 `subgen run`。

可随时重新运行 `subgen init` 更改配置。

---

## 安装 FFmpeg

`subgen init` 可自动下载 FFmpeg。手动安装方法：

### macOS
```bash
brew install ffmpeg
```

### Ubuntu/Debian
```bash
sudo apt update && sudo apt install ffmpeg
```

### Windows
```powershell
# 方式 1：winget (Windows 10+)
winget install FFmpeg

# 方式 2：Chocolatey
choco install ffmpeg

# 方式 3：手动
# 从 https://www.gyan.dev/ffmpeg/builds/ 下载
# 解压到 C:\ffmpeg
# 将 C:\ffmpeg\bin 添加到 PATH
```

验证：
```bash
ffmpeg -version
```

---

## 平台特定设置

### 🍎 Apple Silicon (M1/M2/M3)

**exe 用户**：`subgen init` 会提供 whisper.cpp Metal 加速选项。

**源码用户**：强烈推荐 MLX Whisper — 快速且免费：

```bash
pip install mlx-whisper
```

```yaml
whisper:
  provider: "mlx"
  local_model: "large-v3"
```

---

### 🖥️ Windows + NVIDIA GPU

**exe 用户**：`subgen init` 会提供 whisper.cpp CUDA 加速选项。

**源码用户**：

```powershell
# 安装带 CUDA 的 PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 安装 faster-whisper
pip install faster-whisper
```

```yaml
whisper:
  provider: "local"
  device: "cuda"
  local_model: "large-v3"
```

**旧显卡 (GTX 10xx/Pascal)**：添加 `compute_type: "float32"`

---

### 🖥️ 无 GPU

使用云端 API：

```yaml
whisper:
  provider: "groq"  # 有免费额度，非常快
  groq_key: "gsk_..."
```

---

### 🐧 Linux + NVIDIA GPU

**源码用户**：

```bash
# 先安装 CUDA toolkit（如果未安装）
# 然后：
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install faster-whisper
```

---

## OAuth 设置（推荐）

使用你现有的订阅 — 无需 API Key！

### ChatGPT Plus/Pro

```bash
python subgen.py auth login chatgpt
```

浏览器打开 → 登录 → 完成！

### GitHub Copilot

```bash
python subgen.py auth login copilot
```

按设备代码流程操作。

### 查看状态

```bash
python subgen.py auth status
```

---

## 可选：Ollama（离线 LLM）

完全离线翻译：

### 1. 安装 Ollama

```bash
# macOS/Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows：从 ollama.com 下载
```

### 2. 下载模型

```bash
ollama pull qwen2.5:14b   # 中文最佳 (16GB 显存)
ollama pull qwen2.5:7b    # 较小 (8GB 显存)
ollama pull llama3:8b     # 通用
```

### 3. 配置

```yaml
translation:
  provider: "ollama"
  model: "qwen2.5:14b"
```

---

## 环境检查：`subgen doctor`

运行 `subgen doctor` 验证你的设置：

```bash
python subgen.py doctor
```

检查配置、FFmpeg、Whisper 后端、LLM、GPU 和磁盘使用情况，显示哪些已就绪、哪些需要修复。

---

## 验证安装

```bash
# 检查一切是否正常
python subgen.py doctor

# 用短视频测试
python subgen.py run test.mp4 -s --to zh --debug
```

---

## 常见问题

### PowerShell 执行策略 (Windows)

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 找不到 CUDA

1. 验证 CUDA 安装：`nvcc --version`
2. 验证 PyTorch 能看到 GPU：`python -c "import torch; print(torch.cuda.is_available())"`
3. 安装与你的 CUDA 版本匹配的 PyTorch

### 包冲突 (Anaconda)

如果使用 Anaconda，改用 conda 环境：

```bash
conda create -n subgen python=3.11
conda activate subgen
pip install -r requirements.txt
```

---

## 下一步

1. 运行 `python subgen.py init` 进行配置
2. 试试：`python subgen.py run video.mp4 -s --to zh`
3. 查看 [配置说明](configuration.md) 了解所有选项
