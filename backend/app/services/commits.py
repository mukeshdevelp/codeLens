"""Fetch PR commits with per-file patches and enrich missing diffs."""

from __future__ import annotations

import asyncio
from typing import Any

from app.services.github import GitHubClient
from app.services.patch_enrichment import backfill_file_patch, fetch_compare_patches


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

    compare_patches = (
        await fetch_compare_patches(gh, owner, repo, parent_sha, sha)
        if parent_sha and sha
        else {}
    )

    for entry in formatted["files"]:
        if entry["patch"]:
            continue
        if entry["filename"] in compare_patches:
            entry["patch"] = compare_patches[entry["filename"]]
            continue

        patch = await backfill_file_patch(
            gh,
            owner,
            repo,
            filename=entry["filename"],
            status=entry["status"],
            base_sha=parent_sha,
            head_sha=sha,
            previous_filename=entry.get("previousFilename") or entry["filename"],
        )
        if patch:
            entry["patch"] = patch
        else:
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

    compare_patches = await fetch_compare_patches(gh, owner, repo, base_sha, head_sha)

    for f in files:
        if f.patch:
            continue
        if f.filename in compare_patches:
            f.patch = compare_patches[f.filename]
            continue

        patch = await backfill_file_patch(
            gh,
            owner,
            repo,
            filename=f.filename,
            status=f.status,
            base_sha=base_sha,
            head_sha=head_sha,
        )
        if patch:
            f.patch = patch
