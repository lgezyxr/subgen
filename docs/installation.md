# 📦 安装指南

## 系统要求

- **Python**: 3.10 或更高版本
- **FFmpeg**: 必需，用于音频/视频处理
- **GPU** (可选): 如果使用本地 Whisper，建议 NVIDIA GPU (4GB+ 显存)

---

## 基础安装

### 1. 安装 FFmpeg

**macOS**:
```bash
brew install ffmpeg
```

**Ubuntu/Debian**:
```bash
sudo apt update
sudo apt install ffmpeg
```

**Windows**:
1. 下载 [FFmpeg](https://ffmpeg.org/download.html)
2. 解压到 `C:\ffmpeg`
3. 添加 `C:\ffmpeg\bin` 到系统 PATH

验证安装：
```bash
ffmpeg -version
```

### 2. 安装 SubGen

```bash
# 克隆项目
git clone https://github.com/YOUR_USERNAME/subgen.git
cd subgen

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置

```bash
# 复制配置模板
cp config.example.yaml config.yaml

# 编辑配置，填入 API Keys
nano config.yaml  # 或使用你喜欢的编辑器
```

---

## 可选：本地 Whisper

如果你有 NVIDIA GPU，可以在本地运行 Whisper（免费且更快）：

### 1. 安装 CUDA

确保已安装 NVIDIA 驱动和 CUDA。检查：
```bash
nvidia-smi
```

### 2. 安装 PyTorch

```bash
# CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# CUDA 12.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### 3. 安装 faster-whisper

```bash
pip install faster-whisper
```

### 4. 验证

```python
from faster_whisper import WhisperModel
model = WhisperModel("base", device="cuda")
print("Whisper 本地运行成功！")
```

---

## 可选：本地 LLM (Ollama)

如果你想完全离线翻译：

### 1. 安装 Ollama

**macOS/Linux**:
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows**:
下载 [Ollama 安装包](https://ollama.com/download)

### 2. 下载模型

```bash
# 推荐：Qwen2.5 (中文优化)
ollama pull qwen2.5:14b

# 或：Llama 3
ollama pull llama3:8b
```

### 3. 启动服务

```bash
ollama serve
```

### 4. 配置 SubGen

在 `config.yaml` 中：
```yaml
translation:
  provider: "ollama"
  ollama_host: "http://localhost:11434"
  ollama_model: "qwen2.5:14b"
```

---

## 常见问题

### FFmpeg 找不到

**错误**: `FileNotFoundError: ffmpeg not found`

**解决**:
1. 确认 FFmpeg 已安装：`ffmpeg -version`
2. 确认 FFmpeg 在 PATH 中
3. 或在配置中指定完整路径

### CUDA 内存不足

**错误**: `CUDA out of memory`

**解决**:
1. 使用更小的模型：`local_model: "medium"` 或 `"small"`
2. 关闭其他占用 GPU 的程序
3. 使用云端 API 代替本地

### API 请求失败

**错误**: `APIError: 401 Unauthorized`

**解决**:
1. 检查 API Key 是否正确
2. 检查 API Key 是否有效（是否过期、是否有额度）
3. 检查网络连接

---

## 下一步

安装完成后，请查看：
- [配置说明](configuration.md) - 详细配置选项
- [API 提供商设置](providers.md) - 如何获取各服务的 API Key
