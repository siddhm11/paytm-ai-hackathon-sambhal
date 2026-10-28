"""Check your API keys before the demo:  python scripts/check_keys.py

1. Sarvam text-to-speech (Kannada)
2. Sarvam speech-to-text, fed the audio from step 1 (a full round trip)
3. The LLM reading Ravi's reply
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from datetime import date  # noqa: E402

from app import config, llm, nlu, voice  # noqa: E402
from app.world import RAVI_REPLY  # noqa: E402

ok = True


def line(name, good, detail):
    global ok
    ok &= good
    print(f"  [{'PASS' if good else 'FAIL'}] {name}: {detail}")


print("Sambhal key check")
print(f"  Sarvam key: {'set' if config.SARVAM_API_KEY else 'MISSING'} · LLM: {config.LLM_PROVIDER} {config.LLM_MODEL or ''}")

audio = None
if config.SARVAM_API_KEY:
    try:
        t = time.time()
        p = voice._cache_path(RAVI_REPLY + " (check)", "kn")
        if p.exists():
            p.unlink()
        audio = voice.tts(RAVI_REPLY + " (check)", "kn")
        line("Sarvam text-to-speech", len(audio) > 1000, f"{len(audio):,} bytes of audio in {time.time() - t:.1f}s")
    except RuntimeError as e:
        line("Sarvam text-to-speech", False, str(e))
    except Exception as e:
        line("Sarvam text-to-speech", False, f"{e} · {voice.STATS['last_error']}")
    if audio:
        try:
            r = voice.stt(audio, "check.wav", "audio/wav", "kn")
            line("Sarvam speech-to-text", bool(r["transcript"]), f"heard '{r['transcript']}' in {r['ms']} ms")
        except Exception as e:
            line("Sarvam speech-to-text", False, f"{e} · {voice.STATS['last_error']}")
else:
    line("Sarvam", False, "set SARVAM_API_KEY in .env (dashboard.sarvam.ai)")

if config.llm_configured():
    try:
        t = time.time()
        r = nlu.read(RAVI_REPLY, "kn", date(2026, 10, 23))
        good = r["source"].startswith("llm") and r["intent"] == "family_event"
        line("LLM understanding", good,
             f"intent={r['intent']} days={r.get('event_days')} source={r['source']} in {time.time() - t:.1f}s"
             + (f" · error: {r.get('llm_error')}" if r.get("llm_error") else ""))
    except Exception as e:
        line("LLM understanding", False, str(e))
else:
    line("LLM", False, "not configured: the demo uses the rules reader (fine offline). Set LLM_PROVIDER + key to enable.")

print("\nAll good. Now run: python scripts/warm_voice_cache.py" if ok else
      "\nSome checks failed. The demo still runs offline (rules + templates); fix keys for live voice and AI.")
sys.exit(0 if ok else 1)
