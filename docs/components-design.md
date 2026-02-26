# SubGen 组件化设计文档 — 按需下载架构

> 目标：exe 本体保持轻量（~50MB），用户选择需要的功能后按需下载对应组件。
> 类似 Ollama、VS Code Extensions 的模式。

---

## 1. 核心理念

```
┌─────────────────────────────────────────────────────┐
│  subgen.exe (~50MB)                                 │
│  ┌───────────────────────────────────────────────┐  │
│  │  CLI + Engine + 翻译SDK + 样式/项目系统       │  │
│  │  云端 Whisper (Groq/OpenAI API)               │  │
│  │  OAuth (Copilot/ChatGPT)                      │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                        │
           subgen init / 首次运行
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│  ~/.subgen/                                         │
│  ├── config.yaml          ← 用户配置               │
│  ├── auth/                ← OAuth tokens            │
│  ├── bin/                 ← 按需下载的二进制        │
│  │   ├── ffmpeg(.exe)     ← 可选, ~80MB            │
│  │   └── whisper-cpp(.exe)← 本地 Whisper 引擎      │
│  │       ├── cuda/        ← CUDA 版, ~15MB         │
│  │       └── cpu/         ← CPU 版, ~5MB           │
│  └── models/              ← 按需下载的模型          │
│      └── whisper/                                   │
│          ├── ggml-tiny.bin       ← 75MB             │
│          ├── ggml-base.bin       ← 142MB            │
│          ├── ggml-small.bin      ← 466MB            │
│          ├── ggml-medium.bin     ← 1.5GB            │
│          └── ggml-large-v3.bin   ← 3.1GB            │
└─────────────────────────────────────────────────────┘
```

**原则：**
- exe 只包含能用 Python 纯包实现的功能
- 任何需要编译/大体积的组件都走按需下载
- 下载有进度条、有校验、可断点续传
- 已下载的组件有版本管理，可更新

---

## 2. 组件清单

### 2.1 内置组件（随 exe 打包）

| 组件 | 用途 | 依赖 |
|------|------|------|
| CLI 界面 | 命令行交互 | click, rich |
| SubGenEngine | 核心引擎 | — |
| 翻译模块 | LLM 翻译/校对 | openai, anthropic, httpx |
| 字幕渲染 | SRT/ASS/VTT 生成 | — |
| 样式系统 | StyleProfile + presets | — |
| 项目文件 | .subgen 保存/加载 | — |
| 云端 Whisper | Groq / OpenAI API | groq, openai |
| OAuth 登录 | Copilot / ChatGPT | httpx |
| 组件管理器 | 下载/更新/检查组件 | — |

### 2.2 可下载组件

| 组件 ID | 描述 | 来源 | 大小 | 平台 |
|---------|------|------|------|------|
| `whisper-cpp-cuda` | whisper.cpp CUDA 版 | SubGen Releases / 自编译 | ~15MB | Linux/Windows |
| `whisper-cpp-cpu` | whisper.cpp CPU 版 | SubGen Releases / 自编译 | ~5MB | 全平台 |
| `whisper-cpp-metal` | whisper.cpp Metal 版 | SubGen Releases / 自编译 | ~8MB | macOS |
| `whisper-cpp-vulkan` | whisper.cpp Vulkan 版 | SubGen Releases / 自编译 | ~10MB | 全平台 |
| `model-whisper-tiny` | Whisper tiny 模型 | HuggingFace (ggerganov) | 75MB | 全平台 |
| `model-whisper-base` | Whisper base 模型 | HuggingFace | 142MB | 全平台 |
| `model-whisper-small` | Whisper small 模型 | HuggingFace | 466MB | 全平台 |
| `model-whisper-medium` | Whisper medium 模型 | HuggingFace | 1.5GB | 全平台 |
| `model-whisper-large-v3` | Whisper large-v3 模型 | HuggingFace | 3.1GB | 全平台 |
| `ffmpeg` | 音视频处理 | FFmpeg 官方 / BtbN builds | ~80MB | 全平台 |

### 2.3 模型推荐策略

根据硬件自动推荐模型大小：

| 场景 | 推荐模型 | VRAM 需求 | 原因 |
|------|---------|----------|------|
| NVIDIA ≥8GB VRAM | large-v3 | ~3GB VRAM | 最佳质量 |
| NVIDIA 4-8GB VRAM | medium | ~2GB VRAM | 平衡 |
| NVIDIA <4GB VRAM | small | ~1GB VRAM | 够用 |
| Apple Silicon ≥16GB | large-v3 | 共享内存 | Metal 加速 |
| Apple Silicon 8GB | medium | 共享内存 | 安全选择 |
| CPU only | small 或 base | N/A | 太慢就推荐云端 |

---

## 3. 新增模块：`src/components.py`

### 3.1 数据结构

```python
from dataclasses import dataclass, field
from typing import Optional, List
from pathlib import Path
from enum import Enum

class ComponentType(Enum):
    ENGINE = "engine"      # whisper-cpp 二进制
    MODEL = "model"        # GGML 模型文件
    TOOL = "tool"          # ffmpeg 等外部工具

class Platform(Enum):
    WINDOWS = "windows"
    MACOS_X64 = "macos-x64"
    MACOS_ARM64 = "macos-arm64"
    LINUX_X64 = "linux-x64"

@dataclass
class Component:
    """组件定义"""
    id: str                          # "whisper-cpp-cuda"
    name: str                        # "whisper.cpp (CUDA)"
    type: ComponentType
    version: str                     # "1.7.3"
    description: str
    size_bytes: int                   # 下载大小
    urls: dict[str, str]             # platform -> download URL
    sha256: dict[str, str]           # platform -> checksum
    requires: List[str] = field(default_factory=list)  # 依赖的其他组件
    install_path: str = ""           # 相对于 ~/.subgen/ 的安装路径
    executable: str = ""             # 可执行文件名

@dataclass
class InstalledComponent:
    """已安装的组件"""
    id: str
    version: str
    path: Path
    installed_at: str                # ISO timestamp
    size_bytes: int
```

### 3.2 组件注册表

组件元数据不硬编码在 exe 里，而是从远程获取（支持版本更新）：

```
获取顺序：
1. 本地缓存: ~/.subgen/components.json (24h 有效)
2. 远程: https://github.com/lgezyxr/subgen/releases/latest/download/components.json
3. 内置 fallback: exe 打包时的 components.json 快照
```

**components.json 示例：**

```json
{
  "version": "1",
  "updated": "2026-02-26T00:00:00Z",
  "components": {
    "whisper-cpp-cuda": {
      "name": "whisper.cpp (CUDA)",
      "type": "engine",
      "version": "1.7.3",
      "description": "Local speech recognition with NVIDIA GPU acceleration",
      "urls": {
        "windows": "https://github.com/lgezyxr/subgen/releases/download/components-v1/whisper-cpp-cuda-windows-x64.zip",
        "linux-x64": "https://github.com/lgezyxr/subgen/releases/download/components-v1/whisper-cpp-cuda-linux-x64.tar.gz"
      },
      "sha256": {
        "windows": "abc123...",
        "linux-x64": "def456..."
      },
      "size_bytes": 15728640,
      "install_path": "bin/whisper-cpp",
      "executable": "whisper-cpp"
    },
    "model-whisper-large-v3": {
      "name": "Whisper Large V3",
      "type": "model",
      "version": "1.0",
      "description": "Best quality, 3.1GB, requires ≥8GB VRAM",
      "urls": {
        "*": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin"
      },
      "sha256": {
        "*": "..."
      },
      "size_bytes": 3326234624,
      "install_path": "models/whisper/ggml-large-v3.bin"
    },
    "ffmpeg": {
      "name": "FFmpeg",
      "type": "tool",
      "version": "7.1",
      "description": "Audio/video processing (required for video input)",
      "urls": {
        "windows": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
        "linux-x64": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz",
        "macos-arm64": "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip",
        "macos-x64": "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip"
      },
      "size_bytes": 83886080,
      "install_path": "bin/ffmpeg",
      "executable": "ffmpeg"
    }
  }
}
```

### 3.3 ComponentManager 核心类

```python
class ComponentManager:
    """管理组件的下载、安装、更新、删除"""

    def __init__(self, base_dir: Path = None):
        """
        base_dir: ~/.subgen/
        状态文件: ~/.subgen/installed.json
        """

    # === 查询 ===
    def list_available(self) -> list[Component]:
        """列出所有可用组件（从注册表获取）"""

    def list_installed(self) -> list[InstalledComponent]:
        """列出已安装的组件"""

    def is_installed(self, component_id: str) -> bool:
        """检查组件是否已安装"""

    def get_path(self, component_id: str) -> Optional[Path]:
        """获取已安装组件的路径"""

    def needs_update(self, component_id: str) -> bool:
        """检查是否有可用更新"""

    # === 安装 ===
    def install(self, component_id: str,
                on_progress: Callable[[int, int], None] = None) -> Path:
        """
        下载并安装组件。
        - 显示下载进度
        - SHA256 校验
        - 自动解压 zip/tar.gz
        - 写入 installed.json
        - 返回安装路径
        """

    def install_model(self, model_name: str,
                      on_progress: Callable[[int, int], None] = None) -> Path:
        """安装 Whisper 模型（简化接口）
        model_name: tiny | base | small | medium | large-v3
        """

    # === 管理 ===
    def uninstall(self, component_id: str) -> bool:
        """删除已安装的组件"""

    def update(self, component_id: str) -> bool:
        """更新组件到最新版本"""

    def disk_usage(self) -> dict[str, int]:
        """各组件占用空间"""

    # === 工具 ===
    def find_ffmpeg(self) -> Optional[Path]:
        """查找 ffmpeg: 1) ~/.subgen/bin/ 2) PATH 3) None"""

    def find_whisper_engine(self) -> Optional[Path]:
        """查找 whisper-cpp 引擎"""

    def find_whisper_model(self, model_name: str) -> Optional[Path]:
        """查找已下载的 Whisper 模型"""

    # === 内部 ===
    def _download(self, url: str, dest: Path,
                  on_progress: Callable[[int, int], None] = None,
                  sha256: str = None) -> Path:
        """下载文件，支持进度回调 + 断点续传 + SHA256 校验"""

    def _detect_platform(self) -> str:
        """检测当前平台: windows | linux-x64 | macos-x64 | macos-arm64"""

    def _refresh_registry(self) -> dict:
        """刷新组件注册表（远程 → 缓存）"""
```

### 3.4 状态文件 `~/.subgen/installed.json`

```json
{
  "components": {
    "whisper-cpp-cuda": {
      "version": "1.7.3",
      "path": "/home/user/.subgen/bin/whisper-cpp/whisper-cpp",
      "installed_at": "2026-02-26T12:00:00Z",
      "size_bytes": 15728640
    },
    "model-whisper-large-v3": {
      "version": "1.0",
      "path": "/home/user/.subgen/models/whisper/ggml-large-v3.bin",
      "installed_at": "2026-02-26T12:05:00Z",
      "size_bytes": 3326234624
    }
  },
  "registry_cached_at": "2026-02-26T12:00:00Z"
}
```

---

## 4. whisper.cpp 后端集成

### 4.1 新增 `src/transcribe_cpp.py`

whisper.cpp 的 Python 绑定有两个主要选择：

| 库 | 特点 | 打包友好度 |
|----|------|-----------|
| `pywhispercpp` | Pythonic API，自带预编译 wheel | ❌ 编译时绑定 |
| 直接调用二进制 | 零依赖，通过 subprocess 调用 whisper-cpp CLI | ✅ 完美 |

**选择：直接调用 whisper-cpp 二进制（subprocess）**

原因：
- 不需要在 exe 里打包 C++ 编译产物
- whisper-cpp CLI 输出 JSON/SRT/VTT 格式，容易解析
- 二进制可独立更新，不需要重新打包 exe
- 避免 CUDA/Metal 编译问题

```python
# src/transcribe_cpp.py

"""whisper.cpp backend — calls whisper-cpp binary via subprocess"""

import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from .transcribe import Segment, Word
from .components import ComponentManager
from .logger import debug


def transcribe_cpp(
    audio_path: Path,
    config: Dict[str, Any],
    on_progress: Optional[Callable[[int, int], None]] = None
) -> List[Segment]:
    """
    使用 whisper.cpp 二进制进行语音识别。

    流程：
    1. 通过 ComponentManager 找到 whisper-cpp 引擎和模型
    2. 如果没有则提示安装
    3. 调用 whisper-cpp CLI，输出 JSON
    4. 解析 JSON 为 Segment 列表
    """
    cm = ComponentManager()

    # 找引擎
    engine_path = cm.find_whisper_engine()
    if not engine_path:
        raise RuntimeError(
            "whisper.cpp engine not found.\n"
            "Run: subgen install whisper-cpp\n"
            "Or use cloud Whisper: subgen init"
        )

    # 找模型
    model_name = config['whisper'].get('local_model', 'large-v3')
    model_path = cm.find_whisper_model(model_name)
    if not model_path:
        raise RuntimeError(
            f"Whisper model '{model_name}' not found.\n"
            f"Run: subgen install model-whisper-{model_name}"
        )

    # 构建命令
    cmd = [
        str(engine_path),
        "-m", str(model_path),
        "-f", str(audio_path),
        "--output-json",           # JSON 输出
        "--print-progress",        # 打印进度到 stderr
        "-t", str(config['whisper'].get('threads', 4)),
    ]

    # 语言
    source_lang = config['whisper'].get('source_language')
    if source_lang:
        cmd.extend(["-l", source_lang])

    debug("transcribe_cpp: running %s", " ".join(cmd))

    # 执行
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # 读取 stderr 获取进度
    stderr_lines = []
    for line in process.stderr:
        stderr_lines.append(line)
        # whisper.cpp 输出类似: "whisper_print_progress_callback: progress = 42%"
        if "progress =" in line and on_progress:
            try:
                pct = int(line.split("=")[1].strip().rstrip("%"))
                on_progress(pct, 100)
            except (ValueError, IndexError):
                pass

    stdout = process.stdout.read()
    process.wait()

    if process.returncode != 0:
        raise RuntimeError(
            f"whisper.cpp failed (exit {process.returncode}):\n"
            + "".join(stderr_lines[-10:])
        )

    # 解析 JSON 输出
    return _parse_whisper_json(stdout)


def _parse_whisper_json(json_str: str) -> List[Segment]:
    """解析 whisper.cpp 的 JSON 输出为 Segment 列表"""
    data = json.loads(json_str)

    segments = []
    for item in data.get("transcription", []):
        # 时间戳格式: "00:00:01.234" → 秒
        start = _timestamp_to_seconds(item["timestamps"]["from"])
        end = _timestamp_to_seconds(item["timestamps"]["to"])
        text = item["text"].strip()

        if not text:
            continue

        # word-level timestamps (如果有)
        words = []
        for token in item.get("tokens", []):
            if "timestamps" in token and token.get("text", "").strip():
                w_start = _timestamp_to_seconds(token["timestamps"]["from"])
                w_end = _timestamp_to_seconds(token["timestamps"]["to"])
                words.append(Word(
                    text=token["text"].strip(),
                    start=w_start,
                    end=w_end
                ))

        seg = Segment(
            start=start,
            end=end,
            text=text,
            words=words,
            no_speech_prob=item.get("no_speech_prob", 0.0)
        )
        segments.append(seg)

    return segments


def _timestamp_to_seconds(ts: str) -> float:
    """转换 whisper.cpp 时间戳 "HH:MM:SS.mmm" → 秒"""
    parts = ts.split(":")
    h = int(parts[0])
    m = int(parts[1])
    s = float(parts[2])
    return h * 3600 + m * 60 + s
```

### 4.2 修改 `src/transcribe.py`

在 provider 分支中加入 `cpp`：

```python
# 在 transcribe() 函数的 provider 分支中添加：

elif provider == 'cpp':
    from .transcribe_cpp import transcribe_cpp
    segments = transcribe_cpp(audio_path, config)
```

### 4.3 向后兼容

| provider | 后端 | 依赖 | 状态 |
|----------|------|------|------|
| `local` | faster-whisper (PyTorch) | pip install | 保留，开发者用 |
| `cpp` | whisper.cpp (subprocess) | subgen install | **新增**，exe 用户用 |
| `mlx` | mlx-whisper | pip install | 保留，Mac 开发者用 |
| `groq` | Groq API | 内置 | 保留 |
| `openai` | OpenAI API | 内置 | 保留 |

exe 版 wizard 中不显示 `local`（需要 PyTorch）和 `mlx`（需要 pip），只显示 `cpp`、`groq`、`openai`。

---

## 5. CLI 新命令

### 5.1 `subgen install` — 安装组件

```bash
# 安装本地 Whisper 引擎（自动选 CUDA/Metal/CPU）
subgen install whisper

# 安装指定模型
subgen install model large-v3

# 安装 FFmpeg
subgen install ffmpeg

# 一步到位（引擎 + 推荐模型）
subgen install whisper --with-model
```

交互示例：

```
$ subgen install whisper

🔍 Detecting hardware...
  ✓ NVIDIA GeForce RTX 3060 (12GB VRAM)
  ✓ CUDA 12.4

📥 Installing whisper.cpp (CUDA)...
  Downloading: 15.2 MB [==================] 100% (2.1s)
  Verifying checksum... ✓
  Installed to: ~/.subgen/bin/whisper-cpp

💡 No Whisper model found. Install one?
  1. tiny     (75 MB)   — Fast, lower quality
  2. base     (142 MB)  — Balanced for quick tasks
  3. small    (466 MB)  — Good quality
  4. medium   (1.5 GB)  — Great quality
  5. large-v3 (3.1 GB)  — Best quality ⭐ (recommended for 12GB VRAM)

Select model [5]: 5

📥 Downloading Whisper large-v3 model...
  Downloading: 3.1 GB [=========>         ] 31% (ETA: 45s)
```

### 5.2 `subgen doctor` — 诊断环境

```bash
$ subgen doctor

🏥 SubGen Environment Check
═══════════════════════════

  Config:     ~/.subgen/config.yaml ✓
  FFmpeg:     /usr/bin/ffmpeg (7.0.1) ✓
  Whisper:    whisper.cpp CUDA (~/.subgen/bin/) ✓
  Model:      large-v3 (3.1 GB) ✓
  LLM:        Copilot (authenticated) ✓
  GPU:        NVIDIA RTX 3060 (12GB) ✓
  Disk:       ~/.subgen/ using 3.4 GB

  Status: ✅ Ready to go!
```

```bash
$ subgen doctor

🏥 SubGen Environment Check
═══════════════════════════

  Config:     Not found ✗ (run: subgen init)
  FFmpeg:     Not found ✗ (run: subgen install ffmpeg)
  Whisper:    Not configured ✗
  LLM:        Not configured ✗
  GPU:        No NVIDIA GPU detected
  Disk:       ~/.subgen/ not created

  Status: ❌ Run 'subgen init' to get started
```

### 5.3 `subgen uninstall` — 删除组件

```bash
subgen uninstall model large-v3    # 释放 3.1GB
subgen uninstall whisper           # 删除引擎
subgen uninstall ffmpeg
```

### 5.4 `subgen update` — 更新组件

```bash
subgen update               # 检查所有组件更新
subgen update whisper        # 更新 whisper.cpp 引擎
```

---

## 6. Setup Wizard 改造

### 6.1 核心原则：init = 一站式设置

**用户跑完 `subgen init` 后就能直接 `subgen run`。** 所有需要的组件（引擎、模型、FFmpeg、OAuth）都在 init 过程中完成，不需要用户再手动跑 install 命令。

install/doctor/update/uninstall 作为高级管理命令保留，但普通用户不需要碰。

### 6.2 完整 init 流程

```
$ subgen init

🎬 SubGen Setup Wizard
══════════════════════

🔍 Detecting hardware...
  ✓ NVIDIA GeForce RTX 3060 (12GB VRAM)
  ✓ CUDA 12.4

──────────────────────
📢 Step 1/4: Speech Recognition

  How do you want to transcribe audio?

  1. ☁️  Groq (Cloud)        — Free, fast, no GPU needed ⭐
  2. 💻 Local (whisper.cpp)  — Free, offline, needs download (~3.1GB)
  3. ☁️  OpenAI Whisper API  — $0.006/min, most reliable

> 2

📥 Setting up local speech recognition...

  Downloading whisper.cpp engine (CUDA)...
  15.2 MB [██████████████████] 100% ✓

  Recommended model for your GPU (12GB): large-v3 (best quality)
  Other options: tiny (75MB) | base (142MB) | small (466MB) | medium (1.5GB)
  
  Download large-v3? [Y/n]: y
  
  Downloading Whisper large-v3 model...
  3.1 GB [██████████████████] 100% (1m 23s) ✓

  ✅ Local Whisper ready

──────────────────────
🌍 Step 2/4: Translation

  1. 🐙 GitHub Copilot      — Use your Copilot subscription
  2. 💬 ChatGPT Plus/Pro    — Use your ChatGPT subscription
  3. 🔑 OpenAI API          — Pay per use ($0.15/M tokens)
  4. 🇨🇳 DeepSeek           — Cheap, good for Chinese
  5. 🏠 Ollama (Local)      — Free, requires local setup

> 1

  Starting GitHub OAuth login...
  
  👉 Open this URL: https://github.com/login/device
  👉 Enter code: ABCD-1234
  
  Waiting for authorization... ✓
  ✅ GitHub Copilot connected

──────────────────────
🔧 Step 3/4: FFmpeg

  🔍 Checking FFmpeg...
  ✗ FFmpeg not found

  FFmpeg is required for video processing.

  📥 Download FFmpeg automatically? [Y/n]: y

  Downloading FFmpeg...
  80 MB [██████████████████] 100% ✓
  ✅ FFmpeg installed to ~/.subgen/bin/

──────────────────────
🎯 Step 4/4: Defaults

  Target language [zh]: zh
  Enable bilingual subtitles? [y/N]: y
  Default subtitle format (srt/ass/vtt) [srt]: ass
  Style preset (default/netflix/fansub/minimal) [default]: fansub

══════════════════════════════════════════
✅ All set! SubGen is ready to use.
══════════════════════════════════════════

  Summary:
  ────────
  Whisper:   Local (whisper.cpp CUDA + large-v3)
  LLM:       GitHub Copilot (claude-sonnet-4)
  FFmpeg:    ~/.subgen/bin/ffmpeg
  Language:  zh (中文)
  Bilingual: yes
  Format:    ASS (fansub preset)
  Disk used: 3.3 GB (~/.subgen/)

  Config: ~/.subgen/config.yaml

  🚀 Try it now:
    subgen run movie.mp4
```

### 6.3 init 内部逻辑

```python
def run_setup_wizard():
    """一站式设置，完成后用户可以直接 subgen run"""

    cm = ComponentManager()
    hw = detect_hardware()

    # Step 1: Whisper
    whisper_provider = prompt_whisper_choice(hw)

    if whisper_provider == 'cpp':
        # 自动下载引擎（根据硬件选 CUDA/Metal/CPU）
        engine_variant = pick_engine_variant(hw)
        cm.install(f"whisper-cpp-{engine_variant}", on_progress=rich_progress)

        # 自动推荐 + 下载模型
        recommended_model = recommend_model(hw)
        model_choice = prompt_model_choice(recommended_model)
        cm.install(f"model-whisper-{model_choice}", on_progress=rich_progress)

    elif whisper_provider == 'groq':
        groq_key = prompt_api_key("Groq", "https://console.groq.com/keys")

    # Step 2: LLM
    llm_provider = prompt_llm_choice()
    if llm_provider in ('copilot', 'chatgpt'):
        run_oauth(llm_provider)
    elif needs_key(llm_provider):
        api_key = prompt_api_key(llm_provider)

    # Step 3: FFmpeg（自动检测，没有就下载）
    ffmpeg = cm.find_ffmpeg() or shutil.which('ffmpeg')
    if not ffmpeg:
        if confirm("Download FFmpeg automatically?"):
            cm.install("ffmpeg", on_progress=rich_progress)
        else:
            warn("FFmpeg not installed. Video processing won't work.")

    # Step 4: 默认输出设置
    target_lang = prompt("Target language", default="zh")
    bilingual = confirm("Enable bilingual subtitles?", default=False)
    format = prompt_choice("Subtitle format", ["srt", "ass", "vtt"], default="srt")
    if format == "ass":
        preset = prompt_choice("Style preset", ["default", "netflix", "fansub", "minimal"])

    # 保存 config
    save_config(...)
    print_summary(...)
```

### 6.4 重新运行 init

用户可以随时 `subgen init` 重新设置。如果已有配置，显示当前设置并允许修改：

```
$ subgen init

🎬 SubGen Setup Wizard
══════════════════════

  ℹ️ Existing config found. Current settings:
  
    Whisper: Local (whisper.cpp CUDA + large-v3) ✓
    LLM:     GitHub Copilot ✓
    FFmpeg:  ~/.subgen/bin/ffmpeg ✓

  Reconfigure? [y/N]: y
  
  (进入正常 wizard 流程...)
```

### 6.5 `subgen run` 零配置检测

如果用户直接跑 `subgen run` 但没有 config，自动触发 init：

```python
# subgen.py run 命令入口
def run(input_path, ...):
    config = load_config()
    if config is None:
        print("⚠️  No config found. Let's set up SubGen first.\n")
        run_setup_wizard()
        config = load_config()
    # 继续正常流程...
```

---

## 7. 配置文件变更

### 7.1 `config.yaml` 新增字段

```yaml
whisper:
  # provider: groq | openai | cpp | local | mlx
  provider: "cpp"

  # whisper.cpp 专用配置
  cpp_model: "large-v3"     # 模型名称（需已下载）
  cpp_threads: 4            # CPU 线程数
  cpp_gpu_layers: 0         # GPU 加速层数 (0 = 自动)

  # 保留原有配置（向后兼容）
  local_model: "large-v3"   # for provider: local (faster-whisper)
  device: "cuda"
```

### 7.2 路径搜索优先级

exe 模式下，config.yaml 和其他文件的搜索顺序：

```
config.yaml:
  1. --config 命令行参数
  2. 当前目录 ./config.yaml
  3. ~/.subgen/config.yaml

ffmpeg:
  1. ~/.subgen/bin/ffmpeg
  2. PATH 中的 ffmpeg

whisper-cpp:
  1. ~/.subgen/bin/whisper-cpp/whisper-cpp
  2. PATH 中的 whisper-cpp

模型:
  1. ~/.subgen/models/whisper/ggml-{name}.bin
  2. config 中指定的绝对路径
```

---

## 8. whisper.cpp 二进制分发策略

### 8.1 方案：自建 GitHub Release

在 subgen 仓库创建一个独立的 release tag（如 `components-v1`），上传预编译的 whisper.cpp 二进制：

```
Release: components-v1
  ├── whisper-cpp-cuda-windows-x64.zip
  ├── whisper-cpp-cuda-linux-x64.tar.gz
  ├── whisper-cpp-cpu-windows-x64.zip
  ├── whisper-cpp-cpu-linux-x64.tar.gz
  ├── whisper-cpp-cpu-macos-x64.tar.gz
  ├── whisper-cpp-metal-macos-arm64.tar.gz
  ├── components.json              ← 组件注册表
  └── checksums.sha256
```

### 8.2 编译 CI

用 GitHub Actions 编译 whisper.cpp（从 ggml-org/whisper.cpp 源码）：

```yaml
# .github/workflows/build-components.yml
# 手动触发，编译各平台的 whisper-cpp 二进制
# 上传到 components-v* release
```

### 8.3 模型下载

模型直接从 HuggingFace 下载（官方仓库），不需要我们托管：

```
https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{model}.bin
```

---

## 9. 实施计划

### Phase 1：组件管理器（2-3h）
- [ ] `src/components.py` — ComponentManager 核心类
- [ ] `components.json` — 组件注册表（先内置，后远程）
- [ ] `~/.subgen/` 目录结构初始化
- [ ] 下载逻辑：进度条 + SHA256 校验 + 断点续传
- [ ] `installed.json` 状态管理
- [ ] 测试

### Phase 2：whisper.cpp 后端（1-2h）
- [ ] `src/transcribe_cpp.py` — subprocess 调用 whisper-cpp
- [ ] 修改 `src/transcribe.py` 加入 `cpp` provider
- [ ] JSON 输出解析 → Segment 列表
- [ ] 进度回调（解析 stderr 进度）
- [ ] 测试

### Phase 3：CLI 命令（1-2h）
- [ ] `subgen install` — 安装组件
- [ ] `subgen uninstall` — 删除组件
- [ ] `subgen doctor` — 环境诊断
- [ ] `subgen update` — 更新组件
- [ ] 修改 wizard 适配 exe 模式

### Phase 4：打包 + CI（2-3h）
- [ ] `subgen.spec` — PyInstaller 配置
- [ ] `.github/workflows/release.yml` — 自动打包 4 平台 exe
- [ ] `.github/workflows/build-components.yml` — 编译 whisper-cpp 二进制
- [ ] 测试发布流程
- [ ] 更新 README 加下载说明

### Phase 5：验证（1h）
- [ ] Windows exe 测试
- [ ] macOS arm64 测试
- [ ] Linux x64 测试
- [ ] 全流程：下载 exe → init → install whisper → run video.mp4

**总计约 8-12h 工作量。**

---

## 10. 注意事项

- **杀毒软件**：PyInstaller 打包的 exe 可能被误报，需要签名或上传 VirusTotal 白名单
- **macOS Gatekeeper**：需要 codesign 或告知用户 `xattr -d com.apple.quarantine subgen`
- **CUDA 版本兼容**：whisper-cpp CUDA 版编译时绑定特定 CUDA 版本，需要提供多版本或用 CUDA runtime 动态链接
- **模型许可**：Whisper 模型是 MIT 许可，可以自由分发
- **断点续传**：大模型文件（3.1GB）下载中断很常见，必须支持 HTTP Range 续传
