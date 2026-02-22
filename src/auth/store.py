"""Credential storage for OAuth tokens."""

import json
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta


def get_credentials_path() -> Path:
    """Get the path to credentials file."""
    # Check for XDG config dir first, fallback to ~/.subgen
    xdg_config = Path.home() / ".config" / "subgen"
    default_dir = Path.home() / ".subgen"

    # Use XDG if it exists, otherwise use default
    config_dir = xdg_config if xdg_config.exists() else default_dir
    config_dir.mkdir(parents=True, exist_ok=True)

    return config_dir / "credentials.json"


def load_credentials() -> dict:
    """Load all stored credentials."""
    path = get_credentials_path()
    if not path.exists():
        return {}

    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_credentials(credentials: dict) -> None:
    """Save credentials to file."""
    path = get_credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, 'w') as f:
        json.dump(credentials, f, indent=2)

    # Set restrictive permissions (owner read/write only)
    path.chmod(0o600)


def get_credential(provider: str) -> Optional[dict]:
    """Get credential for a specific provider."""
    creds = load_credentials()
    return creds.get(provider)


def save_credential(provider: str, credential: dict) -> None:
    """Save credential for a specific provider."""
    creds = load_credentials()
    creds[provider] = {
        **credential,
        "saved_at": datetime.now().isoformat()
    }
    save_credentials(creds)


def delete_credential(provider: str) -> bool:
    """Delete credential for a specific provider."""
    creds = load_credentials()
    if provider in creds:
        del creds[provider]
        save_credentials(creds)
        return True
    return False


def is_token_expired(credential: dict, buffer_seconds: int = 300) -> bool:
    """Check if a token is expired (with buffer time)."""
    expires_at = credential.get("expires_at")
    if not expires_at:
        return False  # No expiry info, assume valid

    # expires_at can be Unix timestamp or ISO string
    if isinstance(expires_at, (int, float)):
        expiry_time = datetime.fromtimestamp(expires_at)
    else:
        expiry_time = datetime.fromisoformat(expires_at)

    buffer = buffer_seconds
    return datetime.now() >= expiry_time - timedelta(seconds=buffer)
