"""GitHub production integration API — post comments, embed tokens, install status.

Exposes user-facing actions that bridge the web app and github.com (post summary,
generate embed link for Check details). Webhooks live in ``routers/webhooks.py``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import PrReport, User
from app.routers.auth import get_current_user
from app.services.embed_tokens import embed_token, verify_embed_token
from app.services.github import GitHubClient
from app.services.github_app import get_app_info
from app.services.pr_comments import format_pr_comment, post_pr_summary_comment

router = APIRouter(prefix="/api/github", tags=["github-integration"])


@router.get("/status")
async def github_integration_status() -> dict[str, Any]:
    """
    Production health: which GitHub integration features are configured.

    Used by ops and the frontend settings panel before enabling Checks/comments.
    """
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


@router.post("/repos/{owner}/{repo}/pulls/{number}/post-summary")
async def post_summary_to_github(
    owner: str,
    repo: str,
    number: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    force: bool = Query(False, description="Post even if a summary was already posted"),
) -> dict[str, Any]:
    """
    Post CodeLens markdown summary as a PR comment on github.com.

    Requires OAuth token with repo scope. Records ``pr_review_posts`` to prevent duplicates.
    """
    if not settings.enable_github_pr_comments:
        raise HTTPException(status_code=400, detail="PR comments disabled (ENABLE_GITHUB_PR_COMMENTS)")

    result = await db.execute(
        select(PrReport).where(
            PrReport.owner == owner,
            PrReport.repo == repo,
            PrReport.pr_number == number,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Analyze PR first")

    import json

    report = json.loads(row.report_json)
    embed_url = None
    if settings.embed_configured():
        token = embed_token(owner, repo, number, settings.embed_shared_secret)
        embed_url = f"{settings.frontend_url.rstrip('/')}/embed/repos/{owner}/{repo}/pulls/{number}?token={token}"

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
        embed_url=embed_url,
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
    url = f"{settings.frontend_url.rstrip('/')}/embed/repos/{owner}/{repo}/pulls/{number}?token={token}"
    return {"embedUrl": url}


@router.get("/embed/{owner}/{repo}/pulls/{number}/report")
async def get_embed_report(
    owner: str,
    repo: str,
    number: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    token: str = Query(..., description="HMAC embed token"),
) -> dict[str, Any]:
    """
    Read-only report for github.com embed (no OAuth cookie).

    Secured by ``EMBED_SHARED_SECRET``; used by ``EmbedReport`` iframe page.
    """
    if not settings.embed_configured():
        raise HTTPException(status_code=503, detail="Embed not configured")
    if not verify_embed_token(owner, repo, number, settings.embed_shared_secret, token):
        raise HTTPException(status_code=403, detail="Invalid embed token")

    result = await db.execute(
        select(PrReport).where(
            PrReport.owner == owner,
            PrReport.repo == repo,
            PrReport.pr_number == number,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")

    import json

    return json.loads(row.report_json)


@router.get("/repos/{owner}/{repo}/pulls/{number}/comment-preview")
async def preview_pr_comment(
    owner: str,
    repo: str,
    number: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Preview markdown that would be posted to GitHub (no side effects)."""
    result = await db.execute(
        select(PrReport).where(
            PrReport.owner == owner,
            PrReport.repo == repo,
            PrReport.pr_number == number,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    import json

    report = json.loads(row.report_json)
    return {"markdown": format_pr_comment(report)}
