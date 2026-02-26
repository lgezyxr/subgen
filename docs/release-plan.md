# SubGen Release Plan — No-Install Executables

> Goal: Users download a single file and can start using it immediately — no Python, pip, or dependencies needed.

[中文版](zh/release-plan.md)

---

## 1. Packaging Approach: PyInstaller

**Why PyInstaller:**
- Mature, stable, large community
- Supports Windows / macOS / Linux
- Can build single file (`--onefile`) or single directory (`--onedir`)
- Supports hiding console window (useful for future GUI)

**Build artifacts:**

| Platform | File | Estimated Size |
|----------|------|---------------|
| Windows | `subgen.exe` | ~50-80MB |
| macOS (Intel) | `subgen-macos-x64` | ~50-80MB |
| macOS (Apple Silicon) | `subgen-macos-arm64` | ~50-80MB |
| Linux | `subgen-linux-x64` | ~50-80MB |

> Note: Size mainly comes from Python runtime + dependencies. Including faster-whisper + PyTorch would push it to ~500MB+, so the **base package excludes local Whisper**. Users use cloud Whisper (Groq is free) or install the local whisper.cpp component via `subgen install`.

---

## 2. Packaging Strategy

### 2.1 Lightweight Version (Recommended for Initial Release)

Includes only core features, excludes PyTorch/faster-whisper:

```
Included:
  ✅ CLI interface (click + rich)
  ✅ Translation (openai, anthropic, httpx, requests)
  ✅ Subtitle generation/styles/project files
  ✅ Cloud Whisper (Groq, OpenAI API)
  ✅ OAuth login (Copilot, ChatGPT)
  ✅ Component system (on-demand download)
  ✅ FFmpeg auto-download

Excluded:
  ❌ faster-whisper / PyTorch (too large, 500MB+)
  ❌ MLX (Apple Silicon only)
```

Users run `subgen init` on first launch, which guides them to select Groq (free, fast, no GPU needed) or install local whisper.cpp as the Whisper backend.

### 2.2 Full Version (Future Consideration)

If demand is high, a Windows full version with CUDA (~800MB) could be released, but it's low priority.

---

## 3. PyInstaller Configuration

### 3.1 Spec File: `subgen.spec`

```python
# subgen.spec
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect required data files
datas = [
    ('config.example.yaml', '.'),
    ('rules/', 'rules/'),
]

# Hidden imports (dynamically imported modules)
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

# Exclude large unneeded modules
excludes = [
    'torch', 'torchaudio', 'torchvision',
    'faster_whisper', 'ctranslate2',
    'mlx', 'mlx_whisper',
    'numpy',
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
    upx=True,
    console=True,
    icon=None,
)
```

### 3.2 Issues to Address

| Issue | Solution |
|-------|----------|
| `config.yaml` path | Read from exe directory or `~/.subgen/config.yaml` after packaging |
| OAuth token storage | Already uses `~/.subgen/` directory; unaffected |
| Cache file path | Kept in video's directory `.subgen_cache/`; unaffected |
| FFmpeg dependency | Auto-download via component system, or detect in PATH |
| `rules/` translation rules | Bundled inside exe, accessed via `sys._MEIPASS` path |
| Dynamic imports (providers) | Declared explicitly via `hiddenimports` |

### 3.3 Code Adaptation

Path detection needs to be added to `src/config.py` and the entry file:

```python
import sys
from pathlib import Path

def get_app_dir() -> Path:
    """Get application directory (compatible with PyInstaller packaging)"""
    if getattr(sys, 'frozen', False):
        # Packaged: exe's directory
        return Path(sys.executable).parent
    else:
        # Development mode: project root
        return Path(__file__).parent.parent

def get_bundled_path(relative: str) -> Path:
    """Get path to bundled resource files"""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / relative
    else:
        return Path(__file__).parent.parent / relative
```

---

## 4. GitHub Actions Auto-Release

### 4.1 Trigger Condition

Triggered on tag push (e.g., `v0.2.0`):

```yaml
on:
  push:
    tags: ['v*']
```

### 4.2 Workflow File: `.github/workflows/release.yml`

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

### 4.3 Release Process

```bash
# 1. Ensure code is merged to main and CI passes
# 2. Update version number (pyproject.toml or __version__)
# 3. Tag and push
git tag v0.2.0
git push origin v0.2.0

# 4. GitHub Actions automatically:
#    → Builds on 4 platforms
#    → Creates GitHub Release
#    → Uploads 4 executables
#    → Auto-generates changelog

# 5. Users download the platform-appropriate file from GitHub Releases
```

---

## 5. User Experience

### Post-Download Usage Flow

```bash
# Windows
subgen.exe init                              # First-time setup
subgen.exe run movie.mp4 --to zh             # Generate subtitles

# macOS / Linux
chmod +x subgen-macos-arm64                  # Add execute permission
./subgen-macos-arm64 init
./subgen-macos-arm64 run movie.mp4 --to zh
```

### Prerequisites

- **FFmpeg**: Auto-downloaded by `subgen init`, or install manually
  - Windows: `winget install ffmpeg` or download exe
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`
- **Network**: Required for API access (Groq/OpenAI/Copilot etc.)

### `subgen init` Guided Setup

On first launch of the packaged version, the wizard starts automatically:
1. Detect/download FFmpeg
2. Select Whisper backend → recommends Groq (free, no GPU needed) or local whisper.cpp
3. Select LLM → recommends Copilot (uses GitHub subscription)
4. Set target language
5. Save config to `~/.subgen/config.yaml`

---

## 6. Implementation Steps

### Phase 1: Code Adaptation (1-2h)
- [ ] Add `get_app_dir()` / `get_bundled_path()` path utility functions
- [ ] Add `~/.subgen/config.yaml` to config.yaml search path
- [ ] Make rules/ file loading compatible with `sys._MEIPASS`
- [ ] Add `__version__` variable
- [ ] Test PyInstaller packaging locally

### Phase 2: CI/CD Configuration (1h)
- [ ] Create `subgen.spec`
- [ ] Create `.github/workflows/release.yml`
- [ ] Test by pushing a `v0.2.0-beta` tag to verify the process

### Phase 3: First Release (30min)
- [ ] Fix any packaging issues
- [ ] Push `v0.2.0` tag
- [ ] Verify all 4 platform artifacts work correctly
- [ ] Update README with download links

---

## 7. Future Enhancements

- **Auto-update check**: Check GitHub Releases for new versions on startup
- **Bundled FFmpeg**: Include ffmpeg in the package (~50MB increase)
- **Windows installer**: Use NSIS or Inno Setup for installer package (adds PATH, desktop shortcut)
- **Homebrew formula**: `brew install subgen`
- **GUI version**: Tauri packaging follows the same release process
