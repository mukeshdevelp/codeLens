"""Shared helpers for backfilling missing diff patches from GitHub compare/contents APIs."""

from __future__ import annotations

from app.services.diff import content_to_add_patch, content_to_remove_patch, make_unified_diff
from app.services.github import GitHubClient


async def fetch_compare_patches(
    gh: GitHubClient,
    owner: str,
    repo: str,
    base_sha: str,
    head_sha: str,
) -> dict[str, str]:
    """Return filename → patch map from a compare API response."""
    try:
        compare = await gh.compare_commits(owner, repo, base_sha, head_sha)
        return {
            f["filename"]: f.get("patch") or ""
            for f in compare.get("files", [])
            if f.get("patch")
        }
    except Exception:
        return {}


async def backfill_file_patch(
    gh: GitHubClient,
    owner: str,
    repo: str,
    *,
    filename: str,
    status: str,
    base_sha: str | None,
    head_sha: str | None,
    previous_filename: str | None = None,
) -> str | None:
    """Build a unified patch for one file when GitHub omits it from the PR/files API."""
    prev_name = previous_filename or filename

    try:
        if status == "added" and head_sha:
            content = await gh.get_file_text(owner, repo, filename, head_sha)
            if content is not None:
                return content_to_add_patch(filename, content)
        if status == "removed" and base_sha:
            content = await gh.get_file_text(owner, repo, prev_name, base_sha)
            if content is not None:
                return content_to_remove_patch(prev_name, content)
        if status in ("modified", "renamed", "changed") and base_sha and head_sha:
            old = await gh.get_file_text(owner, repo, prev_name, base_sha)
            new = await gh.get_file_text(owner, repo, filename, head_sha)
            if old is not None and new is not None:
                return make_unified_diff(old, new, filename)
    except Exception:
        pass

    return None
