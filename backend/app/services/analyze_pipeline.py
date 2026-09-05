"""Shared PR analysis pipeline used by OAuth UI, webhooks, and Checks integration.

Centralized so production paths (manual analyze, webhook auto-analyze, check re-runs)
all persist identical report JSON and trigger the same GitHub side-effects.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzers.service import analyze_pull_request
from app.config import settings
from app.db.models import GitHubInstallation, PrReport
from app.services.installations import find_installation_for_repo
from app.services.checks import upsert_check_run
from app.services.commits import enrich_pr_file_patches, fetch_pr_commits_detailed
from app.services.discussion import fetch_pr_discussion
from app.services.embed_tokens import embed_token
from app.services.github import GitHubClient
from app.services.pr_comments import post_pr_summary_comment


async def run_pr_analysis(
    db: AsyncSession,
    gh: GitHubClient,
    owner: str,
    repo: str,
    number: int,
    *,
    user_id: int | None = None,
    installation: GitHubInstallation | None = None,
    source: str = "oauth",
    post_github_comment: bool = False,
    post_comment_force: bool = False,
    sync_github_check: bool | None = None,
) -> dict[str, Any]:
    """
    Fetch PR from GitHub, run analyzers, cache report, optionally sync Checks + PR comment.

    Args:
        db: Async SQLAlchemy session for ``pr_reports`` and integration tables.
        gh: Authenticated GitHub client (OAuth user token or installation token).
        owner: Repository owner login.
        repo: Repository name.
        number: Pull request number.
        user_id: OAuth user when triggered from web UI; None for webhooks.
        installation: GitHub App installation row when triggered by webhook.
        source: Provenance label stored on ``pr_reports.source`` (oauth|webhook|api).
        post_github_comment: Post markdown summary to PR conversation.
        post_comment_force: Allow duplicate comment posts (manual re-post).
        sync_github_check: Create/update Check Run; defaults to ``settings.enable_github_checks``.

    Returns:
        Analysis report dict (``AnalysisReport.to_dict()``).
    """
    pr = await gh.get_pull(owner, repo, number)
    files = await gh.list_pr_files(owner, repo, number)
    await enrich_pr_file_patches(
        gh,
        owner,
        repo,
        files,
        pr.get("base", {}).get("sha"),
        pr.get("head", {}).get("sha"),
    )
    commits = await fetch_pr_commits_detailed(gh, owner, repo, number)
    activity = await fetch_pr_discussion(gh, owner, repo, number)
    head_sha = pr.get("head", {}).get("sha")

    pr_meta = {
        "author": pr["user"]["login"],
        "state": pr["state"],
        "additions": pr.get("additions", 0),
        "deletions": pr.get("deletions", 0),
        "changedFiles": pr.get("changed_files", len(files)),
        "commitCount": len(commits),
        "htmlUrl": pr.get("html_url"),
        "headSha": head_sha,
    }
    report = await analyze_pull_request(
        pr["title"],
        pr.get("body"),
        files,
        pr_meta=pr_meta,
        review_activity=activity,
        commits=commits,
    )
    report_dict = report.to_dict()

    result = await db.execute(
        select(PrReport).where(
            PrReport.owner == owner,
            PrReport.repo == repo,
            PrReport.pr_number == number,
        )
    )
    existing = result.scalar_one_or_none()
    report_json = json.dumps(report_dict)
    if existing:
        existing.title = pr["title"]
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
            pr_number=number,
            title=pr["title"],
            head_sha=head_sha,
            source=source,
            report_json=report_json,
        )
        db.add(report_row)

    await db.commit()
    await db.refresh(report_row)

    embed_url = None
    if settings.embed_configured():
        token = embed_token(owner, repo, number, settings.embed_shared_secret)
        embed_url = (
            f"{settings.frontend_url.rstrip('/')}/embed/repos/{owner}/{repo}/pulls/{number}"
            f"?token={token}"
        )

    should_check = sync_github_check if sync_github_check is not None else settings.enable_github_checks
    if should_check and not installation:
        installation = await find_installation_for_repo(db, owner, repo)
    if should_check and installation and head_sha:
        from app.services.github_app import get_installation_access_token

        inst_token = await get_installation_access_token(installation.installation_id)
        gh_check = GitHubClient(inst_token)
        await upsert_check_run(
            db, gh_check, installation, owner, repo, number, head_sha, report_dict, report_row
        )

    should_comment = post_github_comment or (
        source == "webhook" and settings.auto_post_pr_comment_on_webhook
    )
    if should_comment and settings.enable_github_pr_comments:
        await post_pr_summary_comment(
            db,
            gh,
            owner,
            repo,
            number,
            report_dict,
            report_row,
            user_id=user_id,
            embed_url=embed_url,
            force=post_comment_force,
        )

    return report_dict
