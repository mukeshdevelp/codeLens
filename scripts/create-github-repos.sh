#!/usr/bin/env bash
# Create GitHub repos for CodeLens (requires GitHub CLI: https://cli.github.com)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO_ROOT="$(dirname "$ROOT")/codelens-demo"

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is required. Install: https://cli.github.com"
  echo "Then run: gh auth login"
  exit 1
fi

gh auth status >/dev/null 2>&1 || { echo "Run: gh auth login"; exit 1; }

echo "Creating codelens repo..."
cd "$ROOT"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || git init -b main
if ! git remote get-url origin >/dev/null 2>&1; then
  gh repo create codelens --public --source=. --remote=origin --description "CodeLens — understand a PR before reviewing it (MCP + AI)"
  git push -u origin main
else
  echo "codelens already has remote: $(git remote get-url origin)"
fi

echo "Creating codelens-demo repo..."
cd "$DEMO_ROOT"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || git init -b main
if ! git remote get-url origin >/dev/null 2>&1; then
  gh repo create codelens-demo --public --source=. --remote=origin --description "Demo app for CodeLens PR analysis"
  git push -u origin main
  git push -u origin feature/fix-login-redirect 2>/dev/null || true
else
  echo "codelens-demo already has remote: $(git remote get-url origin)"
fi

echo "Done! Repos created on GitHub."
