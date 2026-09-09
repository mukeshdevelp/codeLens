"""Shared PR analysis pipeline used by OAuth UI, webhooks, and Checks integration.

Centralized so production paths (manual analyze, webhook auto-analyze, check re-runs)
all persist identical report JSON and trigger the same GitHub side-effects.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzers.service import analyze_pull_request
from app.config import settings
from app.db.models import GitHubInstallation
from app.services.checks import upsert_check_run
from app.services.commits import enrich_pr_file_patches, fetch_pr_commits_detailed
from app.services.discussion import fetch_pr_discussion
from app.services.embed_tokens import signed_embed_url
from app.services.github import GitHubClient
from app.services.github_app import get_installation_access_token
from app.services.installations import find_installation_for_repo
from app.services.pr_comments import post_pr_summary_comment
from app.services.reports import persist_pr_report


def _build_pr_meta(pr: dict[str, Any], files: list, commits: list[dict[str, Any]]) -> dict[str, Any]:
    head_sha = pr.get("head", {}).get("sha")
    return {
        "author": pr["user"]["login"],
        "state": pr["state"],
        "additions": pr.get("additions", 0),
        "deletions": pr.get("deletions", 0),
        "changedFiles": pr.get("changed_files", len(files)),
        "commitCount": len(commits),
        "htmlUrl": pr.get("html_url"),
        "headSha": head_sha,
    }


async def _sync_github_check(
    db: AsyncSession,
    installation: GitHubInstallation | None,
    owner: str,
    repo: str,
    number: int,
    head_sha: str | None,
    report_dict: dict[str, Any],
    report_row,
) -> None:
    if not installation or not head_sha:
        return
    inst_token = await get_installation_access_token(installation.installation_id)
    gh_check = GitHubClient(inst_token)
    await upsert_check_run(
        db, gh_check, installation, owner, repo, number, head_sha, report_dict, report_row
    )


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

    report = await analyze_pull_request(
        pr["title"],
        pr.get("body"),
        files,
        pr_meta=_build_pr_meta(pr, files, commits),
        review_activity=activity,
        commits=commits,
    )
    report_dict = report.to_dict()

    report_row = await persist_pr_report(
        db,
        owner=owner,
        repo=repo,
        pr_number=number,
        title=pr["title"],
        head_sha=head_sha,
        report_dict=report_dict,
        source=source,
        user_id=user_id,
        installation=installation,
    )

    embed_url = signed_embed_url(owner, repo, number)

    should_check = sync_github_check if sync_github_check is not None else settings.enable_github_checks
    if should_check and not installation:
        installation = await find_installation_for_repo(db, owner, repo)
    if should_check:
        await _sync_github_check(
            db, installation, owner, repo, number, head_sha, report_dict, report_row
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
