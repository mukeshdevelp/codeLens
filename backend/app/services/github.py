from __future__ import annotations

from typing import Any

import httpx

from app.analyzers.types import FileChange
from app.config import settings


class GitHubClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base = "https://api.github.com"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_user(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.get(f"{self.base}/user", headers=self._headers())
            res.raise_for_status()
            return res.json()

    async def list_repos(self, page: int = 1, per_page: int = 30) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.get(
                f"{self.base}/user/repos",
                headers=self._headers(),
                params={"sort": "updated", "per_page": per_page, "page": page, "affiliation": "owner,collaborator,organization_member"},
            )
            res.raise_for_status()
            return res.json()

    async def list_pulls(self, owner: str, repo: str, state: str = "open") -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.get(
                f"{self.base}/repos/{owner}/{repo}/pulls",
                headers=self._headers(),
                params={"state": state, "per_page": 30, "sort": "updated"},
            )
            res.raise_for_status()
            return res.json()

    async def get_pull(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.get(f"{self.base}/repos/{owner}/{repo}/pulls/{number}", headers=self._headers())
            res.raise_for_status()
            return res.json()

    async def _paginate(self, url: str, params: dict | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page_url: str | None = url
        first = True
        async with httpx.AsyncClient(timeout=60) as client:
            while page_url:
                res = await client.get(
                    page_url,
                    headers=self._headers(),
                    params=params if first else None,
                )
                res.raise_for_status()
                items.extend(res.json())
                first = False
                page_url = None
                link = res.headers.get("Link", "")
                for part in link.split(","):
                    if 'rel="next"' in part:
                        page_url = part.split(";")[0].strip().strip("<>")
                        break
        return items

    async def list_pr_files(self, owner: str, repo: str, number: int) -> list[FileChange]:
        data = await self._paginate(
            f"{self.base}/repos/{owner}/{repo}/pulls/{number}/files",
            params={"per_page": 100},
        )
        return [
            FileChange(
                filename=item["filename"],
                status=item["status"],
                additions=item.get("additions", 0),
                deletions=item.get("deletions", 0),
                patch=item.get("patch"),
            )
            for item in data
        ]

    async def list_pr_commits(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        return await self._paginate(
            f"{self.base}/repos/{owner}/{repo}/pulls/{number}/commits",
            params={"per_page": 100},
        )

    async def list_pr_reviews(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.get(
                f"{self.base}/repos/{owner}/{repo}/pulls/{number}/reviews",
                headers=self._headers(),
            )
            res.raise_for_status()
            return res.json()

    async def list_pr_review_comments(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.get(
                f"{self.base}/repos/{owner}/{repo}/pulls/{number}/comments",
                headers=self._headers(),
                params={"per_page": 100},
            )
            res.raise_for_status()
            return res.json()

    async def list_issue_comments(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.get(
                f"{self.base}/repos/{owner}/{repo}/issues/{number}/comments",
                headers=self._headers(),
                params={"per_page": 100},
            )
            res.raise_for_status()
            return res.json()


def github_oauth_url(state: str) -> str:
    scopes = "read:user repo"
    return (
        "https://github.com/login/oauth/authorize"
        f"?client_id={settings.github_client_id}"
        f"&redirect_uri={settings.github_redirect_uri}"
        f"&scope={scopes.replace(' ', '%20')}"
        f"&state={state}"
    )


async def exchange_code_for_token(code: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            json={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": settings.github_redirect_uri,
            },
        )
        res.raise_for_status()
        data = res.json()
        if "error" in data:
            raise ValueError(data.get("error_description", data["error"]))
        return data["access_token"]
