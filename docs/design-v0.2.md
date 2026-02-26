# SubGen v0.2 — Architecture Refactor & GUI-Compatible Design Document

> Goal: Refactor the core architecture so CLI and future GUI share the same business logic; add a style system supporting bilingual top/bottom layout with font/color customization.

[中文版](zh/design-v0.2.md)

---

## 1. Current State Analysis

### Current Architecture

```
subgen.py (CLI + business logic mixed, 757 lines)
├── run_subtitle_generation()   ← All workflow logic lives here
│   ├── load_config()
│   ├── extract_audio()
│   ├── transcribe_audio()
│   ├── translate_segments()
│   ├── proofread_translations()
│   └── generate_subtitle()
└── CLI definitions (click)
```

### Problems

1. **CLI and core logic coupled** — `subgen.py` mixes click argument parsing, config overrides, progress bars, error handling, and business workflow. GUI cannot reuse it.
2. **Hardcoded styles** — ASS font, color, and size are hardcoded in `subtitle.py`; users cannot customize.
3. **Crude bilingual layout** — Uses two Dialogue lines + MarginV separation; spacing is unstable across resolutions.
4. **No project file concept** — Cannot save intermediate state for GUI editing.
5. **Progress notifications tied to rich** — GUI needs a different progress callback mechanism.

---

## 2. Target Architecture

```
subgen.py                    ← CLI thin shell (parse args → call engine)
src/
├── engine.py                ← [NEW] Core engine, all business workflow
├── project.py               ← [NEW] SubtitleProject data model
├── styles.py                ← [NEW] StyleProfile + preset styles
├── transcribe.py            ←  Unchanged
├── translate.py             ←  Unchanged
├── subtitle.py              ← [MODIFIED] Render functions accept StyleProfile
├── config.py                ← [MODIFIED] Add styles config parsing
├── audio.py                 ←  Unchanged
├── cache.py                 ←  Unchanged
├── embedded.py              ←  Unchanged
├── hardware.py              ←  Unchanged
├── logger.py                ←  Unchanged
├── wizard.py                ←  Unchanged
├── auth/                    ←  Unchanged
└── providers/               ←  Unchanged
```

### Call Graph

```
CLI (click)  ─┐
              ├──→  SubGenEngine  ──→  transcribe / translate / subtitle / styles
GUI (Tauri)  ─┘         │
                         ↓
                  SubtitleProject (data container)
                    ├── segments[]
                    ├── style_profile
                    └── metadata
```

---

## 3. New Module Detailed Design

### 3.1 `src/project.py` — Project Data Model

SubtitleProject is the data bridge between CLI and GUI.

```python
@dataclass
class SubtitleProject:
    """Subtitle project — shared data container for CLI and GUI"""

    # Core data
    segments: List[Segment]           # Subtitle segments (timeline + source + translation)
    style: StyleProfile               # Style configuration

    # Metadata
    video_path: Optional[str]         # Source video path
    source_lang: str                  # Source language
    target_lang: str                  # Target language
    whisper_provider: str             # Whisper backend used
    llm_provider: str                 # LLM used
    llm_model: str                    # Model used
    created_at: str                   # Creation time (ISO 8601)
    modified_at: str                  # Last modified time

    # State
    is_transcribed: bool = False
    is_translated: bool = False
    is_proofread: bool = False

    # Serialization
    def save(self, path: Path) -> None:
        """Save as .subgen project file (JSON)"""

    @classmethod
    def load(cls, path: Path) -> 'SubtitleProject':
        """Load from .subgen file"""

    def to_dict(self) -> dict:
        """Serialize to dict (for GUI JSON API)"""

    @classmethod
    def from_dict(cls, data: dict) -> 'SubtitleProject':
        """Deserialize from dict"""
```

**Project file format** (`.subgen`, actually JSON):

```json
{
  "version": "0.2.0",
  "metadata": {
    "video_path": "/path/to/video.mp4",
    "source_lang": "en",
    "target_lang": "zh",
    "whisper_provider": "local",
    "llm_provider": "copilot",
    "llm_model": "claude-sonnet-4.6",
    "created_at": "2026-02-26T10:00:00Z",
    "modified_at": "2026-02-26T10:30:00Z"
  },
  "state": {
    "is_transcribed": true,
    "is_translated": true,
    "is_proofread": false
  },
  "style": {
    "preset": "default",
    "primary": { "font": "Microsoft YaHei", "size": 60, "color": "#FFFFFF" },
    "secondary": { "font": "Arial", "size": 45, "color": "#00BFFF" }
  },
  "segments": [
    {
      "start": 1.0,
      "end": 3.5,
      "text": "Hello world",
      "translated": "你好世界",
      "words": [
        { "text": "Hello", "start": 1.0, "end": 1.5 },
        { "text": "world", "start": 1.6, "end": 2.0 }
      ]
    }
  ]
}
```

### 3.2 `src/styles.py` — Style System

```python
@dataclass
class FontStyle:
    """Style for a single text layer"""
    font: str = "Arial"
    size: int = 60
    color: str = "#FFFFFF"           # Standard hex, internally converted to ASS format
    bold: bool = False
    italic: bool = False
    outline: float = 3.0
    outline_color: str = "#000000"
    shadow: float = 1.0
    shadow_color: str = "#80000000"  # With alpha

@dataclass
class StyleProfile:
    """Complete style configuration"""
    name: str = "default"

    # Primary subtitle (translated text)
    primary: FontStyle = field(default_factory=lambda: FontStyle(
        font="Arial", size=60, color="#FFFFFF", bold=False, outline=3.0
    ))

    # Secondary subtitle (original text, displayed in bilingual mode)
    secondary: FontStyle = field(default_factory=lambda: FontStyle(
        font="Arial", size=45, color="#AAAAAA", bold=False, outline=2.0
    ))

    # Layout
    alignment: int = 2               # ASS alignment: 2=bottom center
    margin_left: int = 10
    margin_right: int = 10
    margin_bottom: int = 30
    line_spacing: int = 10           # Bilingual line spacing

    # Resolution
    play_res_x: int = 1920
    play_res_y: int = 1080

    # Serialization
    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> 'StyleProfile': ...

    # Helper methods
    def to_ass_header(self) -> str:
        """Generate ASS [Script Info] + [V4+ Styles] section"""

    @staticmethod
    def hex_to_ass_color(hex_color: str) -> str:
        """'#RRGGBB' or '#AARRGGBB' → ASS '&HAABBGGRR' format"""

# ========== Presets ==========

PRESETS: Dict[str, StyleProfile] = {
    "default": StyleProfile(),

    "netflix": StyleProfile(
        name="netflix",
        primary=FontStyle(
            font="Netflix Sans", size=56, color="#FFFFFF",
            bold=False, outline=2.5, outline_color="#000000"
        ),
        secondary=FontStyle(
            font="Netflix Sans", size=42, color="#CCCCCC",
            bold=False, outline=2.0
        ),
        margin_bottom=40
    ),

    "fansub": StyleProfile(
        name="fansub",
        primary=FontStyle(
            font="方正黑体简体", size=64, color="#FFEEDD",
            bold=True, outline=3.0, outline_color="#333333"
        ),
        secondary=FontStyle(
            font="Arial", size=40, color="#66CCFF",
            bold=False, italic=True, outline=1.5
        ),
        margin_bottom=25
    ),

    "minimal": StyleProfile(
        name="minimal",
        primary=FontStyle(
            font="Helvetica Neue", size=52, color="#FFFFFF",
            bold=False, outline=0, shadow=2.0
        ),
        secondary=FontStyle(
            font="Helvetica Neue", size=38, color="#BBBBBB",
            bold=False, outline=0, shadow=1.5
        ),
        margin_bottom=35
    ),
}

def load_style(config: dict) -> StyleProfile:
    """
    Load style from the styles block in config.yaml.
    Supports preset inheritance + partial overrides.
    """
```

### 3.3 `src/engine.py` — Core Engine

```python
from typing import Callable, Optional
from pathlib import Path
from .project import SubtitleProject
from .styles import StyleProfile

# Progress callback type
ProgressCallback = Callable[[str, int, int], None]
# callback(stage, current, total)
# stage: "extracting" | "transcribing" | "translating" | "proofreading" | "exporting"

class SubGenEngine:
    """SubGen core engine — shared by CLI and GUI"""

    def __init__(self, config: dict, on_progress: Optional[ProgressCallback] = None):
        self.config = config
        self.on_progress = on_progress or (lambda *_: None)

    def run(self, input_path: Path, **options) -> SubtitleProject:
        """
        Full pipeline: video → transcription → translation → proofreading → return Project

        options:
            source_lang, target_lang, no_translate, sentence_aware,
            proofread, bilingual, force_transcribe, ...

        Returns SubtitleProject; does not write files directly. Caller decides how to handle output.
        """

    def transcribe(self, input_path: Path, **options) -> SubtitleProject:
        """Transcribe only, return Project"""

    def translate(self, project: SubtitleProject, **options) -> SubtitleProject:
        """Translate an existing Project"""

    def proofread(self, project: SubtitleProject) -> SubtitleProject:
        """Proofread an existing Project"""

    def export(self,
               project: SubtitleProject,
               output_path: Path,
               format: str = 'srt',
               style: Optional[StyleProfile] = None) -> Path:
        """
        Export subtitle file.

        The style parameter can override the project's built-in style_profile.
        GUI scenario: user adjusts style for real-time preview, pass new style.
        """

    def export_video(self,
                     project: SubtitleProject,
                     video_path: Path,
                     output_path: Path,
                     embed_mode: str = 'soft') -> Path:
        """
        Export video with subtitles.
        embed_mode: 'soft' (subtitle track) | 'hard' (burn in)
        """
```

**Engine usage example (CLI):**

```python
# subgen.py becomes:
engine = SubGenEngine(config=cfg, on_progress=rich_progress_callback)
project = engine.run(input_path, target_lang='zh', sentence_aware=True)
engine.export(project, output_path, format='ass')
```

**Engine usage example (GUI):**

```python
# Tauri backend / FastAPI
engine = SubGenEngine(config=cfg, on_progress=websocket_push)
project = engine.run(input_path, target_lang='zh')

# User manually edits the 5th subtitle
project.segments[4].translated = "User-modified translation"

# User adjusts font color
project.style.primary.color = "#FFD700"

# Real-time preview
engine.export(project, preview_path, format='ass')

# Save project
project.save(Path("my_movie.subgen"))
```

---

## 4. Modified Module Detailed Design

### 4.1 `src/subtitle.py` — Rendering Refactor

**Key changes:**

1. `generate_subtitle()` gets a new `style` parameter (optional, backward compatible)
2. ASS generation no longer hardcodes headers; calls `style.to_ass_header()` instead
3. Bilingual mode changed to **single Dialogue + `\N` line break + inline style override**

```python
def generate_subtitle(
    segments: List[Segment],
    output_path: Path,
    config: Dict[str, Any],
    style: Optional[StyleProfile] = None    # New, optional
) -> None:
    """
    Generate subtitle file.

    If style is provided, use the specified style.
    If not provided, load style from config (backward compatible).
    """
```

**ASS bilingual rendering changed to:**

```
Translation on top, original below, same Dialogue line, using \N line break + inline style switch:

Dialogue: 0,0:01:00.00,0:01:03.00,Default,,0,0,0,,你好世界\N{\fnArial\fs45\c&HFFBF00&}Hello World
```

Benefits:
- Two lines are perfectly aligned; no drift across resolutions
- Single Dialogue entry; easier to manage in editors
- Inline style only overrides the secondary subtitle; primary style defined in Style section

### 4.2 `src/config.py` — Style Configuration

New `styles` block in config.yaml:

```yaml
# config.yaml

# ...existing config unchanged...

# [NEW] Style configuration
styles:
  preset: "default"        # Preset: default / netflix / fansub / minimal
  primary:                 # Override primary subtitle (translation) style
    font: "Microsoft YaHei"
    size: 60
    color: "#FFFFFF"
    bold: true
    outline: 3
    outline_color: "#000000"
  secondary:               # Override secondary subtitle (original) style
    font: "Arial"
    size: 45
    color: "#00BFFF"
    bold: false
    outline: 2
  margin_bottom: 30
  line_spacing: 10
```

**Loading logic:** Load preset as base, then overlay user-configured fields. If no `styles` block is present, use the default preset — **100% backward compatible**.

### 4.3 `subgen.py` — CLI Slimming

After refactoring, `subgen.py` responsibilities are limited to:
1. Define click commands and parameters
2. Parse arguments, build config
3. Create SubGenEngine, pass in rich progress callback
4. Call engine methods
5. Output results to terminal

Goal: Reduce from 757 lines to ~200 lines.

**New CLI options:**

```bash
# Style-related
--style-preset <name>     # Select style preset
--primary-font <name>     # Override primary subtitle font
--primary-color <hex>     # Override primary subtitle color
--secondary-font <name>   # Override secondary subtitle font
--secondary-color <hex>   # Override secondary subtitle color

# Project-related
--save-project            # Save .subgen project file alongside export
--load-project <path>     # Load from project file and continue

# Usage example
subgen run movie.mp4 --to zh -s --bilingual \
  --style-preset fansub \
  --primary-font "方正黑体" \
  --secondary-color "#66CCFF" \
  --save-project
```

---

## 5. Backward Compatibility Guarantees

| Scenario | Compatibility |
|----------|---------------|
| No `styles` block in config | ✅ Uses default preset; output identical to before |
| No `--style-*` CLI arguments | ✅ Falls back to config.yaml or default |
| Old `generate_subtitle(segments, path, config)` calls | ✅ style parameter is optional; loads from config if omitted |
| Old cache files | ✅ Cache format is append-only; old caches read normally |
| Calling functions directly without Engine | ✅ Original function signatures preserved, marked deprecated |

---

## 6. GUI Compatibility Design Points

Although GUI is not being built now, the architecture must ensure these capabilities:

### 6.1 Real-Time Preview
```
User adjusts style → build new StyleProfile → engine.export(project, style=new_style)
```
Export a temporary ASS; player loads it in real time. No re-transcription/translation needed.

### 6.2 Per-Segment Editing
```
project.segments[i].translated = "New translation"
project.segments[i].start = 1.5  # Adjust timeline
```
Segments are plain dataclasses; edit fields directly.

### 6.3 Project Save/Restore
```
project.save("movie.subgen")
project = SubtitleProject.load("movie.subgen")
```
JSON format; GUI can implement auto-save independently.

### 6.4 Progress Push
```
engine = SubGenEngine(config, on_progress=my_callback)
```
CLI passes a rich callback; GUI passes a websocket/IPC callback. Engine doesn't care about the implementation.

### 6.5 Batch Operations (Future)
```
for video in videos:
    project = engine.run(video)
    engine.export(project, ...)
```
Engine is stateless and can be called in a loop.

---

## 7. Implementation Plan

### Phase 1: Data Layer (No behavior changes)
- [ ] Create `src/styles.py` — StyleProfile + FontStyle + presets + hex↔ASS conversion
- [ ] Create `src/project.py` — SubtitleProject data model + serialization
- [ ] Add tests `tests/test_styles.py` and `tests/test_project.py`

### Phase 2: Rendering Layer (Modify subtitle.py)
- [ ] Modify `subtitle.py` `_generate_ass()` to accept StyleProfile
- [ ] Implement `StyleProfile.to_ass_header()` to generate ASS headers
- [ ] Change bilingual mode to single Dialogue + `\N` + inline style
- [ ] Add optional `style` parameter to `generate_subtitle()` (backward compatible)
- [ ] Add tests `tests/test_subtitle_styles.py`

### Phase 3: Engine Layer (Refactor core workflow)
- [ ] Create `src/engine.py` — SubGenEngine encapsulating all business workflow
- [ ] Abstract progress callback: `ProgressCallback` type
- [ ] Extract logic from `subgen.py` `run_subtitle_generation()` into engine
- [ ] Slim `subgen.py` down to CLI thin shell

### Phase 4: Config & CLI (User-facing features)
- [ ] Add `styles` config block support in `config.py`
- [ ] Add style examples to `config.example.yaml`
- [ ] Add CLI options: `--style-preset`, `--primary-font`, `--primary-color`, etc.
- [ ] Add CLI options: `--save-project` / `--load-project`
- [ ] Update documentation `docs/configuration.md`

### After each Phase:
- Ensure all existing tests pass
- Ensure `subgen run movie.mp4 --to zh` behavior is identical to pre-refactor
- Commit to a separate branch; merge after PR review

---

## 8. File Impact Summary

| File | Change Type | Description |
|------|------------|-------------|
| `src/styles.py` | **New** | StyleProfile, FontStyle, presets |
| `src/project.py` | **New** | SubtitleProject data model |
| `src/engine.py` | **New** | SubGenEngine core engine |
| `src/subtitle.py` | **Modified** | ASS rendering supports StyleProfile; bilingual uses `\N` |
| `src/config.py` | **Modified** | Add styles config parsing |
| `subgen.py` | **Modified** | Slimmed to CLI thin shell |
| `config.example.yaml` | **Modified** | Add styles examples |
| `tests/test_styles.py` | **New** | Style system tests |
| `tests/test_project.py` | **New** | Project model tests |
| `tests/test_subtitle_styles.py` | **New** | Style rendering tests |
| `docs/configuration.md` | **Modified** | Style configuration docs |
| All other files | **Unchanged** | transcribe, translate, audio, cache, etc. |
