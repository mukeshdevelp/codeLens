"""GitHub Checks API integration — surface CodeLens risk on the PR checks tab.

Integrated so engineers see pass/fail/neutral status on github.com before opening
CodeLens. The check ``details_url`` deep-links to the signed embed report page.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import GitHubInstallation, PrCheckRun, PrReport
from app.services.embed_tokens import embed_token
from app.services.github import GitHubClient


def _risk_to_conclusion(risk_level: str) -> str:
    """Map CodeLens risk to GitHub check conclusion (neutral = informational medium risk)."""
    if risk_level == "high":
        return "failure"
    if risk_level == "medium":
        return "neutral"
    return "success"


def _embed_details_url(owner: str, repo: str, pr_number: int) -> str:
    """Build production URL for Check Run details (signed embed when secret configured)."""
    base = f"{settings.frontend_url.rstrip('/')}/embed/repos/{owner}/{repo}/pulls/{pr_number}"
    if settings.embed_configured():
        token = embed_token(owner, repo, pr_number, settings.embed_shared_secret)
        return f"{base}?token={token}&from=github"
    return f"{base}?from=github"


def _check_output(report: dict[str, Any]) -> dict[str, str]:
    """GitHub Check output block — title + summary shown on the checks tab."""
    risk = report.get("riskLevel", "unknown").upper()
    score = report.get("riskScore", 0)
    focus = report.get("focusAreas") or []
    focus_lines = "\n".join(
        f"- {a.get('area')}: {a.get('reason')}" for a in focus[:3]
    ) or "No critical focus areas."
    return {
        "title": f"CodeLens {risk} risk ({score}/100)",
        "summary": report.get("executiveSummary") or report.get("prOverview") or "Analysis complete.",
        "text": f"### Focus areas\n{focus_lines}",
    }


async def upsert_check_run(
    db: AsyncSession,
    gh: GitHubClient,
    installation: GitHubInstallation,
    owner: str,
    repo: str,
    pr_number: int,
    head_sha: str,
    report: dict[str, Any],
    report_row: PrReport,
) -> dict[str, Any]:
    """Create or update a Check Run on the PR head commit and persist ``pr_check_runs`` row."""
    details_url = _embed_details_url(owner, repo, pr_number)
    conclusion = _risk_to_conclusion(report.get("riskLevel", "low"))
    output = _check_output(report)

    payload = {
        "name": "CodeLens",
        "head_sha": head_sha,
        "status": "completed",
        "conclusion": conclusion,
        "details_url": details_url,
        "output": output,
    }

    result = await db.execute(
        select(PrCheckRun).where(
            PrCheckRun.owner == owner,
            PrCheckRun.repo == repo,
            PrCheckRun.pr_number == pr_number,
            PrCheckRun.head_sha == head_sha,
        )
    )
    row = result.scalar_one_or_none()

    if row and row.check_run_id:
        check = await gh.update_check_run(owner, repo, row.check_run_id, payload)
    else:
        check = await gh.create_check_run(owner, repo, payload)
        if not row:
            row = PrCheckRun(
                installation_id=installation.id,
                report_id=report_row.id,
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                head_sha=head_sha,
            )
            db.add(row)
        row.check_run_id = check.get("id")
        row.conclusion = conclusion
        row.details_url = details_url
        row.report_id = report_row.id

    await db.commit()
    return {"checkRunId": check.get("id"), "conclusion": conclusion, "detailsUrl": details_url}
