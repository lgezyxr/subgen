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

from .openai_codex import (
    openai_codex_login,
    get_openai_codex_token,
    is_openai_codex_logged_in,
    OpenAICodexAuthError
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
    # OpenAI Codex (ChatGPT Plus)
    "openai_codex_login",
    "get_openai_codex_token",
    "is_openai_codex_logged_in",
    "OpenAICodexAuthError",
]
