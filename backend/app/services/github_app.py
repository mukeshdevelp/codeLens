"""GitHub App authentication — JWT + installation access tokens."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import httpx
from jose import jwt

from app.config import settings
from app.services.github_http import GITHUB_API_BASE, github_api_headers

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


async def _app_request(method: str, path: str, *, json: dict | None = None) -> dict[str, Any]:
    app_jwt = create_app_jwt()
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.request(
            method,
            f"{GITHUB_API_BASE}{path}",
            headers=github_api_headers(app_jwt),
            json=json,
        )
        res.raise_for_status()
        return res.json()


async def get_installation_access_token(installation_id: int) -> str:
    """Exchange app JWT for an installation token; cached until 5 minutes before expiry."""
    cached = _token_cache.get(installation_id)
    if cached and cached[1] > int(time.time()) + 300:
        return cached[0]

    data = await _app_request("POST", f"/app/installations/{installation_id}/access_tokens")
    token = data["token"]
    expires_at = data.get("expires_at")
    expiry_epoch = int(time.time()) + 3500
    if expires_at:
        try:
            expiry_epoch = int(datetime.fromisoformat(expires_at.replace("Z", "+00:00")).timestamp())
        except ValueError:
            pass
    _token_cache[installation_id] = (token, expiry_epoch)
    return token


async def get_app_info() -> dict[str, Any]:
    """Fetch GitHub App metadata (health check for production monitoring)."""
    return await _app_request("GET", "/app")
