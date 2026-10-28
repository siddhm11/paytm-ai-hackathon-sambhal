"""Presenter mode: Ravi's week as nine steps you click through on stage."""
from __future__ import annotations

from datetime import datetime

from .world import RAVI_REPLY, World

STEPS = [
    {"at": "2026-10-21T10:00", "title": "Meet Ravi",
     "caption": "Ravi runs a kirana in Basavanagudi. ₹1,36,000 loan; ₹850 is deducted from his sales every evening. "
                "71 installments in a row, never missed one."},
    {"at": "2026-10-21T21:05", "title": "Wednesday: one slow day",
     "caption": "Sales are 48% of a normal Wednesday. One slow day isn't a pattern, so Sambhal only watches."},
    {"at": "2026-10-22T21:05", "title": "Thursday 9 pm: flagged, and held",
     "caption": "A second day below half (31%). Sambhal opens a case before anything is missed. It's 9 pm, outside "
                "RBI's 8 am–7 pm window, so the message waits."},
    {"at": "2026-10-23T08:00", "title": "Friday 8 am: Sambhal checks in",
     "caption": "In Kannada, by voice and text, with a recording notice and the grievance officer's details. "
                "It offers help, not a demand."},
    {"at": "2026-10-23T08:20", "title": "Ravi replies by voice", "action": "ravi_reply",
     "caption": "“ಮನೆಯಲ್ಲಿ ಮದುವೆ ಇದೆ, ಭಾನುವಾರದವರೆಗೆ ಅಂಗಡಿ ಮುಚ್ಚಿರುತ್ತೆ.” There's a wedding at home; the shop is shut "
                "till Sunday. Sambhal offers only what the lender pre-approved."},
    {"at": "2026-10-23T08:22", "title": "Ravi taps Accept", "action": "ravi_accept",
     "caption": "The pause is written into the deduction calendar by code. Sambhal goes quiet until Monday, as RBI "
                "asks around family functions."},
    {"at": "2026-10-25T21:05", "title": "The weekend: shop shut",
     "caption": "No sales, no deduction, nothing overdue, no messages."},
    {"at": "2026-10-26T21:05", "title": "Monday: back to business",
     "caption": "₹1,032 deducted: 17% of the day's sales. Without Sambhal: ₹3,400 (57%) in one sweep, after three "
                "days overdue."},
    {"at": "2026-10-27T08:00", "title": "Tuesday 8 am: case closed",
     "caption": "Sambhal confirms the recovery and closes the case. Every decision is in the lender's audit log."},
]


def run_action(w: World, action: str):
    case = w.case_for("M01")
    if action == "ravi_reply":
        if case and not any(m.dir == "in" for m in case.messages):
            w.inbound("M01", RAVI_REPLY, via="voice")
    elif action == "ravi_accept":
        if case and case.state == "offered" and not case.accepted and case.offered:
            w.accept("M01", case.offered[0], via="tap")


def go_to(w: World, n: int):
    n = max(0, min(n, len(STEPS) - 1))
    if n < w.step:
        w.reset()
    for i in range(0, n + 1):          # steps are idempotent: replaying earlier ones is a no-op
        st = STEPS[i]
        at = datetime.fromisoformat(st["at"])
        if at > w.now:
            w.advance(at)
        if st.get("action"):
            run_action(w, st["action"])
    w.step = n


def view() -> list[dict]:
    return [{"n": i, **s} for i, s in enumerate(STEPS)]
