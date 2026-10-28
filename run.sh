#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env
python -m pytest -q
echo "Open http://localhost:8000"
uvicorn app.main:app --port "${PORT:-8000}"
