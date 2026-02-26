# Contributing Guide

Thank you for your interest in SubGen! We welcome code contributions, documentation, bug reports, and feature suggestions.

[中文版](docs/zh/contributing.md)

## 🏗️ Project Architecture

SubGen v0.2 uses a layered architecture:

```
CLI (subgen.py)
 └── SubGenEngine (src/engine.py)        # Core orchestration engine
      ├── transcribe (src/transcribe.py)  # Speech recognition
      ├── translate (src/translate.py)    # Translation
      ├── subtitle (src/subtitle.py)     # Subtitle rendering (SRT/ASS/VTT)
      └── styles (src/styles.py)         # Style system
```

### Core Components

- **SubGenEngine** (`src/engine.py`): Core engine that orchestrates audio extraction → transcription → translation → proofreading → export. Performs no terminal I/O; reports progress via callbacks.
- **StyleProfile** (`src/styles.py`): Subtitle style data model containing `FontStyle` (font/color/outline, etc.) and layout parameters. Built-in presets: `default`, `netflix`, `fansub`, `minimal`.
- **SubtitleProject** (`src/project.py`): Project data model containing segments, style, metadata, and state. Serializable to `.subgen` JSON files.
- **ComponentManager** (`src/components.py`): Manages on-demand download, installation, and updates of components (whisper.cpp, models, FFmpeg).
- **CLI** (`subgen.py`): Thin shell responsible for argument parsing, config building, calling the Engine, and displaying progress.

### Adding a New Style Preset

1. Open `src/styles.py`
2. Add a new preset to the `PRESETS` dictionary:
   ```python
   PRESETS["my_preset"] = StyleProfile(
       name="my_preset",
       primary=FontStyle(font="My Font", size=55, color="#FFFFFF", ...),
       secondary=FontStyle(font="My Font", size=40, color="#CCCCCC", ...),
       margin_bottom=30,
   )
   ```
3. Add the new preset name to the `click.Choice` for `--style-preset` in `subgen.py`
4. Update documentation

## 🐛 Reporting Bugs

1. Search [Issues](https://github.com/lgezyxr/subgen/issues) first to check for duplicates
2. If none found, create a new Issue including:
   - Your environment (OS, Python version, GPU)
   - Steps to reproduce
   - Expected vs. actual behavior
   - Error logs (if any)

## 💡 Feature Suggestions

1. Create an Issue tagged `feature request`
2. Describe the feature you'd like
3. Explain your use case

## 🔧 Submitting Code

### Development Environment Setup

```bash
# Clone the project
git clone https://github.com/lgezyxr/subgen.git
cd subgen

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Install development tools
pip install black ruff pytest
```

### Code Style

We use:
- **black** for code formatting
- **ruff** for code quality checks

Before committing, run:
```bash
black .
ruff check .
```

### Submitting a Pull Request

1. Fork the project
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push: `git push origin feature/amazing-feature`
5. Create a Pull Request

### Commit Message Format

```
<type>: <description>

[optional detailed description]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation update
- `refactor`: Code refactoring
- `test`: Test-related changes
- `chore`: Build/tooling changes

Examples:
```
feat: add Groq API support for whisper
fix: handle empty subtitle segments
docs: update installation guide for Windows
```

## 📝 Documentation Contributions

Documentation lives in `docs/`. We welcome:
- Error corrections
- Improved descriptions
- Additional examples
- Translations to other languages

English documentation is the primary (authoritative) version. Chinese translations are in `docs/zh/`.

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific tests
pytest tests/test_transcribe.py
```

## 📋 Priority Areas

Areas where help is most needed:

1. **Test cases**: Increase test coverage
2. **Documentation**: Translations and improvements
3. **New providers**: Support for additional APIs
4. **Bug fixes**: Check Issues on GitHub

## 📜 License

Contributed code is released under the MIT License.
