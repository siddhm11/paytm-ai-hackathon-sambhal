"""End-to-end voice check, before you go on stage:  python scripts/check_mic.py [--port 8000]

Needs the app running, a Sarvam key in .env, internet and Google Chrome. It records three Kannada replies in a
different Sarvam voice (a male merchant), plays each one into the app as its microphone, presses Sambhal's own mic
button and checks what comes back: browser recording -> /api/stt -> Sarvam speech-to-text -> reader -> reply.

It moves the presenter to steps 3-4 and adds replies to Ravi's case: press Reset in the app afterwards.
"""
import argparse
import base64
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import httpx  # noqa: E402

from app import config  # noqa: E402

try:
    import websocket  # noqa: E402
except ImportError:
    sys.exit("Install the browser driver first:  pip install websocket-client")

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CASES = [  # name, presenter step, what the merchant says, what Sambhal must understand
    ("Ravi's line", 3, "ಮನೆಯಲ್ಲಿ ಮದುವೆ ಇದೆ, ಭಾನುವಾರದವರೆಗೆ ಅಂಗಡಿ ಮುಚ್ಚಿರುತ್ತೆ.", "family_event"),
    ("Fever, off-script", 3, "ನನಗೆ ಜ್ವರ ಬಂದಿದೆ, ಎರಡು ದಿನ ಅಂಗಡಿ ತೆರೆಯಲ್ಲ.", "illness"),
    ("'Okay, but why only 3 days?'", 4, "ಸರಿ, ಆದರೆ ಯಾಕೆ ಮೂರೇ ದಿನ? ನನಗೆ ಇನ್ನೂ ಹೆಚ್ಚು ದಿನ ಬೇಕು.", "need_time"),
]

# The recording stands in for the microphone; everything after it is the real app.
MIC = """(() => {
  const ab = Uint8Array.from(atob("%s"), c => c.charCodeAt(0)).buffer;
  navigator.mediaDevices.getUserMedia = async () => {
    const ctx = new AudioContext(); await ctx.resume();
    const dest = ctx.createMediaStreamDestination();
    const src = ctx.createBufferSource(); src.buffer = await ctx.decodeAudioData(ab.slice(0));
    src.connect(dest); src.start(ctx.currentTime + 0.3);
    return dest.stream;
  };
})()"""
RUN = """(async () => {
  dispLang = "local"; await goStep(%d); screen = "chat"; renderPhone();    // Kannada on the phone, Kannada mic
  await toggleMic(); await new Promise(r => setTimeout(r, 6500)); toggleMic();
  for (let i = 0; i < 80; i++) {
    await new Promise(r => setTimeout(r, 250));
    if (/Heard|Couldn't|not available/.test($("#recNote").textContent) && !busy) break;
  }
  await new Promise(r => setTimeout(r, 800));
  const th = S.merchant.thread, c = S.merchant.case;
  const lastIn = [...th].reverse().find(m => m.dir === "in" && m.via === "voice");
  const lastOut = [...th].reverse().find(m => m.dir === "out");
  return JSON.stringify({note: $("#recNote").textContent, heard: lastIn && lastIn.text,
    intent: lastIn && lastIn.nlu && lastIn.nlu.intent, reply: lastOut && lastOut.text_en,
    accepted: c && c.accepted});
})()"""


def say(text: str) -> bytes:
    r = httpx.post(f"{config.SARVAM_BASE}/text-to-speech", timeout=30,
                   headers={"api-subscription-key": config.SARVAM_API_KEY, "Content-Type": "application/json"},
                   json={"text": text, "language_code": "kn-IN", "model": config.TTS_MODEL, "speaker": "aditya",
                         "speech_sample_rate": 16000, "pace": 0.95})
    r.raise_for_status()
    return base64.b64decode(r.json()["audios"][0])


def evaluate(ws, expr, seq=[0]):
    seq[0] += 1
    ws.send(json.dumps({"id": seq[0], "method": "Runtime.evaluate",
                        "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == seq[0]:
            return msg["result"]["result"].get("value")


def run(port: int, step: int, audio: bytes, tmp: Path) -> dict:
    chrome = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9339", f"--user-data-dir={tmp}",
                               "--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required",
                               "--mute-audio", f"http://localhost:{port}/?welcome=0"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                pages = json.load(urllib.request.urlopen("http://127.0.0.1:9339/json"))
                page = next(p for p in pages if p.get("type") == "page" and str(port) in p.get("url", ""))
                break
            except Exception:
                time.sleep(0.5)
        ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=90)
        for _ in range(60):
            if evaluate(ws, "typeof S !== 'undefined' && !!S"):
                break
            time.sleep(0.5)
        evaluate(ws, MIC % base64.b64encode(audio).decode())
        return json.loads(evaluate(ws, RUN % step))
    finally:
        chrome.terminate()
        chrome.wait(10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    port = ap.parse_args().port
    if not config.SARVAM_API_KEY:
        sys.exit("Set SARVAM_API_KEY in .env first.")
    if not Path(CHROME).exists():
        sys.exit("Google Chrome not found at " + CHROME)
    try:
        status = json.load(urllib.request.urlopen(f"http://localhost:{port}/api/health"))
    except Exception:
        sys.exit(f"Start the app first (nothing on port {port}).")
    if not status["voice"]["on"]:
        sys.exit("The app's voice is off (Offline switch on, or no key): turn it on and try again.")
    print("Sambhal end-to-end voice check")
    ok = True
    with tempfile.TemporaryDirectory() as td:
        for name, step, text, want in CASES:
            res = run(port, step, say(text), Path(td) / name.replace(" ", "_").replace("'", ""))
            good = res.get("intent") == want and not res.get("accepted")
            ok &= good
            print(f"  [{'PASS' if good else 'FAIL'}] {name}: {res.get('note')}")
            print(f"         read as {res.get('intent')} -> {res.get('reply')}")
    print("\nVoice works end to end. Press Reset in the app." if ok else
          "\nSomething failed. The demo still works with the quick replies and typing; check the lines above.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
