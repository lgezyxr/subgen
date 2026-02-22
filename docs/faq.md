# ❓ 常见问题

## 安装问题

### Q: FFmpeg 找不到怎么办？

**A**: 确保 FFmpeg 已安装并在 PATH 中：

```bash
# 检查是否安装
ffmpeg -version

# macOS 安装
brew install ffmpeg

# Ubuntu 安装
sudo apt install ffmpeg

# Windows: 下载后添加到 PATH
```

---

### Q: 安装 faster-whisper 报错？

**A**: 需要先安装 PyTorch：

```bash
# 有 NVIDIA GPU
pip install torch --index-url https://download.pytorch.org/whl/cu118

# 没有 GPU (CPU 模式，很慢)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# 然后安装 faster-whisper
pip install faster-whisper
```

---

### Q: CUDA out of memory 怎么办？

**A**: 显存不够，有几个解决方案：

1. **用更小的模型**:
   ```yaml
   whisper:
     local_model: "medium"  # 或 "small"
   ```

2. **关闭其他占用 GPU 的程序**

3. **使用云端 API 代替本地**:
   ```yaml
   whisper:
     provider: "openai"  # 或 "groq"
   ```

---

## 使用问题

### Q: 识别结果不准怎么办？

**A**: 几个改进方法：

1. **使用更大的模型** (如 large-v3)
2. **检查音频质量** (背景噪音大会影响识别)
3. **尝试不同的提供商** (OpenAI 和 Groq 结果可能不同)

---

### Q: 翻译质量不好怎么办？

**A**:

1. **使用更好的模型**:
   ```yaml
   translation:
     model: "gpt-4o"  # 最好的质量
   ```

2. **调整批次大小** (给 LLM 更多上下文):
   ```yaml
   advanced:
     translation_batch_size: 30
     translation_context_size: 10
   ```

3. **使用 DeepSeek 做中文翻译** (中文优化)

---

### Q: 字幕时间不准怎么办？

**A**: 这是已知问题，计划在 v0.2.0 优化。临时解决方案：

1. 使用专业字幕编辑软件 (如 Aegisub) 微调
2. 尝试本地 Whisper (时间戳通常更准)

---

### Q: 如何处理多人对话？

**A**: 说话人分离功能计划在 v0.5.0 实现。目前：

1. 字幕不会区分说话人
2. 可以手动编辑添加角色标签

---

## API 问题

### Q: API 请求失败 (401 Unauthorized)？

**A**: API Key 问题：

1. 检查 Key 是否正确复制（没有多余空格）
2. 检查 Key 是否有效（登录控制台确认）
3. 检查账户是否有余额

---

### Q: API 请求超时？

**A**:

1. **检查网络连接**
2. **使用代理** (如果在国内访问 OpenAI):
   ```yaml
   translation:
     base_url: "https://your-proxy.com/v1"
   ```
3. **换一个提供商试试**

---

### Q: 如何估算 API 费用？

**A**: 大致估算：

- **2小时电影**:
  - Whisper API: 120 分钟 × $0.006 = $0.72
  - GPT-4o-mini 翻译: ~$0.05
  - **总计: ~$0.77 (约 ¥5.5)**

- **使用 Groq + 本地翻译**: 接近免费

---

## 其他问题

### Q: 支持什么视频格式？

**A**: 支持所有 FFmpeg 能处理的格式：
- MP4, MKV, AVI, MOV, WMV, FLV
- 音频: MP3, WAV, AAC, FLAC

---

### Q: 可以只做语音识别不翻译吗？

**A**: 暂时不支持，计划在后续版本添加 `--no-translate` 选项。

临时方案：把目标语言设为源语言：
```bash
python subgen.py video.mp4 --target-lang en  # 英文视频
```

---

### Q: 如何贡献代码？

**A**: 欢迎！请查看 [CONTRIBUTING.md](../CONTRIBUTING.md)

1. Fork 项目
2. 创建 feature 分支
3. 提交 Pull Request

---

## 还有问题？

- 提交 [GitHub Issue](https://github.com/YOUR_USERNAME/subgen/issues)
- 搜索已有 Issue 看看有没有类似问题
