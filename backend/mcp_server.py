#!/usr/bin/env python3
"""CodeLens MCP server — exposes PR analysis tools to Cursor AI."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Allow imports from backend app
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server.fastmcp import FastMCP

from app.analyzers.engine import (
    analyze_functionality,
    analyze_volume,
    check_test_coverage,
    detect_critical_paths,
    detect_scope_drift,
    scan_security,
)
from app.analyzers.service import analyze_pull_request
from app.analyzers.types import FileChange

mcp = FastMCP("codelens")


def _parse_files(files: list[dict]) -> list[FileChange]:
    return [
        FileChange(
            filename=f["filename"],
            status=f.get("status", "modified"),
            additions=int(f.get("additions", 0)),
            deletions=int(f.get("deletions", 0)),
            patch=f.get("patch"),
        )
        for f in files
    ]


@mcp.tool()
async def analyze_pull_request_tool(title: str, body: str = "", files: list[dict] | None = None) -> str:
    """Full PR analysis: volume, drift, critical paths, security, tests, risk score, and AI summary."""
    report = await analyze_pull_request(title, body or None, _parse_files(files or []))
    return json.dumps(report.to_dict(), indent=2)


@mcp.tool()
def analyze_diff_volume(files: list[dict]) -> str:
    """Measure PR size: files changed, lines added/removed."""
    result = analyze_volume(_parse_files(files))
    return json.dumps(result.__dict__, default=lambda o: o.__dict__, indent=2)


@mcp.tool()
def detect_critical_paths_tool(files: list[dict]) -> str:
    """Flag changes touching auth, payments, permissions, data, infra, or API surfaces."""
    result = detect_critical_paths(_parse_files(files))
    return json.dumps(result.__dict__, default=lambda o: o.__dict__, indent=2)


@mcp.tool()
def scan_security_patterns(files: list[dict]) -> str:
    """Scan added diff lines for secrets and unsafe code patterns."""
    result = scan_security(_parse_files(files))
    return json.dumps(result.__dict__, default=lambda o: o.__dict__, indent=2)


@mcp.tool()
def check_test_coverage_gaps(files: list[dict]) -> str:
    """Find source files changed without corresponding test file updates."""
    result = check_test_coverage(_parse_files(files))
    return json.dumps(result.__dict__, default=lambda o: o.__dict__, indent=2)


@mcp.tool()
def detect_scope_drift_tool(title: str, body: str = "", files: list[dict] | None = None) -> str:
    """Check if PR changes are broader than the stated title/description."""
    result = detect_scope_drift(title, body or None, _parse_files(files or []))
    return json.dumps(result.__dict__, default=lambda o: o.__dict__, indent=2)


if __name__ == "__main__":
    mcp.run()
