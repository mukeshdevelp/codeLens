"""GitHub App authentication — JWT + installation access tokens.

Integrated for production because OAuth user tokens cannot receive organization webhooks
or create Check Runs on behalf of the app. The GitHub App is the standard way to:
- Verify and process ``pull_request`` webhooks
- Post Check Runs visible on the PR checks tab
- Post PR summary comments without a user session
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from jose import jwt

from app.config import settings

# In-memory installation token cache: installation_id -> (token, expires_at_epoch)
_token_cache: dict[int, tuple[str, int]] = {}


def _load_private_key() -> str:
    """Load PEM private key from env string or file path (production: mount secret as file)."""
    if settings.github_app_private_key:
        return settings.github_app_private_key.replace("\\n", "\n")
    if settings.github_app_private_key_path:
        return open(settings.github_app_private_key_path, encoding="utf-8").read()
    raise ValueError("GitHub App private key not configured")


def create_app_jwt() -> str:
    """Mint a short-lived JWT to authenticate as the GitHub App (max 10 minutes)."""
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 600,
        "iss": settings.github_app_id,
    }
    return jwt.encode(payload, _load_private_key(), algorithm="RS256")


async def get_installation_access_token(installation_id: int) -> str:
    """Exchange app JWT for an installation token; cached until 5 minutes before expiry."""
    cached = _token_cache.get(installation_id)
    if cached and cached[1] > int(time.time()) + 300:
        return cached[0]

    app_jwt = create_app_jwt()
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        res.raise_for_status()
        data = res.json()

    token = data["token"]
    expires_at = data.get("expires_at")
    # GitHub returns ISO timestamp; cache ~1 hour default
    expiry_epoch = int(time.time()) + 3500
    if expires_at:
        from datetime import datetime

        try:
            expiry_epoch = int(datetime.fromisoformat(expires_at.replace("Z", "+00:00")).timestamp())
        except ValueError:
            pass
    _token_cache[installation_id] = (token, expiry_epoch)
    return token


async def get_app_info() -> dict[str, Any]:
    """Fetch GitHub App metadata (health check for production monitoring)."""
    app_jwt = create_app_jwt()
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(
            "https://api.github.com/app",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        res.raise_for_status()
        return res.json()
