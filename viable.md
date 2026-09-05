# CodeLens — PRD Viability & Implementation Tracker

This document maps the **hackathon Product Requirements Document** to what CodeLens actually ships today, what is partial, and what could be added next.

**Legend:** ✅ Implemented · ⚠️ Partial · ❌ Not implemented

**Last reviewed:** March 2026 (prototype at `/home/mukesh/Desktop/codeLens`)

---

## Executive summary

| Area | Status | Coverage |
|------|--------|----------|
| Core analysis dimensions (PRD §4) | ⚠️ | **6 / 7** — code quality missing |
| GitHub-based review workflow (PRD §5) | ⚠️ | **~85%** — web app, not embedded in GitHub.com |
| Expected prototype outcome (PRD §6) | ✅ | Working analyze → report flow |
| Constraints & non-goals (PRD §7) | ✅ | No auto-merge; explainable signals |
| Success criteria (PRD §9) | ⚠️ | Strong prototype; not production-hardened |
| CodeRabbit-inspired UX (PRD §11) | ⚠️ | **~85%** — walkthrough, commits, discussion, AI badges |

**Bottom line:** CodeLens is a **viable hackathon prototype** that answers *what changed, how risky, where to focus* for GitHub PRs. The largest PRD gap is **code quality analysis**. The largest product gap is **native GitHub integration** (App, webhooks, PR comments).

---

## 1. The Problem

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Help reviewers understand scope, breadth, risk before deep review | ✅ | PR report: Overview, Changes, Commits, Discussion, Risk analysis tabs |
| Reduce time spent reconstructing context from diff alone | ✅ | Executive summary, focus areas, per-file Groq summaries, commit timeline |

---

## 2. The Core Idea

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Automatically analyze a PR | ✅ | `POST /api/repos/{owner}/{repo}/pulls/{n}/analyze` |
| Surface signals reviewers need | ✅ | Risk score, dimensions, findings with evidence |
| Answer: what changed, how risky, where to focus | ✅ | `PrReport.jsx` — risk banner + focus list + walkthrough |
| Does **not** replace human review | ✅ | Read-only analysis; no approve/merge/comment bot |

---

## 3. Who Is It For?

| Audience | Status | How we serve them |
|----------|--------|-------------------|
| Developers reviewing PRs | ✅ | Primary flow: repo → PR list → analyze → report |
| Developers seeking early feedback on own changes | ⚠️ | Same flow; no author-specific “pre-submit” mode |
| Tech leads / managers (change risk visibility) | ⚠️ | Risk score + focus areas; no org dashboard or trends |

---

## 4. Core Scope — Analysis Dimensions

| PRD dimension | Asked? | Status | Implementation | Notes |
|---------------|--------|--------|----------------|-------|
| **Change and drift** | Yes | ✅ | `engine.py` → `detect_scope_drift()` | Multi-module clusters, title/body vs changed dirs |
| **Code volume** | Yes | ✅ | `engine.py` → `analyze_volume()` | Lines vs ~200-line baseline, large files |
| **Functionality** | Yes | ✅ | `engine.py` → `analyze_functionality()` | Coherent vs scattered module changes |
| **Critical functionality** | Yes | ✅ | `engine.py` → `detect_critical_paths()` | Auth, payments, permissions, data, infra, API |
| **Code quality** | Yes | ❌ | — | No maintainability, complexity, readability, or error-handling analyzer |
| **Security** | Yes | ✅ | `engine.py` → `scan_security()` | Secrets, eval, SQL concat, XSS, TLS disable |
| **Test coverage** | Yes | ✅ | `engine.py` → `check_test_coverage()` | Source changed without matching test files |

**Dimension score: 6 / 7 (86%)**

### Recent improvements (not in original PRD but aligned)
- Documentation files (`.md`) excluded from false-positive “auth” keyword scans
- Per-commit file diffs with generated patches when GitHub omits them (`services/commits.py`, `services/diff.py`)

---

## 5. GitHub Context

| Requirement | Asked? | Status | Implementation |
|-------------|--------|--------|----------------|
| Use in context of a GitHub PR | Yes | ⚠️ | Standalone app (`localhost:5173`); links to GitHub PR |
| Consider PR diff + repo context | Yes | ⚠️ | Full PR diff, commits, reviews; no deep repo history / blame |
| Understandable in normal review workflow | Yes | ✅ | Tabs: Overview → Changes → Commits → Discussion → Risk |
| Avoid unnecessary noise | Yes | ⚠️ | Top-5 focus areas; AI summaries can be verbose if Groq enabled |

| Integration | Status | Notes |
|-------------|--------|-------|
| GitHub OAuth | ✅ | `routers/auth.py` |
| List repos & open PRs | ✅ | `routers/api.py`, `services/github.py` |
| Fetch PR files, commits, reviews | ✅ | Paginated files; per-commit patches |
| GitHub App / Checks API | ✅ | `services/checks.py`, `services/github_app.py` — see [PRODUCTION_GITHUB.md](./docs/PRODUCTION_GITHUB.md) |
| Webhooks (auto-analyze on push) | ✅ | `routers/webhooks.py` → `POST /webhooks/github` |
| Post findings as PR review comments | ✅ | `services/pr_comments.py`, `POST /api/github/.../post-summary` |
| Embedded in github.com UI | ✅ | `EmbedReport.jsx`, signed `/embed/...` + Check `details_url` |

---

## 6. Expected Outcome

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Working prototype | ✅ | FastAPI + React + SQLite cache |
| See important signals | ✅ | Risk banner, focus cards, dimension findings |
| Understand **why** signals matter | ✅ | Each finding has title, description, evidence (file/line/metric) |
| Interface / scoring / AI left open to teams | ✅ | Weighted 0–100 score; Groq/OpenAI optional |

---

## 7. Constraints and Non-Goals

| Constraint | Status | Notes |
|------------|--------|-------|
| GitHub as initial environment | ✅ | OAuth + REST API |
| Human review is final | ✅ | No merge/approve automation |
| No automatic approval / merge | ✅ | Not implemented |
| Don't maximize finding count | ✅ | Top-5 focus areas; severity-ranked |
| Explainable signals over generic AI prose | ⚠️ | Rule engine + evidence; AI summaries optional with `AI · groq` badges |
| Don't replace all dev/security tools | ✅ | Targeted PR brief, not full SAST/DAST |
| Focused first experience | ✅ | Single PR report page |

---

## 8. What Teams Should Decide — Our Decisions

| Question | Our decision |
|----------|--------------|
| What should a reviewer see first? | **Overview** tab: PR summary, executive summary, focus areas |
| Which signals deserve most attention? | Weighted risk score; Security & Critical Functionality weighted 3× |
| How represent risk? | High / Medium / Low + 0–100 score + color-coded focus cards |
| What evidence with a finding? | File path, line hint, or metric in `Finding.evidence` |
| When stay quiet? | Info-level findings excluded from focus list; docs skip auth heuristics |
| How much repo context? | Current PR only (diff, commits, discussion) — no full-repo baseline |
| AI + tools together? | Rule-based core + optional Groq for summaries; MCP server for Cursor |
| Where does it live? | **Standalone web app** (not GitHub-native) |

---

## 9. Success Criteria

| Criterion | Status | Notes |
|-----------|--------|-------|
| Clear understanding of the problem | ✅ | PRD in README; product copy on login |
| Focused orientation experience | ✅ | Report tabs + focus-first Overview |
| Useful, explainable analysis | ✅ | Rule-based findings with evidence |
| Thoughtful risk prioritization | ✅ | `build_focus_areas()`, weighted scorer |
| Working prototype, easy to demo | ✅ | `POST /api/demo/analyze`, fixture PR, MCP tools |

---

## 10. The Challenge

| From → To | Status |
|-----------|--------|
| “Large PR — where do I start?” → structured entry point | ✅ | Focus areas + risk level |
| “I know what's risky and where to focus” | ⚠️ | Strong for volume/security/tests; weak on code quality |

---

## 11. Reference (CodeRabbit-inspired)

| CodeRabbit-like feature | Asked implicitly | Status | Where |
|------------------------|------------------|--------|-------|
| PR walkthrough / summary | Yes | ✅ | Overview + `summarize_pr_overview()` |
| Per-file change summary | Yes | ✅ | Changes tab + Groq per-file summaries |
| Inline diffs | Yes | ✅ | `DiffViewer.jsx`, green/red lines |
| Commit-by-commit history | Yes | ✅ | **Commits** tab + `CommitWalkthrough.jsx` |
| Review discussion summary | Yes | ✅ | Discussion tab + `summarize_discussion()` |
| AI vs rule badges | — | ✅ | `AiSourceBadge.jsx` on each section |
| Post review comments to GitHub | — | ❌ | Not built |
| Learnings / incremental review | — | ❌ | Not built |

---

## Full feature inventory (what we built)

### Backend
| Feature | Status | File(s) |
|---------|--------|---------|
| Volume analyzer | ✅ | `analyzers/engine.py` |
| Drift analyzer | ✅ | `analyzers/engine.py` |
| Functionality analyzer | ✅ | `analyzers/engine.py` |
| Critical paths analyzer | ✅ | `analyzers/engine.py` |
| Security scanner | ✅ | `analyzers/engine.py` |
| Test coverage checker | ✅ | `analyzers/engine.py` |
| Risk score & level | ✅ | `analyzers/engine.py` |
| Focus area ranking | ✅ | `analyzers/engine.py` |
| AI summaries (Groq/OpenAI/…) | ⚠️ | `analyzers/ai.py`, `summarize.py` |
| PR + file + discussion summaries | ✅ | `analyzers/summarize.py` |
| Report persistence (SQLite) | ✅ | `models.py`, `routers/api.py` |
| PR commits with file patches | ✅ | `services/commits.py`, `services/diff.py` |
| Review activity fetch | ✅ | `services/discussion.py` |
| MCP server | ✅ | `mcp_server.py` |
| Demo analyze (no auth) | ✅ | `POST /api/demo/analyze` |

### Frontend
| Feature | Status | File(s) |
|---------|--------|---------|
| GitHub login | ✅ | `pages/Login.jsx` |
| Repo dashboard | ✅ | `pages/Dashboard.jsx` |
| PR list | ✅ | `pages/RepoDetail.jsx` |
| PR report — Overview | ✅ | `pages/PrReport.jsx` |
| PR report — Changes (walkthrough + diffs) | ✅ | `FileWalkthrough.jsx`, `DiffViewer.jsx` |
| PR report — Commits (per-commit diffs) | ✅ | `CommitWalkthrough.jsx` |
| PR report — Discussion | ✅ | `ReviewDiscussion.jsx` |
| PR report — Risk analysis | ✅ | `pages/PrReport.jsx` |
| AI source badges | ✅ | `AiSourceBadge.jsx` |
| Re-analyze + cached reports | ✅ | `PrReport.jsx`, `api/client.js` |

---

## Suggested features to add (prioritized)

### High impact — closes PRD gaps

1. **Code quality dimension** ❌ → ✅  
   - Detect long functions, deep nesting, missing error handling in changed lines  
   - File: new `analyze_code_quality()` in `engine.py`  
   - PRD §4 explicit requirement

2. **Repo-relative volume baseline** ⚠️ → ✅  
   - Compare PR size to repo’s historical median (GitHub API or cached stats)  
   - Today uses fixed ~200-line default

3. **Dependency / supply-chain signals** ⚠️ → ✅  
   - Flag `package.json`, `requirements.txt`, lockfile changes in security dimension  
   - PRD §4 mentions “dependency risks”

### Medium impact — better GitHub workflow

4. **GitHub webhook auto-analyze** ❌  
   - On `pull_request` synchronize, run analyze and update cache  
   - Env: `GITHUB_WEBHOOK_SECRET` already stubbed

5. **GitHub App or Check Run** ❌  
   - Show risk summary as a PR check on github.com  
   - Addresses PRD §5 “experience within GitHub”

6. **Optional PR comment export** ❌  
   - “Post summary as review comment” (human-triggered, not auto-merge)  
   - Aligns with CodeRabbit without violating non-goals

### UX & trust

7. **Confidence / quiet mode** ⚠️  
   - Hide low-severity dimensions when score &lt; threshold  
   - PRD §8: “When should CodeLens stay quiet?”

8. **Author vs reviewer view** ⚠️  
   - Same report; optional “submit for review” checklist for authors  
   - PRD §3 secondary audience

9. **Manager / org dashboard** ❌  
   - Open PR risk across repos  
   - PRD §3 tech leads

### AI improvements

10. **Shorter, evidence-linked AI summaries** ⚠️  
    - Tie Groq bullets to specific findings IDs  
    - PRD §7: explainable over generic prose

11. **AI test for health** ✅ (exists)  
    - Extend: show provider status in report header (`GET /api/ai/status`)

### Technical hardening

12. **Rate-limit & parallel commit fetch** ⚠️  
    - Batch GitHub calls; backoff on 403/429 for large PRs

13. **Side-by-side diff view** ❌  
    - Optional UI mode for Commits tab (unified diff exists today)

---

## Quick reference — PRD section checklist

| PRD § | Topic | Done? |
|-------|-------|-------|
| 1 | Problem statement | ✅ Addressed by product |
| 2 | Core idea | ✅ |
| 3 | Target users | ⚠️ Reviewers yes; managers partial |
| 4 | Seven analysis dimensions | ⚠️ 6/7 |
| 5 | GitHub context | ⚠️ API yes; native UI no |
| 6 | Working prototype | ✅ |
| 7 | Constraints / non-goals | ✅ |
| 8 | Team decisions | ✅ Documented above |
| 9 | Success criteria | ⚠️ Mostly met |
| 10 | Challenge (where to start → where to focus) | ✅ |
| 11 | CodeRabbit reference | ⚠️ ~85% |

---

## How to verify locally

```bash
# Backend
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev

# Demo without GitHub
curl -X POST http://localhost:8000/api/demo/analyze

# AI health
curl http://localhost:8000/api/ai/status
```

Sign in → pick repo → open PR → **Re-analyze** → review all five tabs.

---

## Related docs

- Full PRD copy: [README.md — Product Requirements Document](./README.md#product-requirements-document)
- **Production GitHub setup:** [docs/PRODUCTION_GITHUB.md](./docs/PRODUCTION_GITHUB.md)
- Implementation tables: [README.md — Implementation status](./README.md#implementation-status)
- Architecture: [docs/architecture.svg](./docs/architecture.svg)
