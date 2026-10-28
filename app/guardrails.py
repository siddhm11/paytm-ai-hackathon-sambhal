"""Guardrails: checked in code before anything reaches a merchant.

Based on RBI's recovery directions (6 Aug 2026, in force 1 Jan 2027): contact
only 08:00-19:00, calls recorded, a named grievance officer in every recovery
communication, no harassment or repeated contact, sensitivity around
bereavement, medical emergencies and family functions. Plus our own rules:
consent, the lender's menu only, and a check on every AI-written message.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from .config import CONTACT_END, CONTACT_START, REPLY_WINDOW_MIN

MAX_PROACTIVE_PER_DAY = 1
MAX_PROACTIVE_PER_WEEK = 3


def t12(dt: datetime, day: bool = False) -> str:
    """'9:00 pm' or 'Fri 8:00 am'."""
    t = dt.strftime("%I:%M %p").lstrip("0").lower()   # portable (Windows has no %-I)
    return f"{dt:%a} {t}" if day else t


def next_contact_time(now: datetime) -> datetime:
    start = now.replace(hour=CONTACT_START.hour, minute=CONTACT_START.minute, second=0, microsecond=0)
    if now.time() < CONTACT_START:
        return start
    return start + timedelta(days=1)


def in_hours(now: datetime) -> bool:
    return CONTACT_START <= now.time() < CONTACT_END


def decide(rule: str, ok: bool, why: str, hold_until: datetime | None = None, block: bool = False) -> dict:
    return {"rule": rule, "ok": ok, "why": why, "hold_until": hold_until, "block": block}


def check_outbound(case, merchant, now: datetime, kind: str, recipient: str | None = None) -> list[dict]:
    """Run every outbound rule. kind = 'proactive' (we start) or 'reply' (answering the merchant).
    Returns the list of rule results; the message goes out only if all are ok."""
    out = []
    recipient = recipient or merchant.phone
    out.append(decide("Borrower only", recipient == merchant.phone,
                      "Recipient is the borrower on file" if recipient == merchant.phone
                      else "Blocked: never contact anyone other than the borrower", block=True))
    if kind == "proactive":
        out.append(decide("Consent", merchant.consent,
                          "Merchant opted in to Sambhal messages at loan sign-up" if merchant.consent
                          else "No messaging consent: case goes to a person instead", block=True))
    if case.stopped:
        out.append(decide("Stop request", kind == "reply" and case.last_inbound_recent(now, REPLY_WINDOW_MIN),
                          "Merchant asked us to stop: only answering their own message" if kind == "reply"
                          else "Merchant asked us to stop contacting them", block=True))
    if case.sensitive_until and now < case.sensitive_until and kind == "proactive":
        out.append(decide("Sensitive situation", False,
                          f"No outreach until {case.sensitive_until:%d %b} (bereavement or medical emergency)",
                          block=True))
    if case.quiet_until and now < case.quiet_until and kind == "proactive":
        out.append(decide("Family function", False, f"Quiet until {t12(case.quiet_until, day=True)} (family function)",
                          hold_until=case.quiet_until))
    if kind == "proactive":
        today = [t for t in case.proactive_sent if t.date() == now.date()]
        week = [t for t in case.proactive_sent if now - t < timedelta(days=7)]
        ok = len(today) < MAX_PROACTIVE_PER_DAY and len(week) < MAX_PROACTIVE_PER_WEEK
        out.append(decide("No repeated contact", ok,
                          f"{len(today)} today, {len(week)} this week (limits {MAX_PROACTIVE_PER_DAY}/day, "
                          f"{MAX_PROACTIVE_PER_WEEK}/week)", block=not ok))
    if in_hours(now):
        out.append(decide("Contact hours", True, f"{t12(now)} is within 8 am–7 pm"))
    elif kind == "reply" and case.last_inbound_recent(now, REPLY_WINDOW_MIN):
        out.append(decide("Contact hours", True,
                          f"{t12(now)} is outside 8 am–7 pm, but the merchant wrote to us just now"))
    else:
        nt = next_contact_time(now)
        out.append(decide("Contact hours", False, f"{t12(now)} is outside RBI's 8 am–7 pm window: held until {t12(nt, day=True)}",
                          hold_until=nt))
    return out


def verdict(results: list[dict]) -> dict:
    """Combine rule results: blocked beats held beats send."""
    failed = [r for r in results if not r["ok"]]
    if not failed:
        return {"action": "send", "failed": []}
    if any(r["block"] for r in failed):
        return {"action": "block", "failed": failed}
    hold = max(r["hold_until"] for r in failed if r["hold_until"])
    return {"action": "hold", "hold_until": hold, "failed": failed}


# --------------------------------------------------------------------------
# Output check for AI-written text
# --------------------------------------------------------------------------
BANNED = [
    # English
    r"\blegal action\b", r"\bpolice\b", r"\bcourt\b", r"\barrest", r"\bjail\b", r"\bcibil\b",
    r"\bcredit score\b", r"\bdefaulter\b", r"\bseize", r"\bfinal warning\b", r"\blast warning\b",
    r"\b(family|relatives|neighbou?rs|friends|colleagues)\b[^.!?]{0,25}\b(will be )?(informed|told|contacted|called)\b",
    r"\b(inform|tell|contact|call)\b[^.!?]{0,25}\b(family|relatives|neighbou?rs|friends|colleagues)\b",
    r"\bvisit (your|the) (shop|home|house)\b", r"\bpenalt", r"\bblacklist",
    # Hindi
    "पुलिस", "कोर्ट", "अदालत", "कानूनी", "क़ानूनी", "जेल", "गिरफ्तार", "डिफॉल्टर", "रिश्तेदार", "पड़ोसी", "जुर्माना",
    "सिबिल",
    # Kannada
    "ಪೊಲೀಸ್", "ನ್ಯಾಯಾಲಯ", "ಕೋರ್ಟ್", "ಕಾನೂನು ಕ್ರಮ", "ಜೈಲು", "ಸಂಬಂಧಿಕರು", "ನೆರೆಹೊರೆ", "ದಂಡ", "ಸಿಬಿಲ್",
]

_DIGITS = str.maketrans("೦೧೨೩೪೫೬೭೮೯०१२३४५६७८९", "01234567890123456789")
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> set[str]:
    t = text.translate(_DIGITS)
    return {n.replace(",", "").rstrip(".") for n in NUM_RE.findall(t)}


def script_share(text: str, lang: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    if lang == "kn":
        hit = sum(1 for c in letters if "ಀ" <= c <= "೿")
    elif lang == "hi":
        hit = sum(1 for c in letters if "ऀ" <= c <= "ॿ")
    else:
        hit = sum(1 for c in letters if c.isascii())
    return hit / len(letters)


def validate_draft(text: str, lang: str, allowed_numbers: set[str]) -> dict:
    problems = []
    low = text.lower()
    for pat in BANNED:
        if (re.search(pat, low) if pat.startswith("\\b") else pat in text):
            problems.append(f"threatening or third-party language ({pat.strip(chr(92)+'b')})")
            break
    extra = sorted(numbers_in(text) - {n.replace(",", "") for n in allowed_numbers})
    if extra:
        problems.append("numbers not in the approved terms: " + ", ".join(extra))
    share = script_share(text, lang)
    if share < 0.6:
        problems.append(f"wrong language: only {share:.0%} of letters are in the merchant's script")
    if len(text) > 700:
        problems.append("too long")
    return {"ok": not problems, "problems": problems}
