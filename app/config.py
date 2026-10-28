"""Settings, read once from the environment (.env is loaded if present)."""
from __future__ import annotations

import os
from datetime import datetime, time
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:  # dotenv is optional
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "data" / "tts_cache"

# ---- Simulation -----------------------------------------------------------
DEMO_START = datetime(2026, 10, 21, 10, 0)          # Wed 21 Oct 2026, 10:00 IST
SETTLEMENT_TIME = time(21, 0)                        # daily settlement + deduction batch
CONTACT_START = time(8, 0)                           # RBI: contact only 08:00-19:00
CONTACT_END = time(19, 0)
REPLY_WINDOW_MIN = 30                                # borrower-initiated: we may answer within 30 min
LENDER_NAME = os.getenv("LENDER_NAME", "Demo NBFC")
GRIEVANCE_OFFICER = os.getenv(
    "GRIEVANCE_OFFICER", "Grievance Officer, Demo NBFC · grievance@demo-nbfc.example · 1800-000-0000"
)

# ---- LLM ------------------------------------------------------------------
# LLM_PROVIDER: sarvam | openai | anthropic | none
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "sarvam" if os.getenv("SARVAM_API_KEY") else "none").lower()
LLM_API_KEY = os.getenv("LLM_API_KEY") or (os.getenv("SARVAM_API_KEY") if LLM_PROVIDER == "sarvam" else "")
LLM_MODEL = os.getenv(
    "LLM_MODEL",
    {"sarvam": "sarvam-105b", "openai": "gpt-4o-mini", "anthropic": "claude-haiku-4-5"}.get(LLM_PROVIDER, ""),
)
LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    {"sarvam": "https://api.sarvam.ai/v1", "openai": "https://api.openai.com/v1",
     "anthropic": "https://api.anthropic.com/v1"}.get(LLM_PROVIDER, ""),
)
# Sarvam-105b thinks for ~1,450 tokens (6-9 s) even on "low", and sometimes runs out before answering.
# "none" switches thinking off: replies in under 1.5 s, and it reads the demo replies correctly.
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "none" if LLM_PROVIDER == "sarvam" else "")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "8"))   # on timeout the rules reader answers instead
LLM_REWRITE = os.getenv("LLM_REWRITE", "0") == "1"   # 1 = LLM may rephrase approved messages (then validated). Off by default for a deterministic stage demo.

# ---- Voice (Sarvam) --------------------------------------------------------
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_BASE = os.getenv("SARVAM_BASE", "https://api.sarvam.ai")
STT_MODEL = os.getenv("STT_MODEL", "saaras:v4")
TTS_MODEL = os.getenv("TTS_MODEL", "bulbul:v3")
TTS_SPEAKER = os.getenv("TTS_SPEAKER", "priya")
TTS_PACE = float(os.getenv("TTS_PACE", "1.0"))
VOICE_TIMEOUT = float(os.getenv("VOICE_TIMEOUT", "20"))

# ---- Offline switch ---------------------------------------------------------
# OFFLINE=1 forces rules + templates + cached audio, even if keys are set.
OFFLINE = os.getenv("OFFLINE", "0") == "1"
RUNTIME = {"offline": OFFLINE}   # can be flipped from the UI during the demo


def llm_configured() -> bool:
    return LLM_PROVIDER != "none" and bool(LLM_API_KEY) and bool(LLM_MODEL)


def llm_enabled() -> bool:
    return not RUNTIME["offline"] and llm_configured()


def voice_enabled() -> bool:
    return not RUNTIME["offline"] and bool(SARVAM_API_KEY)
