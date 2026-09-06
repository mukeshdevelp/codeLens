#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Building backend image..."
docker build -t codelens-backend:latest ./backend

echo "Building frontend image..."
docker build -t codelens-frontend:latest ./frontend

echo "Done."
echo "  Docker Compose:  docker compose up"
echo "  Kubernetes:      kubectl apply -k deploy/kubernetes  (after creating secret.yaml)"
