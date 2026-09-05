"""Signed embed tokens for read-only PR reports inside github.com iframes.

Integrated so Check Run ``details_url`` and GitHub sidebar embeds can load CodeLens
without requiring the reviewer's OAuth session, while still preventing public enumeration.
"""

from __future__ import annotations

import hashlib
import hmac


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
