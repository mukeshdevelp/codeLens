from __future__ import annotations

import re
from collections import defaultdict

from app.analyzers.types import DimensionResult, FileChange, Finding

CRITICAL_PATTERNS = [
    ("auth", "Authentication", "high", [r"auth", r"login", r"session", r"jwt", r"oauth", r"password", r"token"]),
    ("payments", "Payments & Billing", "high", [r"payment", r"billing", r"stripe", r"checkout", r"invoice", r"subscription"]),
    ("permissions", "Permissions & Access Control", "high", [r"permission", r"rbac", r"acl", r"authorize", r"role", r"policy"]),
    ("data", "Data Handling", "medium", [r"database", r"migration", r"schema", r"sql", r"encrypt", r"pii"]),
    ("infra", "Infrastructure & Config", "medium", [r"docker", r"kubernetes", r"terraform", r"deploy", r"\.env", r"config"]),
    ("api", "Public API Surface", "medium", [r"routes?/", r"controller", r"middleware", r"endpoint", r"graphql"]),
]

SECRET_PATTERNS = [
    ("aws-key", re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key"),
    ("github-token", re.compile(r"ghp_[a-zA-Z0-9]{36}"), "GitHub token"),
    ("private-key", re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"), "Private key"),
    ("api-key-assign", re.compile(r"(?:api[_-]?key|secret|password|token)\s*[=:]\s*['\"][^'\"]{8,}['\"]", re.I), "Hardcoded credential"),
    ("hardcoded-fallback", re.compile(r"\|\|\s*['\"][^'\"]{12,}['\"]"), "Hardcoded fallback secret"),
]

UNSAFE_PATTERNS = [
    ("eval", re.compile(r"\beval\s*\("), "eval() usage", "high"),
    ("exec", re.compile(r"child_process\.(exec|execSync)"), "Shell command execution", "high"),
    ("sql-concat", re.compile(r"(?:query|execute)\s*\(\s*[`'\"].*\$\{"), "Possible SQL injection", "high"),
    ("innerhtml", re.compile(r"\.innerHTML\s*="), "Direct innerHTML assignment (XSS risk)", "medium"),
    ("disable-ssl", re.compile(r"rejectUnauthorized\s*:\s*false"), "TLS verification disabled", "high"),
]

SOURCE_EXT = re.compile(r"\.(ts|tsx|js|jsx|py|go|rs|java)$", re.I)
TEST_PATTERNS = [re.compile(p, re.I) for p in [r"/tests?/", r"\.test\.", r"\.spec\.", r"_test\.", r"test_"]]

WEIGHTS = {
    "Security": 3,
    "Critical Functionality": 3,
    "Test Coverage": 2,
    "Change & Drift": 1.5,
    "Code Volume": 1,
    "Functionality": 1,
}


def analyze_volume(files: list[FileChange], repo_average: int = 200) -> DimensionResult:
    additions = sum(f.additions for f in files)
    deletions = sum(f.deletions for f in files)
    total = additions + deletions
    findings: list[Finding] = []
    score = 0

    if total > repo_average * 3:
        score += 35
        findings.append(Finding("volume-large", "volume", "high", "Large PR", f"{total} lines across {len(files)} files.", {"metric": f"{total} lines"}))
    elif total > repo_average:
        score += 15
        findings.append(Finding("volume-medium", "volume", "medium", "Above-average PR size", f"{total} lines changed.", {"metric": f"{total} lines"}))

    for f in sorted(files, key=lambda x: x.additions + x.deletions, reverse=True)[:3]:
        if f.additions + f.deletions > 150:
            score += 5
            findings.append(Finding(f"volume-file-{f.filename}", "volume", "medium", "Large file change", f"{f.filename} has significant churn.", {"file": f.filename}))

    return DimensionResult("Code Volume", min(score, 100), f"{len(files)} files, {additions}+ / {deletions}-.", findings)


def _top_level_dirs(files: list[FileChange]) -> list[str]:
    dirs = set()
    for f in files:
        parts = f.filename.split("/")
        dirs.add("/".join(parts[:2]) if len(parts) >= 2 else parts[0] if parts else "(root)")
    return sorted(dirs)


def detect_scope_drift(title: str, body: str | None, files: list[FileChange]) -> DimensionResult:
    findings: list[Finding] = []
    dirs = _top_level_dirs(files)
    stated = set(re.findall(r"\b[a-z]{4,}\b", f"{title} {body or ''}".lower()))

    if len(dirs) >= 4:
        findings.append(Finding("drift-many", "drift", "medium", "Changes span many modules", f"Touches {len(dirs)} areas.", {"metric": ", ".join(dirs)}))

    unrelated = [d for d in dirs if d != "(root)" and not any(w in d.lower() or d.lower() in w for w in stated)]
    if len(unrelated) >= 2 and title:
        findings.append(Finding("drift-unrelated", "drift", "medium", "Possible scope drift", "Title may not cover all changed areas.", {"metric": title}))

    clusters = _cluster_dirs(files)
    if len(clusters) >= 3:
        findings.append(Finding("drift-multi", "drift", "low", "Multiple functional areas changed", f"{len(clusters)} clusters.", {"metric": ", ".join(clusters)}))

    return DimensionResult("Change & Drift", min(len(findings) * 15, 100), "Scope signals detected." if findings else "Scope appears aligned.", findings)


def analyze_functionality(files: list[FileChange]) -> DimensionResult:
    clusters = _cluster_dirs(files)
    findings: list[Finding] = []
    if len(clusters) == 1:
        findings.append(Finding("func-coherent", "functionality", "info", "Coherent change", "Single module change.", {"metric": clusters[0]}))
    elif len(clusters) >= 3:
        findings.append(Finding("func-scattered", "functionality", "medium", "Scattered functionality", "Multiple modules changed.", {"metric": ", ".join(clusters)}))
    score = 40 if len(clusters) >= 3 else 15 if len(clusters) == 2 else 0
    return DimensionResult("Functionality", score, f"{len(clusters)} functional area(s).", findings)


def detect_critical_paths(files: list[FileChange]) -> DimensionResult:
    findings: list[Finding] = []
    seen: set[str] = set()
    labels: set[str] = set()

    for f in files:
        content = f"{f.filename}\n{f.patch or ''}"
        for area_id, label, severity, patterns in CRITICAL_PATTERNS:
            if any(re.search(p, content, re.I) for p in patterns):
                key = f"{label}:{f.filename}"
                if key not in seen:
                    seen.add(key)
                    labels.add(label)
                    findings.append(Finding(f"critical-{area_id}-{f.filename}", "critical", severity, f"{label} area touched", f"Review {label.lower()} changes.", {"file": f.filename}))

    return DimensionResult("Critical Functionality", min(len(findings) * 12, 100), f"Touches: {', '.join(labels)}." if labels else "No critical paths detected.", findings)


def scan_security(files: list[FileChange]) -> DimensionResult:
    findings: list[Finding] = []
    for f in files:
        for i, line in enumerate((f.patch or "").split("\n")):
            if not line.startswith("+") or line.startswith("+++"):
                continue
            added = line[1:]
            for rule_id, pattern, label in SECRET_PATTERNS:
                if pattern.search(added):
                    findings.append(Finding(f"sec-{rule_id}-{f.filename}-{i}", "security", "high", f"Possible secret: {label}", "Added line may contain a credential.", {"file": f.filename, "line": i}))
            for rule_id, pattern, label, severity in UNSAFE_PATTERNS:
                if pattern.search(added):
                    findings.append(Finding(f"sec-{rule_id}-{f.filename}-{i}", "security", severity, f"Unsafe pattern: {label}", "Risky code pattern in diff.", {"file": f.filename, "line": i}))
    high = sum(1 for x in findings if x.severity == "high")
    return DimensionResult("Security", min(high * 25 + len(findings) * 8, 100), f"{len(findings)} security signal(s)." if findings else "No obvious security issues.", findings)


def _is_test(path: str) -> bool:
    return any(p.search(path) for p in TEST_PATTERNS)


def _is_source(path: str) -> bool:
    return bool(SOURCE_EXT.search(path)) and not _is_test(path)


def check_test_coverage(files: list[FileChange]) -> DimensionResult:
    changed = {f.filename for f in files}
    source_files = [f for f in files if _is_source(f.filename) and f.status != "removed"]
    test_files = [f for f in files if _is_test(f.filename)]
    findings: list[Finding] = []

    for src in source_files:
        base = SOURCE_EXT.sub("", src.filename)
        ext = SOURCE_EXT.search(src.filename)
        ext_s = ext.group(0) if ext else ".ts"
        candidates = {f"{base}.test{ext_s}", f"{base}.spec{ext_s}"}
        if not candidates & changed and not test_files:
            sev = "high" if src.additions > 20 else "medium"
            findings.append(Finding(f"test-gap-{src.filename}", "tests", sev, "Source changed without test update", "No matching test file in PR.", {"file": src.filename}))

    if source_files and not test_files:
        findings.append(Finding("test-none", "tests", "medium", "No test files in PR", "Source changed without test updates.", {"metric": str(len(source_files))}))

    return DimensionResult("Test Coverage", min(len(findings) * 18, 100), f"{len(test_files)} test file(s) updated." if test_files else "No test changes.", findings)


def _cluster_dirs(files: list[FileChange]) -> list[str]:
    counts: dict[str, int] = defaultdict(int)
    for f in files:
        parts = f.filename.split("/")
        key = "/".join(parts[:2]) if len(parts) >= 2 else parts[0]
        counts[key] += 1
    return [k for k, _ in sorted(counts.items(), key=lambda x: -x[1])]


def compute_risk_score(dimensions: list[DimensionResult]) -> int:
    weighted = sum(d.score * WEIGHTS.get(d.name, 1) for d in dimensions)
    total = sum(WEIGHTS.get(d.name, 1) for d in dimensions)
    return round(min(weighted / total, 100)) if total else 0


def risk_level(score: int) -> str:
    if score >= 55:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def build_focus_areas(findings: list[Finding]) -> list[dict]:
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    ranked = sorted([f for f in findings if f.severity != "info"], key=lambda f: order[f.severity])
    areas: dict[str, dict] = {}
    for f in ranked:
        area = f.evidence.get("file") or f.category
        if area not in areas:
            areas[area] = {"reason": f.title, "severity": f.severity, "files": set()}
        if f.evidence.get("file"):
            areas[area]["files"].add(f.evidence["file"])
        if order[f.severity] < order[areas[area]["severity"]]:
            areas[area]["severity"] = f.severity
            areas[area]["reason"] = f.title
    return [
        {"rank": i + 1, "area": area, "reason": data["reason"], "severity": data["severity"], "files": list(data["files"])}
        for i, (area, data) in enumerate(list(areas.items())[:5])
    ]


def rule_based_summary(risk_level_value: str, risk_score: int, dimensions: list[DimensionResult], focus_areas: list[dict]) -> str:
    highlights = [d.name for d in dimensions if any(f.severity in ("high", "medium") for f in d.findings)]
    focus = f" Start with: {', '.join(a['area'] for a in focus_areas[:3])}." if focus_areas else ""
    if risk_level_value == "high":
        return f"High-risk PR (score {risk_score}/100). Key concerns: {', '.join(highlights) or 'multiple signals'}.{focus}"
    if risk_level_value == "medium":
        return f"Medium-risk PR (score {risk_score}/100). Review {', '.join(highlights) or 'changed areas'} before approving.{focus}"
    return f"Low-risk PR (score {risk_score}/100). Focused change with no major red flags.{focus}"
