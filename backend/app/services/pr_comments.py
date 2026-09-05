"""Format and post PR analysis summaries as GitHub issue comments.

Integrated so reviewers see CodeLens output directly on the PR conversation thread
on github.com, without leaving GitHub. Posts are recorded in ``pr_review_posts`` to
avoid duplicate comments on webhook re-runs unless ``force=True``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PrReport, PrReviewPost
from app.services.github import GitHubClient


def format_pr_comment(report: dict[str, Any], embed_url: str | None = None) -> str:
    """Build markdown comment body from analysis report (concise, evidence-linked)."""
    risk = report.get("riskLevel", "unknown").upper()
    score = report.get("riskScore", 0)
    lines = [
        f"## CodeLens — {risk} risk ({score}/100)",
        "",
        report.get("executiveSummary") or report.get("prOverview") or "_No summary available._",
        "",
    ]
    focus = report.get("focusAreas") or []
    if focus:
        lines.append("### Where to focus")
        for area in focus[:5]:
            files = ", ".join(area.get("files") or [])
            suffix = f" — `{files}`" if files else ""
            lines.append(f"- **#{area.get('rank')} {area.get('area')}** ({area.get('severity')}): {area.get('reason')}{suffix}")
        lines.append("")

    if embed_url:
        lines.append(f"[Open full CodeLens report]({embed_url})")
    lines.append("")
    lines.append("_Automated PR brief by [CodeLens](https://github.com) — human review still required._")
    return "\n".join(lines)


async def post_pr_summary_comment(
    db: AsyncSession,
    gh: GitHubClient,
    owner: str,
    repo: str,
    pr_number: int,
    report: dict[str, Any],
    report_row: PrReport | None,
    user_id: int | None = None,
    embed_url: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Post summary comment to PR; skip if already posted unless ``force``."""
    if not force:
        existing = await db.execute(
            select(PrReviewPost).where(
                PrReviewPost.owner == owner,
                PrReviewPost.repo == repo,
                PrReviewPost.pr_number == pr_number,
            )
        )
        if existing.scalar_one_or_none():
            return {"skipped": True, "reason": "already_posted"}

    body = format_pr_comment(report, embed_url=embed_url)
    comment = await gh.create_issue_comment(owner, repo, pr_number, body)

    db.add(
        PrReviewPost(
            user_id=user_id,
            report_id=report_row.id if report_row else None,
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            github_comment_id=comment.get("id"),
            comment_type="issue_comment",
            body_preview=body[:500],
            posted_at=datetime.utcnow(),
        )
    )
    await db.commit()
    return {"posted": True, "commentId": comment.get("id"), "htmlUrl": comment.get("html_url")}
