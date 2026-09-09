"""Shared GitHub REST API HTTP constants and header builders."""

from __future__ import annotations

GITHUB_API_VERSION = "2022-11-28"
GITHUB_API_BASE = "https://api.github.com"


def github_api_headers(token: str) -> dict[str, str]:
    """Standard headers for GitHub REST v3 requests."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
