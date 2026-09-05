# Production GitHub Integration

CodeLens supports production deployment with **GitHub App**, **webhooks**, **Checks API**, **PR comments**, and **github.com embeds**.

## Architecture

```
GitHub PR event (push/open)
    → POST /webhooks/github (HMAC verified)
    → run_pr_analysis (installation token)
    → SQLite/Postgres (pr_reports, pr_check_runs, webhook_deliveries)
    → GitHub Checks API (risk on PR checks tab)
    → Optional PR issue comment
    → details_url → /embed/...?token=HMAC (iframe on github.com)
```

## Database schema (new tables)

| Table | Purpose |
|-------|---------|
| `github_installations` | GitHub App install per org/user |
| `registered_repositories` | Repos in scope for auto-analysis |
| `webhook_deliveries` | Idempotency + audit log |
| `pr_check_runs` | Check Run IDs linked to reports |
| `pr_review_posts` | Posted PR comments (no duplicates) |

`pr_reports` extended: `installation_id`, `head_sha`, `source` (`oauth` \| `webhook`).

## 1. Create a GitHub App

1. GitHub → **Settings → Developer settings → GitHub Apps → New**
2. **Webhook URL:** `https://your-api.example.com/webhooks/github`
3. **Webhook secret:** generate and set `GITHUB_WEBHOOK_SECRET`
4. **Permissions:**
   - Contents: Read
   - Pull requests: Read & write (for comments)
   - Checks: Read & write
   - Metadata: Read
5. **Subscribe to events:** `Pull request`, `Installation`, `Installation repositories`
6. Generate a **private key** → save as file or PEM in env

## 2. Environment variables

```bash
# Webhook (required for auto-analyze)
GITHUB_WEBHOOK_SECRET=your-webhook-secret

# GitHub App (required for Checks + webhook API calls)
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY_PATH=/secrets/github-app.pem
# or GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n..."
GITHUB_APP_SLUG=codelens

# Feature flags
ENABLE_GITHUB_CHECKS=true
ENABLE_GITHUB_PR_COMMENTS=true
AUTO_POST_PR_COMMENT_ON_WEBHOOK=false

# Embed (Check details_url + github.com iframe)
EMBED_SHARED_SECRET=long-random-secret
EMBED_ALLOWED_FRAME_ANCESTORS=https://github.com

# Public URLs (production)
FRONTEND_URL=https://app.codelens.example
BACKEND_URL=https://api.codelens.example
```

## 3. Install the app

Users install via: `https://github.com/apps/{GITHUB_APP_SLUG}/installations/new`

Or use **GET /api/github/status** → `installUrl`.

## 4. API endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/webhooks/github` | HMAC signature | Auto-analyze on PR events |
| GET | `/api/github/status` | None | Integration health |
| POST | `/api/github/repos/{o}/{r}/pulls/{n}/post-summary` | OAuth | Post PR comment |
| GET | `/api/github/embed/{o}/{r}/pulls/{n}/report?token=` | HMAC token | Embed report JSON |
| POST | `/api/repos/.../analyze?sync_github_check=true` | OAuth | Analyze + Check Run |

## 5. Embed on github.com

Check Run `details_url` points to:

```
https://app.example.com/embed/repos/{owner}/{repo}/pulls/{n}?token={hmac}&from=github
```

Token = `HMAC-SHA256(EMBED_SHARED_SECRET, "{owner}/{repo}/{n}")`.

CSP `frame-ancestors` is set on embed API responses for `github.com`.

## 6. Production checklist

- [ ] Use PostgreSQL (`DATABASE_URL=postgresql+asyncpg://...`) instead of SQLite
- [ ] Set strong `SESSION_SECRET` and `EMBED_SHARED_SECRET`
- [ ] HTTPS on frontend + backend (GitHub requires HTTPS webhooks)
- [ ] Store `GITHUB_APP_PRIVATE_KEY` in a secret manager (not git)
- [ ] Configure GitHub App webhook delivery retries monitoring via `webhook_deliveries` table
- [ ] Set `ENABLE_GITHUB_PR_COMMENTS=true` only when ready for visible PR comments
- [ ] Consider Alembic migrations for schema changes beyond SQLite dev helper

## 7. Local testing webhooks

Use [smee.io](https://smee.io) or `gh webhook forward`:

```bash
smee -u https://smee.io/your-channel -t http://localhost:8000/webhooks/github
```

Point GitHub App webhook URL to the smee URL.
