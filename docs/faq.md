# ❓ FAQ

## Installation

### FFmpeg not found?

Make sure FFmpeg is installed and in PATH:

```bash
# Check installation
ffmpeg -version

# Install
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows (PowerShell as admin)
winget install FFmpeg
```

---

### CUDA out of memory?

Your GPU doesn't have enough VRAM for the selected model.

**Solutions**:

1. Use a smaller Whisper model:
   ```yaml
   whisper:
     local_model: "medium"  # or "small"
   ```

2. Use float32 (uses less VRAM than float16):
   ```yaml
   whisper:
     compute_type: "float32"
   ```

3. Use cloud API instead:
   ```yaml
   whisper:
     provider: "groq"  # Free tier available
   ```

---

### GPU crash after transcription (Windows)?

This is a known issue with CTranslate2 on Windows. SubGen automatically keeps the model in memory to prevent crashes.

If you still experience crashes, try:
```yaml
whisper:
  compute_type: "float32"
```

---

### Older NVIDIA GPU (GTX 10xx) not working?

Pascal-era GPUs don't support float16. Use float32:

```yaml
whisper:
  provider: "local"
  device: "cuda"
  compute_type: "float32"
```

---

## Usage

### What's the difference between translation modes?

| Mode | Command | Quality | Speed |
|------|---------|---------|-------|
| Basic | `--to zh` | ★★★☆☆ | Fast |
| Sentence-aware | `-s --to zh` | ★★★★☆ | Medium |
| With proofreading | `-s --proofread --to zh` | ★★★★★ | Slower |

**Sentence-aware** (`-s`):
- Groups subtitle segments into complete sentences
- Uses word-level timestamps for precise timing
- LLM decides natural break points

**Proofreading** (`--proofread`):
- Second AI pass with full story context
- Reviews all translations for consistency
- Fixes character names, terminology, tone

---

### How does caching work?

SubGen caches transcription results in `.subgen-cache.json` alongside your video.

```bash
# First run: transcribes and caches
python subgen.py run video.mp4 -s --to zh

# Second run: uses cache (instant!)
python subgen.py run video.mp4 -s --to ja

# Force re-transcription
python subgen.py run video.mp4 -s --to zh --force-transcribe
```

Cache includes:
- Audio transcription
- Word-level timestamps
- Translations (after translation step)

---

### Can I proofread existing subtitles?

Yes! Use `--proofread-only`:

```bash
# First: generate translation
python subgen.py run video.mp4 -s --to zh

# Later: proofread only (uses cached translations)
python subgen.py run video.mp4 --proofread-only --to zh
```

Output: `video_zh.proofread.srt`

---

### Why is dialogue missing when music is loud?

By default, music/noise filtering is disabled. If you previously enabled it:

```yaml
advanced:
  filter_music: false      # Disable music filtering
  validate_segments: false # Disable density filtering
```

Then re-transcribe:
```bash
python subgen.py run video.mp4 -s --to zh --force-transcribe
```

---

### How to debug translation issues?

Use `--debug` flag:

```bash
python subgen.py run video.mp4 -s --to zh --debug
```

Shows:
- Segment transcription details
- LLM requests and responses
- Word-level timestamp mapping
- Proofreading corrections

---

## Providers

### ChatGPT login not working?

1. Make sure you have ChatGPT Plus or Pro subscription
2. Try logging out and back in:
   ```bash
   python subgen.py auth logout chatgpt
   python subgen.py auth login chatgpt
   ```
3. Clear browser cookies for chatgpt.com

---

### Which ChatGPT model should I use?

| Model | Quality | Speed | Notes |
|-------|---------|-------|-------|
| `gpt-5.3-codex` | ★★★★★ | Medium | Has reasoning, best for proofreading |
| `gpt-5.2-codex` | ★★★★☆ | Medium | Previous version |
| `gpt-5.1-codex-mini` | ★★★☆☆ | Fast | Less capable |

Configure in `config.yaml`:
```yaml
translation:
  provider: "chatgpt"
  model: "gpt-5.3-codex"
```

---

### API request timeout?

**Solutions**:

1. Check network connection
2. Try a different provider
3. Use a proxy (if needed for your region):
   ```yaml
   translation:
     base_url: "https://your-proxy.com/v1"
   ```

---

### How to estimate API costs?

For a 2-hour movie:

| Service | Cost |
|---------|------|
| OpenAI Whisper | ~$0.72 (120 min × $0.006) |
| GPT-4o-mini | ~$0.05 |
| DeepSeek | ~¥0.1 |
| ChatGPT/Copilot | $0 (subscription) |
| Local/MLX/Groq | $0 |

---

## Output

### What subtitle formats are supported?

| Format | Extension | Notes |
|--------|-----------|-------|
| SRT | `.srt` | Most universal, all players |
| ASS | `.ass` | Styling support, fansub standard |
| VTT | `.vtt` | Web video standard |

Configure:
```yaml
output:
  format: "srt"
```

---

### Can I get bilingual subtitles?

Yes:

```bash
python subgen.py run video.mp4 -s --to zh --bilingual
```

Or in config:
```yaml
output:
  bilingual: true
```

Output format:
```
1
00:00:01,000 --> 00:00:03,000
Hello, how are you?
你好，你怎么样？
```

---

### What video formats work?

Any format FFmpeg supports:
- Video: MP4, MKV, AVI, MOV, WMV, FLV, WebM
- Audio: MP3, WAV, AAC, FLAC, M4A

---

## Still have questions?

- [GitHub Issues](https://github.com/lgezyxr/subgen/issues)
- Search existing issues first
- Include `--debug` output when reporting bugs
