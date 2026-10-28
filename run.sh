#!/usr/bin/env bash
# One step: make a Python 3.10+ environment, install, test, start.
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  if command -v uv >/dev/null 2>&1; then uv venv -q --python 3.12 .venv; else python3 -m venv .venv; fi
fi
source .venv/bin/activate
if command -v uv >/dev/null 2>&1; then uv pip install -q -r requirements.txt; else pip install -q -r requirements.txt; fi
[ -f .env ] || cp .env.example .env
python -m pytest -q
echo "Open http://localhost:${PORT:-8000}"
uvicorn app.main:app --port "${PORT:-8000}"
