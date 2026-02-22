"""配置加载模块"""

import yaml
from pathlib import Path
from typing import Dict, Any


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """加载配置文件"""
    path = Path(config_path)
    
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 设置默认值
    config.setdefault('whisper', {})
    config['whisper'].setdefault('provider', 'openai')
    config['whisper'].setdefault('local_model', 'large-v3')
    config['whisper'].setdefault('device', 'cuda')
    
    config.setdefault('translation', {})
    config['translation'].setdefault('provider', 'openai')
    config['translation'].setdefault('model', 'gpt-4o-mini')
    
    config.setdefault('output', {})
    config['output'].setdefault('format', 'srt')
    config['output'].setdefault('target_language', 'zh')
    config['output'].setdefault('bilingual', False)
    config['output'].setdefault('max_chars_per_line', 42)
    config['output'].setdefault('embed_in_video', False)
    
    config.setdefault('advanced', {})
    config['advanced'].setdefault('translation_batch_size', 20)
    config['advanced'].setdefault('translation_context_size', 5)
    config['advanced'].setdefault('temp_dir', './temp')
    config['advanced'].setdefault('keep_temp_files', False)
    
    return config


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
