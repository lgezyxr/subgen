"""OpenAI Codex (ChatGPT Plus) OAuth authentication.

Uses Auth0-based OAuth to authenticate with ChatGPT and access the backend API.
This allows using your ChatGPT Plus subscription for translation.
"""

import time
import json
import secrets
import hashlib
import base64
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs
from typing import Optional, Callable

import requests

from .store import get_credential, save_credential


# OAuth Configuration (from OpenClaw/pi-ai)
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
REDIRECT_URI = "http://localhost:1455/auth/callback"
SCOPE = "openid profile email offline_access"
CHATGPT_API_URL = "https://chatgpt.com/backend-api"
JWT_CLAIM_PATH = "https://api.openai.com/auth"


class OpenAICodexAuthError(Exception):
    """OpenAI Codex authentication error."""
    pass


def _generate_pkce() -> tuple[str, str]:
    """Generate PKCE code verifier and challenge."""
    # Generate 32 random bytes for verifier
    verifier_bytes = secrets.token_bytes(32)
    verifier = base64.urlsafe_b64encode(verifier_bytes).rstrip(b'=').decode('ascii')

    # Create challenge from verifier
    challenge_bytes = hashlib.sha256(verifier.encode('ascii')).digest()
    challenge = base64.urlsafe_b64encode(challenge_bytes).rstrip(b'=').decode('ascii')

    return verifier, challenge


def _decode_jwt(token: str) -> Optional[dict]:
    """Decode JWT payload without verification."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None

        # Add padding if needed
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding

        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception:
        return None


def _get_account_id(access_token: str) -> Optional[str]:
    """Extract ChatGPT account ID from JWT token."""
    payload = _decode_jwt(access_token)
    if not payload:
        return None

    auth_claim = payload.get(JWT_CLAIM_PATH, {})
    account_id = auth_claim.get("chatgpt_account_id")

    return account_id if isinstance(account_id, str) and account_id else None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""

    def log_message(self, format, *args):
        """Suppress HTTP server logs."""
        pass

    def do_GET(self):
        """Handle OAuth callback."""
        parsed = urlparse(self.path)

        if parsed.path != "/auth/callback":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        params = parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]

        if not code:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing authorization code")
            return

        # Store code and state on server instance
        self.server.auth_code = code
        self.server.auth_state = state

        # Send success response
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"""<!doctype html>
<html><head><title>Success</title></head>
<body><h1>Authentication successful!</h1>
<p>You can close this window and return to the terminal.</p></body></html>""")


def _exchange_code_for_token(code: str, verifier: str) -> dict:
    """Exchange authorization code for tokens."""
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    if not response.ok:
        raise OpenAICodexAuthError(f"Token exchange failed: {response.status_code} {response.text[:200]}")

    data = response.json()

    if "access_token" not in data or "refresh_token" not in data:
        raise OpenAICodexAuthError("Invalid token response")

    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_in": data.get("expires_in", 3600),
    }


def _refresh_access_token(refresh_token: str) -> dict:
    """Refresh the access token."""
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    if not response.ok:
        raise OpenAICodexAuthError(f"Token refresh failed: {response.status_code}")

    data = response.json()

    if "access_token" not in data:
        raise OpenAICodexAuthError("Invalid refresh response")

    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", refresh_token),
        "expires_in": data.get("expires_in", 3600),
    }


def openai_codex_login(
    on_url: Optional[Callable[[str], None]] = None,
    timeout: int = 120
) -> dict:
    """
    Complete OpenAI Codex (ChatGPT Plus) OAuth login flow.

    Args:
        on_url: Callback when auth URL is ready
        timeout: Timeout in seconds waiting for callback

    Returns:
        dict with access_token, refresh_token, expires_at, account_id
    """
    # Generate PKCE and state
    verifier, challenge = _generate_pkce()
    state = secrets.token_hex(16)

    # Build authorization URL
    auth_params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "originator": "subgen",
    }
    auth_url = f"{AUTHORIZE_URL}?{urlencode(auth_params)}"

    # Start local server
    server = HTTPServer(("127.0.0.1", 1455), OAuthCallbackHandler)
    server.auth_code = None
    server.auth_state = None
    server.timeout = 1

    # Notify about URL
    if on_url:
        on_url(auth_url)
    else:
        print("\n🔐 OpenAI ChatGPT Authorization")
        print("   Opening browser...")
        print(f"   If browser doesn't open, visit:\n   {auth_url}\n")

    # Open browser
    webbrowser.open(auth_url)

    # Wait for callback
    start_time = time.time()
    while time.time() - start_time < timeout:
        server.handle_request()
        if server.auth_code:
            break

    server.server_close()

    if not server.auth_code:
        raise OpenAICodexAuthError("Authorization timeout. Please try again.")

    if server.auth_state != state:
        raise OpenAICodexAuthError("State mismatch. Possible CSRF attack.")

    # Exchange code for tokens
    tokens = _exchange_code_for_token(server.auth_code, verifier)

    # Extract account ID
    account_id = _get_account_id(tokens["access_token"])
    if not account_id:
        raise OpenAICodexAuthError("Failed to extract account ID from token")

    # Calculate expiration
    expires_at = time.time() + tokens["expires_in"]

    # Save credentials
    credential = {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "expires_at": expires_at,
        "account_id": account_id,
    }
    save_credential("openai-codex", credential)

    return credential


def get_openai_codex_token() -> tuple[str, str]:
    """
    Get valid OpenAI Codex access token and account ID, refreshing if needed.

    Returns:
        Tuple of (access_token, account_id)

    Raises:
        OpenAICodexAuthError if not logged in or refresh fails
    """
    cred = get_credential("openai-codex")

    if not cred:
        raise OpenAICodexAuthError("Not logged in. Please run: subgen auth login chatgpt")

    # Check if token is expired (with 5 min buffer)
    expires_at = cred.get("expires_at", 0)
    if time.time() >= expires_at - 300:
        # Refresh token
        refresh_token = cred.get("refresh_token")
        if not refresh_token:
            raise OpenAICodexAuthError("No refresh token. Please login again.")

        try:
            tokens = _refresh_access_token(refresh_token)

            # Update stored credential
            cred["access_token"] = tokens["access_token"]
            cred["refresh_token"] = tokens["refresh_token"]
            cred["expires_at"] = time.time() + tokens["expires_in"]

            # Re-extract account ID in case it changed
            account_id = _get_account_id(tokens["access_token"])
            if account_id:
                cred["account_id"] = account_id

            save_credential("openai-codex", cred)

        except OpenAICodexAuthError:
            raise OpenAICodexAuthError("Session expired. Please login again: subgen auth login chatgpt")

    return cred["access_token"], cred["account_id"]


def is_openai_codex_logged_in() -> bool:
    """Check if user is logged in to OpenAI Codex."""
    cred = get_credential("openai-codex")
    return cred is not None and "access_token" in cred
