# CodeLens

**Understand a pull request before reviewing it.**

CodeLens analyzes GitHub PRs across volume, scope drift, critical paths, security, and test coverage — then surfaces a prioritized brief so reviewers know **where to focus first**.

Built with an **MCP server** (Model Context Protocol) so AI agents in Cursor can call analysis tools directly, plus optional **OpenAI summarization** grounded in structured findings.

## Architecture

```
GitHub PR webhook → API → Analyzers → Risk Scorer → PR Comment + Check Run + Dashboard
                              ↑
                    MCP Server (Cursor / AI agents)
```

| Package | Purpose |
|---------|---------|
| `packages/analyzers` | Core PR analysis (volume, drift, security, tests, critical paths) |
| `packages/mcp-server` | MCP tools exposed to Cursor AI |
| `packages/reporter` | Markdown + check summaries for GitHub |
| `apps/api` | Webhook receiver + REST API |
| `apps/web` | Report dashboard |

## MCP Tools

Register in Cursor via `.cursor/mcp.json`. Available tools:

| Tool | Description |
|------|-------------|
| `analyze_pull_request` | Full analysis with risk score and focus areas |
| `analyze_diff_volume` | PR size metrics |
| `detect_critical_paths` | Auth, payments, permissions, infra flags |
| `scan_security_patterns` | Secrets, eval, SQL injection, XSS patterns |
| `check_test_coverage_gaps` | Source changes without test updates |
| `detect_scope_drift` | Title/body vs actual changed areas |

## Quick Start

```bash
npm install
npm run build
npm run demo:analyze    # Run demo analysis on fixture PR
```

### Run locally

```bash
# Terminal 1 — API
npm run dev:api

# Terminal 2 — Dashboard
npm run dev:web

# Terminal 3 — MCP server (for Cursor)
npm run dev:mcp
```

Open dashboard: http://localhost:3000/report/demo/codelens-demo/1

### Demo analysis (no GitHub needed)

```bash
npm run demo:analyze
```

This analyzes `fixtures/demo-pr.json` — a PR titled "Fix login redirect bug" that secretly touches auth, payments, and API routes without tests.

## GitHub App Setup

1. Create a GitHub App at https://github.com/settings/apps
2. Set webhook URL: `https://your-host/webhooks/github`
3. Permissions: Pull requests (R/W), Contents (R), Checks (W)
4. Subscribe to: `Pull request`
5. Copy App ID + generate private key → `.env`

```bash
cp .env.example .env
# Fill in GITHUB_APP_ID, GITHUB_PRIVATE_KEY, GITHUB_WEBHOOK_SECRET
# Optional: OPENAI_API_KEY for AI summaries
```

Install the app on your repos (including `codelens-demo`).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/webhooks/github` | GitHub PR webhook |
| POST | `/api/analyze` | Analyze PR payload directly |
| GET | `/api/reports/:owner/:repo/:number` | Fetch saved report |

## Demo Repository

See **[codelens-demo](https://github.com)** — a sample app with a demo PR branch showing how CodeLens flags risky changes.

## Problem → Solution

| Before CodeLens | After CodeLens |
|-----------------|----------------|
| "Where do I start?" | Risk level + top 5 focus areas |
| Read entire diff first | Critical paths flagged upfront |
| Miss scope drift | "Fix login" but billing also changed |
| Security issues buried | Secrets & unsafe patterns highlighted |
| Unknown test gaps | Source files without test updates flagged |

## License

MIT
