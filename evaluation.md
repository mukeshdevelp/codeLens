# CodeLens PR Evaluation — Dimension Scoring Reference

This document describes how CodeLens calculates risk scores for pull requests: per-dimension formulas, the overall weighted score, risk level thresholds, and source file references.

---

## Overview

CodeLens evaluates every PR across **six dimensions**. Each dimension produces:

- A **score** from **0 to 100** (higher = more concern)
- One or more **findings** with individual severities (`high`, `medium`, `low`, `info`)

Those six scores are combined into a **final risk score (0–100)**, which maps to an overall **risk level**: `low`, `medium`, or `high`.

```
PR files + metadata
    → 6 dimension scores (0–100 each)
    → weighted average → final risk score (0–100)
    → risk level (low / medium / high)
```

---

## Source Files

| Purpose | File |
|---------|------|
| **Dimension formulas & weights** | [`backend/app/analyzers/engine.py`](backend/app/analyzers/engine.py) |
| **Orchestration (runs all dimensions)** | [`backend/app/analyzers/service.py`](backend/app/analyzers/service.py) |
| **Data types (`FileChange`, `Finding`, `AnalysisReport`)** | [`backend/app/analyzers/types.py`](backend/app/analyzers/types.py) |
| **End-to-end pipeline (fetch → analyze → save)** | [`backend/app/services/analyze_pipeline.py`](backend/app/services/analyze_pipeline.py) |
| **HTTP API (`POST /analyze`, `GET /report`)** | [`backend/app/routers/api.py`](backend/app/routers/api.py) |

---

## Final Risk Score

### Formula

```
riskScore = round( Σ (dimensionScore × weight) / Σ weights )
```

Capped at **100**. Implemented in `compute_risk_score()` — [`engine.py`](backend/app/analyzers/engine.py) (lines 195–199).

### Weights

| Dimension | Weight |
|-----------|--------|
| Security | 3 |
| Critical Functionality | 3 |
| Test Coverage | 2 |
| Change & Drift | 1.5 |
| Code Volume | 1 |
| Functionality | 1 |

**Total weight = 11.5**

### Risk Level Thresholds

Implemented in `risk_level()` — [`engine.py`](backend/app/analyzers/engine.py) (lines 202–208).

| Final `riskScore` | Risk Level |
|-------------------|------------|
| 0 – 24 | `low` |
| 25 – 54 | `medium` |
| 55 – 100 | `high` |

### GitHub Check Mapping

When GitHub Checks are enabled — [`backend/app/services/checks.py`](backend/app/services/checks.py):

| Risk Level | Check Conclusion |
|------------|------------------|
| `high` | `failure` |
| `medium` | `neutral` |
| `low` | `success` |

---

## Dimension 1: Code Volume

**Function:** `analyze_volume()` — [`engine.py`](backend/app/analyzers/engine.py) (lines 53–73)

**Question:** How large is this PR?

### Inputs

- `additions` and `deletions` per file (from GitHub)
- `repo_average` baseline (default: **200** lines)

```
total = Σ (additions + deletions) across all files
```

### Score Formula

Start at `score = 0`, then add points (mutually exclusive tiers for total size):

| Condition | Points |
|-----------|--------|
| `total > repo_average × 3` (> 600 lines) | +35 |
| `total > repo_average` (> 200 lines, ≤ 600) | +15 |
| Otherwise | +0 |

Additionally, for each of the **top 3 files** by churn (`additions + deletions`):

| Condition | Points |
|-----------|--------|
| File churn > 150 lines | +5 per file |

```
volumeScore = min(score, 100)
```

### Findings

| Trigger | Finding Severity |
|---------|------------------|
| `total > 600` | `high` — "Large PR" |
| `200 < total ≤ 600` | `medium` — "Above-average PR size" |
| Top file churn > 150 | `medium` — "Large file change" |

---

## Dimension 2: Change & Drift

**Function:** `detect_scope_drift()` — [`engine.py`](backend/app/analyzers/engine.py) (lines 84–101)

**Question:** Do the changed files align with what the PR title/body claims?

### Helpers

- **Top-level dirs:** first 1–2 path segments per file (e.g. `backend/app`, `frontend/src`)
- **Stated words:** words with 4+ letters from `title + body` (lowercased)
- **Clusters:** same grouping as Functionality (`_cluster_dirs()`)

### Findings (each adds one warning)

| # | Condition | Finding Severity |
|---|-----------|------------------|
| 1 | ≥ 4 distinct top-level dirs | `medium` — "Changes span many modules" |
| 2 | ≥ 2 dirs unrelated to title/body words (and title is non-empty) | `medium` — "Possible scope drift" |
| 3 | ≥ 3 functional clusters | `low` — "Multiple functional areas changed" |

A dir is "related" if any stated word appears in the dir path or vice versa.

### Score Formula

```
driftScore = min(numberOfFindings × 15, 100)
```

---

## Dimension 3: Functionality

**Function:** `analyze_functionality()` — [`engine.py`](backend/app/analyzers/engine.py) (lines 104–113)

**Question:** Are changes focused in one area or scattered across modules?

### Cluster Definition

Groups files by first 1–2 path segments, sorted by file count (descending).  
Helper: `_cluster_dirs()` — lines 186–192.

### Score Formula

| Number of clusters | Score |
|--------------------|-------|
| 1 | 0 |
| 2 | 15 |
| ≥ 3 | 40 |

### Findings

| Clusters | Finding Severity |
|----------|------------------|
| 1 | `info` — "Coherent change" |
| ≥ 3 | `medium` — "Scattered functionality" |

---

## Dimension 4: Critical Functionality

**Function:** `detect_critical_paths()` — [`engine.py`](backend/app/analyzers/engine.py) (lines 116–135)

**Question:** Does the PR touch sensitive areas (auth, payments, database, API, etc.)?

### Pattern Table

Defined in `CRITICAL_PATTERNS` — lines 14–21. Each match is on `filename + patch` (case-insensitive regex). Documentation files (`.md`, `.txt`, etc.) are **skipped**.

| Area ID | Label | Finding Severity | Keywords (examples) |
|---------|-------|------------------|---------------------|
| `auth` | Authentication | `high` | auth, login, session, jwt, oauth, password, token |
| `payments` | Payments & Billing | `high` | payment, billing, stripe, checkout, invoice |
| `permissions` | Permissions & Access Control | `high` | permission, rbac, acl, authorize, role, policy |
| `data` | Data Handling | `medium` | database, migration, schema, sql, encrypt, pii |
| `infra` | Infrastructure & Config | `medium` | docker, kubernetes, terraform, deploy, .env, config |
| `api` | Public API Surface | `medium` | routes/, controller, middleware, endpoint, graphql |

One finding per unique `(label, filename)` pair.

### Score Formula

```
criticalScore = min(numberOfFindings × 12, 100)
```

---

## Dimension 5: Security

**Function:** `scan_security()` — [`engine.py`](backend/app/analyzers/engine.py) (lines 138–153)

**Question:** Are there secrets or unsafe patterns in **newly added lines**?

### Scan Scope

Only lines in the patch that start with `+` (added lines). Lines starting with `+++` (file headers) are excluded.

### Secret Patterns (`SECRET_PATTERNS`)

All matches produce findings with severity **`high`**:

| Rule ID | Detects |
|---------|---------|
| `aws-key` | AWS access key (`AKIA...`) |
| `github-token` | GitHub personal token (`ghp_...`) |
| `private-key` | PEM private key block |
| `api-key-assign` | `api_key = "..."`, `password: "..."`, etc. |
| `hardcoded-fallback` | `\|\| "long-string"` fallback patterns |

### Unsafe Patterns (`UNSAFE_PATTERNS`)

| Rule ID | Detects | Finding Severity |
|---------|---------|------------------|
| `eval` | `eval(` | `high` |
| `exec` | `child_process.exec` / `execSync` | `high` |
| `sql-concat` | SQL/query string interpolation | `high` |
| `disable-ssl` | `rejectUnauthorized: false` | `high` |
| `innerhtml` | `.innerHTML =` | `medium` |

### Score Formula

```
highCount = count of findings where severity == "high"
totalFindings = count of all security findings

securityScore = min(highCount × 25 + totalFindings × 8, 100)
```

### Examples

| Findings | Calculation | Score |
|----------|-------------|-------|
| None | 0 | 0 |
| 1 medium (innerHTML) | 0×25 + 1×8 | 8 |
| 1 high (secret) | 1×25 + 1×8 | 33 |
| 2 high | 2×25 + 2×8 | 66 |

---

## Dimension 6: Test Coverage

**Function:** `check_test_coverage()` — [`engine.py`](backend/app/analyzers/engine.py) (lines 164–183)

**Question:** Did source code change without corresponding test updates?

### Definitions

- **Source file:** matches `.(ts|tsx|js|jsx|py|go|rs|java)$` and is not a test path
- **Test file:** path matches `/test/`, `.test.`, `.spec.`, `_test.`, or `test_`

### Findings

| Condition | Finding Severity |
|-----------|------------------|
| Source file changed; no `{base}.test.{ext}` or `{base}.spec.{ext}` in PR; no test files at all | `high` if source additions > 20, else `medium` |
| Any source files changed but zero test files in PR | `medium` — "No test files in PR" |

### Score Formula

```
testScore = min(numberOfFindings × 18, 100)
```

---

## Focus Areas

**Function:** `build_focus_areas()` — [`engine.py`](backend/app/analyzers/engine.py) (lines 211–228)

Ranks non-`info` findings by severity (`high` > `medium` > `low`), groups by file or category, returns **top 5** areas for reviewers.

---

## Worked Example

**PR characteristics:**

- 350 lines changed → Volume: **15**
- 2 drift warnings → Drift: **30**
- 3 clusters → Functionality: **40**
- 1 auth file touch → Critical: **12**
- 1 secret in diff → Security: **33**
- 1 test gap → Tests: **18**

**Final score:**

```
(33×3 + 12×3 + 18×2 + 30×1.5 + 15×1 + 40×1) / 11.5
= (99 + 36 + 36 + 45 + 15 + 40) / 11.5
= 271 / 11.5
≈ 24  →  LOW risk
```

---

## Pipeline Flow

```
analyze_pipeline.py
    ├── GitHub: PR, files, commits, discussion
    └── service.py :: analyze_pull_request()
            ├── engine.py: 6 dimensions
            ├── compute_risk_score()
            ├── risk_level()
            ├── build_focus_areas()
            └── optional AI summaries (ai.py) — does not change dimension scores
```

---

## Notes

- All dimension scores are **independent** and each capped at **100**.
- Individual **finding** severities (`high`/`medium`/`low`) are separate from the overall PR **risk level**.
- The `repo_average` baseline for Code Volume is a **fixed default (200)** — not computed from repository history.
- AI summaries (when configured) enrich text fields only; they do **not** alter dimension or risk scores.
