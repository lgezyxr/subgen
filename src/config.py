"""配置加载模块"""

import yaml
from pathlib import Path
from typing import Dict, Any


# 默认配置
DEFAULT_CONFIG: Dict[str, Any] = {
    'whisper': {
        'provider': 'local',
        'local_model': 'large-v3',
        'device': 'cuda',
        'source_language': 'auto',  # 源语言，auto=自动检测
    },
    'translation': {
        'provider': 'openai',
        'model': 'gpt-4o-mini',
    },
    'output': {
        'format': 'srt',
        'source_language': 'auto',  # 翻译源语言
        'target_language': 'zh',    # 翻译目标语言
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
    """加载配置文件"""
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f) or {}

    # 与默认配置合并
    import copy
    result = copy.deepcopy(DEFAULT_CONFIG)
    for key, value in config.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key].update(value)
        else:
            result[key] = value

    return result


def get_api_key(config: Dict[str, Any], provider: str, key_name: str) -> str:
    """获取 API Key，支持从环境变量读取"""
    import os

    # 先从配置文件读
    key = config.get(provider, {}).get(key_name, '')

    # 如果为空，尝试从环境变量读
    if not key:
        env_var_name = f"{provider.upper()}_{key_name.upper()}"
        key = os.environ.get(env_var_name, '')

    return key
