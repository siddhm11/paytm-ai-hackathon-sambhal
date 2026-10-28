"""Pre-generate Sarvam audio for every message the stage demo can produce, and listen back to each one.

Run with SARVAM_API_KEY set:  python scripts/warm_voice_cache.py
Afterwards the demo speaks Kannada/Hindi even with no internet (audio is in data/tts_cache/).

Each line is played back through Sarvam speech-to-text: if an amount isn't heard as written or the end of the line
is missing, the line is made again (up to 3 times). A Wispr Flow listening test found both faults in saved audio.
Listening back costs a little speech-to-text credit; --no-check skips it.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from app import config, presenter, replies, voice, voice_qa  # noqa: E402
from app.world import World  # noqa: E402

TRY_LINES = ["Business is slow because of the rain", "Can you waive the interest?", "ನಮ್ಮ ಅಮ್ಮ ನಿನ್ನೆ ತೀರಿಕೊಂಡರು",
             "ಸರಿ, ಒಪ್ಪುತ್ತೇನೆ"]
AFTER_OFFER = ["Can I get more days?"]   # asked while Ravi's 3-day pause is on offer


def outbound(w: World):
    for c in w.cases.values():
        for m in c.messages:
            if m.dir == "out":
                yield f"{replies.header(m.lang)}. {m.text}", m.lang


def collect():
    lines = {}
    w = World(use_llm=False)
    presenter.go_to(w, len(presenter.STEPS) - 1)        # Ravi's week, pay-ahead, Shobha, Bellandur: every shop
    lines.update({t: l for t, l in outbound(w)})
    for key, by_lang in replies.QUICK_REPLIES.items():  # one-tap replies and home buttons, Ravi in Kannada
        w = World(use_llm=False)
        presenter.go_to(w, 3)
        w.inbound("M01", by_lang["kn"])
        lines.update({t: l for t, l in outbound(w)})
    w = World(use_llm=False)                            # the switches: consent and pay-ahead, off and on
    presenter.go_to(w, 9)
    for on in (False, True):
        w.set_consent("M01", on)
    w.set_cushion("M01", False)
    lines.update({t: l for t, l in outbound(w)})
    for lang in ("kn", "hi", "en"):                     # Sambhal's promise, read aloud
        lines[" ".join(p["text"][lang] for p in replies.PROMISES)] = lang
    for text in TRY_LINES:                    # what the quick-reply chips can trigger on stage
        w = World(use_llm=False)
        presenter.go_to(w, 3)
        w.inbound("M01", text)
        c = w.case_for("M01")
        if c.state == "offered":
            w.accept("M01", c.offered[0])
        lines.update({t: l for t, l in outbound(w)})
    for text in AFTER_OFFER:
        w = World(use_llm=False)
        presenter.go_to(w, 4)
        w.inbound("M01", text)
        lines.update({t: l for t, l in outbound(w)})
    return lines


def main():
    ap = argparse.ArgumentParser(description="Save every demo line as Sarvam audio, then listen back to each one.")
    ap.add_argument("--no-check", action="store_true", help="only make missing lines; don't listen back")
    ap.add_argument("--tries", type=int, default=3, help="remakes allowed for a line that sounds wrong")
    ap.add_argument("--remake", default="", help="languages to make again from scratch, e.g. kn,en (after a change "
                                                  "to how they are spoken)")
    args = ap.parse_args()
    if not config.SARVAM_API_KEY:
        sys.exit("Set SARVAM_API_KEY in .env first.")
    config.RUNTIME["offline"] = False
    todo = collect()
    remake = {x.strip() for x in args.remake.split(",") if x.strip()}
    print(f"{len(todo)} lines" + (f"; making {', '.join(sorted(remake))} again from scratch" if remake else ""))
    made = remade = 0
    wrong = []
    try:
        for text, lang in todo.items():
            audio = None if lang in remake else voice.cached_tts(text, lang)
            if not audio:
                audio = voice.tts(text, lang, fresh=True)
                made += 1
            if args.no_check:
                continue
            # Listen back: the amount must be heard as written and the line must not be cut off.
            problems = voice_qa.check(text, lang, voice_qa.transcribe(audio, lang))
            tries = 0
            while problems and tries < args.tries:
                tries += 1
                remade += 1
                audio = voice.tts(text, lang, fresh=True)
                problems = voice_qa.check(text, lang, voice_qa.transcribe(audio, lang))
            status = "ok " if not problems else "BAD"
            print(f"  {status} {lang} {text[:70]}" + (f"\n        {'; '.join(problems)}" if problems else ""))
            if problems:
                wrong.append((lang, text, problems))
    except RuntimeError as e:          # e.g. no Sarvam credits left
        sys.exit(f"\nStopped: {e}\nMade {made}, remade {remade}. Top up Sarvam credits and run this again.")
    print(f"\n{len(todo)} lines in {config.CACHE_DIR}: {made} new, {remade} remade after listening back")
    if wrong:
        print(f"{len(wrong)} still sound wrong after {args.tries} remakes: check them by ear (Play in the app).")
    sys.exit(1 if wrong else 0)


if __name__ == "__main__":
    main()
