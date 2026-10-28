"""Listen back to Sambhal's own voice: Sarvam speech-to-text on each spoken line, compared with what it should say.

Found with a Wispr Flow listening test, confirmed with Sarvam: the Kannada voice dropped "fifty" from amounts
(₹850 was spoken as 800) and long Hindi lines were sometimes cut off before the end. This check catches both, so
`warm_voice_cache.py` can regenerate a line until it is spoken right.
"""
from __future__ import annotations

import io
import re
import time
import wave

import httpx

from . import config
from .guardrails import _DIGITS
from .voice import LANG_CODES

WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
ZW = dict.fromkeys(map(ord, "‌‍"))       # zero-width joiners used in Kannada


def _pieces(audio: bytes, seconds: float = 25.0, overlap: float = 1.0) -> list[bytes]:
    """Sarvam's REST speech-to-text takes about 30 s at most: split longer lines, with a little overlap."""
    with wave.open(io.BytesIO(audio)) as w:
        params, rate, frames = w.getparams(), w.getframerate(), w.readframes(w.getnframes())
    step = params.sampwidth * params.nchannels
    n = len(frames) // step
    if n <= rate * (seconds + 3):
        return [audio]
    out, start = [], 0
    while start < n:
        end = min(n, start + int(rate * seconds))
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setparams(params)
            w.writeframes(frames[start * step:end * step])
        out.append(buf.getvalue())
        if end == n:
            break
        start = end - int(rate * overlap)
    return out


def transcribe(audio: bytes, lang: str) -> str:
    return " ".join(_transcribe(p, lang) for p in _pieces(audio))


def _transcribe(audio: bytes, lang: str) -> str:
    for attempt in range(6):                    # Sarvam rate-limits bursts (429): back off and retry
        r = httpx.post(f"{config.SARVAM_BASE}/speech-to-text", timeout=config.VOICE_TIMEOUT,
                       headers={"api-subscription-key": config.SARVAM_API_KEY},
                       data={"model": config.STT_MODEL, "language_code": LANG_CODES.get(lang, "unknown")},
                       files={"file": ("line.wav", audio, "audio/wav")})
        if r.status_code != 429:
            break
        time.sleep(2 ** attempt)
    r.raise_for_status()
    return r.json().get("transcript", "")


def amounts(text: str) -> list[str]:
    """Rupee amounts in a line, as plain digits: '₹2,550' -> '2550'."""
    return [a.replace(",", "") for a in re.findall(r"₹\s?([\d,]+)", text.translate(_DIGITS))]


def heard_numbers(transcript: str) -> set[str]:
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*", transcript.translate(_DIGITS))}


def check(text: str, lang: str, transcript: str) -> list[str]:
    """Problems with how a line was spoken (empty = it sounds right)."""
    problems = []
    heard = heard_numbers(transcript)
    if lang != "hi":            # Hindi recognition often writes amounts as words ('एक सौ साठ'); checked by ear
        missing = [a for a in amounts(text) if a not in heard]
        if missing:
            problems.append(f"amount not heard: ₹{', ₹'.join(missing)} (heard numbers: {', '.join(sorted(heard)) or 'none'})")
    words = [w.translate(ZW) for w in WORD.findall(text)]
    got = {w.translate(ZW) for w in WORD.findall(transcript)}
    tail = [w for w in words[-4:] if len(w) > 2]
    if tail and not any(w in got for w in tail):
        problems.append("the end of the line was not heard (cut off?): …" + " ".join(words[-4:]))
    return problems
