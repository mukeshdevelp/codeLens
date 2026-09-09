"""GitHub REST API client, OAuth URL helpers, and PR review/merge actions."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from app.analyzers.types import FileChange
from app.config import settings
from app.services.github_http import GITHUB_API_BASE, github_api_headers


class GitHubClient:
    """Async GitHub REST v3 client with pagination and PR workflow helpers."""

    def __init__(self, access_token: str):
        """Authenticate requests with a user OAuth token or App installation token."""
        self.access_token = access_token
        self.base = GITHUB_API_BASE

    def _headers(self) -> dict[str, str]:
        return github_api_headers(self.access_token)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        timeout: int = 30,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        allow_404: bool = False,
    ) -> httpx.Response:
        url = path if path.startswith("http") else f"{self.base}{path}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.request(
                method,
                url,
                headers=self._headers(),
                params=params,
                json=json,
            )
        if allow_404 and res.status_code == 404:
            return res
        res.raise_for_status()
        return res

    async def _get_json(
        self,
        path: str,
        *,
        timeout: int = 30,
        params: dict[str, Any] | None = None,
        allow_404: bool = False,
    ) -> dict[str, Any] | list[Any] | None:
        res = await self._request("GET", path, timeout=timeout, params=params, allow_404=allow_404)
        if allow_404 and res.status_code == 404:
            return None
        return res.json()

    async def get_user(self) -> dict[str, Any]:
        return await self._get_json("/user")  # type: ignore[return-value]

    async def list_repos(self, page: int = 1, per_page: int = 30) -> list[dict[str, Any]]:
        return await self._get_json(  # type: ignore[return-value]
            "/user/repos",
            params={
                "sort": "updated",
                "per_page": per_page,
                "page": page,
                "affiliation": "owner,collaborator,organization_member",
            },
        )

    async def list_pulls(self, owner: str, repo: str, state: str = "open") -> list[dict[str, Any]]:
        return await self._get_json(  # type: ignore[return-value]
            f"/repos/{owner}/{repo}/pulls",
            params={"state": state, "per_page": 30, "sort": "updated"},
        )

    async def get_pull(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        return await self._get_json(f"/repos/{owner}/{repo}/pulls/{number}")  # type: ignore[return-value]

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

    async def get_commit(self, owner: str, repo: str, sha: str) -> dict[str, Any]:
        return await self._get_json(f"/repos/{owner}/{repo}/commits/{sha}", timeout=60)  # type: ignore[return-value]

    async def compare_commits(self, owner: str, repo: str, base: str, head: str) -> dict[str, Any]:
        return await self._get_json(  # type: ignore[return-value]
            f"/repos/{owner}/{repo}/compare/{base}...{head}",
            timeout=60,
        )

    async def get_file_text(self, owner: str, repo: str, path: str, ref: str) -> str | None:
        res = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/contents/{path}",
            timeout=60,
            params={"ref": ref},
            allow_404=True,
        )
        if res.status_code == 404:
            return None
        data = res.json()
        if isinstance(data, list):
            return None
        content = data.get("content")
        if not content:
            return None
        raw = base64.b64decode(content)
        return raw.decode("utf-8", errors="replace")

    async def create_check_run(self, owner: str, repo: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a GitHub Check Run on a commit (requires GitHub App ``checks:write`` permission)."""
        res = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/check-runs",
            timeout=60,
            json=payload,
        )
        return res.json()

    async def update_check_run(
        self, owner: str, repo: str, check_run_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing Check Run (e.g. mark completed after analysis finishes)."""
        res = await self._request(
            "PATCH",
            f"/repos/{owner}/{repo}/check-runs/{check_run_id}",
            timeout=60,
            json=payload,
        )
        return res.json()

    async def create_issue_comment(
        self, owner: str, repo: str, issue_number: int, body: str
    ) -> dict[str, Any]:
        """Post a comment on a PR (PRs are issues in GitHub's API). Used for CodeLens summaries."""
        res = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            timeout=60,
            json={"body": body},
        )
        return res.json()

    async def list_pr_reviews(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        return await self._get_json(f"/repos/{owner}/{repo}/pulls/{number}/reviews")  # type: ignore[return-value]

    async def list_pr_review_comments(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        return await self._get_json(  # type: ignore[return-value]
            f"/repos/{owner}/{repo}/pulls/{number}/comments",
            params={"per_page": 100},
        )

    async def list_issue_comments(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        return await self._get_json(  # type: ignore[return-value]
            f"/repos/{owner}/{repo}/issues/{number}/comments",
            params={"per_page": 100},
        )

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        return await self._get_json(f"/repos/{owner}/{repo}")  # type: ignore[return-value]

    async def _mutate_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """POST/PUT helper that surfaces GitHub API errors as ``ValueError``."""
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.request(
                method,
                f"{self.base}{path}",
                headers=self._headers(),
                json=payload,
            )
        if res.status_code >= 400:
            raise ValueError(_github_error_detail(res))
        return res.json()

    async def approve_pull_request(
        self,
        owner: str,
        repo: str,
        number: int,
        body: str = "Approved via CodeLens after review.",
    ) -> dict[str, Any]:
        """Submit an APPROVE pull request review on GitHub."""
        return await self._mutate_json(
            "POST",
            f"/repos/{owner}/{repo}/pulls/{number}/reviews",
            {"event": "APPROVE", "body": body},
        )

    async def merge_pull_request(
        self,
        owner: str,
        repo: str,
        number: int,
        *,
        merge_method: str = "merge",
        commit_title: str | None = None,
    ) -> dict[str, Any]:
        """Merge a pull request via GitHub (merge, squash, or rebase)."""
        payload: dict[str, Any] = {"merge_method": merge_method}
        if commit_title:
            payload["commit_title"] = commit_title
        return await self._mutate_json(
            "PUT",
            f"/repos/{owner}/{repo}/pulls/{number}/merge",
            payload,
        )


def _github_error_detail(res: httpx.Response) -> str:
    try:
        data = res.json()
        msg = data.get("message") or res.reason_phrase or "GitHub API error"
        errors = data.get("errors")
        if errors:
            parts: list[str] = []
            for item in errors:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(item.get("message") or str(item))
                else:
                    parts.append(str(item))
            msg = f"{msg}: {'; '.join(parts)}"
        return msg
    except Exception:
        return res.text or res.reason_phrase or "GitHub API error"


def pr_author_login(pr: dict[str, Any]) -> str | None:
    """Return the GitHub login of the pull request author."""
    return (pr.get("user") or {}).get("login")


def user_has_approved_pr(reviews: list[dict[str, Any]], login: str) -> bool:
    """True if the given user already left an APPROVED review on this PR."""
    return any(
        r.get("user", {}).get("login") == login and r.get("state") == "APPROVED"
        for r in reviews
    )


def can_user_approve_pr(pr: dict[str, Any], login: str, reviews: list[dict[str, Any]]) -> tuple[bool, str | None]:
    """Whether the signed-in user may submit an APPROVE review (GitHub rules)."""
    if pr.get("state") != "open":
        return False, "Only open pull requests can be approved."
    author = pr_author_login(pr)
    if author and author == login:
        return False, "GitHub does not allow approving your own pull request. You can still merge if branch protection allows."
    if user_has_approved_pr(reviews, login):
        return False, "You have already approved this pull request."
    return True, None


def github_oauth_url(state: str) -> str:
    """Build the GitHub OAuth authorize URL with CSRF ``state`` and repo scope."""
    from urllib.parse import urlencode

    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": settings.github_redirect_uri,
        "scope": "read:user repo",
        "state": state,
    }
    return f"https://github.com/login/oauth/authorize?{urlencode(params)}"


async def exchange_code_for_token(code: str) -> str:
    """Exchange OAuth authorization code for a GitHub access token."""
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
