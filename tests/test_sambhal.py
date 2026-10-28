"""Run: pytest -q"""
import base64
import json
from datetime import date, datetime

import pytest

from app import config, evals, guardrails, llm, nlu, policy, replay, voice
from app.presenter import go_to
from app.world import RAVI_REPLY, World


# ---------------------------------------------------------------- scenario suite
@pytest.mark.parametrize("sc", evals.load(), ids=lambda s: s["id"])
def test_scenario(sc):
    r = evals.run_one(sc)
    assert r["ok"], (r["error"], [c for c in r["checks"] if not c["ok"]])


def test_forty_scenarios():
    assert len(evals.load()) == 40


# ---------------------------------------------------------------- the demo story
def test_presenter_story_end_to_end():
    w = World(use_llm=False)
    go_to(w, 8)
    c = w.case_for("M01")
    assert c.state == "recovered" and c.accepted == "PAUSE_3"
    wk = {r["date"]: r for r in w.week("M01")["rows"]}
    assert wk["2026-10-26"]["with"]["deducted"] == 1032
    assert wk["2026-10-26"]["without"]["deducted"] == 3400
    assert wk["2026-10-25"]["without"]["dpd"] == 3
    assert w.states["M01"].missed_days == 0
    # every message Ravi got was sent inside 8 am-7 pm or right after he wrote
    for m in c.messages:
        if m.dir == "out" and m.status == "sent":
            assert guardrails.in_hours(m.sent_at) or not m.proactive


def test_presenter_back_and_forth_is_stable():
    w = World(use_llm=False)
    go_to(w, 7)
    a = w.week("M01")
    go_to(w, 2)
    go_to(w, 7)
    assert w.week("M01") == a


def test_replay_has_no_violations_and_helps():
    r = replay.run()
    assert r["violations"] == []
    assert r["with"]["merchants_overdue"] < r["without"]["merchants_overdue"]
    assert all(x["state"] in ("with_person", "review", "grievance") for x in r["still_overdue_with"])


# ---------------------------------------------------------------- rules reader
@pytest.mark.parametrize("text,intent", [
    (RAVI_REPLY, "family_event"),
    ("घर में शादी है, तीन दिन दुकान बंद रहेगी।", "family_event"),
    ("dhandha bahut kam hai bhai", "business_slow"),
    ("ನನಗೆ ಜ್ವರ, ಹುಷಾರಿಲ್ಲ", "illness"),
    ("ನನ್ನ ಮಗ ಆಸ್ಪತ್ರೆಯಲ್ಲಿ ICU ನಲ್ಲಿ ಇದ್ದಾನೆ", "medical_emergency"),
    ("सब ठीक है, कोई दिक्कत नहीं", "business_normal"),
    ("ಸರಿ, ಒಪ್ಪುತ್ತೇನೆ", "accept"),
    ("STOP", "stop_contact"),
    ("how much is left to pay?", "question"),
    ("asdf qwerty", "unclear"),
])
def test_rules_reader(text, intent):
    assert nlu.read_rules(text, "kn", date(2026, 10, 23))["intent"] == intent


def test_event_days_from_weekday():
    # Friday + "till Sunday" = Fri, Sat, Sun
    assert nlu.read_rules(RAVI_REPLY, "kn", date(2026, 10, 23))["event_days"] == 3


# ---------------------------------------------------------------- policy maths
def test_reduce_terms():
    w = World(use_llm=False)
    t = policy.terms("HALF_14", w.loans["M01"], date(2026, 10, 23))
    assert t["reduced_installment"] == 425 and t["deferred_total"] == 425 * 14 and t["extra_days"] == 7


# ---------------------------------------------------------------- LLM paths (mocked, no network)
@pytest.fixture
def fake_llm(monkeypatch):
    calls = []

    def install(reply_fn):
        monkeypatch.setattr(llm, "available", lambda: True)
        monkeypatch.setattr(config, "LLM_REWRITE", True)

        def chat_json(system, user):
            calls.append((system, user))
            return reply_fn(system, user)
        monkeypatch.setattr(llm, "chat_json", chat_json)
        return calls
    return install


def test_llm_reading_used_and_safety_net(fake_llm):
    fake_llm(lambda s, u: {"intent": "business_slow", "language": "kn", "event_days": None,
                           "summary_en": "Business is slow."} if "Classify" in s else {"text": "x"})
    r = nlu.read("ನಮ್ಮ ಅಪ್ಪ ತೀರಿಕೊಂಡರು", "kn", date(2026, 10, 23))
    assert r["intent"] == "bereavement" and r["source"] == "llm+safety-net"


def test_llm_bad_draft_falls_back_to_template(fake_llm):
    def reply(system, user):
        if "Classify" in system:
            return {"intent": "family_event", "language": "kn", "event_days": 3, "summary_en": "Wedding."}
        return {"text": "ದಿನಕ್ಕೆ ₹500 ಕಟ್ಟಿ, ಇಲ್ಲದಿದ್ದರೆ ಪೊಲೀಸ್."}   # invented amount + threat
    fake_llm(reply)
    w = World(use_llm=True)
    w.advance(datetime(2026, 10, 23, 8, 20))
    w.inbound("M01", RAVI_REPLY)
    offer = [m for m in w.case_for("M01").messages if m.kind == "offer"][0]
    assert offer.author == "template" and offer.draft and not offer.draft["ok"]
    assert any(a["rule"] == "AI message check" and a["decision"] == "rejected" for a in w.audit_log)


def test_llm_good_draft_is_used(fake_llm):
    def reply(system, user):
        if "Classify" in system:
            return {"intent": "family_event", "language": "kn", "event_days": 3, "summary_en": "Wedding."}
        return {"text": user.replace("ಶುಭಾಶಯಗಳು.", "ಹೃತ್ಪೂರ್ವಕ ಶುಭಾಶಯಗಳು.")}
    fake_llm(reply)
    w = World(use_llm=True)
    w.advance(datetime(2026, 10, 23, 8, 20))
    w.inbound("M01", RAVI_REPLY)
    offer = [m for m in w.case_for("M01").messages if m.kind == "offer"][0]
    assert offer.author == "llm"


def test_llm_error_falls_back_to_rules(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "chat_json", lambda s, u: (_ for _ in ()).throw(RuntimeError("timeout")))
    r = nlu.read(RAVI_REPLY, "kn", date(2026, 10, 23))
    assert r["intent"] == "family_event" and r["source"] == "rules" and "llm_error" in r


def test_extract_json_handles_think_and_fences():
    assert llm._extract_json('<think>hmm</think>```json\n{"intent": "accept"}\n```') == {"intent": "accept"}


# ---------------------------------------------------------------- Sarvam request shapes (mocked)
class FakeResp:
    def __init__(self, status, payload):
        self.status_code, self._p, self.text = status, payload, json.dumps(payload)

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def test_sarvam_tts_and_stt_requests(monkeypatch, tmp_path):
    seen = []

    def fake_post(url, **kw):
        seen.append((url, kw))
        if url.endswith("/text-to-speech"):
            return FakeResp(200, {"audios": [base64.b64encode(b"RIFFfake").decode()]})
        return FakeResp(200, {"transcript": RAVI_REPLY, "language_code": "kn-IN"})

    monkeypatch.setattr(config, "SARVAM_API_KEY", "sk_test")
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    monkeypatch.setitem(config.RUNTIME, "offline", False)
    monkeypatch.setattr(voice.httpx, "post", fake_post)
    assert voice.tts("ನಮಸ್ಕಾರ", "kn") == b"RIFFfake"
    url, kw = seen[-1]
    assert kw["headers"]["api-subscription-key"] == "sk_test"
    assert kw["json"]["language_code"] == "kn-IN" and kw["json"]["model"] == config.TTS_MODEL
    assert voice.tts("ನಮಸ್ಕಾರ", "kn") == b"RIFFfake" and len(seen) == 1     # second call is cached
    r = voice.stt(b"\x00" * 2000, "reply.webm", "audio/webm", "kn")
    assert r["transcript"] == RAVI_REPLY and r["language"] == "kn"
    url, kw = seen[-1]
    assert url.endswith("/speech-to-text") and kw["data"]["language_code"] == "kn-IN"


# ---------------------------------------------------------------- reader safety: accepting changes the loan
@pytest.mark.parametrize("text,intent", [
    ("I am not ok", "unclear"),                      # "ok" with "not" is never a yes
    ("ಸರಿ ಇಲ್ಲ", "unclear"),
    ("ok but why only 3 days?", "need_time"),        # a question about the offer is not a yes
    ("Please give me some more time", "need_time"),
    ("I will pay tomorrow", "need_time"),
    ("thoda time chahiye bhai", "need_time"),
    ("no", "decline"),
    ("Not now.", "decline"),
    ("नहीं", "decline"),
    ("ನಮ್ಮ ಮನೆಯಲ್ಲಿ ಹಬ್ಬ", "family_event"),
    ("No sales this week, big loss", "business_slow"),
    ("Wedding at home, need more time", "family_event"),   # a stated reason beats "more time"
    ("हाँ, ठीक है", "accept"),
    ("Yes, okay", "accept"),
])
def test_reader_safety(text, intent):
    assert nlu.read_rules(text, "kn", date(2026, 10, 23))["intent"] == intent


def test_more_time_goes_to_staff_and_offer_stays_open():
    w = World(use_llm=False)
    go_to(w, 4)                                     # Ravi has the 3-day pause on offer
    w.inbound("M01", "ok but why only 3 days?")
    c = w.case_for("M01")
    assert c.state == "offered" and c.human and not c.accepted
    assert c.messages[-1].kind == "more_time" and "still open" in c.messages[-1].text_en
    assert w.accept("M01", "PAUSE_3")["ok"]        # he can still take the pause


def test_bare_no_to_a_checkin_asks_why():
    w = World(use_llm=False)
    go_to(w, 3)                                     # check-in asked "Is everything okay?"
    w.inbound("M01", "no")
    assert w.case_for("M01").messages[-1].kind == "ask_reason"
