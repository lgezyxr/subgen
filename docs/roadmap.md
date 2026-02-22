# 🗺️ SubGen Development Roadmap

> Detailed development plan from MVP to complete product

---

## 📅 Version Planning

### v0.1.0 - MVP (Current)
> Development time: Completed

**Goal**: Run through core workflow, validate technical feasibility

- [x] Project structure setup
- [x] Configuration file system
- [x] Audio extraction (FFmpeg)
- [x] Speech recognition
  - [x] Local faster-whisper
  - [x] OpenAI Whisper API
  - [x] Groq API
- [x] Translation
  - [x] OpenAI GPT
  - [x] Claude
  - [x] DeepSeek
  - [x] Ollama (local)
- [x] Subtitle generation
  - [x] SRT format
  - [x] ASS format
  - [x] VTT format
- [x] CLI interface
- [x] Language switching CLI (--from, --to)
- [x] Multi-language translation rules
- [x] Basic documentation
- [x] Unit tests & CI

---

### v0.2.0 - Stability & Usability
> Estimated: 1-2 weeks

**Goal**: Improve user experience, handle edge cases

#### Feature Enhancements
- [ ] Setup wizard (`subgen init`)
- [ ] API key validation and better error messages
- [ ] Progress display improvements (percentage, ETA)
- [ ] Resume interrupted processing (for large files)
- [ ] Comprehensive logging system

#### Subtitle Quality
- [ ] Subtitle timing fine-tuning (avoid appearing before/after speech)
- [ ] Automatic long sentence line breaks
- [ ] Punctuation normalization

#### Error Handling
- [ ] Network timeout retries
- [ ] Invalid audio detection
- [ ] API quota exhausted warnings

#### Testing
- [ ] Unit test coverage
- [ ] Integration tests
- [ ] Different video format tests (mp4, mkv, avi, mov)

---

### v0.3.0 - Translation Quality
> Estimated: 2-3 weeks

**Goal**: Professional-level subtitle translation quality

#### Context-Aware Translation
- [ ] Sliding window context (provide surrounding text during translation)
- [ ] Global character/terminology extraction
- [ ] Consistency checking

#### Glossary System
- [ ] User-defined glossary (`glossary.yaml`)
- [ ] Name and place consistency
- [ ] Domain-specific terminology
- [ ] Auto-extraction suggestions

#### Translation Style
- [ ] Multiple style options (formal/casual/fansub style)
- [ ] Tone preservation (questions, exclamations, etc.)
- [ ] Cultural adaptation options

#### Quality Assurance
- [ ] Post-translation length check
- [ ] Obvious error detection (missing, duplicates, etc.)
- [ ] Optional manual review mode

---

### v0.4.0 - Batch Processing & Automation
> Estimated: 2 weeks

**Goal**: Support batch tasks and automated workflows

#### Batch Processing
- [ ] Folder batch processing
- [ ] Task queue
- [ ] Parallel processing (multiple videos simultaneously)
- [ ] Batch task reports

#### Automation
- [ ] Watch folder (auto-process new files)
- [ ] Command-line pipe support
- [ ] Output format templates

#### Performance Optimization
- [ ] Parallel audio segment recognition
- [ ] Concurrent translation requests
- [ ] Memory optimization (streaming for large files)

---

### v0.5.0 - Speaker Diarization
> Estimated: 3-4 weeks

**Goal**: Support multi-speaker dialogue scenarios

#### Speaker Recognition
- [ ] Integrate pyannote-audio
- [ ] Automatic speaker count detection
- [ ] Speaker labels (Speaker A, Speaker B)

#### Character Management
- [ ] Manual character name assignment
- [ ] Save character voice profiles
- [ ] Reuse characters across videos

#### Output Enhancement
- [ ] Color-coded by character (ASS)
- [ ] Character label prefix option

---

### v0.6.0 - GUI Interface
> Estimated: 4-6 weeks

**Goal**: Graphical interface to lower the barrier to entry

#### Tech Stack
- [ ] Framework selection: Tauri (Rust + Web) or Electron
- [ ] UI design

#### Core Features
- [ ] Drag-and-drop video upload
- [ ] Settings interface (API key management)
- [ ] Real-time progress display
- [ ] Subtitle preview

#### Editing Features
- [ ] Timeline editor
- [ ] Per-subtitle modification
- [ ] Keyboard shortcut support

#### Video Preview
- [ ] Embedded video player
- [ ] Live subtitle preview
- [ ] Timestamp navigation

---

### v0.7.0 - Advanced Features
> Estimated: 4-6 weeks

**Goal**: Advanced features for professional fansubbers

#### Subtitle Styling
- [ ] Visual style editor
- [ ] Preset style templates
- [ ] Font, color, position customization
- [ ] Effects support (gradients, outlines, etc.)

#### Audio Processing
- [ ] Background music separation
- [ ] Noise reduction
- [ ] Volume normalization

#### Special Scenarios
- [ ] Lyrics recognition mode
- [ ] Multi-language mixed processing
- [ ] SDH subtitles (sound effect descriptions)

---

### v1.0.0 - Official Release
> Estimated: 4-6 months total

**Goal**: Production-ready complete product

#### Release Preparation
- [ ] Complete documentation
- [ ] Installers (Windows, macOS, Linux)
- [ ] Auto-update mechanism
- [ ] User feedback channels

#### Commercial Features (Optional)
- [ ] Pro version licensing system
- [ ] Built-in API quota
- [ ] Priority support

---

## 🏗️ Technical Debt & Optimization

### Code Quality
- [ ] Complete type annotations
- [ ] Docstring coverage
- [ ] Code review checklist

### Architecture
- [ ] Plugin system (easy to add new providers)
- [ ] Configuration system refactor
- [ ] Async I/O optimization

### Dependency Management
- [ ] Optional dependency groups
- [ ] Version locking
- [ ] Security update checks

---

## 📊 Milestones

| Version | Target Date | Key Features |
|---------|-------------|--------------|
| v0.1.0 | ✅ Completed | MVP - Core workflow |
| v0.2.0 | +2 weeks | Stability & usability |
| v0.3.0 | +5 weeks | Translation quality |
| v0.4.0 | +7 weeks | Batch processing |
| v0.5.0 | +11 weeks | Speaker diarization |
| v0.6.0 | +17 weeks | GUI interface |
| v1.0.0 | +24 weeks | Official release |

---

## 🤝 Contribution Guide

Community contributions welcome! High priority tasks:

1. **Documentation**: Multi-language README and docs
2. **Test cases**: Increase test coverage
3. **New providers**: Support more Whisper/LLM APIs
4. **Bug fixes**: Issues marked in GitHub

See [CONTRIBUTING.md](../CONTRIBUTING.md)

---

## 💡 Feature Suggestions

Have a new feature idea? Submit in GitHub Issues with the `feature request` label.

Highly voted features will be prioritized!
