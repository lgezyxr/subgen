# ❓ 常见问题 (FAQ)

## 安装问题

### Q: 提示找不到 FFmpeg

**A**: FFmpeg 是必需的系统依赖。

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
# 下载 https://ffmpeg.org/download.html 并添加到 PATH
```

### Q: pip install 报错

**A**: 确保 Python 版本 >= 3.10

```bash
python --version  # 检查版本

# 如果版本过低，使用 pyenv 管理多版本
pyenv install 3.11
pyenv local 3.11
```

### Q: CUDA 相关错误

**A**: 本地 Whisper 需要 NVIDIA GPU 和正确的 CUDA 配置。

```bash
# 检查 GPU
nvidia-smi

# 如果没有 GPU 或不想配置，使用云端 API
whisper:
  provider: "openai"  # 或 "groq"
```

---

## 使用问题

### Q: 处理速度很慢

**A**: 几个优化方向：

1. **使用 Groq API**（极快）
   ```yaml
   whisper:
     provider: "groq"
   ```

2. **使用更小的本地模型**
   ```yaml
   whisper:
     local_model: "medium"  # 而不是 large-v3
   ```

3. **使用更快的翻译模型**
   ```yaml
   translation:
     model: "gpt-4o-mini"  # 而不是 gpt-4o
   ```

### Q: 字幕时间不准确

**A**: 这是 Whisper 的已知问题，特别是：
- 说话速度快
- 有背景音乐
- 多人同时说话

**改善方法**：
1. 使用 `large-v3` 模型
2. 等待 v0.2.0 的时间轴优化功能

### Q: 翻译质量不好

**A**: 
1. 使用更强的模型（如 `gpt-4o`）
2. 等待 v0.3.0 的上下文翻译功能
3. 手动编辑结果

### Q: 支持什么视频格式？

**A**: 任何 FFmpeg 支持的格式：
- MP4, MKV, AVI, MOV, WMV
- WebM, FLV, M4V
- 等等

### Q: 支持什么语言？

**A**: 
- **语音识别**：Whisper 支持 99+ 种语言
- **翻译**：取决于 LLM，主流语言都支持

---

## API 问题

### Q: API 请求失败 (401)

**A**: API Key 问题。

1. 检查 Key 是否正确复制（无多余空格）
2. 检查 Key 是否过期
3. 检查账户是否有余额

### Q: API 请求超时

**A**: 
1. 检查网络连接
2. 如果在中国大陆，可能需要代理
3. 尝试使用 DeepSeek（国内服务）

### Q: 提示配额不足

**A**: 
1. 充值账户
2. 切换到更便宜的模型
3. 使用本地模型

---

## 输出问题

### Q: 字幕乱码

**A**: 编码问题。确保：
1. 使用 UTF-8 编码打开字幕文件
2. 播放器支持 UTF-8

### Q: 字幕不显示

**A**: 
1. 检查字幕文件是否生成
2. 确保播放器加载了字幕
3. 尝试不同的字幕格式（SRT 最通用）

### Q: 双语字幕重叠

**A**: 使用 ASS 格式，它支持更好的位置控制：
```yaml
output:
  format: "ass"
  bilingual: true
```

---

## 性能问题

### Q: 内存不足

**A**: 
1. 使用更小的模型
2. 关闭其他程序
3. 使用云端 API 代替本地

### Q: GPU 内存不足

**A**: 
1. 使用更小的模型：
   ```yaml
   whisper:
     local_model: "small"  # 只需 2GB
   ```
2. 使用 CPU 模式（慢但稳定）：
   ```yaml
   whisper:
     device: "cpu"
   ```

### Q: 处理大文件卡死

**A**: 当前版本对大文件支持有限。
- 暂时手动分割视频
- 等待 v0.4.0 的分段处理功能

---

## 其他问题

### Q: 如何贡献代码？

**A**: 欢迎！请查看 [CONTRIBUTING.md](../CONTRIBUTING.md)

### Q: 如何报告 Bug？

**A**: 在 GitHub Issues 中提交，请包含：
1. 操作系统和 Python 版本
2. 完整的错误信息
3. 复现步骤
4. 配置文件（隐藏 API Key）

### Q: 有商业授权吗？

**A**: MIT 协议，可自由商用。

---

## 还有问题？

- 📖 查看 [完整文档](./README.md)
- 💬 在 GitHub Issues 提问
- 🤝 加入社区讨论
