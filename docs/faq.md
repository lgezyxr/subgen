# ❓ FAQ

## Installation Issues

### Q: FFmpeg not found?

**A**: Make sure FFmpeg is installed and in PATH:

```bash
# Check if installed
ffmpeg -version

# macOS
brew install ffmpeg

# Ubuntu
sudo apt install ffmpeg

# Windows: Download and add to PATH
```

---

### Q: Error installing faster-whisper?

**A**: Install PyTorch first:

```bash
# With NVIDIA GPU
pip install torch --index-url https://download.pytorch.org/whl/cu118

# Without GPU (CPU mode, very slow)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Then install faster-whisper
pip install faster-whisper
```

---

### Q: CUDA out of memory?

**A**: Not enough VRAM. Solutions:

1. **Use a smaller model**:
   ```yaml
   whisper:
     local_model: "medium"  # or "small"
   ```

2. **Close other GPU-intensive programs**

3. **Use cloud API instead of local**:
   ```yaml
   whisper:
     provider: "openai"  # or "groq"
   ```

---

## Usage Issues

### Q: Transcription not accurate?

**A**: Some improvements:

1. **Use a larger model** (e.g., large-v3)
2. **Check audio quality** (background noise affects accuracy)
3. **Try different providers** (OpenAI and Groq may give different results)

---

### Q: Translation quality not good?

**A**:

1. **Use a better model**:
   ```yaml
   translation:
     model: "gpt-4o"  # best quality
   ```

2. **Adjust batch size** (give LLM more context):
   ```yaml
   advanced:
     translation_batch_size: 30
     translation_context_size: 10
   ```

3. **Use DeepSeek for Chinese translation** (Chinese optimized)

---

### Q: Subtitle timing is off?

**A**: This is a known issue, planned for optimization in v0.2.0. Workarounds:

1. Use professional subtitle editing software (e.g., Aegisub) for fine-tuning
2. Try local Whisper (timestamps are usually more accurate)

---

### Q: How to handle multi-speaker dialogues?

**A**: Speaker diarization is planned for v0.5.0. Currently:

1. Subtitles don't distinguish speakers
2. You can manually add speaker labels

---

## API Issues

### Q: API request failed (401 Unauthorized)?

**A**: API key issue:

1. Check if key is correctly copied (no extra spaces)
2. Check if key is valid (log into console to verify)
3. Check if account has balance

---

### Q: API request timeout?

**A**:

1. **Check network connection**
2. **Use a proxy** (if accessing OpenAI from restricted regions):
   ```yaml
   translation:
     base_url: "https://your-proxy.com/v1"
   ```
3. **Try a different provider**

---

### Q: How to estimate API costs?

**A**: Rough estimates:

- **2-hour movie**:
  - Whisper API: 120 min × $0.006 = $0.72
  - GPT-4o-mini translation: ~$0.05
  - **Total: ~$0.77**

- **Using Groq + local translation**: Nearly free

---

## Other Questions

### Q: What video formats are supported?

**A**: All formats FFmpeg can process:
- Video: MP4, MKV, AVI, MOV, WMV, FLV
- Audio: MP3, WAV, AAC, FLAC

---

### Q: Can I do transcription only without translation?

**A**: Not currently supported. Planning to add `--no-translate` option in future versions.

Workaround: Set target language same as source:
```bash
python subgen.py video.mp4 --from en --to en  # English video
```

---

### Q: How to contribute code?

**A**: Welcome! See [CONTRIBUTING.md](../CONTRIBUTING.md)

1. Fork the project
2. Create a feature branch
3. Submit a Pull Request

---

## Still have questions?

- Submit a [GitHub Issue](https://github.com/lgezyxr/subgen/issues)
- Search existing issues for similar problems
