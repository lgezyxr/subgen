# SubGen v0.2 — 架构重构 & GUI 兼容设计文档

> 目标：重构核心架构，使 CLI 和未来 GUI 共享同一套业务逻辑；同时新增样式系统，支持双语上下排列和字体/颜色自定义。

---

## 1. 现状分析

### 当前架构

```
subgen.py (CLI + 业务逻辑混合，757 行)
├── run_subtitle_generation()   ← 所有流程逻辑都在这里
│   ├── load_config()
│   ├── extract_audio()
│   ├── transcribe_audio()
│   ├── translate_segments()
│   ├── proofread_translations()
│   └── generate_subtitle()
└── CLI 定义 (click)
```

### 问题

1. **CLI 和核心逻辑耦合** — `subgen.py` 里 click 参数解析、config 覆盖、进度条、错误处理、业务流程全部混在一起。GUI 无法复用。
2. **样式硬编码** — ASS 的字体、颜色、大小写死在 `subtitle.py` 里，用户无法自定义。
3. **双语排列简陋** — 用两条 Dialogue + MarginV 分离，不同分辨率下间距不稳定。
4. **没有项目文件概念** — 无法保存中间状态供 GUI 编辑。
5. **进度通知硬绑 rich** — GUI 需要不同的进度回调方式。

---

## 2. 目标架构

```
subgen.py                    ← CLI 薄壳（参数解析 → 调 engine）
src/
├── engine.py                ← 【新增】核心引擎，所有业务流程
├── project.py               ← 【新增】SubtitleProject 数据模型
├── styles.py                ← 【新增】StyleProfile + 预设样式
├── transcribe.py            ←  不变
├── translate.py             ←  不变
├── subtitle.py              ← 【改】渲染函数接收 StyleProfile
├── config.py                ← 【改】新增 styles 配置解析
├── audio.py                 ←  不变
├── cache.py                 ←  不变
├── embedded.py              ←  不变
├── hardware.py              ←  不变
├── logger.py                ←  不变
├── wizard.py                ←  不变
├── auth/                    ←  不变
└── providers/               ←  不变
```

### 调用关系

```
CLI (click)  ─┐
              ├──→  SubGenEngine  ──→  transcribe / translate / subtitle / styles
GUI (Tauri)  ─┘         │
                         ↓
                  SubtitleProject（数据容器）
                    ├── segments[]
                    ├── style_profile
                    └── metadata
```

---

## 3. 新增模块详细设计

### 3.1 `src/project.py` — 项目数据模型

SubtitleProject 是 CLI 和 GUI 之间的数据桥梁。

```python
@dataclass
class SubtitleProject:
    """字幕项目 — CLI 和 GUI 共用的数据容器"""

    # 核心数据
    segments: List[Segment]           # 字幕段落（时间轴 + 原文 + 翻译）
    style: StyleProfile               # 样式配置

    # 元数据
    video_path: Optional[str]         # 源视频路径
    source_lang: str                  # 源语言
    target_lang: str                  # 目标语言
    whisper_provider: str             # 使用的 Whisper 后端
    llm_provider: str                 # 使用的 LLM
    llm_model: str                    # 使用的模型
    created_at: str                   # 创建时间 (ISO 8601)
    modified_at: str                  # 最后修改时间

    # 状态
    is_transcribed: bool = False      # 是否已转录
    is_translated: bool = False       # 是否已翻译
    is_proofread: bool = False        # 是否已校对

    # 序列化
    def save(self, path: Path) -> None:
        """保存为 .subgen 项目文件 (JSON)"""

    @classmethod
    def load(cls, path: Path) -> 'SubtitleProject':
        """从 .subgen 文件加载"""

    def to_dict(self) -> dict:
        """序列化为 dict（GUI JSON API 用）"""

    @classmethod
    def from_dict(cls, data: dict) -> 'SubtitleProject':
        """从 dict 反序列化"""
```

**项目文件格式** (`.subgen`，实际是 JSON)：

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

### 3.2 `src/styles.py` — 样式系统

```python
@dataclass
class FontStyle:
    """单个文字层的样式"""
    font: str = "Arial"
    size: int = 60
    color: str = "#FFFFFF"           # 标准 hex，代码内部转 ASS 格式
    bold: bool = False
    italic: bool = False
    outline: float = 3.0
    outline_color: str = "#000000"
    shadow: float = 1.0
    shadow_color: str = "#80000000"  # 带透明度

@dataclass
class StyleProfile:
    """完整样式配置"""
    name: str = "default"

    # 主字幕（翻译文字）
    primary: FontStyle = field(default_factory=lambda: FontStyle(
        font="Arial", size=60, color="#FFFFFF", bold=False, outline=3.0
    ))

    # 副字幕（原文，双语模式下显示）
    secondary: FontStyle = field(default_factory=lambda: FontStyle(
        font="Arial", size=45, color="#AAAAAA", bold=False, outline=2.0
    ))

    # 布局
    alignment: int = 2               # ASS alignment: 2=底部居中
    margin_left: int = 10
    margin_right: int = 10
    margin_bottom: int = 30
    line_spacing: int = 10           # 双语行间距

    # 分辨率
    play_res_x: int = 1920
    play_res_y: int = 1080

    # 序列化
    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> 'StyleProfile': ...

    # 辅助方法
    def to_ass_header(self) -> str:
        """生成 ASS [Script Info] + [V4+ Styles] 部分"""

    @staticmethod
    def hex_to_ass_color(hex_color: str) -> str:
        """'#RRGGBB' 或 '#AARRGGBB' → ASS '&HAABBGGRR' 格式"""

# ========== 预设 ==========

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
    从 config.yaml 的 styles 块加载样式。
    支持 preset 继承 + 部分覆盖。
    """
```

### 3.3 `src/engine.py` — 核心引擎

```python
from typing import Callable, Optional
from pathlib import Path
from .project import SubtitleProject
from .styles import StyleProfile

# 进度回调类型
ProgressCallback = Callable[[str, int, int], None]
# callback(stage, current, total)
# stage: "extracting" | "transcribing" | "translating" | "proofreading" | "exporting"

class SubGenEngine:
    """SubGen 核心引擎 — CLI 和 GUI 共用"""

    def __init__(self, config: dict, on_progress: Optional[ProgressCallback] = None):
        self.config = config
        self.on_progress = on_progress or (lambda *_: None)

    def run(self, input_path: Path, **options) -> SubtitleProject:
        """
        完整流程：视频 → 转录 → 翻译 → 校对 → 返回 Project

        options:
            source_lang, target_lang, no_translate, sentence_aware,
            proofread, bilingual, force_transcribe, ...

        返回 SubtitleProject，不直接写文件。调用方决定如何处理。
        """

    def transcribe(self, input_path: Path, **options) -> SubtitleProject:
        """只做转录，返回 Project"""

    def translate(self, project: SubtitleProject, **options) -> SubtitleProject:
        """对已有 Project 做翻译"""

    def proofread(self, project: SubtitleProject) -> SubtitleProject:
        """对已有 Project 做校对"""

    def export(self,
               project: SubtitleProject,
               output_path: Path,
               format: str = 'srt',
               style: Optional[StyleProfile] = None) -> Path:
        """
        导出字幕文件。

        style 参数可覆盖 project 自带的 style_profile。
        GUI 场景：用户调整样式后实时预览，传入新的 style 即可。
        """

    def export_video(self,
                     project: SubtitleProject,
                     video_path: Path,
                     output_path: Path,
                     embed_mode: str = 'soft') -> Path:
        """
        导出带字幕的视频。
        embed_mode: 'soft' (字幕轨) | 'hard' (烧录)
        """
```

**Engine 使用示例（CLI）：**

```python
# subgen.py 里变成这样
engine = SubGenEngine(config=cfg, on_progress=rich_progress_callback)
project = engine.run(input_path, target_lang='zh', sentence_aware=True)
engine.export(project, output_path, format='ass')
```

**Engine 使用示例（GUI）：**

```python
# Tauri backend / FastAPI
engine = SubGenEngine(config=cfg, on_progress=websocket_push)
project = engine.run(input_path, target_lang='zh')

# 用户手动编辑了第 5 条字幕
project.segments[4].translated = "用户修改的翻译"

# 用户调了字体颜色
project.style.primary.color = "#FFD700"

# 实时预览
engine.export(project, preview_path, format='ass')

# 保存项目
project.save(Path("my_movie.subgen"))
```

---

## 4. 改动模块详细设计

### 4.1 `src/subtitle.py` — 渲染重构

**改动要点：**

1. `generate_subtitle()` 新增 `style` 参数（可选，向后兼容）
2. ASS 生成不再硬编码 header，改为调用 `style.to_ass_header()`
3. 双语模式改为**单条 Dialogue + `\N` 换行 + 内联样式覆盖**

```python
def generate_subtitle(
    segments: List[Segment],
    output_path: Path,
    config: Dict[str, Any],
    style: Optional[StyleProfile] = None    # 新增，可选
) -> None:
    """
    生成字幕文件。

    如果传入 style，使用指定样式。
    如果不传，从 config 中加载样式（向后兼容）。
    """
```

**ASS 双语渲染改为：**

```
翻译在上，原文在下，同一条 Dialogue，用 \N 分行 + 内联样式切换：

Dialogue: 0,0:01:00.00,0:01:03.00,Default,,0,0,0,,你好世界\N{\fnArial\fs45\c&HFFBF00&}Hello World
```

好处：
- 两行绝对对齐，不会因分辨率飘动
- 单条 Dialogue，编辑器里好管理
- 内联样式只覆盖副字幕部分，主样式用 Style 定义

### 4.2 `src/config.py` — 样式配置

config.yaml 新增 `styles` 配置块：

```yaml
# config.yaml

# ...原有配置不变...

# 【新增】样式配置
styles:
  preset: "default"        # 预设：default / netflix / fansub / minimal
  primary:                 # 覆盖主字幕（翻译）样式
    font: "Microsoft YaHei"
    size: 60
    color: "#FFFFFF"
    bold: true
    outline: 3
    outline_color: "#000000"
  secondary:               # 覆盖副字幕（原文）样式
    font: "Arial"
    size: 45
    color: "#00BFFF"
    bold: false
    outline: 2
  margin_bottom: 30
  line_spacing: 10
```

**加载逻辑：** 先加载 preset 作为基础，再用用户配置的字段覆盖。没配 styles 块则用 default preset，**100% 向后兼容**。

### 4.3 `subgen.py` — CLI 瘦身

改动后的 `subgen.py` 职责仅为：
1. 定义 click 命令和参数
2. 解析参数，构建 config
3. 创建 SubGenEngine，传入 rich 进度回调
4. 调用 engine 方法
5. 输出结果到终端

目标：从 757 行缩减到 ~200 行。

**新增 CLI 选项：**

```bash
# 样式相关
--style-preset <name>     # 选择预设样式
--primary-font <name>     # 覆盖主字幕字体
--primary-color <hex>     # 覆盖主字幕颜色
--secondary-font <name>   # 覆盖副字幕字体
--secondary-color <hex>   # 覆盖副字幕颜色

# 项目相关
--save-project            # 导出时同时保存 .subgen 项目文件
--load-project <path>     # 从项目文件加载并继续

# 使用示例
subgen run movie.mp4 --to zh -s --bilingual \
  --style-preset fansub \
  --primary-font "方正黑体" \
  --secondary-color "#66CCFF" \
  --save-project
```

---

## 5. 向后兼容保证

| 场景 | 兼容性 |
|------|--------|
| 不配 `styles` 块 | ✅ 使用 default preset，输出与现在完全一致 |
| 不传 `--style-*` CLI 参数 | ✅ 走 config.yaml 或 default |
| 旧的 `generate_subtitle(segments, path, config)` 调用 | ✅ style 参数可选，不传则从 config 加载 |
| 旧的缓存文件 | ✅ 缓存格式只增不改，旧缓存正常读取 |
| 不使用 Engine，直接调函数 | ✅ 原有函数签名不删除，标记 deprecated |

---

## 6. GUI 兼容设计要点

虽然现在不做 GUI，但架构要确保以下能力：

### 6.1 实时预览
```
用户调样式 → 构建新 StyleProfile → engine.export(project, style=new_style)
```
导出一个临时 ASS，播放器实时加载。不需要重新转录/翻译。

### 6.2 逐条编辑
```
project.segments[i].translated = "新翻译"
project.segments[i].start = 1.5  # 调时间轴
```
Segment 是普通 dataclass，直接改字段。

### 6.3 项目保存/恢复
```
project.save("movie.subgen")
project = SubtitleProject.load("movie.subgen")
```
JSON 格式，GUI 可以自己做自动保存。

### 6.4 进度推送
```
engine = SubGenEngine(config, on_progress=my_callback)
```
CLI 传 rich 回调，GUI 传 websocket/IPC 回调，Engine 不关心具体实现。

### 6.5 批量操作（未来）
```
for video in videos:
    project = engine.run(video)
    engine.export(project, ...)
```
Engine 是无状态的，可以循环调用。

---

## 7. 实施计划

### Phase 1：数据层（不改现有行为）
- [ ] 新建 `src/styles.py` — StyleProfile + FontStyle + presets + hex↔ASS 转换
- [ ] 新建 `src/project.py` — SubtitleProject 数据模型 + 序列化
- [ ] 新增测试 `tests/test_styles.py` 和 `tests/test_project.py`

### Phase 2：渲染层（改 subtitle.py）
- [ ] `subtitle.py` 的 `_generate_ass()` 改为接收 StyleProfile
- [ ] 实现 `StyleProfile.to_ass_header()` 生成 ASS 头部
- [ ] 双语模式改为单条 Dialogue + `\N` + 内联样式
- [ ] `generate_subtitle()` 加 `style` 可选参数（向后兼容）
- [ ] 新增测试 `tests/test_subtitle_styles.py`

### Phase 3：引擎层（重构核心流程）
- [ ] 新建 `src/engine.py` — SubGenEngine 封装所有业务流程
- [ ] 进度回调抽象：`ProgressCallback` 类型
- [ ] 从 `subgen.py` 的 `run_subtitle_generation()` 抽取逻辑到 engine
- [ ] `subgen.py` 瘦身为 CLI 薄壳

### Phase 4：配置 & CLI（用户可见功能）
- [ ] `config.py` 支持 `styles` 配置块
- [ ] `config.example.yaml` 添加样式示例
- [ ] CLI 新增 `--style-preset`、`--primary-font`、`--primary-color` 等选项
- [ ] CLI 新增 `--save-project` / `--load-project`
- [ ] 更新文档 `docs/configuration.md`

### 每个 Phase 完成后：
- 确保所有现有测试通过
- 确保 `subgen run movie.mp4 --to zh` 行为与重构前完全一致
- 提交到独立分支，PR review 后合并

---

## 8. 文件影响总结

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `src/styles.py` | **新建** | StyleProfile, FontStyle, presets |
| `src/project.py` | **新建** | SubtitleProject 数据模型 |
| `src/engine.py` | **新建** | SubGenEngine 核心引擎 |
| `src/subtitle.py` | **修改** | ASS 渲染支持 StyleProfile，双语改 `\N` |
| `src/config.py` | **修改** | 新增 styles 配置解析 |
| `subgen.py` | **修改** | 瘦身为 CLI 薄壳 |
| `config.example.yaml` | **修改** | 添加 styles 示例 |
| `tests/test_styles.py` | **新建** | 样式系统测试 |
| `tests/test_project.py` | **新建** | 项目模型测试 |
| `tests/test_subtitle_styles.py` | **新建** | 样式渲染测试 |
| `docs/configuration.md` | **修改** | 样式配置文档 |
| 其余所有文件 | **不动** | transcribe, translate, audio, cache 等 |
