from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzers.service import analyze_pull_request
from app.database import get_db
from app.models import PrReport, User
from app.routers.auth import get_current_user
from app.config import settings
from app.services.discussion import fetch_pr_discussion
from app.services.github import GitHubClient

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
):
    gh = GitHubClient(user.access_token)
    pr = await gh.get_pull(owner, repo, number)
    files = await gh.list_pr_files(owner, repo, number)
    raw_commits = await gh.list_pr_commits(owner, repo, number)
    activity = await fetch_pr_discussion(gh, owner, repo, number)
    commits = [
        {
            "sha": c["sha"],
            "message": (c.get("commit", {}).get("message") or "").strip(),
            "author": (c.get("author") or {}).get("login")
            or (c.get("commit", {}).get("author") or {}).get("name")
            or "unknown",
            "date": (c.get("commit", {}).get("author") or {}).get("date", ""),
            "htmlUrl": c.get("html_url", ""),
            "additions": sum(f.get("additions", 0) for f in c.get("files", [])),
            "deletions": sum(f.get("deletions", 0) for f in c.get("files", [])),
        }
        for c in raw_commits
    ]
    pr_meta = {
        "author": pr["user"]["login"],
        "state": pr["state"],
        "additions": pr.get("additions", 0),
        "deletions": pr.get("deletions", 0),
        "changedFiles": pr.get("changed_files", len(files)),
        "commitCount": len(commits),
        "htmlUrl": pr.get("html_url"),
    }
    report = await analyze_pull_request(
        pr["title"],
        pr.get("body"),
        files,
        pr_meta=pr_meta,
        review_activity=activity,
        commits=commits,
    )

    result = await db.execute(
        select(PrReport).where(PrReport.owner == owner, PrReport.repo == repo, PrReport.pr_number == number)
    )
    existing = result.scalar_one_or_none()
    report_json = json.dumps(report.to_dict())
    if existing:
        existing.title = pr["title"]
        existing.report_json = report_json
        existing.user_id = user.id
    else:
        db.add(
            PrReport(
                user_id=user.id,
                owner=owner,
                repo=repo,
                pr_number=number,
                title=pr["title"],
                report_json=report_json,
            )
        )
    await db.commit()
    return report.to_dict()


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
