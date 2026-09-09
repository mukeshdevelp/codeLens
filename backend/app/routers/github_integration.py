"""GitHub production integration API — post comments, embed tokens, install status."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.db.models import User
from app.routers.auth import get_current_user
from app.services.embed_tokens import build_embed_url, embed_token, signed_embed_url, verify_embed_token
from app.services.github import GitHubClient
from app.services.github_app import get_app_info
from app.services.pr_comments import format_pr_comment, post_pr_summary_comment
from app.services.reports import get_pr_report_row, load_report_dict

router = APIRouter(prefix="/api/github", tags=["github-integration"])


@router.get("/status")
async def github_integration_status() -> dict[str, Any]:
    """Production health: which GitHub integration features are configured."""
    app_ok = False
    app_name = None
    if settings.github_app_configured():
        try:
            info = await get_app_info()
            app_ok = True
            app_name = info.get("name")
        except Exception as exc:
            app_name = str(exc)[:120]

    return {
        "oauthConfigured": bool(settings.github_client_id and settings.github_client_secret),
        "appConfigured": settings.github_app_configured(),
        "appReachable": app_ok,
        "appName": app_name,
        "webhookSecretConfigured": bool(settings.github_webhook_secret),
        "checksEnabled": settings.enable_github_checks,
        "prCommentsEnabled": settings.enable_github_pr_comments,
        "embedConfigured": settings.embed_configured(),
        "installUrl": (
            f"https://github.com/apps/{settings.github_app_slug}/installations/new"
            if settings.github_app_slug
            else None
        ),
    }


async def _require_report_row(
    db: AsyncSession,
    owner: str,
    repo: str,
    number: int,
    *,
    analyze_first_message: str = "Report not found",
) -> tuple[Any, dict[str, Any]]:
    row = await get_pr_report_row(db, owner, repo, number)
    if not row:
        raise HTTPException(status_code=404, detail=analyze_first_message)
    return row, load_report_dict(row)


@router.post("/repos/{owner}/{repo}/pulls/{number}/post-summary")
async def post_summary_to_github(
    owner: str,
    repo: str,
    number: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    force: bool = Query(False, description="Post even if a summary was already posted"),
) -> dict[str, Any]:
    """Post CodeLens markdown summary as a PR comment on github.com."""
    if not settings.enable_github_pr_comments:
        raise HTTPException(status_code=400, detail="PR comments disabled (ENABLE_GITHUB_PR_COMMENTS)")

    row, report = await _require_report_row(db, owner, repo, number, analyze_first_message="Analyze PR first")
    gh = GitHubClient(user.access_token)
    return await post_pr_summary_comment(
        db,
        gh,
        owner,
        repo,
        number,
        report,
        row,
        user_id=user.id,
        embed_url=signed_embed_url(owner, repo, number),
        force=force,
    )


@router.get("/repos/{owner}/{repo}/pulls/{number}/embed-url")
async def get_embed_url(
    owner: str,
    repo: str,
    number: int,
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    """Return signed embed URL for Check Run details_url and GitHub iframe embedding."""
    if not settings.embed_configured():
        raise HTTPException(status_code=400, detail="EMBED_SHARED_SECRET not configured")
    token = embed_token(owner, repo, number, settings.embed_shared_secret)
    return {"embedUrl": build_embed_url(owner, repo, number, token=token)}


@router.get("/embed/{owner}/{repo}/pulls/{number}/report")
async def get_embed_report(
    owner: str,
    repo: str,
    number: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    token: str = Query(..., description="HMAC embed token"),
) -> dict[str, Any]:
    """Read-only report for github.com embed (no OAuth cookie)."""
    if not settings.embed_configured():
        raise HTTPException(status_code=503, detail="Embed not configured")
    if not verify_embed_token(owner, repo, number, settings.embed_shared_secret, token):
        raise HTTPException(status_code=403, detail="Invalid embed token")

    _, report = await _require_report_row(db, owner, repo, number)
    return report


@router.get("/repos/{owner}/{repo}/pulls/{number}/comment-preview")
async def preview_pr_comment(
    owner: str,
    repo: str,
    number: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Preview markdown that would be posted to GitHub (no side effects)."""
    _, report = await _require_report_row(db, owner, repo, number)
    return {"markdown": format_pr_comment(report)}
