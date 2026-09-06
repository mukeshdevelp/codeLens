# CodeLens — Canva presentation guide

Copy each section into a Canva slide. Use a **dark tech** or **startup pitch deck** template and customize colors below.

---

## Brand colors (paste into Canva color picker)

| Role | Hex |
|------|-----|
| Background | `#0B1020` |
| Card / surface | `#121A2F` |
| Primary accent | `#5B8CFF` |
| Secondary accent | `#7C5CFF` |
| Text | `#EEF2FF` |
| Muted text | `#9AA8C7` |
| Low risk (green) | `#06D6A0` |
| Medium risk (yellow) | `#FFD166` |
| High risk (red) | `#FF6B6B` |

**Fonts:** Canva → Inter, Poppins, or Space Grotesk (headings bold, body regular).

---

## Option A — Import the PowerPoint (fastest)

1. Open [Canva](https://www.canva.com) → **Create a design** → **Import file**
2. Upload `docs/CodeLens-Presentation.pptx`
3. Canva converts slides — tweak fonts, spacing, and add screenshots
4. Export as PDF or present from Canva

> Import quality varies. For a polished hackathon deck, use Option B with a Canva template.

---

## Option B — Build slide by slide (recommended)

### Slide 1 — Title
**Badge:** PR Review Intelligence  
**Title:** CodeLens  
**Subtitle:** Understand a pull request before reviewing it.  
**Footer:** GitHub · Risk analysis · AI summaries · Human review stays in control

---

### Slide 2 — The problem
**Title:** The problem  
**Subtitle:** From “Where do I start?” to focused, explainable review

- Large PRs hide scope, risk, and impact across diffs, commits, and comments.
- Reviewers spend time reconstructing context before useful feedback.
- Critical paths (auth, payments, security) are easy to miss.
- Teams need orientation — not hundreds of generic bot comments.

---

### Slide 3 — The answer
**Title:** The CodeLens answer  
**Subtitle:** What changed · How risky · Where to look

- Connect GitHub → pick a repo → analyze any open PR.
- Structured brief: risk score, executive summary, focus areas.
- File-by-file and commit-by-commit walkthrough with diffs + AI.
- Human review stays final — you decide approve & merge.

---

### Slide 4 — User journey
**Title:** User journey  
**Subtitle:** End-to-end flow in the dashboard

| Step | Title | Body |
|------|-------|------|
| 1 | Sign in | GitHub OAuth — repo access |
| 2 | Select repo | Dashboard lists repositories |
| 3 | Open PR | View open pull requests |
| 4 | Analyze | One click — rules + optional AI |
| 5 | Review | Overview · Changes · Commits · Discussion · Risk |
| 6 | Act | Approve or merge on GitHub (with confirmation) |

*Layout tip: 6 cards in a 2×3 grid on Canva.*

---

### Slide 5 — PR report tabs
**Title:** PR report — five lenses  
**Subtitle:** One page, multiple ways to orient

- **Overview** — Summary, executive brief, ranked focus areas
- **Changes** — File walkthrough + full diffs + AI per-file notes
- **Commits** — Timeline with per-commit patches
- **Discussion** — Summarized review comments
- **Risk analysis** — Weighted dimensions + evidence

*Add a screenshot of `PrReport.jsx` if you have one.*

---

### Slide 6 — Analysis engine
**Title:** Analysis engine  
**Subtitle:** Risk score 0–100 → High / Medium / Low

| Dimension | What it checks |
|-----------|----------------|
| Change & drift | Scope vs PR title; multi-module clusters |
| Code volume | Lines changed; oversized files |
| Functionality | Coherent change vs scattered edits |
| Critical paths | Auth, payments, permissions, data, infra |
| Security | Secrets, eval, SQL, XSS, TLS issues |
| Test coverage | Source changed without test files |

---

### Slide 7 — AI layer
**Title:** AI layer (optional)  
**Subtitle:** Explainable signals first; AI augments

- Groq, OpenAI, Perplexity, OpenRouter
- Executive summary, PR overview, discussion + per-file notes
- Badges: **AI · groq** vs **Rules**
- Falls back to rules when AI is off
- MCP server for Cursor IDE integration

---

### Slide 8 — GitHub integration
**Title:** GitHub integration

- **OAuth** — login, repos, PRs, approve & merge
- **GitHub App** — webhooks auto-analyze on PR events
- **Checks API** — risk on PR Checks tab
- **PR comments** — post summary to conversation
- **Embed** — signed URLs for github.com / Check details

---

### Slide 9 — Architecture
**Title:** Architecture  
**Subtitle:** FastAPI + React + SQLite · Docker & Kubernetes

```
[React/Vite]  →  [FastAPI API]  →  [GitHub REST]
                      ↓
              [Rule engine + Groq AI]
                      ↓
              [SQLite / cached reports]
```

- Frontend: dashboard, PR report, embed route  
- Backend: OAuth, analyze, webhooks, merge  
- Deploy: `docker-compose.yml` + `deploy/kubernetes/`

---

### Slide 10 — Live demo
**Title:** Live demo checklist

1. Login with GitHub → Dashboard → pick repo  
2. Open PR → analyze  
3. Overview: risk banner + focus areas  
4. Changes: expand file diff + AI badge  
5. Risk tab: findings with file evidence  
6. Merge into main (confirm modal)  
7. No GitHub? `/api/demo/analyze` fixture  

**URLs:** `localhost:5173` (dev) · `localhost:8080` (Docker)

---

### Slide 11 — Why CodeLens?
**Title:** Why CodeLens?

- Focused brief — top areas, not noise  
- Explainable — findings tie to files & evidence  
- Transparent AI — source badges  
- Full story — files + commits + discussion  
- Production path — webhooks, Checks, Docker/K8s  

---

### Slide 12 — Roadmap
**Title:** Roadmap & gaps

- Code quality analyzer (PRD gap)  
- Org-level risk dashboards  
- PostgreSQL for scale  
- Deeper repo context  
- GitHub Marketplace listing  

---

### Slide 13 — Thank you
**Title:** Thank you  
**Subtitle:** Questions?  
**Footer:** CodeLens — Understand before you review

---

## Canva template search terms

- "Dark tech pitch deck"
- "SaaS product presentation"
- "Developer tools startup"
- "Minimal dark presentation"

## Assets to add in Canva

- Screenshot: Login page  
- Screenshot: PR report Overview tab  
- Screenshot: Changes / diff walkthrough  
- Screenshot: Risk analysis tab  
- GitHub logo (Canva elements)  
- Simple flow diagram (Canva → Diagram)

## Export

- **Present:** Canva → Present full screen  
- **Share:** Download → PDF (for judges) or PPTX (backup)
