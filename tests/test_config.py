"""配置模块单元测试"""

import pytest
import tempfile
from pathlib import Path
from src.config import load_config, DEFAULT_CONFIG


class TestLoadConfig:
    """配置加载测试"""

    def test_load_valid_config(self, tmp_path):
        """加载有效配置"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
whisper:
  provider: openai
output:
  format: srt
""")
        cfg = load_config(str(config_file))
        assert cfg['whisper']['provider'] == 'openai'
        assert cfg['output']['format'] == 'srt'

    def test_load_missing_file(self):
        """加载不存在的文件应报错"""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.yaml")

    def test_default_config_structure(self):
        """默认配置应包含所有必要键"""
        assert 'whisper' in DEFAULT_CONFIG
        assert 'translation' in DEFAULT_CONFIG
        assert 'output' in DEFAULT_CONFIG
        assert 'advanced' in DEFAULT_CONFIG

    def test_default_config_values(self):
        """默认配置值检查"""
        assert DEFAULT_CONFIG['whisper']['provider'] == 'local'
        assert DEFAULT_CONFIG['output']['format'] == 'srt'
        assert DEFAULT_CONFIG['output']['bilingual'] is False

    def test_config_merge_with_defaults(self, tmp_path):
        """用户配置应与默认配置合并"""
        config_file = tmp_path / "config.yaml"
        # 只覆盖部分配置
        config_file.write_text("""
whisper:
  provider: groq
""")
        cfg = load_config(str(config_file))
        # 用户指定的值
        assert cfg['whisper']['provider'] == 'groq'
        # 默认值应该保留
        assert 'output' in cfg
        assert cfg['output']['format'] == 'srt'
        # whisper 的其他默认值也应该保留
        assert cfg['whisper']['local_model'] == 'large-v3'
