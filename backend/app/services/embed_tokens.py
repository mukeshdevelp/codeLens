"""Signed embed tokens and embed URL builders for read-only PR reports in github.com iframes.

Integrated so Check Run ``details_url`` and GitHub sidebar embeds can load CodeLens
without requiring the reviewer's OAuth session, while still preventing public enumeration.
"""

from __future__ import annotations

import hashlib
import hmac

from app.config import settings


def embed_token(owner: str, repo: str, pr_number: int, secret: str) -> str:
    """Create HMAC token for ``/embed/...`` and ``/api/embed/.../report`` endpoints."""
    message = f"{owner}/{repo}/{pr_number}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_embed_token(owner: str, repo: str, pr_number: int, secret: str, token: str) -> bool:
    """Validate embed token; constant-time compare to resist timing attacks."""
    if not secret or not token:
        return False
    expected = embed_token(owner, repo, pr_number, secret)
    return hmac.compare_digest(expected, token)


def build_embed_url(
    owner: str,
    repo: str,
    pr_number: int,
    *,
    token: str | None = None,
    from_github: bool = False,
) -> str:
    """Build frontend embed URL, optionally with signed token and GitHub referrer flag."""
    base = (
        f"{settings.frontend_url.rstrip('/')}/embed/repos/{owner}/{repo}/pulls/{pr_number}"
    )
    params: list[str] = []
    if token:
        params.append(f"token={token}")
    if from_github:
        params.append("from=github")
    if params:
        return f"{base}?{'&'.join(params)}"
    return base


def signed_embed_url(owner: str, repo: str, pr_number: int) -> str | None:
    """Return a signed embed URL when ``EMBED_SHARED_SECRET`` is configured."""
    if not settings.embed_configured():
        return None
    token = embed_token(owner, repo, pr_number, settings.embed_shared_secret)
    return build_embed_url(owner, repo, pr_number, token=token)
