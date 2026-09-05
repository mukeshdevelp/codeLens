from __future__ import annotations

import asyncio
from typing import Any

from app.services.diff import content_to_add_patch, content_to_remove_patch, make_unified_diff
from app.services.github import GitHubClient


def _format_commit(c: dict[str, Any]) -> dict[str, Any]:
    commit_obj = c.get("commit", {})
    author_info = commit_obj.get("author") or {}
    stats = c.get("stats") or {}
    files = [
        {
            "filename": f.get("filename", ""),
            "status": f.get("status", "modified"),
            "additions": f.get("additions", 0),
            "deletions": f.get("deletions", 0),
            "patch": f.get("patch") or "",
            "previousFilename": f.get("previous_filename") or "",
            "patchUnavailable": False,
        }
        for f in (c.get("files") or [])
    ]
    additions = stats.get("additions") or sum(f["additions"] for f in files)
    deletions = stats.get("deletions") or sum(f["deletions"] for f in files)
    return {
        "sha": c.get("sha", ""),
        "message": (commit_obj.get("message") or "").strip(),
        "author": (c.get("author") or {}).get("login")
        or author_info.get("name")
        or "unknown",
        "date": author_info.get("date", ""),
        "htmlUrl": c.get("html_url", ""),
        "additions": additions,
        "deletions": deletions,
        "files": files,
    }


async def _fill_missing_patches(
    gh: GitHubClient,
    owner: str,
    repo: str,
    commit_detail: dict[str, Any],
    formatted: dict[str, Any],
) -> None:
    parents = commit_detail.get("parents") or []
    parent_sha = parents[0].get("sha") if parents else None
    sha = commit_detail.get("sha", "")

    compare_patches: dict[str, str] = {}
    if parent_sha and sha:
        try:
            compare = await gh.compare_commits(owner, repo, parent_sha, sha)
            compare_patches = {
                f["filename"]: f.get("patch") or ""
                for f in compare.get("files", [])
                if f.get("patch")
            }
        except Exception:
            pass

    for entry in formatted["files"]:
        if entry["patch"]:
            continue
        if entry["filename"] in compare_patches:
            entry["patch"] = compare_patches[entry["filename"]]
            continue

        filename = entry["filename"]
        status = entry["status"]
        prev_name = entry.get("previousFilename") or filename

        try:
            if status == "added" and sha:
                content = await gh.get_file_text(owner, repo, filename, sha)
                if content is not None:
                    entry["patch"] = content_to_add_patch(filename, content)
                    continue
            if status == "removed" and parent_sha:
                content = await gh.get_file_text(owner, repo, prev_name, parent_sha)
                if content is not None:
                    entry["patch"] = content_to_remove_patch(prev_name, content)
                    continue
            if status in ("modified", "renamed", "changed") and parent_sha and sha:
                old = await gh.get_file_text(owner, repo, prev_name, parent_sha)
                new = await gh.get_file_text(owner, repo, filename, sha)
                if old is not None and new is not None:
                    entry["patch"] = make_unified_diff(old, new, filename)
                    continue
        except Exception:
            pass

        entry["patchUnavailable"] = True


async def fetch_pr_commits_detailed(gh: GitHubClient, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
    """Fetch each PR commit with per-file patches (before → after diff)."""
    raw_commits = await gh.list_pr_commits(owner, repo, number)

    async def enrich(summary: dict[str, Any]) -> dict[str, Any]:
        sha = summary.get("sha")
        if not sha:
            return _format_commit(summary)
        detail = await gh.get_commit(owner, repo, sha)
        formatted = _format_commit(detail)
        await _fill_missing_patches(gh, owner, repo, detail, formatted)
        return formatted

    return list(await asyncio.gather(*[enrich(c) for c in raw_commits]))


async def enrich_pr_file_patches(
    gh: GitHubClient,
    owner: str,
    repo: str,
    files: list,
    base_sha: str | None,
    head_sha: str | None,
) -> None:
    """Fill missing PR file patches when GitHub omits them (large/new files)."""
    if not base_sha or not head_sha:
        return

    compare_patches: dict[str, str] = {}
    try:
        compare = await gh.compare_commits(owner, repo, base_sha, head_sha)
        compare_patches = {
            f["filename"]: f.get("patch") or ""
            for f in compare.get("files", [])
            if f.get("patch")
        }
    except Exception:
        pass

    for f in files:
        if f.patch:
            continue
        if f.filename in compare_patches:
            f.patch = compare_patches[f.filename]
            continue
        try:
            if f.status == "added":
                content = await gh.get_file_text(owner, repo, f.filename, head_sha)
                if content is not None:
                    f.patch = content_to_add_patch(f.filename, content)
            elif f.status == "removed":
                content = await gh.get_file_text(owner, repo, f.filename, base_sha)
                if content is not None:
                    f.patch = content_to_remove_patch(f.filename, content)
            elif f.status in ("modified", "renamed", "changed"):
                old = await gh.get_file_text(owner, repo, f.filename, base_sha)
                new = await gh.get_file_text(owner, repo, f.filename, head_sha)
                if old is not None and new is not None:
                    f.patch = make_unified_diff(old, new, f.filename)
        except Exception:
            pass
