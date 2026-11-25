#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo "  CloudBox (Mini Dropbox) - Demo Launcher "
echo "=========================================="

cd "$ROOT_DIR/backend"
./.venv/bin/python manage.py migrate --noinput
./.venv/bin/python manage.py seed_demo

echo ""
echo "Starting Django API on http://127.0.0.1:8000 ..."
./.venv/bin/python manage.py runserver 127.0.0.1:8000 &
BACKEND_PID=$!

cleanup() {
  echo ""
  echo "Shutting down CloudBox demo servers..."
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting React frontend on http://localhost:5173 ..."
echo "Demo Accounts: saar (Admin) / rohan (User) — Password: demo1234"
echo ""
cd "$ROOT_DIR/frontend"
npm run dev
