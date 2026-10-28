"""Sarvam speech-to-text and text-to-speech, with an on-disk audio cache.

Every spoken line is cached by (text, language, speaker). Run
`python scripts/warm_voice_cache.py` once with your key and the whole demo's
audio is on disk: the demo then speaks even with no internet.
"""
from __future__ import annotations

import base64
import hashlib
import json
import time

import httpx

from . import config

LANG_CODES = {"kn": "kn-IN", "hi": "hi-IN", "en": "en-IN"}
STATS = {"stt_calls": 0, "tts_calls": 0, "tts_cache_hits": 0, "last_stt_ms": None, "last_tts_ms": None,
         "last_error": None}


def _cache_path(text: str, lang: str):
    key = hashlib.sha1(json.dumps([text, lang, config.TTS_SPEAKER, config.TTS_MODEL, config.TTS_PACE]).encode()).hexdigest()
    return config.CACHE_DIR / f"{key}.wav"


def cached_tts(text: str, lang: str) -> bytes | None:
    p = _cache_path(text, lang)
    return p.read_bytes() if p.exists() else None


def tts(text: str, lang: str) -> bytes:
    """WAV bytes. Cache first; then Sarvam if a key is set; else raises."""
    hit = cached_tts(text, lang)
    if hit:
        STATS["tts_cache_hits"] += 1
        return hit
    if not config.voice_enabled():
        raise RuntimeError("voice offline and line not cached")
    t0 = time.time()
    STATS["tts_calls"] += 1
    r = httpx.post(
        f"{config.SARVAM_BASE}/text-to-speech",
        headers={"api-subscription-key": config.SARVAM_API_KEY, "Content-Type": "application/json"},
        json={"text": text[:2400], "language_code": LANG_CODES.get(lang, "en-IN"), "model": config.TTS_MODEL,
              "speaker": config.TTS_SPEAKER, "pace": config.TTS_PACE, "speech_sample_rate": 22050},
        timeout=config.VOICE_TIMEOUT,
    )
    if r.status_code >= 400:
        STATS["last_error"] = f"TTS {r.status_code}: {r.text[:200]}"
        r.raise_for_status()
    audio = base64.b64decode(r.json()["audios"][0])
    STATS["last_tts_ms"] = int((time.time() - t0) * 1000)
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(text, lang).write_bytes(audio)
    return audio


def stt(audio: bytes, filename: str, mime: str, lang_hint: str | None = None) -> dict:
    if not config.voice_enabled():
        raise RuntimeError("voice offline")
    t0 = time.time()
    STATS["stt_calls"] += 1
    data = {"model": config.STT_MODEL, "language_code": LANG_CODES.get(lang_hint or "", "unknown")}
    if config.STT_MODEL.startswith("saaras:v4"):
        data["keyterms"] = json.dumps(["Sambhal", "EMI", "installment", "किस्त", "ಕಂತು"])
    r = httpx.post(
        f"{config.SARVAM_BASE}/speech-to-text",
        headers={"api-subscription-key": config.SARVAM_API_KEY},
        data=data, files={"file": (filename, audio, mime or "audio/webm")}, timeout=config.VOICE_TIMEOUT,
    )
    if r.status_code == 400 and "keyterms" in data:   # older accounts/models: retry without keyterms
        data.pop("keyterms")
        r = httpx.post(f"{config.SARVAM_BASE}/speech-to-text",
                       headers={"api-subscription-key": config.SARVAM_API_KEY},
                       data=data, files={"file": (filename, audio, mime or "audio/webm")},
                       timeout=config.VOICE_TIMEOUT)
    if r.status_code >= 400:
        STATS["last_error"] = f"STT {r.status_code}: {r.text[:200]}"
        r.raise_for_status()
    j = r.json()
    STATS["last_stt_ms"] = int((time.time() - t0) * 1000)
    code = (j.get("language_code") or "").split("-")[0]
    return {"transcript": j.get("transcript", ""), "language": code if code in ("kn", "hi", "en") else None,
            "ms": STATS["last_stt_ms"]}
