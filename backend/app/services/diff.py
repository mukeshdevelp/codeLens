"""Unified diff helpers when GitHub omits per-file patches."""

from __future__ import annotations

import difflib

MAX_PATCH_LINES = 4000


def make_unified_diff(old: str, new: str, filename: str) -> str:
    """Build a capped unified diff string between two file versions."""
    diff_lines = list(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            lineterm="",
        )
    )
    if not diff_lines:
        return ""
    return _cap_lines("\n".join(diff_lines))


def content_to_add_patch(filename: str, content: str) -> str:
    lines = content.splitlines()
    capped = lines[:MAX_PATCH_LINES]
    body = "\n".join(f"+{line}" for line in capped)
    more = f"\n+... ({len(lines) - len(capped)} more lines)" if len(lines) > len(capped) else ""
    return f"--- /dev/null\n+++ b/{filename}\n@@ -0,0 +1,{len(capped)} @@\n{body}{more}"


def content_to_remove_patch(filename: str, content: str) -> str:
    lines = content.splitlines()
    capped = lines[:MAX_PATCH_LINES]
    body = "\n".join(f"-{line}" for line in capped)
    more = f"\n-... ({len(lines) - len(capped)} more lines)" if len(lines) > len(capped) else ""
    return f"--- a/{filename}\n+++ /dev/null\n@@ -1,{len(capped)} +0,0 @@\n{body}{more}"


def _cap_lines(patch: str) -> str:
    lines = patch.splitlines()
    if len(lines) <= MAX_PATCH_LINES:
        return patch
    return "\n".join(lines[:MAX_PATCH_LINES]) + f"\n... ({len(lines) - MAX_PATCH_LINES} more lines)"
