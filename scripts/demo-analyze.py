#!/usr/bin/env python3
"""Run demo PR analysis using fixtures/demo-pr.json"""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.analyzers.service import analyze_pull_request
from app.analyzers.types import FileChange


async def main() -> None:
    fixture = json.loads((ROOT / "fixtures" / "demo-pr.json").read_text())
    files = [FileChange(**f) for f in fixture["files"]]
    report = await analyze_pull_request(fixture["title"], fixture.get("body"), files)
    print("\n" + "=" * 60)
    print("CODELENS DEMO — PR ANALYSIS")
    print("=" * 60)
    print(f"\nRisk: {report.risk_level.upper()} ({report.risk_score}/100)\n")
    print(report.executive_summary)
    print("\nFocus areas:")
    for area in report.focus_areas:
        print(f"  {area.rank}. [{area.severity}] {area.area} — {area.reason}")
    out = ROOT / ".reports" / "demo-output.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report.to_dict(), indent=2))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    asyncio.run(main())
