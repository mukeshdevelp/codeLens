"""PrReport database helpers — lookup, load, and persist cached analysis JSON."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GitHubInstallation, PrReport


async def get_pr_report_row(
    db: AsyncSession,
    owner: str,
    repo: str,
    pr_number: int,
) -> PrReport | None:
    """Return the cached ``PrReport`` row for a pull request, if any."""
    result = await db.execute(
        select(PrReport).where(
            PrReport.owner == owner,
            PrReport.repo == repo,
            PrReport.pr_number == pr_number,
        )
    )
    return result.scalar_one_or_none()


def load_report_dict(row: PrReport) -> dict[str, Any]:
    """Deserialize ``report_json`` from a ``PrReport`` row."""
    return json.loads(row.report_json)


async def persist_pr_report(
    db: AsyncSession,
    *,
    owner: str,
    repo: str,
    pr_number: int,
    title: str,
    head_sha: str | None,
    report_dict: dict[str, Any],
    source: str,
    user_id: int | None = None,
    installation: GitHubInstallation | None = None,
) -> PrReport:
    """Insert or update a cached PR analysis report."""
    existing = await get_pr_report_row(db, owner, repo, pr_number)
    report_json = json.dumps(report_dict)

    if existing:
        existing.title = title
        existing.report_json = report_json
        existing.head_sha = head_sha
        existing.source = source
        if user_id is not None:
            existing.user_id = user_id
        if installation is not None:
            existing.installation_id = installation.id
        report_row = existing
    else:
        report_row = PrReport(
            user_id=user_id,
            installation_id=installation.id if installation else None,
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            title=title,
            head_sha=head_sha,
            source=source,
            report_json=report_json,
        )
        db.add(report_row)

    await db.commit()
    await db.refresh(report_row)
    return report_row
