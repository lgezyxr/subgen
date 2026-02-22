"""Authentication module for SubGen."""

from .store import (
    get_credential,
    save_credential,
    delete_credential,
    get_credentials_path
)

from .copilot import (
    copilot_login,
    get_copilot_api_token,
    is_copilot_logged_in,
    CopilotAuthError
)

__all__ = [
    # Store
    "get_credential",
    "save_credential",
    "delete_credential",
    "get_credentials_path",
    # Copilot
    "copilot_login",
    "get_copilot_api_token",
    "is_copilot_logged_in",
    "CopilotAuthError",
]
