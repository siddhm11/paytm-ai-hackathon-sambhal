"""Pre-generate Sarvam audio for every message the stage demo can produce.

Run once with SARVAM_API_KEY set:  python scripts/warm_voice_cache.py
Afterwards the demo speaks Kannada/Hindi even with no internet (audio is in data/tts_cache/).
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from app import config, presenter, replies, voice  # noqa: E402
from app.world import World  # noqa: E402

TRY_LINES = ["Business is slow because of the rain", "Can you waive the interest?", "ನಮ್ಮ ಅಮ್ಮ ನಿನ್ನೆ ತೀರಿಕೊಂಡರು",
             "ಸರಿ, ಒಪ್ಪುತ್ತೇನೆ"]


def outbound(w: World):
    for c in w.cases.values():
        for m in c.messages:
            if m.dir == "out":
                yield f"{replies.header(m.lang)}. {m.text}", m.lang


def collect():
    lines = {}
    w = World(use_llm=False)
    presenter.go_to(w, 8)
    lines.update({t: l for t, l in outbound(w)})
    for text in TRY_LINES:                    # what the quick-reply chips can trigger on stage
        w = World(use_llm=False)
        presenter.go_to(w, 3)
        w.inbound("M01", text)
        c = w.case_for("M01")
        if c.state == "offered":
            w.accept("M01", c.offered[0])
        lines.update({t: l for t, l in outbound(w)})
    return lines


if __name__ == "__main__":
    if not config.SARVAM_API_KEY:
        sys.exit("Set SARVAM_API_KEY in .env first.")
    config.RUNTIME["offline"] = False
    todo = collect()
    print(f"{len(todo)} lines to cache")
    done = 0
    for text, lang in todo.items():
        if voice.cached_tts(text, lang):
            done += 1
            continue
        t = time.time()
        try:
            voice.tts(text, lang)
            done += 1
            print(f"  ok  {lang} {time.time() - t:.1f}s  {text[:60]}")
        except Exception as e:
            print(f"  ERR {lang} {e} {voice.STATS['last_error']}")
    print(f"Cached {done}/{len(todo)} in {config.CACHE_DIR}")
