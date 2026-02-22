"""Configuration loading module"""

import yaml
from pathlib import Path
from typing import Dict, Any


# Default configuration
DEFAULT_CONFIG: Dict[str, Any] = {
    'whisper': {
        'provider': 'local',
        'local_model': 'large-v3',
        'device': 'cuda',
        'source_language': 'auto',  # Source language, auto=auto-detect
    },
    'translation': {
        'provider': 'openai',
        'model': 'gpt-4o-mini',
    },
    'output': {
        'format': 'srt',
        'source_language': 'auto',  # Translation source language
        'target_language': 'zh',    # Translation target language
        'bilingual': False,
        'max_chars_per_line': 42,
        'embed_in_video': False,
    },
    'advanced': {
        'translation_batch_size': 20,
        'translation_context_size': 5,
        'temp_dir': './temp',
        'keep_temp_files': False,
    },
}


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration file"""
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f) or {}

    # Merge with default config
    import copy
    result = copy.deepcopy(DEFAULT_CONFIG)
    for key, value in config.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key].update(value)
        else:
            result[key] = value

    return result


def get_api_key(config: Dict[str, Any], provider: str, key_name: str) -> str:
    """Get API key, supports reading from environment variables"""
    import os

    # First try config file
    key = config.get(provider, {}).get(key_name, '')

    # If empty, try environment variable
    if not key:
        env_var_name = f"{provider.upper()}_{key_name.upper()}"
        key = os.environ.get(env_var_name, '')

    return key
