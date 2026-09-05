"""Persist GitHub App installation and repository registry from webhook payloads.

Integrated so webhook handlers know which installation_id to use for API calls
and which repositories are in scope for auto-analysis.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GitHubInstallation, RegisteredRepository


async def upsert_installation(db: AsyncSession, payload: dict[str, Any]) -> GitHubInstallation:
    """Create or update ``github_installations`` from an installation webhook payload."""
    installation = payload.get("installation") or payload
    inst_id = installation["id"]
    account = installation.get("account") or {}

    result = await db.execute(
        select(GitHubInstallation).where(GitHubInstallation.installation_id == inst_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        row = GitHubInstallation(installation_id=inst_id)
        db.add(row)

    row.account_login = account.get("login", row.account_login or "unknown")
    row.account_type = account.get("type", row.account_type or "User")
    row.repository_selection = installation.get("repository_selection", row.repository_selection)
    row.suspended = bool(installation.get("suspended_at"))
    row.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(row)
    return row


async def sync_repositories(
    db: AsyncSession,
    installation: GitHubInstallation,
    repositories_added: list[dict[str, Any]] | None = None,
    repositories_removed: list[dict[str, Any]] | None = None,
) -> None:
    """Register or deactivate repos when GitHub sends ``installation_repositories`` events."""
    for repo in repositories_added or []:
        full_name = repo.get("full_name") or f"{repo.get('owner', {}).get('login')}/{repo['name']}"
        parts = full_name.split("/", 1)
        owner, name = parts[0], parts[1] if len(parts) > 1 else repo["name"]
        result = await db.execute(
            select(RegisteredRepository).where(
                RegisteredRepository.installation_id == installation.id,
                RegisteredRepository.full_name == full_name,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            row = RegisteredRepository(
                installation_id=installation.id,
                owner=owner,
                repo=name,
                full_name=full_name,
            )
            db.add(row)
        row.active = True

    for repo in repositories_removed or []:
        full_name = repo.get("full_name") or repo.get("name", "")
        result = await db.execute(
            select(RegisteredRepository).where(
                RegisteredRepository.installation_id == installation.id,
                RegisteredRepository.full_name == full_name,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            row.active = False

    await db.commit()


async def get_installation_by_github_id(
    db: AsyncSession, installation_id: int
) -> GitHubInstallation | None:
    """Lookup installation row by GitHub's installation id (from webhook payload)."""
    result = await db.execute(
        select(GitHubInstallation).where(GitHubInstallation.installation_id == installation_id)
    )
    return result.scalar_one_or_none()


async def find_installation_for_repo(
    db: AsyncSession, owner: str, repo: str
) -> GitHubInstallation | None:
    """Find active GitHub App installation that registered this repository (for OAuth-triggered Checks)."""
    result = await db.execute(
        select(GitHubInstallation)
        .join(RegisteredRepository, RegisteredRepository.installation_id == GitHubInstallation.id)
        .where(
            RegisteredRepository.owner == owner,
            RegisteredRepository.repo == repo,
            RegisteredRepository.active.is_(True),
            GitHubInstallation.suspended.is_(False),
        )
    )
    return result.scalar_one_or_none()
