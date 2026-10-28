"""Sambhal demo server. Run: uvicorn app.main:app --port 8000"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, evals, llm, presenter, replay, replies, sizer, voice
from .data import money
from .world import World

app = FastAPI(title="Sambhal", version="1.0")
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")

W = World()
LOCK = threading.RLock()
FOCUS = "M01"


def status() -> dict:
    return {
        "offline": config.RUNTIME["offline"],
        "llm": {"configured": config.llm_configured(), "on": config.llm_enabled(), "provider": config.LLM_PROVIDER,
                "model": config.LLM_MODEL, "rewrite": config.LLM_REWRITE, **llm.STATS},
        "voice": {"configured": bool(config.SARVAM_API_KEY), "on": config.voice_enabled(), "stt": config.STT_MODEL,
                  "tts": config.TTS_MODEL, "speaker": config.TTS_SPEAKER, **voice.STATS},
        "lender": config.LENDER_NAME,
    }


def case_summary(c) -> dict:
    m = W.merchants[c.merchant_id]
    last = c.messages[-1] if c.messages else None
    held = next((x for x in c.messages if x.status == "held"), None)
    return {
        "id": c.id, "merchant_id": c.merchant_id, "merchant": m.owner, "shop": m.shop, "lang": m.lang,
        "state": c.state, "reason": c.reason, "human": c.human, "human_reason": c.human_reason,
        "trigger": (c.trigger or {}).get("reason"), "level": (c.trigger or {}).get("level"),
        "opened_at": c.opened_at.isoformat(), "last": last.text_en if last else None,
        "last_at": (last.sent_at or last.at).isoformat() if last else None,
        "held_until": held.held_until.isoformat() if held and held.held_until else None,
        "accepted": c.accepted, "demo": c.merchant_id == "M01",
    }


def snapshot(focus: Optional[str] = None) -> dict:
    focus = focus or FOCUS
    cases = sorted(W.cases.values(), key=lambda c: (c.merchant_id != "M01", c.opened_at))
    states = {}
    for c in cases:
        states[c.state] = states.get(c.state, 0) + 1
    return {
        "now": W.now.isoformat(), "step": W.step, "steps": presenter.view(), "status": status(),
        "focus": focus, "merchant": W.merchant_view(focus), "cases": [case_summary(c) for c in cases],
        "counts": {"merchants": len(W.merchants), "cases": len(cases), "by_state": states,
                   "with_person": sum(1 for c in cases if c.human), "held": len(W.outbox)},
        "audit_count": len(W.audit_log), "quick": replies.QUICK_REPLIES, "promises": replies.PROMISES,
    }


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/state")
def state(focus: Optional[str] = None):
    with LOCK:
        return snapshot(focus)


class StepIn(BaseModel):
    n: int


@app.post("/api/step")
def step(body: StepIn):
    with LOCK:
        presenter.go_to(W, body.n)
        return snapshot("M01")


class AdvanceIn(BaseModel):
    to: Optional[str] = None
    hours: Optional[float] = None
    next_event: bool = False


@app.post("/api/advance")
def advance(body: AdvanceIn):
    with LOCK:
        if body.next_event:
            target = W.next_event_time()
        elif body.to:
            target = datetime.fromisoformat(body.to)
        else:
            target = W.now + timedelta(hours=body.hours or 1)
        if target > datetime(2026, 11, 29):
            raise HTTPException(400, "The synthetic data ends on 29 Nov 2026")
        W.advance(target)
        return snapshot()


@app.post("/api/reset")
def reset():
    with LOCK:
        W.reset()
        return snapshot("M01")


class InboundIn(BaseModel):
    merchant_id: str = "M01"
    text: str
    via: str = "text"


@app.post("/api/inbound")
def inbound(body: InboundIn):
    if not body.text.strip():
        raise HTTPException(400, "Empty message")
    with LOCK:
        if body.merchant_id not in W.merchants:
            raise HTTPException(404, "Unknown merchant")
        res = W.inbound(body.merchant_id, body.text.strip(), via=body.via)
        return {"result": res, **snapshot(body.merchant_id)}


class AcceptIn(BaseModel):
    merchant_id: str = "M01"
    option_id: str


@app.post("/api/accept")
def accept(body: AcceptIn):
    with LOCK:
        res = W.accept(body.merchant_id, body.option_id)
        return {"result": res, **snapshot(body.merchant_id)}


class ConsentIn(BaseModel):
    merchant_id: str = "M01"
    on: bool


@app.post("/api/consent")
def consent(body: ConsentIn):
    with LOCK:
        if body.merchant_id not in W.merchants:
            raise HTTPException(404, "Unknown merchant")
        res = W.set_consent(body.merchant_id, body.on)
        return {"result": res, **snapshot(body.merchant_id)}


class CushionIn(BaseModel):
    merchant_id: str = "M01"
    on: bool


@app.post("/api/cushion")
def cushion(body: CushionIn):
    with LOCK:
        if body.merchant_id not in W.merchants:
            raise HTTPException(404, "Unknown merchant")
        res = W.set_cushion(body.merchant_id, body.on)
        return {"result": res, **snapshot(body.merchant_id)}


@app.get("/api/merchant/{mid}")
def merchant(mid: str):
    with LOCK:
        if mid not in W.merchants:
            raise HTTPException(404, "Unknown merchant")
        return W.merchant_view(mid)


@app.get("/api/week/{mid}")
def week(mid: str):
    with LOCK:
        wk = W.week(mid)
        loan = W.loans[mid]
        wk["installment"] = loan.installment
        return wk


@app.get("/api/audit")
def audit(merchant: Optional[str] = None, limit: int = 300):
    with LOCK:
        rows = [a for a in W.audit_log if not merchant or a["merchant_id"] == merchant]
        return {"rows": rows[-limit:][::-1], "total": len(rows)}


@app.get("/api/evals")
def run_evals():
    return evals.run_all()


@app.get("/api/replay")
def run_replay():
    return replay.run()


class SizerIn(BaseModel):
    merchant_id: str = "M01"
    amount: int
    tenure_days: int = 180


@app.post("/api/sizer")
def size(body: SizerIn):
    if not 10000 <= body.amount <= 1000000 or body.tenure_days not in (90, 180, 270, 365):
        raise HTTPException(400, "Amount must be ₹10,000-₹10,00,000; tenure 90, 180, 270 or 365 days")
    with LOCK:
        m = W.merchants[body.merchant_id]
        return sizer.size(W.sales[body.merchant_id], datetime(2026, 10, 21).date(), body.amount, body.tenure_days,
                          m.lang)


class TtsIn(BaseModel):
    text: str
    lang: str = "kn"


@app.post("/api/tts")
def tts(body: TtsIn):
    try:
        audio = voice.tts(body.text, body.lang)
        return Response(audio, media_type="audio/wav")
    except Exception as e:
        return JSONResponse({"error": str(e)[:200], "fallback": "browser"}, status_code=503)


@app.post("/api/stt")
async def stt(file: UploadFile = File(...), lang: str = Form("")):
    audio = await file.read()
    if len(audio) < 800:
        raise HTTPException(400, "Recording too short")
    try:
        return voice.stt(audio, file.filename or "voice.webm", file.content_type or "audio/webm", lang or None)
    except Exception as e:
        return JSONResponse({"error": str(e)[:200], "fallback": "type"}, status_code=503)


class OfflineIn(BaseModel):
    on: bool


@app.post("/api/offline")
def offline(body: OfflineIn):
    config.RUNTIME["offline"] = body.on
    return status()


@app.get("/api/health")
def health():
    return {"ok": True, **status(), "money_check": money(136000)}
