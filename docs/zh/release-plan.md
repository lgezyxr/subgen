# SubGen Release 计划 — 免安装可执行文件

> 目标：用户下载一个文件就能用，不需要装 Python、pip、任何依赖。

---

## 1. 打包方案：PyInstaller

**为什么选 PyInstaller：**
- 成熟稳定，社区大
- 支持 Windows / macOS / Linux
- 可打成单文件（`--onefile`）或单目录（`--onedir`）
- 支持隐藏控制台窗口（GUI 以后用得到）

**打包产物：**

| 平台 | 文件 | 预估大小 |
|------|------|---------|
| Windows | `subgen.exe` | ~50-80MB |
| macOS (Intel) | `subgen-macos-x64` | ~50-80MB |
| macOS (Apple Silicon) | `subgen-macos-arm64` | ~50-80MB |
| Linux | `subgen-linux-x64` | ~50-80MB |

> 注：大小主要来自 Python runtime + 依赖。如果包含 faster-whisper + PyTorch 会更大（~500MB+），所以建议 **基础包不含本地 Whisper**，用户用云端 Whisper（Groq 免费）或自行安装本地环境。

---

## 2. 打包策略

### 2.1 轻量版（推荐首发）

只包含核心功能，不含 PyTorch/faster-whisper：

```
包含：
  ✅ CLI 界面 (click + rich)
  ✅ 翻译 (openai, anthropic, httpx, requests)
  ✅ 字幕生成/样式/项目文件
  ✅ 云端 Whisper (Groq, OpenAI API)
  ✅ OAuth 登录 (Copilot, ChatGPT)
  ✅ FFmpeg 调用（需用户自行安装 FFmpeg）

不含：
  ❌ faster-whisper / PyTorch（太大，500MB+）
  ❌ MLX（仅 Apple Silicon）
```

用户首次运行 `subgen init`，引导选 Groq（免费、快速、不需 GPU）作为 Whisper 后端。

### 2.2 完整版（以后考虑）

如果需求量大，可以出含 CUDA 的 Windows 完整版（~800MB），但优先级低。

---

## 3. PyInstaller 配置

### 3.1 spec 文件：`subgen.spec`

```python
# subgen.spec
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# 收集所有需要的数据文件
datas = [
    ('config.example.yaml', '.'),
    ('rules/', 'rules/'),
]

# 隐式导入（动态 import 的模块）
hidden_imports = [
    'src.auth.copilot',
    'src.auth.openai_codex',
    'src.auth.store',
    'src.providers',
    'yaml',
    'click',
    'rich',
    'rich.console',
    'rich.progress',
    'openai',
    'anthropic',
    'httpx',
    'requests',
]

# 排除不需要的大模块
excludes = [
    'torch', 'torchaudio', 'torchvision',
    'faster_whisper', 'ctranslate2',
    'mlx', 'mlx_whisper',
    'numpy',  # 如果不用本地 whisper 则不需要
    'matplotlib', 'scipy', 'pandas',
    'tkinter', 'unittest',
]

a = Analysis(
    ['subgen.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='subgen',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,           # 压缩，减小体积
    console=True,        # CLI 工具需要控制台
    icon=None,           # 以后加图标
)
```

### 3.2 需要解决的问题

| 问题 | 方案 |
|------|------|
| `config.yaml` 路径 | 打包后从 exe 同目录 或 `~/.subgen/config.yaml` 读取 |
| OAuth token 存储 | 已用 `~/.subgen/` 目录，不受影响 |
| 缓存文件路径 | 保持在视频同目录 `.subgen_cache/`，不受影响 |
| FFmpeg 依赖 | 检测 PATH 中是否有 ffmpeg，没有则提示安装 |
| `rules/` 翻译规则 | 打包到 exe 内部，用 `sys._MEIPASS` 路径访问 |
| 动态 import（providers） | 用 `hiddenimports` 显式声明 |

### 3.3 代码适配

需要在 `src/config.py` 和入口文件加一个路径检测：

```python
import sys
from pathlib import Path

def get_app_dir() -> Path:
    """获取应用目录（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        # 打包后，exe 同目录
        return Path(sys.executable).parent
    else:
        # 开发模式，项目根目录
        return Path(__file__).parent.parent

def get_bundled_path(relative: str) -> Path:
    """获取打包内的资源文件路径"""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / relative
    else:
        return Path(__file__).parent.parent / relative
```

---

## 4. GitHub Actions 自动发布

### 4.1 触发条件

推送 tag 时触发（如 `v0.2.0`）：

```yaml
on:
  push:
    tags: ['v*']
```

### 4.2 workflow 文件：`.github/workflows/release.yml`

```yaml
name: Build & Release

on:
  push:
    tags: ['v*']

permissions:
  contents: write

jobs:
  build:
    strategy:
      matrix:
        include:
          - os: windows-latest
            artifact: subgen-windows-x64.exe
            pyinstaller_args: ""
          - os: macos-13          # Intel
            artifact: subgen-macos-x64
            pyinstaller_args: ""
          - os: macos-latest      # Apple Silicon
            artifact: subgen-macos-arm64
            pyinstaller_args: ""
          - os: ubuntu-latest
            artifact: subgen-linux-x64
            pyinstaller_args: ""

    runs-on: ${{ matrix.os }}

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install pyinstaller
          pip install pyyaml rich click openai anthropic httpx requests groq

      - name: Build executable
        run: |
          pyinstaller subgen.spec

      - name: Rename artifact
        run: |
          mv dist/subgen* dist/${{ matrix.artifact }}
        shell: bash

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.artifact }}
          path: dist/${{ matrix.artifact }}

  release:
    needs: build
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Download all artifacts
        uses: actions/download-artifact@v4
        with:
          path: dist/

      - name: Create Release
        uses: softprops/action-gh-release@v2
        with:
          files: dist/**/*
          generate_release_notes: true
          draft: false
          prerelease: false
```

### 4.3 发布流程

```bash
# 1. 确保代码已合并到 main，CI 通过
# 2. 更新版本号（pyproject.toml 或 __version__）
# 3. 打 tag 并 push
git tag v0.2.0
git push origin v0.2.0

# 4. GitHub Actions 自动：
#    → 在 4 个平台打包
#    → 创建 GitHub Release
#    → 上传 4 个可执行文件
#    → 自动生成 changelog

# 5. 用户在 GitHub Releases 页面下载对应平台的文件
```

---

## 5. 用户体验

### 下载后的使用流程

```bash
# Windows
subgen.exe init                              # 首次设置
subgen.exe run movie.mp4 --to zh             # 生成字幕

# macOS / Linux
chmod +x subgen-macos-arm64                  # 添加执行权限
./subgen-macos-arm64 init
./subgen-macos-arm64 run movie.mp4 --to zh
```

### 前置要求

- **FFmpeg**：仍然需要用户安装（用于音频提取和字幕嵌入）
  - Windows: `winget install ffmpeg` 或下载 exe
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`
- **网络**：需要能访问 API（Groq/OpenAI/Copilot 等）

### `subgen init` 引导

打包版首次运行时，wizard 自动启动：
1. 检测 FFmpeg → 没有则提示安装
2. 选 Whisper 后端 → 推荐 Groq（免费、无需 GPU）
3. 选 LLM → 推荐 Copilot（用 GitHub 订阅）
4. 设置目标语言
5. 保存 config 到 `~/.subgen/config.yaml`

---

## 6. 实施步骤

### Phase 1：代码适配（1-2h）
- [ ] 添加 `get_app_dir()` / `get_bundled_path()` 路径工具函数
- [ ] config.yaml 搜索路径加入 `~/.subgen/config.yaml`
- [ ] rules/ 文件加载兼容 `sys._MEIPASS`
- [ ] 添加 `__version__` 变量
- [ ] 本地测试 PyInstaller 打包

### Phase 2：CI/CD 配置（1h）
- [ ] 创建 `subgen.spec`
- [ ] 创建 `.github/workflows/release.yml`
- [ ] 测试推一个 `v0.2.0-beta` tag 验证流程

### Phase 3：首次发布（30min）
- [ ] 修复可能的打包问题
- [ ] 推 `v0.2.0` tag
- [ ] 验证 4 个平台的产物都能正常运行
- [ ] 更新 README 加下载链接

---

## 7. 以后的增强

- **自动更新检查**：启动时检查 GitHub Releases 有没有新版本
- **FFmpeg 内置**：打包时把 ffmpeg 一起打进去（体积会增加 ~50MB）
- **Windows 安装器**：用 NSIS 或 Inno Setup 做安装包（加 PATH、桌面快捷方式）
- **Homebrew formula**：`brew install subgen`
- **GUI 版本**：Tauri 打包后也走同样的 release 流程
