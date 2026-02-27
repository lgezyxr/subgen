"""Configuration loading module"""

import sys
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


def load_config(config_path: str = None) -> Dict[str, Any]:
    """Load configuration file.

    Search order: config_path arg → ./config.yaml → ~/.subgen/config.yaml

    Args:
        config_path: Explicit config file path. If None, searches default locations.

    Returns:
        Merged configuration dictionary.

    Raises:
        FileNotFoundError: If no config file found.
    """
    if config_path:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
    else:
        # Search default locations
        candidates = [
            Path("config.yaml"),
            get_subgen_dir() / "config.yaml",
        ]
        path = None
        for candidate in candidates:
            if candidate.exists():
                path = candidate
                break
        if path is None:
            raise FileNotFoundError("Config file not found in ./config.yaml or ~/.subgen/config.yaml")

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

    # Validate that top-level keys are dicts where expected
    _validate_config(result)

    return result


def _validate_config(config: Dict[str, Any]) -> None:
    """Validate basic config schema after merge.

    Ensures top-level keys that are expected to be dicts are actually dicts,
    preventing cryptic crashes later (e.g. 'whisper: null' in YAML).

    Args:
        config: Merged configuration dictionary.

    Raises:
        ValueError: If validation fails.
    """
    required_dict_keys = ['whisper', 'translation', 'output', 'advanced']
    for key in required_dict_keys:
        value = config.get(key)
        if value is None:
            raise ValueError(
                f"Configuration error: '{key}' is null/missing. "
                f"Please provide a valid mapping or remove the key to use defaults."
            )
        if not isinstance(value, dict):
            raise ValueError(
                f"Configuration error: '{key}' must be a mapping/dict, "
                f"got {type(value).__name__}: {value!r}"
            )


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


def get_subgen_dir() -> Path:
    """Get the SubGen data directory (~/.subgen/).

    Returns:
        Path to ~/.subgen/ directory.
    """
    return Path.home() / ".subgen"


def get_bundled_path(relative: str) -> Path:
    """Get path to a bundled resource, compatible with PyInstaller.

    Args:
        relative: Relative path within the bundle.

    Returns:
        Absolute path to the resource.
    """
    # PyInstaller sets sys._MEIPASS to the temp extraction dir
    base = getattr(sys, "_MEIPASS", Path(__file__).parent.parent)
    return Path(base) / relative


def is_bundled() -> bool:
    """Check if running as PyInstaller bundle."""
    return getattr(sys, '_MEIPASS', None) is not None
