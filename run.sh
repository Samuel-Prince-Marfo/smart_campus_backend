#!/usr/bin/env bash
# Convenience launcher for the Smart Campus backend.
# Creates a virtualenv (if missing), installs deps, and starts the server.
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt

echo "Starting Smart Campus API on http://localhost:8000  (docs at /docs)"
exec uvicorn app.main:app --reload --port 8000
