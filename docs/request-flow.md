# CodeLens — Request Flows

Step-by-step documentation for how requests move through CodeLens.

![PR analysis sequence](analyze-flow.svg)

---

## 1. GitHub OAuth login

**Goal:** Authenticate user and store GitHub access token for API calls.

```
User (browser)
  │
  │ 1. Click "Continue with GitHub"
  ▼
Frontend :5173
  │
  │ 2. GET /auth/github  (Vite proxy → backend :8000)
  ▼
backend/app/routers/auth.py :: login_github()
  │
  │ 3. Generate random `state`, set `oauth_state` cookie
  │ 4. Redirect to github.com/login/oauth/authorize
  ▼
GitHub
  │
  │ 5. User approves; GitHub redirects with ?code=&state=
  ▼
GET /auth/github/callback  (must match GITHUB_REDIRECT_URI)
  │
  │ 6. Verify state cookie === query state
  │ 7. POST code → access_token (exchange_code_for_token)
  │ 8. GET /user → profile
  │ 9. Upsert User row in SQLite (stores access_token)
  │ 10. Set `codelens_session` JWT cookie
  │ 11. Redirect to FRONTEND_URL/dashboard
  ▼
Frontend Dashboard
  │
  │ 12. AuthContext calls GET /auth/me (cookie sent)
  ▼
{ id, login, name, avatarUrl }
```

**Failure paths:**

| Error | Redirect |
|-------|----------|
| Invalid/missing state | `/?error=invalid_oauth_state` |
| Token exchange failed | `/?error=token_exchange_failed` |

**Important:** `GITHUB_REDIRECT_URI` must match your OAuth App callback URL (e.g. `http://localhost:5173/auth/github/callback` in dev).

---

## 2. List repositories

```
Frontend Dashboard
  │
  │ GET /api/repos  (cookie: codelens_session)
  ▼
api.py :: list_repos()
  │
  │ get_current_user() → decode JWT → load User
  │ GitHubClient(user.access_token)
  │ GET https://api.github.com/user/repos
  ▼
JSON array → repo cards on Dashboard
```

---

## 3. List open pull requests

```
Frontend RepoDetail  (/repos/{owner}/{repo})
  │
  │ GET /api/repos/{owner}/{repo}/pulls
  ▼
api.py :: list_pulls()
  │
  │ GET https://api.github.com/repos/{owner}/{repo}/pulls?state=open
  ▼
PR rows with "Analyze" links
```

---

## 4. Analyze a PR (manual — web UI)

**Goal:** Fetch PR from GitHub, run analyzers, cache report, optionally sync Checks/comments.

```
Frontend PrReport
  │
  │ POST /api/repos/{owner}/{repo}/pulls/{number}/analyze
  ▼
api.py :: analyze_pr()
  │
  │ GitHubClient(user.access_token)
  ▼
services/analyze_pipeline.py :: run_pr_analysis(source="oauth")
  │
  ├─ 1. gh.get_pull(owner, repo, number)
  ├─ 2. gh.list_pr_files() → FileChange[]
  ├─ 3. enrich_pr_file_patches() → full diffs if truncated
  ├─ 4. fetch_pr_commits_detailed() → per-commit changes
  ├─ 5. fetch_pr_discussion() → reviews + comments
  │
  ▼
analyzers/service.py :: analyze_pull_request()
  │
  ├─ engine.py: volume, drift, functionality, critical, security, tests
  ├─ compute_risk_score() + build_focus_areas()
  ├─ summarize.py: PR overview, file summaries, discussion summary
  └─ ai.py: executive summary (if AI configured)
  │
  ▼
AnalysisReport.to_dict()
  │
  ├─ 6. Upsert pr_reports row (SQLite)
  │
  ├─ 7. [Optional] upsert_check_run() → GitHub Checks API
  │      (if ENABLE_GITHUB_CHECKS + App installed)
  │
  └─ 8. [Optional] post_pr_summary_comment()
         (if ENABLE_GITHUB_PR_COMMENTS + user/post flag)
  │
  ▼
JSON report → Frontend PrReport (5 tabs)
```

### Report tabs consume report fields

| Tab | Report fields |
|-----|---------------|
| Overview | `riskLevel`, `riskScore`, `executiveSummary`, `focusAreas`, `prOverview` |
| Changes | `fileChanges[]` with patches + summaries |
| Commits | `commits[]` with per-commit file changes |
| Discussion | `reviewActivity[]`, `discussionSummary` |
| Risk analysis | `dimensions[]` with findings + evidence |

---

## 5. Get cached report (no re-analyze)

```
Frontend PrReport (on load)
  │
  │ GET /api/repos/{owner}/{repo}/pulls/{number}/report
  ▼
api.py :: get_report()
  │
  │ SELECT pr_reports WHERE owner, repo, pr_number
  ▼
200 → render report
404 → frontend falls back to POST .../analyze
```

---

## 6. Webhook auto-analyze (production)

**Goal:** Analyze PR automatically when opened or updated — no user login required.

```
GitHub (PR opened / synchronize / reopened / ready_for_review)
  │
  │ POST /webhooks/github
  │ Headers: X-GitHub-Event, X-GitHub-Delivery, X-Hub-Signature-256
  ▼
webhooks.py :: github_webhook()
  │
  ├─ 1. verify_github_signature(body, secret)
  ├─ 2. Check webhook_deliveries for duplicate delivery_id → skip
  ├─ 3. Record delivery as pending
  │
  │ event == "pull_request" && action in PR_ANALYZE_ACTIONS
  ▼
  ├─ 4. upsert_installation() from payload
  ├─ 5. sync_repositories()
  ├─ 6. get_installation_access_token(installation_id)
  ├─ 7. GitHubClient(installation_token)
  │
  ▼
run_pr_analysis(source="webhook", installation=..., user_id=None)
  │
  │ (same pipeline as manual analyze — steps 1–8 above)
  │
  ├─ Checks synced if ENABLE_GITHUB_CHECKS
  └─ PR comment if AUTO_POST_PR_COMMENT_ON_WEBHOOK + ENABLE_GITHUB_PR_COMMENTS
  │
  ▼
Mark webhook_deliveries.status = "processed"
```

**Requires:** `GITHUB_WEBHOOK_SECRET`, `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`

---

## 7. GitHub Checks flow

After `run_pr_analysis()` when Checks are enabled:

```
checks.py :: upsert_check_run()
  │
  ├─ Map riskLevel → conclusion (high=failure, medium=neutral, low=success)
  ├─ Build output.title + output.summary from report
  ├─ details_url → /embed/repos/...?token=HMAC (if EMBED_SHARED_SECRET set)
  │
  │ POST /repos/{owner}/{repo}/check-runs  (installation token)
  ▼
GitHub PR "Checks" tab shows CodeLens result
  │
  │ User clicks "Details"
  ▼
EmbedReport.jsx (iframe on github.com if CSP allows)
```

---

## 8. Post PR summary comment (manual)

```
Frontend PrReport → "Post to GitHub"
  │
  │ POST /api/github/repos/{o}/{r}/pulls/{n}/post-summary
  ▼
github_integration.py
  │
  ├─ Load cached pr_reports
  ├─ format_pr_comment(report) → markdown
  ├─ POST issue comment on PR (or update existing)
  └─ Insert pr_review_posts row (dedupe)
  ▼
Comment visible on github.com PR conversation
```

---

## 9. Demo analyze (no GitHub)

```
curl -X POST http://localhost:8000/api/demo/analyze
  │
  ▼
api.py :: demo_analyze()
  │
  ├─ Load fixtures/demo-pr.json
  ├─ analyze_pull_request(title, body, files)  — no GitHub fetch
  └─ Return report JSON (not cached unless you extend it)
```

Or CLI: `python scripts/demo-analyze.py`

---

## 10. AI status check

```
GET /api/ai/status
  │
  ▼
{ configured, provider, model, lastError }

GET /api/ai/test
  │
  ▼
ai_complete("Reply with exactly: CodeLens AI is working.")
  │
  ▼
{ ok, provider, model, sample, lastError }
```

---

## Request path summary

| User action | HTTP | Service chain |
|-------------|------|---------------|
| Login | `GET /auth/github` | auth → GitHub OAuth |
| View repos | `GET /api/repos` | api → github.py |
| View PRs | `GET /api/pulls` | api → github.py |
| Analyze | `POST /api/.../analyze` | api → analyze_pipeline → analyzers |
| View report | `GET /api/.../report` | api → SQLite |
| Auto-analyze | `POST /webhooks/github` | webhooks → analyze_pipeline |
| Post comment | `POST /api/github/.../post-summary` | github_integration → pr_comments |
| Demo | `POST /api/demo/analyze` | api → analyzers (fixture) |

---

## Local dev proxy

Vite (`frontend/vite.config.js`) proxies these paths to `http://localhost:8000`:

- `/auth/*`
- `/api/*`

Cookies are set for `localhost` and work across the proxy because login and callback both go through `:5173` when `GITHUB_REDIRECT_URI` points there.

---

## Related docs

- [architecture.md](architecture.md) — system design
- [implemented.md](implemented.md) — feature checklist
- [PRODUCTION_GITHUB.md](PRODUCTION_GITHUB.md) — webhook + App setup
