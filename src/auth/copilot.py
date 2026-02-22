"""GitHub Copilot OAuth authentication using device code flow."""

import time
import requests
from typing import Optional, Callable

from .store import get_credential, save_credential


# GitHub's public Copilot OAuth client ID
CLIENT_ID = "Iv1.b507a08c87ecfe98"
DEVICE_CODE_URL = "https://github.com/login/device/code"
ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
COPILOT_TOKEN_URL = "https://api.github.com/copilot_internal/v2/token"


class CopilotAuthError(Exception):
    """Copilot authentication error."""
    pass


def request_device_code() -> dict:
    """Request a device code from GitHub."""
    response = requests.post(
        DEVICE_CODE_URL,
        data={
            "client_id": CLIENT_ID,
            "scope": "read:user"
        },
        headers={
            "Accept": "application/json"
        }
    )

    if not response.ok:
        raise CopilotAuthError(f"Failed to get device code: HTTP {response.status_code}")

    data = response.json()

    if "error" in data:
        raise CopilotAuthError(f"GitHub error: {data.get('error_description', data['error'])}")

    return {
        "device_code": data["device_code"],
        "user_code": data["user_code"],
        "verification_uri": data["verification_uri"],
        "expires_in": data["expires_in"],
        "interval": data.get("interval", 5)
    }


def poll_for_access_token(device_code: str, interval: int, expires_in: int,
                          on_waiting: Optional[Callable] = None) -> str:
    """Poll GitHub for access token after user authorizes."""
    expires_at = time.time() + expires_in
    poll_interval = max(interval, 5)  # Minimum 5 seconds

    while time.time() < expires_at:
        response = requests.post(
            ACCESS_TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
            },
            headers={
                "Accept": "application/json"
            }
        )

        if not response.ok:
            raise CopilotAuthError(f"Token request failed: HTTP {response.status_code}")

        data = response.json()

        if "access_token" in data:
            return data["access_token"]

        error = data.get("error", "unknown")

        if error == "authorization_pending":
            if on_waiting:
                on_waiting()
            time.sleep(poll_interval)
            continue
        elif error == "slow_down":
            poll_interval += 5
            time.sleep(poll_interval)
            continue
        elif error == "expired_token":
            raise CopilotAuthError("Device code expired. Please try again.")
        elif error == "access_denied":
            raise CopilotAuthError("Authorization was denied.")
        else:
            raise CopilotAuthError(f"Authorization error: {error}")

    raise CopilotAuthError("Device code expired. Please try again.")


def get_copilot_token(github_token: str) -> dict:
    """Exchange GitHub token for Copilot API token."""
    response = requests.get(
        COPILOT_TOKEN_URL,
        headers={
            "Authorization": f"token {github_token}",
            "Accept": "application/json"
        }
    )

    if response.status_code == 401:
        raise CopilotAuthError("GitHub token is invalid or expired. Please login again.")

    if not response.ok:
        raise CopilotAuthError(f"Failed to get Copilot token: HTTP {response.status_code}")

    data = response.json()

    return {
        "token": data["token"],
        "expires_at": data.get("expires_at", 0)
    }


def copilot_login(on_code: Optional[Callable[[str, str], None]] = None,
                  on_waiting: Optional[Callable] = None) -> dict:
    """
    Complete Copilot OAuth login flow.

    Args:
        on_code: Callback when device code is ready. Receives (user_code, verification_uri)
        on_waiting: Callback while waiting for user authorization

    Returns:
        dict with github_token and copilot_token info
    """
    # Step 1: Get device code
    device = request_device_code()

    # Notify user
    if on_code:
        on_code(device["user_code"], device["verification_uri"])
    else:
        print("\n🔐 GitHub Copilot Authorization Required")
        print(f"   Visit: {device['verification_uri']}")
        print(f"   Enter code: {device['user_code']}\n")

    # Step 2: Poll for access token
    github_token = poll_for_access_token(
        device["device_code"],
        device["interval"],
        device["expires_in"],
        on_waiting
    )

    # Step 3: Get Copilot token
    copilot = get_copilot_token(github_token)

    # Save credentials
    credential = {
        "github_token": github_token,
        "copilot_token": copilot["token"],
        "copilot_expires_at": copilot["expires_at"]
    }
    save_credential("copilot", credential)

    return credential


def get_copilot_api_token() -> str:
    """
    Get a valid Copilot API token, refreshing if necessary.

    Returns:
        Copilot API token string

    Raises:
        CopilotAuthError if not logged in or refresh fails
    """
    cred = get_credential("copilot")

    if not cred:
        raise CopilotAuthError("Not logged in. Please run: subgen auth login copilot")

    # Check if Copilot token is expired
    copilot_expires = cred.get("copilot_expires_at", 0)
    if copilot_expires and time.time() >= copilot_expires - 300:  # 5 min buffer
        # Refresh Copilot token using GitHub token
        try:
            github_token = cred.get("github_token")
            if not github_token:
                raise CopilotAuthError("GitHub token missing. Please login again.")

            copilot = get_copilot_token(github_token)

            # Update stored credential
            cred["copilot_token"] = copilot["token"]
            cred["copilot_expires_at"] = copilot["expires_at"]
            save_credential("copilot", cred)

            return copilot["token"]
        except CopilotAuthError:
            raise CopilotAuthError("Session expired. Please login again: subgen auth login copilot")

    return cred["copilot_token"]


def is_copilot_logged_in() -> bool:
    """Check if user is logged in to Copilot."""
    cred = get_credential("copilot")
    return cred is not None and "github_token" in cred
