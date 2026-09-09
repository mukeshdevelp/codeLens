"""GitHub webhook endpoint — auto-analyze PRs on open/sync (production entry point)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.db.models import WebhookDelivery
from app.services.analyze_pipeline import run_pr_analysis
from app.services.github import GitHubClient
from app.services.github_app import get_installation_access_token
from app.services.installations import get_installation_by_github_id, sync_repositories, upsert_installation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

PR_ANALYZE_ACTIONS = {"opened", "synchronize", "reopened", "ready_for_review"}


def verify_github_signature(payload: bytes, signature_header: str | None, secret: str) -> bool:
    """Validate ``X-Hub-Signature-256`` per GitHub docs."""
    if not secret:
        return False
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature_header[7:], expected)


async def _record_delivery(
    db: AsyncSession,
    delivery_id: str,
    event_type: str,
    action: str | None,
    repository: str | None,
    status: str,
    error: str | None = None,
) -> WebhookDelivery:
    """Persist webhook delivery for idempotency and ops debugging."""
    result = await db.execute(
        select(WebhookDelivery).where(WebhookDelivery.delivery_id == delivery_id)
    )
    row = result.scalar_one_or_none()
    if row:
        return row
    row = WebhookDelivery(
        delivery_id=delivery_id,
        event_type=event_type,
        action=action,
        repository=repository,
        status=status,
        error_message=error,
        processed_at=datetime.utcnow() if status != "pending" else None,
    )
    db.add(row)
    await db.commit()
    return row


async def _mark_processed(
    db: AsyncSession, delivery_id: str | None, error: str | None = None
) -> None:
    """Mark delivery processed or failed."""
    if not delivery_id:
        return
    result = await db.execute(
        select(WebhookDelivery).where(WebhookDelivery.delivery_id == delivery_id)
    )
    row = result.scalar_one_or_none()
    if row:
        row.status = "failed" if error else "processed"
        row.error_message = error
        row.processed_at = datetime.utcnow()
        await db.commit()


async def _handle_installation(db: AsyncSession, payload: dict[str, Any], delivery_id: str) -> dict[str, Any]:
    installation = await upsert_installation(db, payload)
    repos = payload.get("repositories") or []
    if repos:
        await sync_repositories(db, installation, repositories_added=repos)
    await _mark_processed(db, delivery_id)
    return {"ok": True, "event": "installation"}


async def _handle_installation_repositories(
    db: AsyncSession, payload: dict[str, Any], delivery_id: str
) -> dict[str, Any]:
    inst_payload = payload.get("installation") or {}
    installation = await get_installation_by_github_id(db, inst_payload["id"])
    if not installation:
        installation = await upsert_installation(db, payload)
    await sync_repositories(
        db,
        installation,
        repositories_added=payload.get("repositories_added"),
        repositories_removed=payload.get("repositories_removed"),
    )
    await _mark_processed(db, delivery_id)
    return {"ok": True, "event": "installation_repositories"}


async def _handle_pull_request(
    db: AsyncSession, payload: dict[str, Any], delivery_id: str
) -> dict[str, Any]:
    if not settings.github_app_configured():
        await _mark_processed(db, delivery_id, error="github_app_not_configured")
        return {"ok": False, "reason": "github_app_not_configured"}

    pr = payload.get("pull_request") or {}
    number = pr.get("number")
    installation_payload = payload.get("installation") or {}
    inst_id = installation_payload.get("id")
    if not number or not inst_id:
        await _mark_processed(db, delivery_id, error="missing_pr_or_installation")
        return {"ok": False}

    repo = payload.get("repository") or {}
    repo_full = repo.get("full_name", "")

    installation = await get_installation_by_github_id(db, inst_id)
    if not installation:
        installation = await upsert_installation(db, payload)

    await sync_repositories(db, installation, repositories_added=[repo])

    owner_login = repo.get("owner", {}).get("login") or repo_full.split("/")[0]
    repo_name = repo.get("name") or repo_full.split("/")[-1]

    token = await get_installation_access_token(inst_id)
    gh = GitHubClient(token)
    await run_pr_analysis(
        db,
        gh,
        owner_login,
        repo_name,
        number,
        installation=installation,
        source="webhook",
    )
    await _mark_processed(db, delivery_id)
    return {"ok": True, "analyzed": number}


@router.post("/github")
async def github_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Receive GitHub App / webhook events."""
    body = await request.body()
    event = request.headers.get("X-GitHub-Event", "")
    delivery_id = request.headers.get("X-GitHub-Delivery", "")
    signature = request.headers.get("X-Hub-Signature-256")

    if not verify_github_signature(body, signature, settings.github_webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = json.loads(body.decode())
    action = payload.get("action")
    repo = payload.get("repository") or {}
    repo_full = repo.get("full_name")

    if delivery_id:
        existing = await db.execute(
            select(WebhookDelivery).where(
                WebhookDelivery.delivery_id == delivery_id,
                WebhookDelivery.status == "processed",
            )
        )
        if existing.scalar_one_or_none():
            return {"ok": True, "skipped": "duplicate_delivery"}

    await _record_delivery(db, delivery_id or "unknown", event, action, repo_full, "pending")

    try:
        if event == "installation":
            return await _handle_installation(db, payload, delivery_id)

        if event == "installation_repositories":
            return await _handle_installation_repositories(db, payload, delivery_id)

        if event == "pull_request" and action in PR_ANALYZE_ACTIONS:
            return await _handle_pull_request(db, payload, delivery_id)

        await _mark_processed(db, delivery_id)
        return {"ok": True, "ignored": event}

    except Exception as exc:
        logger.exception("Webhook processing failed: %s", exc)
        await _mark_processed(db, delivery_id, error=str(exc)[:500])
        raise HTTPException(status_code=500, detail="Webhook processing failed") from exc
