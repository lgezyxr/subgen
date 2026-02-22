"""Configuration module unit tests"""

import pytest
from src.config import load_config, DEFAULT_CONFIG


class TestLoadConfig:
    """Configuration loading tests"""

    def test_load_valid_config(self, tmp_path):
        """Load valid config file"""
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
        """Loading non-existent file should raise error"""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.yaml")

    def test_default_config_structure(self):
        """Default config should contain all required keys"""
        assert 'whisper' in DEFAULT_CONFIG
        assert 'translation' in DEFAULT_CONFIG
        assert 'output' in DEFAULT_CONFIG
        assert 'advanced' in DEFAULT_CONFIG

    def test_default_config_values(self):
        """Default config values check"""
        assert DEFAULT_CONFIG['whisper']['provider'] == 'local'
        assert DEFAULT_CONFIG['output']['format'] == 'srt'
        assert DEFAULT_CONFIG['output']['bilingual'] is False

    def test_config_merge_with_defaults(self, tmp_path):
        """User config should merge with defaults"""
        config_file = tmp_path / "config.yaml"
        # Only override partial config
        config_file.write_text("""
whisper:
  provider: groq
""")
        cfg = load_config(str(config_file))
        # User specified value
        assert cfg['whisper']['provider'] == 'groq'
        # Default values should be preserved
        assert 'output' in cfg
        assert cfg['output']['format'] == 'srt'
        # Other whisper defaults should also be preserved
        assert cfg['whisper']['local_model'] == 'large-v3'
