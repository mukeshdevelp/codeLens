from __future__ import annotations

import base64
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

    async def get_commit(self, owner: str, repo: str, sha: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.get(
                f"{self.base}/repos/{owner}/{repo}/commits/{sha}",
                headers=self._headers(),
            )
            res.raise_for_status()
            return res.json()

    async def compare_commits(self, owner: str, repo: str, base: str, head: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.get(
                f"{self.base}/repos/{owner}/{repo}/compare/{base}...{head}",
                headers=self._headers(),
            )
            res.raise_for_status()
            return res.json()

    async def get_file_text(self, owner: str, repo: str, path: str, ref: str) -> str | None:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.get(
                f"{self.base}/repos/{owner}/{repo}/contents/{path}",
                headers=self._headers(),
                params={"ref": ref},
            )
            if res.status_code == 404:
                return None
            res.raise_for_status()
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
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.post(
                f"{self.base}/repos/{owner}/{repo}/check-runs",
                headers=self._headers(),
                json=payload,
            )
            res.raise_for_status()
            return res.json()

    async def update_check_run(
        self, owner: str, repo: str, check_run_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing Check Run (e.g. mark completed after analysis finishes)."""
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.patch(
                f"{self.base}/repos/{owner}/{repo}/check-runs/{check_run_id}",
                headers=self._headers(),
                json=payload,
            )
            res.raise_for_status()
            return res.json()

    async def create_issue_comment(
        self, owner: str, repo: str, issue_number: int, body: str
    ) -> dict[str, Any]:
        """Post a comment on a PR (PRs are issues in GitHub's API). Used for CodeLens summaries."""
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.post(
                f"{self.base}/repos/{owner}/{repo}/issues/{issue_number}/comments",
                headers=self._headers(),
                json={"body": body},
            )
            res.raise_for_status()
            return res.json()

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

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.get(f"{self.base}/repos/{owner}/{repo}", headers=self._headers())
            res.raise_for_status()
            return res.json()

    async def approve_pull_request(
        self,
        owner: str,
        repo: str,
        number: int,
        body: str = "Approved via CodeLens after review.",
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                f"{self.base}/repos/{owner}/{repo}/pulls/{number}/reviews",
                headers=self._headers(),
                json={"event": "APPROVE", "body": body},
            )
            if res.status_code >= 400:
                raise ValueError(_github_error_detail(res))
            return res.json()

    async def merge_pull_request(
        self,
        owner: str,
        repo: str,
        number: int,
        *,
        merge_method: str = "merge",
        commit_title: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"merge_method": merge_method}
        if commit_title:
            payload["commit_title"] = commit_title
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.put(
                f"{self.base}/repos/{owner}/{repo}/pulls/{number}/merge",
                headers=self._headers(),
                json=payload,
            )
            if res.status_code >= 400:
                raise ValueError(_github_error_detail(res))
            return res.json()


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
    return (pr.get("user") or {}).get("login")


def user_has_approved_pr(reviews: list[dict[str, Any]], login: str) -> bool:
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
