from __future__ import annotations

import secrets

import httpx
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User
from app.services.github import GitHubClient, exchange_code_for_token, github_oauth_url

router = APIRouter(prefix="/auth", tags=["auth"])

ALGORITHM = "HS256"


def create_session_token(user_id: int) -> str:
    return jwt.encode({"sub": str(user_id)}, settings.session_secret, algorithm=ALGORITHM)


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="codelens_session",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
        max_age=60 * 60 * 24 * 7,
    )


def auth_error_redirect(reason: str = "auth_failed") -> RedirectResponse:
    return RedirectResponse(f"{settings.frontend_url}/?error={reason}")


async def get_current_user(request: Request, db: Annotated[AsyncSession, Depends(get_db)]) -> User:
    token = request.cookies.get("codelens_session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.session_secret, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub", 0))
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid session")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.get("/github")
async def login_github():
    state = secrets.token_urlsafe(16)
    redirect = RedirectResponse(github_oauth_url(state))
    redirect.set_cookie(
        "oauth_state",
        state,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
        max_age=600,
    )
    return redirect


@router.get("/github/callback")
async def github_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    db: Annotated[AsyncSession, Depends(get_db)] = ...,
):
    saved_state = request.cookies.get("oauth_state")
    if not code or not state or not saved_state or state != saved_state:
        return auth_error_redirect("invalid_oauth_state")

    try:
        access_token = await exchange_code_for_token(code)
    except (ValueError, httpx.HTTPError):
        return auth_error_redirect("token_exchange_failed")
    gh = GitHubClient(access_token)
    profile = await gh.get_user()

    result = await db.execute(select(User).where(User.github_id == profile["id"]))
    user = result.scalar_one_or_none()
    if user:
        user.login = profile["login"]
        user.name = profile.get("name")
        user.avatar_url = profile.get("avatar_url")
        user.access_token = access_token
    else:
        user = User(
            github_id=profile["id"],
            login=profile["login"],
            name=profile.get("name"),
            avatar_url=profile.get("avatar_url"),
            access_token=access_token,
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    redirect = RedirectResponse(f"{settings.frontend_url}/dashboard")
    set_session_cookie(redirect, create_session_token(user.id))
    redirect.delete_cookie("oauth_state")
    return redirect


@router.get("/me")
async def me(user: Annotated[User, Depends(get_current_user)]):
    return {
        "id": user.id,
        "login": user.login,
        "name": user.name,
        "avatarUrl": user.avatar_url,
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("codelens_session")
    return {"ok": True}
