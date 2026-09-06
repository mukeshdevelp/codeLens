"""REST API routes for repos, PR analysis, AI status, and GitHub review actions."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzers.service import analyze_pull_request
from app.db import get_db
from app.db.models import PrReport, User
from app.routers.auth import get_current_user
from app.config import settings
from app.services.analyze_pipeline import run_pr_analysis
from app.services.github import (
    GitHubClient,
    can_user_approve_pr,
    pr_author_login,
    user_has_approved_pr,
)

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/ai/status")
async def ai_status():
    from app.analyzers.ai import ai_is_configured, get_last_ai_error, resolve_ai_config

    config = resolve_ai_config()
    return {
        "configured": ai_is_configured(),
        "provider": settings.resolved_ai_provider(),
        "model": config[2] if config else None,
        "lastError": get_last_ai_error(),
    }


@router.get("/ai/test")
async def ai_test():
    """Call the configured AI provider with a short prompt (verifies key + model)."""
    from app.analyzers.ai import ai_complete, get_last_ai_error, resolve_ai_config

    config = resolve_ai_config()
    if not config:
        return {"ok": False, "error": "No AI API key configured"}
    sample = await ai_complete("Reply with exactly: CodeLens AI is working.", max_tokens=100)
    return {
        "ok": bool(sample),
        "provider": settings.resolved_ai_provider(),
        "model": config[2],
        "sample": sample,
        "lastError": get_last_ai_error(),
    }


@router.post("/demo/analyze")
async def demo_analyze():
    """Analyze fixture PR without GitHub auth — for hackathon demo."""
    import json
    from pathlib import Path

    from app.analyzers.types import FileChange

    fixture_path = Path(__file__).resolve().parents[3] / "fixtures" / "demo-pr.json"
    data = json.loads(fixture_path.read_text())
    files = [FileChange(**f) for f in data["files"]]
    report = await analyze_pull_request(data["title"], data.get("body"), files)
    return report.to_dict()


@router.get("/repos")
async def list_repos(user: Annotated[User, Depends(get_current_user)]):
    """List GitHub repositories visible to the signed-in user."""
    gh = GitHubClient(user.access_token)
    repos = await gh.list_repos()
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "fullName": r["full_name"],
            "owner": r["owner"]["login"],
            "private": r["private"],
            "description": r.get("description"),
            "updatedAt": r["updated_at"],
            "openIssues": r["open_issues_count"],
            "defaultBranch": r["default_branch"],
            "htmlUrl": r["html_url"],
        }
        for r in repos
    ]


@router.get("/repos/{owner}/{repo}/pulls")
async def list_pulls(owner: str, repo: str, user: Annotated[User, Depends(get_current_user)]):
    gh = GitHubClient(user.access_token)
    pulls = await gh.list_pulls(owner, repo)
    return [
        {
            "number": p["number"],
            "title": p["title"],
            "state": p["state"],
            "author": p["user"]["login"],
            "createdAt": p["created_at"],
            "updatedAt": p["updated_at"],
            "htmlUrl": p["html_url"],
            "additions": p.get("additions"),
            "deletions": p.get("deletions"),
            "changedFiles": p.get("changed_files"),
        }
        for p in pulls
    ]


@router.post("/repos/{owner}/{repo}/pulls/{number}/analyze")
async def analyze_pr(
    owner: str,
    repo: str,
    number: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    post_github_comment: bool = False,
    sync_github_check: bool = False,
):
    """Analyze PR via OAuth user token; optionally post GitHub comment or sync Check Run if App installed."""
    gh = GitHubClient(user.access_token)
    return await run_pr_analysis(
        db,
        gh,
        owner,
        repo,
        number,
        user_id=user.id,
        source="oauth",
        post_github_comment=post_github_comment,
        sync_github_check=sync_github_check or settings.enable_github_checks,
    )


@router.get("/repos/{owner}/{repo}/pulls/{number}/report")
async def get_report(
    owner: str,
    repo: str,
    number: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(PrReport).where(PrReport.owner == owner, PrReport.repo == repo, PrReport.pr_number == number)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found. Run analyze first.")
    return json.loads(row.report_json)


@router.get("/repos/{owner}/{repo}/pulls/{number}/actions")
async def pr_actions(
    owner: str,
    repo: str,
    number: int,
    user: Annotated[User, Depends(get_current_user)],
):
    """Live PR state for approve/merge controls (mergeable, base branch, user approval)."""
    gh = GitHubClient(user.access_token)
    try:
        pr = await gh.get_pull(owner, repo, number)
        repo_meta = await gh.get_repo(owner, repo)
        reviews = await gh.list_pr_reviews(owner, repo, number)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load PR from GitHub: {exc}") from exc

    user_approved = user_has_approved_pr(reviews, user.login)
    author_login = pr_author_login(pr)
    is_author = bool(author_login and author_login == user.login)
    can_approve, approve_blocked_reason = can_user_approve_pr(pr, user.login, reviews)
    return {
        "state": pr.get("state"),
        "merged": bool(pr.get("merged")),
        "mergeable": pr.get("mergeable"),
        "mergeableState": pr.get("mergeable_state"),
        "baseRef": pr.get("base", {}).get("ref"),
        "defaultBranch": repo_meta.get("default_branch"),
        "authorLogin": author_login,
        "isAuthor": is_author,
        "userApproved": user_approved,
        "canApprove": can_approve,
        "approveBlockedReason": approve_blocked_reason,
        "title": pr.get("title"),
    }


@router.post("/repos/{owner}/{repo}/pulls/{number}/approve")
async def approve_pr(
    owner: str,
    repo: str,
    number: int,
    user: Annotated[User, Depends(get_current_user)],
):
    gh = GitHubClient(user.access_token)
    try:
        pr = await gh.get_pull(owner, repo, number)
        reviews = await gh.list_pr_reviews(owner, repo, number)
        can_approve, reason = can_user_approve_pr(pr, user.login, reviews)
        if not can_approve:
            raise HTTPException(status_code=400, detail=reason or "Cannot approve this pull request.")
        review = await gh.approve_pull_request(owner, repo, number)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub approve failed: {exc}") from exc
    return {
        "ok": True,
        "reviewId": review.get("id"),
        "state": review.get("state"),
        "htmlUrl": review.get("html_url"),
    }


@router.post("/repos/{owner}/{repo}/pulls/{number}/merge")
async def merge_pr(
    owner: str,
    repo: str,
    number: int,
    user: Annotated[User, Depends(get_current_user)],
    merge_method: str = "merge",
):
    if merge_method not in ("merge", "squash", "rebase"):
        raise HTTPException(status_code=400, detail="merge_method must be merge, squash, or rebase")

    gh = GitHubClient(user.access_token)
    try:
        pr = await gh.get_pull(owner, repo, number)
        if pr.get("state") != "open":
            raise HTTPException(status_code=400, detail="Only open pull requests can be merged.")
        if pr.get("merged"):
            raise HTTPException(status_code=400, detail="This pull request is already merged.")
        if pr.get("mergeable") is False:
            state = pr.get("mergeable_state") or "not mergeable"
            raise HTTPException(
                status_code=409,
                detail=f"Pull request cannot be merged ({state}). Resolve conflicts or wait for checks.",
            )
        result = await gh.merge_pull_request(owner, repo, number, merge_method=merge_method)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub merge failed: {exc}") from exc
    return {
        "ok": True,
        "merged": result.get("merged", True),
        "sha": result.get("sha"),
        "message": result.get("message"),
        "baseRef": pr.get("base", {}).get("ref"),
    }
