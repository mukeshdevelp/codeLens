from __future__ import annotations

from typing import Any

from app.services.github import GitHubClient


def collect_review_activity(
    reviews: list[dict[str, Any]],
    review_comments: list[dict[str, Any]],
    issue_comments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    activity: list[dict[str, Any]] = []

    for r in reviews:
        if r.get("body"):
            activity.append(
                {
                    "type": "review",
                    "author": r["user"]["login"],
                    "body": r["body"],
                    "state": r.get("state"),
                    "createdAt": r.get("submitted_at") or r.get("created_at", ""),
                }
            )

    for c in review_comments:
        activity.append(
            {
                "type": "review_comment",
                "author": c["user"]["login"],
                "body": c.get("body", ""),
                "file": c.get("path"),
                "line": c.get("line") or c.get("original_line"),
                "createdAt": c.get("created_at", ""),
            }
        )

    for c in issue_comments:
        activity.append(
            {
                "type": "comment",
                "author": c["user"]["login"],
                "body": c.get("body", ""),
                "createdAt": c.get("created_at", ""),
            }
        )

    activity.sort(key=lambda a: a.get("createdAt", ""))
    return activity


async def fetch_pr_discussion(gh: GitHubClient, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
    reviews = await gh.list_pr_reviews(owner, repo, number)
    review_comments = await gh.list_pr_review_comments(owner, repo, number)
    issue_comments = await gh.list_issue_comments(owner, repo, number)
    return collect_review_activity(reviews, review_comments, issue_comments)
