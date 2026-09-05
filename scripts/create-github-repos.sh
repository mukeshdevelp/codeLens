#!/usr/bin/env bash
# Create GitHub repos for CodeLens + codelens-demo
set -euo pipefail

if ! command -v gh >/dev/null 2>&1; then
  echo "Install GitHub CLI: https://cli.github.com"
  exit 1
fi

gh auth status >/dev/null 2>&1 || { echo "Run: gh auth login"; exit 1; }

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO="$(dirname "$ROOT")/codelens-demo"

echo "==> Creating codelens repo"
cd "$ROOT"
if ! git remote get-url origin >/dev/null 2>&1; then
  gh repo create codelens --public --source=. --remote=origin --description "CodeLens — understand a PR before reviewing it"
  git push -u origin main
else
  echo "Remote exists: $(git remote get-url origin)"
fi

echo "==> Creating codelens-demo repo"
cd "$DEMO"
git init -b main 2>/dev/null || true
git add -A && git commit -m "Initial commit: demo app baseline" 2>/dev/null || true
if ! git remote get-url origin >/dev/null 2>&1; then
  gh repo create codelens-demo --public --source=. --remote=origin --description "Demo app for CodeLens PR analysis"
  git push -u origin main
  git checkout -b feature/fix-login-redirect 2>/dev/null || git checkout feature/fix-login-redirect
  git push -u origin feature/fix-login-redirect 2>/dev/null || true
else
  echo "Remote exists: $(git remote get-url origin)"
fi

echo "Done."
