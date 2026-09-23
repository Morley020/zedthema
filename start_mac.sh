#!/bin/bash

# ============================================================
# ZedThema - macOS Development Launcher
# ============================================================

set -euo pipefail

# ------------------------------------------------------------
# Project root
# ------------------------------------------------------------

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "=========================================="
echo "        ZedThema Development Server"
echo "=========================================="
echo ""
echo "Project: $ROOT"
echo ""

# ------------------------------------------------------------
# Python virtual environment
# ------------------------------------------------------------

VENV="$ROOT/.venv"

if [ ! -d "$VENV" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "$VENV"
fi

# ------------------------------------------------------------
# Activate virtual environment
# ------------------------------------------------------------

source "$VENV/bin/activate"

echo "Python:"
which python
python --version
echo ""

# ------------------------------------------------------------
# Install core backend dependencies
# ------------------------------------------------------------

echo "Checking backend dependencies..."

python -m pip install -r "$ROOT/backend/requirements.txt"

# ------------------------------------------------------------
# Create backend .env
# ------------------------------------------------------------

if [ ! -f "$ROOT/backend/.env" ]; then
    echo "Creating backend/.env..."
    cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"
fi

# ------------------------------------------------------------
# Start FastAPI backend
# ------------------------------------------------------------

echo ""
echo "Starting ZedThema API..."
echo ""

cd "$ROOT/backend"

python -m uvicorn app.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --reload &

API_PID=$!

# ------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------

cleanup() {
    echo ""
    echo "Stopping ZedThema backend..."
    kill "$API_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

# ------------------------------------------------------------
# Start React/Vite frontend
# ------------------------------------------------------------

cd "$ROOT/frontend"

echo ""
echo "Starting ZedThema frontend..."
echo ""

npm install

npm run dev -- --host 127.0.0.1
