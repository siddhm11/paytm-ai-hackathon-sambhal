@echo off
cd /d %~dp0
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -q -r requirements.txt
if not exist .env copy .env.example .env
python -m pytest -q
echo Open http://localhost:8000
uvicorn app.main:app --port 8000
