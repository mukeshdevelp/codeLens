# CodeLens — Implementation Status

Legend: ✅ Implemented · ⚠️ Partial · ❌ Not implemented

Last updated to match the current codebase (`backend/app/`, `frontend/src/`).

---

## PRD core scope → analyzers

| PRD dimension | Status | Module | How it works |
|---------------|--------|--------|--------------|
| Change and drift | ✅ | `analyzers/engine.py` → `detect_scope_drift()` | Flags multi-module changes and title/body vs actual file paths |
| Code volume | ✅ | `engine.py` → `analyze_volume()` | Lines changed vs ~200-line baseline; large file warnings |
| Functionality | ✅ | `engine.py` → `analyze_functionality()` | Single-module vs scattered directory clusters |
| Critical functionality | ✅ | `engine.py` → `detect_critical_paths()` | Regex on paths/diff for auth, payments, permissions, data, infra, API |
| Code quality | ❌ | — | No complexity/maintainability analyzer |
| Security | ✅ | `engine.py` → `scan_security()` | Secrets, eval, SQL concat, innerHTML, TLS disable on added lines |
| Test coverage | ✅ | `engine.py` → `check_test_coverage()` | Source files without matching test file changes in PR |

**Risk scoring:** `compute_risk_score()` + `risk_level()` — weighted 0–100 → High / Medium / Low.

---

## GitHub integration

| Feature | Status | Backend | Frontend |
|---------|--------|---------|----------|
| GitHub OAuth login | ✅ | `routers/auth.py` | `pages/Login.jsx` |
| Session (JWT cookie) | ✅ | `routers/auth.py` | `context/AuthContext.jsx` |
| List repositories | ✅ | `routers/api.py`, `services/github.py` | `pages/Dashboard.jsx` |
| List open PRs | ✅ | `routers/api.py` | `pages/RepoDetail.jsx` |
| Analyze PR (manual) | ✅ | `routers/api.py` → `run_pr_analysis()` | `pages/PrReport.jsx` |
| Cached reports | ✅ | `db/models.py` → `PrReport` | `api/client.js` → `report()` |
| Re-analyze | ✅ | `POST .../analyze` | Re-analyze button |
| PR diff display | ✅ | `services/diff.py`, patches in report | `DiffViewer.jsx`, `FileWalkthrough.jsx` |
| Per-commit view | ✅ | `services/commits.py` | `CommitWalkthrough.jsx` |
| Review discussion | ⚠️ | `services/discussion.py` | `ReviewDiscussion.jsx` |
| GitHub App webhooks | ✅ | `routers/webhooks.py` | — |
| Auto-analyze on PR push | ✅ | `webhooks.py` → `run_pr_analysis(source=webhook)` | — |
| GitHub Checks API | ✅ | `services/checks.py` | Check appears on github.com |
| PR summary comments | ✅ | `services/pr_comments.py` | Post via `github_integration.py` |
| Embed in github.com | ⚠️ | `services/embed_tokens.py` | `pages/EmbedReport.jsx` |
| Native GitHub.com UI | ❌ | — | Standalone web app + embed only |

**Feature flags (`.env`):**

- `ENABLE_GITHUB_CHECKS=true` — post Check Run on analyze
- `ENABLE_GITHUB_PR_COMMENTS=false` — allow PR comments (off by default)
- `AUTO_POST_PR_COMMENT_ON_WEBHOOK=false` — auto-comment on webhook analyze

---

## Analysis output & UX

| Output | Status | Implementation |
|--------|--------|----------------|
| Risk level (H/M/L) | ✅ | `PrReport.jsx` Overview tab |
| Risk score 0–100 | ✅ | `engine.py` → `compute_risk_score()` |
| Executive summary | ✅ | `ai.py` + `service.py` (AI or rule-based) |
| Focus areas (top 5) | ✅ | `build_focus_areas()` |
| Explainable findings | ✅ | `Finding.evidence` in Risk analysis tab |
| PR overview (what/why) | ✅ | `summarize.py` → `summarize_pr_overview()` |
| File-by-file walkthrough | ✅ | `summarize_file_changes()` + `FileWalkthrough.jsx` |
| Discussion summary | ⚠️ | `summarize_discussion()` — best with AI key |
| AI multi-provider | ⚠️ | `ai.py` — needs `AI_PROVIDER` + API key |
| AI source badges | ✅ | `AiSourceBadge.jsx` |
| Demo without GitHub | ✅ | `POST /api/demo/analyze`, `scripts/demo-analyze.py` |
| MCP tools (Cursor) | ✅ | `backend/mcp_server.py` |

---

## Frontend pages

| Page / component | Status | File |
|------------------|--------|------|
| Login | ✅ | `pages/Login.jsx` |
| Protected routes | ✅ | `components/ProtectedRoute.jsx` |
| Dashboard (repos) | ✅ | `pages/Dashboard.jsx` |
| Repo PR list | ✅ | `pages/RepoDetail.jsx` |
| PR report — Overview | ✅ | `pages/PrReport.jsx` |
| PR report — Changes | ✅ | `FileWalkthrough.jsx`, `DiffViewer.jsx` |
| PR report — Commits | ✅ | `CommitWalkthrough.jsx` |
| PR report — Discussion | ✅ | `ReviewDiscussion.jsx` |
| PR report — Risk analysis | ✅ | `pages/PrReport.jsx` |
| Embed report (iframe) | ✅ | `pages/EmbedReport.jsx` |
| Layout + logout | ✅ | `components/Layout.jsx` |

---

## API endpoints

| Method | Path | Auth | Status |
|--------|------|------|--------|
| `GET` | `/health` | No | ✅ |
| `GET` | `/auth/github` | No | ✅ |
| `GET` | `/auth/github/callback` | No | ✅ |
| `GET` | `/auth/me` | Cookie | ✅ |
| `POST` | `/auth/logout` | Cookie | ✅ |
| `GET` | `/api/repos` | Cookie | ✅ |
| `GET` | `/api/repos/{o}/{r}/pulls` | Cookie | ✅ |
| `POST` | `/api/repos/{o}/{r}/pulls/{n}/analyze` | Cookie | ✅ |
| `GET` | `/api/repos/{o}/{r}/pulls/{n}/report` | Cookie | ✅ |
| `GET` | `/api/ai/status` | No | ✅ |
| `GET` | `/api/ai/test` | No | ✅ |
| `POST` | `/api/demo/analyze` | No | ✅ |
| `POST` | `/webhooks/github` | HMAC | ✅ |
| `GET` | `/api/github/status` | No | ✅ |
| `POST` | `/api/github/repos/{o}/{r}/pulls/{n}/post-summary` | Cookie | ✅ |
| `GET` | `/api/github/embed/...` | Token | ✅ |

---

## PRD non-goals

| Constraint | Status | Notes |
|------------|--------|-------|
| Human review is final | ✅ | Read-only analysis |
| No auto-approve / merge in product | ✅ | No merge automation in pipeline |
| Explainable over generic AI | ✅ | Rules always run; AI summarizes structured data |
| Focused, low-noise | ⚠️ | Top-5 focus areas; AI can be verbose |
| Not full SAST replacement | ✅ | Diff-only rule checks |

---

## Deployment

| Item | Status | Location |
|------|--------|----------|
| Docker backend | ✅ | `backend/Dockerfile` |
| Docker frontend | ✅ | `frontend/Dockerfile` |
| Docker Compose | ✅ | `docker-compose.yml` |
| Kubernetes manifests | ✅ | `deploy/kubernetes/` |
| Production GitHub guide | ✅ | `docs/PRODUCTION_GITHUB.md` |

---

## Coverage summary

| Area | Score |
|------|-------|
| Core PR analysis dimensions (PRD §4) | **6 / 7** |
| GitHub workflow (PRD §5–6) | **~95%** |
| CodeRabbit-style UX (PRD §11) | **~90%** |
| Non-goals respected (PRD §7) | **100%** |

---

## Not yet implemented

1. **Code quality dimension** — complexity, maintainability, linter integration
2. **Native GitHub.com UI** — browser extension or GitHub App UI module
3. **Dependency vulnerability scanning** — npm audit / Snyk-style checks
4. **Team/org analytics** — aggregate risk across repos
