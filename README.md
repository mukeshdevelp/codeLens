# CodeLens

**Understand a pull request before reviewing it.**

CodeLens is a GitHub-based tool that analyzes pull requests and gives reviewers a structured brief before they read the full diff. It answers: *What changed? How risky is it? Where should I focus?*

---

## Table of contents

- [Problem](#problem)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Functionalities](#functionalities)
- [Project structure](#project-structure)
- [Setup](#setup)
- [Environment variables](#environment-variables)
- [User flow](#user-flow)
- [API reference](#api-reference)
- [PR analysis dimensions](#pr-analysis-dimensions)
- [Demo without GitHub](#demo-without-github)
- [MCP server (optional)](#mcp-server-optional)
- [Scripts](#scripts)

---

## Problem

Code reviews get harder as PRs grow. Reviewers often spend time figuring out scope, risk, and where to look before they can review meaningfully. CodeLens surfaces those signals upfront — without replacing human judgment.

---

## Architecture

### System architecture

![CodeLens system architecture](docs/architecture.svg)

### PR analysis request flow

![PR analysis sequence flow](docs/analyze-flow.svg)

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19 (plain JavaScript / JSX), Vite, React Router |
| Backend | FastAPI, SQLAlchemy, SQLite (async) |
| Auth | GitHub OAuth 2.0, JWT session cookies |
| GitHub | REST API via `httpx` |
| Analysis | Python rule-based analyzers |
| AI summary | Cursor API (primary) or OpenAI (fallback) |
| MCP | Python MCP server for Cursor IDE integration |

---

## Functionalities

### Authentication & access
- **GitHub OAuth login** — users sign in with GitHub and grant repo read access
- **Session management** — HTTP-only JWT cookie, 7-day expiry
- **Repo listing** — shows repositories the user owns or collaborates on

### Pull request analysis
- **List open PRs** per repository
- **One-click analyze** — fetches PR diff from GitHub and runs full analysis
- **Cached reports** — results stored in SQLite; re-fetch without re-analyzing
- **Re-analyze** — refresh analysis after new commits

### Analysis output (per PR)
| Output | Description |
|--------|-------------|
| **Risk level** | High / Medium / Low with score 0–100 |
| **Executive summary** | AI-generated (or rule-based) overview |
| **Focus areas** | Top 5 places to review first, ranked by severity |
| **Dimension breakdown** | Per-dimension findings with evidence (file, line, metric) |

### Analysis dimensions (PRD-aligned)
| Dimension | What it detects |
|-----------|-----------------|
| **Code volume** | PR size, large file changes vs typical ~200 lines |
| **Change & drift** | Many modules touched, scope wider than PR title/body |
| **Functionality** | Coherent single-module change vs scattered work |
| **Critical paths** | Auth, payments, permissions, data, infra, API surfaces |
| **Security** | Secrets in diff, eval, SQL injection, XSS, disabled TLS |
| **Test coverage** | Source files changed without matching test updates |

### Demo mode
- **`POST /api/demo/analyze`** — analyze fixture PR without GitHub login
- **`scripts/demo-analyze.py`** — CLI demo using `fixtures/demo-pr.json`

### MCP integration (optional)
- **`backend/mcp_server.py`** — exposes analysis tools to Cursor AI agents

---

## Project structure

```
codeLens/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Settings from .env
│   │   ├── database.py          # SQLite + SQLAlchemy
│   │   ├── models.py            # User, PrReport
│   │   ├── routers/
│   │   │   ├── auth.py          # GitHub OAuth + session
│   │   │   └── api.py           # Repos, PRs, analyze
│   │   ├── services/
│   │   │   └── github.py        # GitHub API client
│   │   └── analyzers/
│   │       ├── engine.py        # Volume, drift, security, tests…
│   │       ├── service.py       # Orchestrator + report builder
│   │       ├── ai.py            # Cursor / OpenAI summarizer
│   │       └── types.py         # Data models
│   ├── mcp_server.py            # MCP tools for Cursor
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/client.js        # API client
│   │   ├── context/AuthContext.jsx
│   │   ├── components/          # Layout, ProtectedRoute
│   │   ├── pages/               # Login, Dashboard, RepoDetail, PrReport
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── index.html
│   ├── vite.config.js           # Proxies /auth, /api → :8000
│   └── package.json
├── fixtures/
│   └── demo-pr.json             # Sample risky PR for demo
├── docs/
│   ├── architecture.svg         # System architecture diagram
│   └── analyze-flow.svg         # PR analysis sequence diagram
├── scripts/
│   ├── dev-backend.sh
│   └── demo-analyze.py
├── .env.example
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- A GitHub account

### 1. Create a GitHub OAuth App

1. Go to [GitHub Developer Settings](https://github.com/settings/developers) → **New OAuth App**
2. Fill in:
   - **Application name:** CodeLens (local)
   - **Homepage URL:** `http://localhost:5173`
   - **Authorization callback URL:** `http://localhost:8000/auth/github/callback`
3. Copy the **Client ID** and generate a **Client Secret**

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```env
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
SESSION_SECRET=a-long-random-string
```

### 3. Install and run backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Or from project root:

```bash
./scripts/dev-backend.sh
```

Backend runs at http://localhost:8000  
Health check: http://localhost:8000/health

### 4. Install and run frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173

The Vite dev server proxies `/auth` and `/api` to the backend.

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_CLIENT_ID` | Yes | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | Yes | GitHub OAuth App client secret |
| `GITHUB_REDIRECT_URI` | No | Default: `http://localhost:8000/auth/github/callback` |
| `SESSION_SECRET` | Yes | Secret for signing JWT session cookies |
| `FRONTEND_URL` | No | Default: `http://localhost:5173` |
| `BACKEND_URL` | No | Default: `http://localhost:8000` |
| `DATABASE_URL` | No | Default: `sqlite+aiosqlite:///./codelens.db` |
| `CURSOR_API_KEY` | No | Cursor API key for AI summaries |
| `CURSOR_MODEL` | No | Default: `composer-2.5` |
| `OPENAI_API_KEY` | No | Fallback AI provider |
| `OPENAI_MODEL` | No | Default: `gpt-4o-mini` |

Without AI keys, CodeLens uses a rule-based executive summary.

---

## User flow

1. Open http://localhost:5173
2. Click **Continue with GitHub** → authorize repo access
3. **Dashboard** — pick a repository
4. **Repo page** — see open pull requests
5. Click **Analyze** on a PR
6. Review:
   - Risk level (High / Medium / Low)
   - Executive summary
   - Top focus areas with file paths
   - Expandable dimension breakdown with findings

---

## API reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | No | Health check |
| `GET` | `/auth/github` | No | Start GitHub OAuth |
| `GET` | `/auth/github/callback` | No | OAuth callback |
| `GET` | `/auth/me` | Yes | Current user profile |
| `POST` | `/auth/logout` | Yes | Clear session |
| `GET` | `/api/repos` | Yes | List user repositories |
| `GET` | `/api/repos/{owner}/{repo}/pulls` | Yes | List open PRs |
| `POST` | `/api/repos/{owner}/{repo}/pulls/{n}/analyze` | Yes | Analyze PR |
| `GET` | `/api/repos/{owner}/{repo}/pulls/{n}/report` | Yes | Get cached report |
| `POST` | `/api/demo/analyze` | No | Analyze fixture PR (demo) |

### Example report response

```json
{
  "riskLevel": "high",
  "riskScore": 59,
  "executiveSummary": "High-risk PR...",
  "focusAreas": [
    { "rank": 1, "area": "src/auth/login.ts", "severity": "high", "reason": "...", "files": ["src/auth/login.ts"] }
  ],
  "dimensions": [
    { "name": "Security", "score": 45, "summary": "...", "findings": [...] }
  ],
  "generatedAt": "2026-09-05T..."
}
```

---

## PR analysis dimensions

### Risk scoring

Dimensions are weighted and combined into a 0–100 score:

| Dimension | Weight |
|-----------|--------|
| Security | 3× |
| Critical Functionality | 3× |
| Test Coverage | 2× |
| Change & Drift | 1.5× |
| Code Volume | 1× |
| Functionality | 1× |

| Score | Risk level |
|-------|------------|
| ≥ 55 | High |
| 25–54 | Medium |
| < 25 | Low |

---

## Demo without GitHub

### CLI

```bash
cd backend && source .venv/bin/activate
python ../scripts/demo-analyze.py
```

### API

```bash
curl -X POST http://localhost:8000/api/demo/analyze
```

Uses `fixtures/demo-pr.json` — a PR titled *"Fix login redirect bug"* that also touches auth, payments, and API routes without test updates.

---

## MCP server (optional)

Exposes CodeLens analyzers as MCP tools for Cursor AI:

```bash
cd backend && source .venv/bin/activate
python mcp_server.py
```

| Tool | Description |
|------|-------------|
| `analyze_pull_request_tool` | Full PR analysis |
| `analyze_diff_volume` | PR size metrics |
| `detect_critical_paths_tool` | Critical path flags |
| `scan_security_patterns` | Secret & unsafe pattern scan |
| `check_test_coverage_gaps` | Missing test detection |
| `detect_scope_drift_tool` | Title vs actual scope |

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "codelens": {
      "command": "python",
      "args": ["backend/mcp_server.py"],
      "cwd": "/path/to/codeLens"
    }
  }
}
```

---

## Scripts

| Script | Description |
|--------|-------------|
| `scripts/dev-backend.sh` | Start FastAPI with hot reload on port 8000 |
| `scripts/demo-analyze.py` | Run analysis on fixture PR from terminal |

---

## License

MIT
