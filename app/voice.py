"""Sarvam speech-to-text and text-to-speech, with an on-disk audio cache.

Every spoken line is cached by (text, language, speaker). Run
`python scripts/warm_voice_cache.py` once with your key and the whole demo's
audio is on disk: the demo then speaks even with no internet.

What the voice is given is not always what the screen shows (`speech_text`). A Wispr Flow listening test, then
Sarvam's own speech-to-text, showed the Kannada voice dropping "fifty" from amounts (₹850 spoken as 800, ₹2,550
as 2,500) and reading ₹ as the English "rupees"; amounts in Kannada words came back exactly. Long lines were
sometimes cut off before the end, so they are spoken one sentence at a time and joined.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import time
import wave
from concurrent.futures import ThreadPoolExecutor

import httpx

from . import config

LANG_CODES = {"kn": "kn-IN", "hi": "hi-IN", "en": "en-IN"}
STATS = {"stt_calls": 0, "tts_calls": 0, "tts_cache_hits": 0, "last_stt_ms": None, "last_tts_ms": None,
         "last_error": None}


# ---------------------------------------------------------------- what the voice says
KN_UNITS = ["ಸೊನ್ನೆ", "ಒಂದು", "ಎರಡು", "ಮೂರು", "ನಾಲ್ಕು", "ಐದು", "ಆರು", "ಏಳು", "ಎಂಟು", "ಒಂಬತ್ತು"]
KN_TEENS = ["ಹತ್ತು", "ಹನ್ನೊಂದು", "ಹನ್ನೆರಡು", "ಹದಿಮೂರು", "ಹದಿನಾಲ್ಕು", "ಹದಿನೈದು", "ಹದಿನಾರು", "ಹದಿನೇಳು", "ಹದಿನೆಂಟು",
            "ಹತ್ತೊಂಬತ್ತು"]
KN_TENS = {2: "ಇಪ್ಪತ್ತು", 3: "ಮೂವತ್ತು", 4: "ನಲವತ್ತು", 5: "ಐವತ್ತು", 6: "ಅರವತ್ತು", 7: "ಎಪ್ಪತ್ತು", 8: "ಎಂಬತ್ತು",
           9: "ತೊಂಬತ್ತು"}
KN_HUNDREDS = {1: "ನೂರು", 2: "ಇನ್ನೂರು", 3: "ಮುನ್ನೂರು", 4: "ನಾನೂರು", 5: "ಐನೂರು", 6: "ಆರುನೂರು", 7: "ಏಳುನೂರು",
               8: "ಎಂಟುನೂರು", 9: "ಒಂಬೈನೂರು"}
KN_JOIN = {"ಒ": "ೊ", "ಎ": "ೆ", "ಐ": "ೈ", "ಆ": "ಾ", "ಏ": "ೇ"}    # ಇಪ್ಪತ್ತು + ಒಂದು -> ಇಪ್ಪತ್ತೊಂದು


def _kn_99(n: int) -> str:
    if n < 10:
        return KN_UNITS[n]
    if n < 20:
        return KN_TEENS[n - 10]
    tens, unit = divmod(n, 10)
    if not unit:
        return KN_TENS[tens]
    stem, word = KN_TENS[tens][:-1], KN_UNITS[unit]      # drop the final ು: ಇಪ್ಪತ್ತು -> ಇಪ್ಪತ್ತ
    return stem + KN_JOIN[word[0]] + word[1:] if word[0] in KN_JOIN else stem + word


def kn_number(n: int) -> str:
    """850 -> 'ಎಂಟುನೂರ ಐವತ್ತು', 2550 -> 'ಎರಡು ಸಾವಿರದ ಐನೂರ ಐವತ್ತು', 136000 -> 'ಒಂದು ಲಕ್ಷದ ಮೂವತ್ತಾರು ಸಾವಿರ'."""
    if n == 0:
        return KN_UNITS[0]
    lakh, rest = divmod(n, 100000)
    thousand, rest = divmod(rest, 1000)
    hundred, rest = divmod(rest, 100)
    parts = []
    if lakh:
        parts.append(f"{kn_number(lakh) if lakh >= 100 else _kn_99(lakh)} ಲಕ್ಷ")
    if thousand:
        parts.append(f"{_kn_99(thousand)} ಸಾವಿರ")
    if hundred:
        parts.append(KN_HUNDREDS[hundred])
    if rest:
        parts.append(_kn_99(rest))
    for i in range(len(parts) - 1):                     # every part but the last joins on to what follows
        p = parts[i]
        parts[i] = p + "ದ" if p.endswith(("ಲಕ್ಷ", "ಸಾವಿರ")) else p[:-1]     # ಸಾವಿರದ, ಲಕ್ಷದ, ಎಂಟುನೂರ
    return " ".join(parts)


# Case endings written apart from a digit ("8 ರಿಂದ", "26 ವರೆಗೆ") and the joined form they take when spoken.
KN_SUFFIX = {"ರಿಂದ": "ರಿಂದ", "ರವರೆಗೆ": "ರವರೆಗೆ", "ವರೆಗೆ": "ರವರೆಗೆ", "ರಂದು": "ರಂದು", "ರ": "ರ"}


def _kn_amount(m) -> str:
    return f"{kn_number(int(m.group(1).replace(',', '')))} ರೂಪಾಯಿ"


def _kn_with_suffix(m) -> str:
    """'25 ರವರೆಗೆ' -> 'ಇಪ್ಪತ್ತೈದರವರೆಗೆ', '7 ರ' -> 'ಏಳರ': the ending joins the number, as it is spoken."""
    word, suffix = kn_number(int(m.group(1).replace(",", ""))), m.group(2)
    return word[:-1] + KN_SUFFIX[suffix] if word.endswith("ು") else f"{word} {suffix}"


def speech_text(text: str, lang: str) -> str:
    """The words the voice is given. The screen keeps showing the original text.

    Heard in a Wispr Flow listening test: "ಅಕ್ಟೋಬರ್ 23–25" came across as "23 and 25" (the dash is silent, so
    Saturday sounds deducted); "ಸಂಭಾಲ್ · ಈ" ran together into "ಸಂಭಾಷಣಾ"; "+" was read as the English "plus".
    """
    text = text.replace(" · ", ". ")                    # a real pause after the name
    if lang == "kn":
        text = re.sub(r"\s?–\s?(.{1,25}?)\sರಂದು", r" ರಿಂದ \1 ರವರೆಗೆ", text)    # 23–25 ರಂದು -> 23 ರಿಂದ 25 ರವರೆಗೆ
        text = re.sub(r"\s?–\s?", " ರಿಂದ ", text).replace(" + ", " ಮತ್ತು ")
        text = re.sub(r"₹\s?(\d[\d,]*)", _kn_amount, text)
        text = re.sub(r"(\d[\d,]*) (" + "|".join(sorted(KN_SUFFIX, key=len, reverse=True)) + r")(?![\u0C80-\u0CFF])",
                      _kn_with_suffix, text)
        text = re.sub(r"\d[\d,]*", lambda m: kn_number(int(m.group(0).replace(",", ""))), text)
    elif lang == "hi":
        text = re.sub(r"\s?–\s?", " से ", text).replace(" + ", " और ")             # 23–25 अक्टूबर -> 23 से 25 अक्टूबर
    else:
        text = re.sub(r"\s?–\s?", " to ", text)
        text = text.replace("Sambhal", "Sambhaal")      # said "Sambal" ("Symbol" to Wispr); the name means संभाल
    return text


def sentences(text: str, limit: int = 140) -> list[str]:
    """Short pieces, so a long line can't be cut off before its end."""
    out, cur = [], ""
    for s in re.split(r"(?<=[.!?।])\s+", text.strip()):
        if cur and len(cur) + 1 + len(s) > limit:
            out.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    return out + [cur] if cur else out


def join_wavs(parts: list[bytes], gap: float = 0.12) -> bytes:
    """One WAV from several with the same format, with a short pause between them."""
    frames, params = [], None
    for p in parts:
        with wave.open(io.BytesIO(p)) as w:
            params = params or w.getparams()
            frames.append(w.readframes(w.getnframes()))
    silence = b"\x00" * int(params.framerate * gap) * params.sampwidth * params.nchannels
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setparams(params)
        w.writeframes(silence.join(frames))
    return buf.getvalue()


def _sarvam_error(r, what: str):
    STATS["last_error"] = f"{what} {r.status_code}: {r.text[:200]}"
    if r.status_code == 402:        # out of credits: switch voice and the Sarvam LLM off for this run, don't fail on stage
        config.RUNTIME["sarvam_out"] = True
        raise RuntimeError("Sarvam: no credits left (voice and AI switched to cached audio, browser speech and rules)")
    r.raise_for_status()


def _cache_path(text: str, lang: str):
    key = hashlib.sha1(json.dumps([text, lang, config.TTS_SPEAKER, config.TTS_MODEL, config.TTS_PACE]).encode()).hexdigest()
    return config.CACHE_DIR / f"{key}.wav"


def cached_tts(text: str, lang: str) -> bytes | None:
    p = _cache_path(text, lang)
    return p.read_bytes() if p.exists() else None


def _speak(piece: str, lang: str) -> bytes:
    for attempt in range(5):                    # Sarvam rate-limits bursts (429): back off and retry
        r = httpx.post(
            f"{config.SARVAM_BASE}/text-to-speech",
            headers={"api-subscription-key": config.SARVAM_API_KEY, "Content-Type": "application/json"},
            json={"text": piece[:2400], "language_code": LANG_CODES.get(lang, "en-IN"), "model": config.TTS_MODEL,
                  "speaker": config.TTS_SPEAKER, "pace": config.TTS_PACE, "speech_sample_rate": 22050},
            timeout=config.VOICE_TIMEOUT,
        )
        if r.status_code != 429:
            break
        time.sleep(2 ** attempt)
    if r.status_code >= 400:
        _sarvam_error(r, "TTS")
    return base64.b64decode(r.json()["audios"][0])


def tts(text: str, lang: str, fresh: bool = False) -> bytes:
    """WAV bytes. Cache first (unless fresh); then Sarvam if a key is set; else raises."""
    hit = None if fresh else cached_tts(text, lang)
    if hit:
        STATS["tts_cache_hits"] += 1
        return hit
    if not config.voice_enabled():
        raise RuntimeError("voice offline and line not cached")
    t0 = time.time()
    STATS["tts_calls"] += 1
    pieces = sentences(speech_text(text, lang))
    with ThreadPoolExecutor(max_workers=3) as ex:
        audio = join_wavs(list(ex.map(lambda p: _speak(p, lang), pieces)))
    STATS["last_tts_ms"] = int((time.time() - t0) * 1000)
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(text, lang).write_bytes(audio)
    return audio


def stt(audio: bytes, filename: str, mime: str, lang_hint: str | None = None) -> dict:
    if not config.voice_enabled():
        raise RuntimeError("voice offline")
    t0 = time.time()
    STATS["stt_calls"] += 1
    # Browsers label recordings "audio/webm;codecs=opus"; Sarvam accepts "audio/webm" but rejects the codec suffix
    # (found in an end-to-end mic test: every browser recording got 400 Bad Request).
    mime = (mime or "audio/webm").split(";")[0].strip()
    # No 'keyterms' hint list: given silence or noise, Sarvam returned a hint word ("ಕಂತು") as the transcript, and
    # the agent acted on it. Without hints, silence comes back empty and the app asks the merchant to try again.
    data = {"model": config.STT_MODEL, "language_code": LANG_CODES.get(lang_hint or "", "unknown")}
    r = httpx.post(
        f"{config.SARVAM_BASE}/speech-to-text",
        headers={"api-subscription-key": config.SARVAM_API_KEY},
        data=data, files={"file": (filename, audio, mime)}, timeout=config.VOICE_TIMEOUT,
    )
    if r.status_code >= 400:
        _sarvam_error(r, "STT")
    j = r.json()
    STATS["last_stt_ms"] = int((time.time() - t0) * 1000)
    code = (j.get("language_code") or "").split("-")[0]
    return {"transcript": j.get("transcript", ""), "language": code if code in ("kn", "hi", "en") else None,
            "ms": STATS["last_stt_ms"]}
