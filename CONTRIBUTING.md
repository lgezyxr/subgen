# 贡献指南

感谢你对 SubGen 的兴趣！欢迎贡献代码、文档、Bug 报告或功能建议。

## 🐛 报告 Bug

1. 先搜索 [Issues](https://github.com/YOUR_USERNAME/subgen/issues) 看看是否已有类似问题
2. 如果没有，创建新 Issue，包含：
   - 你的环境 (OS, Python 版本, GPU)
   - 重现步骤
   - 期望行为 vs 实际行为
   - 错误日志 (如果有)

## 💡 功能建议

1. 创建 Issue，标记 `feature request`
2. 描述你想要的功能
3. 说明使用场景

## 🔧 提交代码

### 开发环境设置

```bash
# 克隆项目
git clone https://github.com/YOUR_USERNAME/subgen.git
cd subgen

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装开发依赖
pip install -r requirements.txt
pip install -e .

# 安装开发工具
pip install black ruff pytest
```

### 代码风格

我们使用：
- **black** 格式化代码
- **ruff** 检查代码质量

提交前运行：
```bash
black .
ruff check .
```

### 提交 Pull Request

1. Fork 项目
2. 创建 feature 分支: `git checkout -b feature/amazing-feature`
3. 提交更改: `git commit -m 'Add amazing feature'`
4. 推送: `git push origin feature/amazing-feature`
5. 创建 Pull Request

### Commit 消息格式

```
<type>: <description>

[可选的详细描述]
```

Type:
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具

示例：
```
feat: add Groq API support for whisper
fix: handle empty subtitle segments
docs: update installation guide for Windows
```

## 📝 文档贡献

文档在 `docs/` 目录，欢迎：
- 修复错误
- 改进描述
- 添加示例
- 翻译成其他语言

## 🧪 测试

```bash
# 运行测试
pytest

# 运行特定测试
pytest tests/test_transcribe.py
```

## 📋 优先事项

当前最需要帮助的方向：

1. **测试用例**: 增加测试覆盖率
2. **文档**: 多语言翻译
3. **新提供商**: 支持更多 API
4. **Bug 修复**: 查看 Issues

## 📜 许可证

贡献的代码将采用 MIT 许可证发布。
