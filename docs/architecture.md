# CodeLens Architecture

This document describes the system design, components, data model, and deployment topology for CodeLens.

---

## Overview

CodeLens is a **GitHub PR analysis platform** that helps reviewers understand a pull request before manual review. It combines:

- **Rule-based analyzers** (volume, drift, security, tests, critical paths)
- **Optional AI summaries** (Groq, OpenAI, Perplexity, OpenRouter, Cursor)
- **GitHub OAuth** (user login + repo access)
- **GitHub App** (webhooks, Checks API, PR comments, embed in github.com)

---

## System diagram

![System architecture](architecture.svg)

### Layers

```
┌─────────────────────────────────────────────────────────────────┐
│  CLIENT                                                          │
│  React 19 (JSX) + Vite  →  localhost:5173 (dev) / nginx :8080   │
└───────────────────────────────┬─────────────────────────────────┘
                                │ /auth, /api (proxy)
┌───────────────────────────────▼─────────────────────────────────┐
│  API LAYER                                                       │
│  FastAPI  →  localhost:8000                                      │
│  Routers: auth | api | webhooks | github_integration             │
└───────┬─────────────────┬──────────────────┬──────────────────┘
        │                 │                  │
┌───────▼──────┐  ┌───────▼───────┐  ┌───────▼──────────────────┐
│  SERVICES    │  │  ANALYZERS    │  │  PERSISTENCE              │
│  github      │  │  engine.py    │  │  SQLite (async SQLAlchemy)  │
│  analyze_    │  │  service.py   │  │  backend/app/db/          │
│  pipeline    │  │  summarize.py │  └───────────────────────────┘
│  checks      │  │  ai.py        │
│  pr_comments │  └───────────────┘
│  discussion  │
│  commits     │
│  embed_tokens│
│  github_app  │
└──────┬───────┘
       │
┌──────▼──────────────────────────────────────────────────────────┐
│  EXTERNAL                                                        │
│  GitHub REST API  |  GitHub Webhooks  |  AI provider APIs       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Entry points

CodeLens has **three ways** analysis can be triggered. All converge on `run_pr_analysis()` in `backend/app/services/analyze_pipeline.py`.

| Entry point | Trigger | Auth token | `source` field |
|-------------|---------|------------|----------------|
| **Web UI** | User clicks Analyze | OAuth user token | `oauth` |
| **Webhook** | PR opened / synchronized | GitHub App installation token | `webhook` |
| **Demo API** | `POST /api/demo/analyze` | None (fixture file) | — |

See [request-flow.md](request-flow.md) for step-by-step flows.

---

## Backend structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI app, CORS, embed CSP middleware
│   ├── config.py               # Settings from .env
│   ├── routers/
│   │   ├── auth.py             # GitHub OAuth + JWT session
│   │   ├── api.py              # Repos, PRs, analyze, AI status, review actions
│   │   ├── webhooks.py         # GitHub App webhook receiver
│   │   └── github_integration.py  # Post comment, embed token, install status
│   ├── services/
│   │   ├── analyze_pipeline.py # Central PR analysis orchestrator
│   │   ├── github.py           # GitHub REST client (OAuth token)
│   │   ├── github_app.py       # App JWT + installation tokens
│   │   ├── checks.py           # GitHub Checks API
│   │   ├── pr_comments.py      # PR issue comments
│   │   ├── discussion.py       # Reviews + comments fetch
│   │   ├── commits.py          # Per-commit diffs
│   │   ├── diff.py             # Patch enrichment
│   │   ├── embed_tokens.py     # HMAC signed embed URLs
│   │   └── installations.py    # GitHub App install registry
│   ├── analyzers/
│   │   ├── engine.py           # Rule-based PRD dimensions
│   │   ├── service.py          # Report builder + orchestration
│   │   ├── summarize.py        # PR overview, file walkthrough, discussion
│   │   ├── ai.py               # Multi-provider AI completion
│   │   └── types.py            # AnalysisReport, Finding, FileChange
│   └── db/
│       ├── database.py         # Async SQLAlchemy engine
│       └── models.py           # User, PrReport, installations, webhooks…
├── mcp_server.py               # MCP tools for Cursor IDE
└── requirements.txt
```

---

## Frontend structure

```
frontend/
├── src/
│   ├── api/client.js           # Fetch wrapper (credentials: include)
│   ├── context/AuthContext.jsx # Session state
│   ├── pages/
│   │   ├── Login.jsx
│   │   ├── Dashboard.jsx       # Repo list
│   │   ├── RepoDetail.jsx      # Open PRs
│   │   ├── PrReport.jsx        # 5-tab report UI
│   │   └── EmbedReport.jsx     # github.com iframe embed
│   └── components/
│       ├── DiffViewer.jsx
│       ├── FileWalkthrough.jsx
│       ├── CommitWalkthrough.jsx
│       ├── ReviewDiscussion.jsx
│       └── AiSourceBadge.jsx
├── vite.config.js              # Dev proxy → backend :8000
└── nginx.conf.template         # Production reverse proxy
```

---

## Analysis pipeline

```
GitHub PR data
    │
    ├─ list_pr_files()          → FileChange[] with patches
    ├─ enrich_pr_file_patches() → full diffs when patch truncated
    ├─ fetch_pr_commits_detailed() → per-commit file changes
    └─ fetch_pr_discussion()    → reviews + issue comments
    │
    ▼
analyze_pull_request()          backend/app/analyzers/service.py
    │
    ├─ engine.py (6 dimensions) → findings + dimension scores
    ├─ compute_risk_score()     → 0–100 weighted score
    ├─ build_focus_areas()      → top 5 review targets
    ├─ summarize.py             → PR overview, file summaries (AI or rules)
    └─ ai.py                    → executive summary (optional)
    │
    ▼
AnalysisReport.to_dict()        → JSON cached in pr_reports
    │
    ├─ upsert_check_run()       → GitHub Checks tab (if App configured)
    └─ post_pr_summary_comment()→ PR conversation comment (optional)
```

---

## Database schema

SQLite by default (`backend/app/db/codelens.db`). Postgres-compatible via `DATABASE_URL`.

| Table | Purpose |
|-------|---------|
| `users` | OAuth users + GitHub access tokens |
| `pr_reports` | Cached analysis JSON per owner/repo/PR |
| `github_installations` | GitHub App installs |
| `registered_repositories` | Repos in App scope |
| `webhook_deliveries` | Idempotency + audit log |
| `pr_check_runs` | GitHub Check Run IDs per head SHA |
| `pr_review_posts` | Posted PR comments (dedupe) |

---

## Authentication model

### OAuth (web app users)

1. User visits `/auth/github` → redirect to GitHub with `state` cookie
2. Callback exchanges `code` for access token
3. JWT stored in `codelens_session` HTTP-only cookie (7 days)
4. User token used for `list_repos`, `list_pulls`, `analyze`

### GitHub App (production automation)

1. Org/user installs App on GitHub
2. `installation` webhook → row in `github_installations`
3. `pull_request` webhook → installation token → `run_pr_analysis()`
4. Checks + comments use installation token (no logged-in user required)

### Embed tokens (github.com iframe)

HMAC-signed tokens (`EMBED_SHARED_SECRET`) allow `EmbedReport.jsx` to load without OAuth when opened from a Check Run `details_url`.

---

## AI providers

Configured via `AI_PROVIDER` + API keys in `.env`:

| Provider | Env vars | Default model |
|----------|----------|---------------|
| Groq | `GROQ_API_KEY` or `AI_API_KEY` | `openai/gpt-oss-20b` |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o-mini` |
| Perplexity | `AI_API_KEY` | `sonar` |
| OpenRouter | `AI_API_KEY` | provider-specific |
| Cursor | `CURSOR_API_KEY` | `composer-2.5` (executive summary fallback) |

Rule-based summaries always run when AI is unavailable.

---

## Deployment topologies

### Local development

| Service | URL |
|---------|-----|
| Frontend (Vite) | http://localhost:5173 |
| Backend (Uvicorn) | http://localhost:8000 |
| OAuth callback | http://localhost:5173/auth/github/callback |

### Docker Compose

```bash
docker compose up --build
```

Single host on **:8080** — nginx serves frontend and proxies `/auth`, `/api`, `/webhooks` to backend.

### Kubernetes

Manifests in `deploy/kubernetes/` — Ingress, Deployments, PVC for SQLite, ConfigMap + Secret.

See [PRODUCTION_GITHUB.md](PRODUCTION_GITHUB.md) for GitHub App + webhook setup.

---

## Security considerations

| Area | Implementation |
|------|----------------|
| Session | HTTP-only JWT cookie, `SESSION_SECRET` |
| OAuth state | CSRF protection via `oauth_state` cookie |
| Webhooks | HMAC `X-Hub-Signature-256` verification |
| Embed | HMAC token + `Content-Security-Policy: frame-ancestors` |
| Tokens at rest | User OAuth tokens in SQLite (encrypt in production) |
| Scopes | OAuth: `read:user repo`; App: Contents, PRs, Checks |

---

## Related docs

- [implemented.md](implemented.md) — feature checklist
- [request-flow.md](request-flow.md) — request flows step by step
- [PRODUCTION_GITHUB.md](PRODUCTION_GITHUB.md) — GitHub App production setup
