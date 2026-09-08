# CodeLens — Architecture & Working Q&A

A reference guide for interviews, demos, and architecture discussions.

---

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Tech Stack](#2-tech-stack)
3. [Authentication & Sessions](#3-authentication--sessions)
4. [Manual Analyze Flow](#4-manual-analyze-flow)
5. [Webhook / Auto-Analyze Flow](#5-webhook--auto-analyze-flow)
6. [Analyzers & Risk Scoring](#6-analyzers--risk-scoring)
7. [AI Integration](#7-ai-integration)
8. [Database Design](#8-database-design)
9. [GitHub Integration Features](#9-github-integration-features)
10. [Security](#10-security)
11. [Deployment & Dev Setup](#11-deployment--dev-setup)
12. [Design Decisions & Tradeoffs](#12-design-decisions--tradeoffs)
13. [30-Second Elevator Pitch](#13-30-second-elevator-pitch)
14. [Tricky Follow-Up Questions](#14-tricky-follow-up-questions)

---

## 1. High-Level Architecture

### Q: What is CodeLens and what problem does it solve?

**A:** CodeLens is a GitHub PR analysis tool. It fetches pull request data from GitHub, runs rule-based (and optional AI) analysis across six risk dimensions, and shows a report in a web UI — risk score, focus areas, file summaries, commits, and discussion. It can also push results back to GitHub via Checks and PR comments.

### Q: Describe the overall architecture.

**A:** It is a **two-tier app**:

- **Frontend:** React + Vite (`:5173`) — login, repo list, PR report UI
- **Backend:** FastAPI + Uvicorn (`:8000`) — OAuth, REST API, analyzers, SQLite
- **External:** GitHub REST API (PR data), optional LLM API (Groq/OpenAI), optional GitHub App (webhooks + Checks)

User → React UI → FastAPI API → GitHub API ↓ SQLite (cached reports) ↓ Optional: GitHub Checks / PR comments



### Q: Why separate `analyzers/` and `services/`?

**A:**

- **`analyzers/`** = pure analysis logic (rules, scoring, AI summaries) — no HTTP, no DB
- **`services/`** = integrations (GitHub client, pipeline, webhooks, checks, comments)

This keeps analysis testable and reusable from manual UI, webhooks, and checks.

### Q: What is the single shared pipeline for all analyze paths?

**A:** `run_pr_analysis()` in `backend/app/services/analyze_pipeline.py`. Manual OAuth analyze, webhook auto-analyze, and check re-runs all go through it so reports are identical and stored the same way.

---

## 2. Tech Stack

### Q: What frontend technologies are used?

**A:** React 19, React Router 7, Vite 6. HTTP via native `fetch` (no Axios). Dev proxy forwards `/api` and `/auth` to the backend.

### Q: What backend technologies are used?

**A:** FastAPI, Uvicorn, SQLAlchemy 2 (async), aiosqlite (SQLite), httpx (GitHub + AI), python-jose (JWT sessions), pydantic-settings (config).

### Q: Why httpx instead of a GitHub SDK?

**A:** Lightweight, async-friendly, full control over REST calls. GitHub OAuth, PR fetch, reviews, merge, and Checks are all plain REST — no SDK needed.

### Q: Why SQLite?

**A:** Simple local/small-deploy setup — users, cached reports, webhook idempotency, installation metadata. Fine for MVP; can swap `DATABASE_URL` for Postgres in production.

---

## 3. Authentication & Sessions

### Q: How does GitHub login work?

**A:** Standard **GitHub OAuth App** flow:

1. User hits `/auth/github`
2. Redirect to GitHub with `state` cookie
3. Callback `/auth/github/callback` exchanges `code` for `access_token` via httpx
4. User profile saved in `users` table
5. Backend issues JWT in `codelens_session` HttpOnly cookie (python-jose)

### Q: How are API requests authenticated?

**A:** Cookie-based. `get_current_user()` reads `codelens_session`, decodes JWT, loads `User` from DB. Frontend uses `credentials: "include"`.

### Q: Where is the GitHub token stored?

**A:** In SQLite `users.access_token`. Used for all manual analyze GitHub API calls.

### Q: OAuth App vs GitHub App — why both?

**A:**

- **OAuth App** → user login + manual analyze with **user token** (repos user can access)
- **GitHub App** → **webhooks**, **Checks**, **installation token** — works without a logged-in user and can react to PR events automatically

OAuth user tokens cannot receive org webhooks reliably; that is why the App exists.

### Q: What is `GITHUB_REDIRECT_URI` and why did it cause errors?

**A:** Must exactly match the callback URL registered in the GitHub OAuth App settings. It should be `{FRONTEND_URL}/auth/github/callback`, not the webhook URL.

---

## 4. Manual Analyze Flow

### Q: What happens when a user clicks "Analyze"?

**A:**

1. Navigate to PR report page
2. `GET /api/.../report` — try cached report
3. If missing or stale → `POST /api/.../analyze`
4. Backend fetches PR from GitHub, runs analyzers, saves to `pr_reports`, returns JSON
5. UI renders Overview, Changes, Commits, Discussion, Risk tabs

### Q: What does "stale report" mean?

**A:** Frontend `isStaleReport()` checks schema/version signals — missing fields like `aiProvider`, `commits`, `summarySource`, or AI summaries when AI is configured. Stale reports trigger automatic re-analyze.

### Q: What GitHub data is fetched during analyze?

**A:** PR metadata, file list + patches, enriched diffs (compare/contents if patch missing), detailed commits, reviews + review comments + issue comments.

### Q: Is analyze synchronous or async?

**A:** **Synchronous HTTP request** from the user's perspective — one `POST /analyze` blocks until done (can take 10–60s with AI). Backend uses async/await internally but does not queue jobs.

### Q: How is caching handled?

**A:** Full report JSON stored in `pr_reports.report_json`. `GET /report` returns cache without re-calling GitHub. **Re-analyze** always re-fetches and re-runs everything.

### Request flow (manual)
Browser (React + fetch) → Vite proxy (:5173 → :8000) → FastAPI analyze_pr() → get_current_user() [python-jose + SQLAlchemy] → run_pr_analysis() → httpx → GitHub API (PR, files, commits, discussion) → analyze_pull_request() [engine.py + optional AI via httpx] → SQLAlchemy → pr_reports (SQLite) → JSON response → React UI



---

## 5. Webhook / Auto-Analyze Flow

### Q: How does automatic analysis work?

**A:** GitHub App sends `POST /webhooks/github` on `pull_request` events (`opened`, `synchronize`, `reopened`, `ready_for_review`). Backend verifies `X-Hub-Signature-256`, gets installation token, calls same `run_pr_analysis()` with `source="webhook"`.

### Q: How are duplicate webhooks handled?

**A:** `webhook_deliveries` table stores `X-GitHub-Delivery` ID. Already-processed deliveries are skipped (idempotency).

### Q: Manual vs webhook — key differences?

| | Manual | Webhook |
|--|--------|---------|
| Trigger | User clicks Analyze | PR opened/updated |
| Token | User OAuth token | Installation token |
| `source` | `oauth` | `webhook` |
| User required | Yes | No |
| Pipeline | Same `run_pr_analysis()` | Same |

---

## 6. Analyzers & Risk Scoring

### Q: What are the six analysis dimensions?

**A:**

1. **Code Volume** — lines changed vs baseline
2. **Change & Drift** — title/body vs folders touched
3. **Functionality** — focused vs scattered changes
4. **Critical Functionality** — auth, payments, API, infra paths
5. **Security** — secrets, eval, SQL concat, innerHTML, etc. in `+` lines
6. **Test Coverage** — source files changed without test files

### Q: How is the risk score calculated?

**A:** **Weighted average** of dimension scores:

| Dimension | Weight |
|-----------|--------|
| Security | × 3 |
| Critical Functionality | × 3 |
| Test Coverage | × 2 |
| Change & Drift | × 1.5 |
| Code Volume | × 1 |
| Functionality | × 1 |

Rounded to 0–100.

### Q: How are risk levels mapped?

**A:**

- **High:** score ≥ 55
- **Medium:** 25–54
- **Low:** < 25

### Q: What are focus areas?

**A:** Top 5 ranked findings (by severity) grouped by file or category — tells reviewers where to look first.

### Q: Does analysis send code to GitHub?

**A:** No. It **reads** from GitHub. Analysis runs locally on fetched diffs/patches.

### Q: Rule-based vs AI — what is the split?

**A:** **Rules always run** (dimensions, score, focus areas). **AI is optional** — executive summary, PR overview, per-file summaries, discussion summary. If no API key or AI fails, rule-based fallbacks are used.

---

## 7. AI Integration

### Q: Which AI providers are supported?

**A:** OpenAI-compatible APIs: OpenAI, Groq, Perplexity, OpenRouter. Configured via `AI_PROVIDER`, `AI_API_KEY` / `GROQ_API_KEY`, etc.

### Q: What does AI actually summarize?

**A:** Executive summary, PR overview, discussion thread, and per-file change summaries (when enabled and key is set).

### Q: How does the UI know if AI was used?

**A:** Report includes fields like `aiProvider`, `aiSummariesUsed`, `executiveSummarySource`, `summarySource` per file (`"ai"` vs `"rules"`).

---

## 8. Database Design

### Q: What are the main tables?

**A:**

| Table | Purpose |
|-------|---------|
| `users` | OAuth users + GitHub tokens |
| `pr_reports` | Cached analysis JSON (unique per owner/repo/PR#) |
| `github_installations` | App installs |
| `registered_repositories` | Repos under an installation |
| `webhook_deliveries` | Idempotency + audit |
| `pr_check_runs` | GitHub Check Run IDs per PR/SHA |
| `pr_review_posts` | Tracks posted PR comments (avoid duplicates) |

### Q: Why store report as JSON blob instead of normalized tables?

**A:** Report shape evolves (commits, AI metadata, file summaries). JSON blob is simpler for read-heavy cache; frontend consumes one object.

### Q: What is `head_sha` on reports?

**A:** Commit SHA at PR head when analyzed — used to tie Check Runs to the right commit and detect if PR moved forward.

---

## 9. GitHub Integration Features

### Q: What are GitHub Checks?

**A:** A Check Run on the PR's Checks tab. Risk maps to conclusion: high → `failure`, medium → `neutral`, low → `success`. Details link goes to embed report page.

### Q: How are PR summary comments posted?

**A:** Optional via `post_pr_summary_comment()` — markdown summary on the PR. Tracked in `pr_review_posts` to avoid duplicate spam. Manual "Post to GitHub" button or webhook auto-post if enabled.

### Q: Can users approve/merge from CodeLens?

**A:** Yes — `PrReport` has Approve and Merge buttons that call GitHub API with the user's OAuth token (`/approve`, `/merge` endpoints).

### Q: What is the embed flow?

**A:** Signed token (`embed_shared_secret`) allows viewing report in an iframe on github.com (Check details link). CSP `frame-ancestors` allows github.com when configured.

---

## 10. Security

### Q: How are webhooks secured?

**A:** HMAC-SHA256 signature verification (`X-Hub-Signature-256`) against `GITHUB_WEBHOOK_SECRET`. Invalid signature → 401.

### Q: How are sessions secured?

**A:** HttpOnly cookies, `SameSite=lax`, `Secure` when `FRONTEND_URL` is HTTPS (e.g. ngrok).

### Q: Does CodeLens scan for secrets in PRs?

**A:** Yes — rule engine looks for AWS keys, GitHub tokens, private keys, hardcoded credentials in added lines (`SECRET_PATTERNS` in `engine.py`).

### Q: Where are API keys stored?

**A:** `.env` file (not committed). Loaded by pydantic-settings.

### Q: Risk of storing GitHub user tokens in SQLite?

**A:** Real concern for production — should encrypt at rest, use shorter-lived tokens, or prefer GitHub App installation tokens where possible.

---

## 11. Deployment & Dev Setup

### Q: How do frontend and backend talk in development?

**A:** Vite dev server proxies `/api`, `/auth`, `/webhooks` → `localhost:8000`. User only hits `:5173`.

### Q: How do you expose locally for GitHub OAuth?

**A:** ngrok/Cloudflare Tunnel on port 5173. Set `FRONTEND_URL`, `BACKEND_URL`, and `GITHUB_REDIRECT_URI` to the public URL. GitHub OAuth callback must match.

### Q: What env vars are essential?

**A:**

- `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_REDIRECT_URI`
- `SESSION_SECRET`
- `FRONTEND_URL`, `BACKEND_URL`
- Optional: `GROQ_API_KEY`, GitHub App keys, `GITHUB_WEBHOOK_SECRET`

### Q: Is there a demo mode without GitHub?

**A:** Yes — `POST /api/demo/analyze` uses a fixture JSON file, no login required.

---

## 12. Design Decisions & Tradeoffs

### Q: Why one big analyze endpoint instead of streaming?

**A:** Simpler UX and implementation. Tradeoff: long wait on large PRs with AI. Could add SSE/WebSockets later.

### Q: Why not analyze on every page view?

**A:** GitHub rate limits + cost/latency. Cache in SQLite; re-analyze only when user asks or report is stale.

### Q: Why FastAPI over Django/Flask?

**A:** Native async, automatic OpenAPI docs, clean dependency injection (`get_current_user`, `get_db`), good fit for httpx + SQLAlchemy async.

### Q: How would you scale this?

**A:**

- Move analyze to a **job queue** (Celery/Redis)
- **Postgres** instead of SQLite
- Cache GitHub responses
- Rate-limit AI calls
- Horizontal backend replicas behind a load balancer
- Webhook workers separate from API

### Q: What would you improve next?

**A:** Background jobs, token encryption, incremental analyze (only new commits), branch protection integration, team dashboards, configurable rule weights per repo.

---

## 13. 30-Second Elevator Pitch

> CodeLens is a React + FastAPI app. Users log in with GitHub OAuth. When they analyze a PR, the backend fetches the PR diff, commits, and reviews from GitHub using httpx, runs six rule-based analyzers plus optional AI summaries, computes a weighted risk score, caches the result in SQLite, and returns a rich JSON report to the UI. For production, a GitHub App listens to webhooks and runs the same pipeline automatically, optionally posting a Check Run and PR comment. Manual and webhook paths share one pipeline so results stay consistent.

---

## 14. Tricky Follow-Up Questions

### Q: What happens if GitHub token expires?

**A:** GitHub API calls fail (401/403). User must log out and log in again to refresh the stored token. No refresh-token flow is implemented unless GitHub provides one for the app type.

### Q: What if two users analyze the same PR?

**A:** `pr_reports` has unique constraint on `(owner, repo, pr_number)` — one cached report per PR; last analyze overwrites.

### Q: Does analyze run on closed PRs?

**A:** Repo list shows open PRs by default. You can still open/analyze if you have the URL; GitHub API returns closed PR data if accessible.

### Q: How do you test analyzers without GitHub?

**A:** Demo endpoint + unit tests on `engine.py` with mock `FileChange` objects (patches as strings).

---

## Key Source Files

| Area | File |
|------|------|
| UI trigger | `frontend/src/pages/PrReport.jsx` |
| HTTP client | `frontend/src/api/client.js` |
| API routes | `backend/app/routers/api.py` |
| Auth | `backend/app/routers/auth.py` |
| Pipeline | `backend/app/services/analyze_pipeline.py` |
| GitHub client | `backend/app/services/github.py` |
| Analyzers | `backend/app/analyzers/service.py`, `engine.py` |
| Webhooks | `backend/app/routers/webhooks.py` |
| DB models | `backend/app/db/models.py` |
| Config | `backend/app/config.py` |