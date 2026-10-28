"""Presenter mode: Ravi's week as nine steps you click through on stage."""
from __future__ import annotations

from datetime import datetime

from .world import RAVI_REPLY, World

STEPS = [
    {"at": "2026-10-21T10:00", "title": "Meet Ravi", "phone": "home", "tab": "cases", "spot": "home",
     "caption": "Ravi runs a kirana in Basavanagudi. ₹1,36,000 loan; ₹850 is deducted from his sales every evening. "
                "71 installments in a row, never missed one."},
    {"at": "2026-10-21T21:05", "title": "Wednesday: one slow day", "phone": "home", "tab": "cases", "spot": "settle",
     "caption": "Sales are 48% of a normal Wednesday. One slow day isn't a pattern, so Sambhal only watches."},
    {"at": "2026-10-22T21:05", "title": "Thursday 9 pm: flagged, and held", "phone": "chat", "tab": "cases",
     "spot": "guard",
     "caption": "A second day below half (31%). Sambhal opens a case before anything is missed. It's 9 pm, outside "
                "RBI's 8 am–7 pm window, so the message waits."},
    {"at": "2026-10-23T08:00", "title": "Friday 8 am: Sambhal checks in", "phone": "chat", "tab": "cases",
     "spot": "voice",
     "caption": "In Kannada, by voice and text, with a recording notice and the grievance officer's details. "
                "It offers help, not a demand."},
    {"at": "2026-10-23T08:20", "title": "Ravi replies by voice", "action": "ravi_reply", "phone": "chat",
     "tab": "cases", "spot": "reading",
     "caption": "“ಮನೆಯಲ್ಲಿ ಮದುವೆ ಇದೆ, ಭಾನುವಾರದವರೆಗೆ ಅಂಗಡಿ ಮುಚ್ಚಿರುತ್ತೆ.” There's a wedding at home; the shop is shut "
                "till Sunday. Sambhal offers only what the lender pre-approved."},
    {"at": "2026-10-23T08:22", "title": "Ravi taps Accept", "action": "ravi_accept", "phone": "loan", "tab": "cases",
     "spot": "calendar",
     "caption": "The pause is written into the deduction calendar by code. Sambhal goes quiet until Monday, as RBI "
                "asks around family functions."},
    {"at": "2026-10-25T21:05", "title": "The weekend: shop shut", "phone": "loan", "tab": "week", "spot": "week",
     "caption": "No sales, no deduction, nothing overdue, no messages."},
    {"at": "2026-10-26T21:05", "title": "Monday: back to business", "phone": "home", "tab": "week",
     "spot": "payoff",
     "caption": "₹1,032 deducted: 17% of the day's sales. Without Sambhal: ₹3,400 (57%) in one sweep, after three "
                "days overdue."},
    {"at": "2026-10-27T08:00", "title": "Tuesday 8 am: case closed", "phone": "chat", "tab": "audit", "spot": "audit",
     "caption": "Sambhal confirms the recovery and closes the case. Every decision is in the lender's audit log."},
    {"at": "2026-10-27T08:10", "title": "Prepare: Ravi turns on pay-ahead", "action": "ravi_cushion", "phone": "home",
     "tab": "week", "spot": "cushion",
     "caption": "Ready for the next slow week: on days Ravi sells ₹6,000 or more, ₹100 goes towards future installments. "
                "Had it been on from the start, ₹3,800 paid ahead would have covered the wedding by itself: no pause, "
                "no catch-up, nothing overdue."},
    # Beyond Ravi (optional): the same week, other shops
    {"at": "2026-10-27T11:00", "title": "Beyond Ravi: Shobha tells us first", "action": "shobha_plan", "focus": "M42",
     "phone": "chat", "tab": "cases", "spot": "offer", "extra": True,
     "caption": "Shobha's sister is getting married. She taps 'Tell us about a closure' and picks Fri–Sun before "
                "anything happens. The lender's pause is booked for those exact days: no dip alarm, no check-in, no worry."},
    {"at": "2026-10-28T21:05", "title": "Bellandur: eight shops dip together", "focus": "M43", "phone": "home",
     "tab": "cases", "spot": "alert", "extra": True,
     "caption": "Eight shops in one neighbourhood fall to a quarter of normal on the same evening while the rest of the "
                "city is normal. A local event, not eight separate problems: Sambhal sends no reminders there and asks "
                "the lender for one decision."},
    {"at": "2026-10-29T10:00", "title": "The lender approves one area pause", "action": "area_approve", "focus": "M43",
     "phone": "loan", "tab": "cases", "spot": "alert", "extra": True,
     "caption": "One click: a 3-day pause for every eligible shop in Bellandur, from the lender's own menu. The notice "
                "waits until sales there recover; until then each shop sees the pause in its app."},
    {"at": "2026-11-01T21:05", "title": "Trust, then check: Shobha reopened early", "focus": "M42", "phone": "loan",
     "tab": "cases", "spot": "timeline", "extra": True,
     "caption": "Sunday's sales were normal, so Shobha's shop was open. The pause ends early and her catch-up shrinks "
                "to the two days she was really shut. The lender sees why in the audit log."},
]


def run_action(w: World, action: str):
    case = w.case_for("M01")
    if action == "ravi_reply":
        if case and not any(m.dir == "in" for m in case.messages):
            w.inbound("M01", RAVI_REPLY, via="voice")
    elif action == "ravi_accept":
        if case and case.state == "offered" and not case.accepted and case.offered:
            w.accept("M01", case.offered[0], via="tap")
    elif action == "shobha_plan":
        c = w.case_for("M42")
        if not (c and c.planned):
            w.plan_closure("M42", "family_event", datetime(2026, 10, 30).date(), 3)
            c = w.case_for("M42")
        if c.state == "offered" and c.offered and not c.accepted:
            w.accept("M42", c.offered[0], via="tap")
    elif action == "area_approve":
        for a in w.alerts.values():
            if a["area"] == "Bellandur" and not a["approved"]:
                w.approve_area(a["id"])
    elif action == "ravi_cushion":
        if not w.loans["M01"].cushion.get("on"):
            w.set_cushion("M01", True)


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
