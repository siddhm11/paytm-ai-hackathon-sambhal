"""With vs without Sambhal: replay the same 50 synthetic merchants through both.

"With" runs the full agent (rules reader, templates, guardrails) with every
merchant replying as scripted. "Without" replays the identical sales through
the plain daily-deduction loan. Same data, same days; only Sambhal differs.
This shows how a pilot would be measured. It is not a result from real merchants.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import lru_cache
from statistics import median

from . import guardrails, policy
from .world import World

START = date(2026, 10, 21)
END = date(2026, 11, 10)


def _overdue(rows, installment):
    return {"overdue_days": sum(1 for r in rows if r["arrears"] > 0),
            "max_dpd": max((r["dpd"] for r in rows), default=0),
            "peak_deduction": max((r["deducted"] for r in rows), default=0),
            "peak_multiple": round(max((r["deducted"] for r in rows), default=0) / installment, 2)}


def violations(w: World) -> list[dict]:
    """Independent audit of every message the agent sent."""
    menu = {o["id"]: o for o in policy.load_policy()["options"]}
    out = []
    for c in w.cases.values():
        m = w.merchants[c.merchant_id]
        inbound = [x.at for x in c.messages if x.dir == "in"]
        for msg in c.messages:
            if msg.dir != "out" or msg.status != "sent":
                continue
            t = msg.sent_at
            near_inbound = any(timedelta(0) <= t - i <= timedelta(minutes=30) for i in inbound)
            if not guardrails.in_hours(t) and not (not msg.proactive and near_inbound):
                out.append({"case": c.id, "rule": "Contact hours", "at": t.isoformat()})
            if msg.proactive and not m.consent:
                out.append({"case": c.id, "rule": "Consent", "at": t.isoformat()})
            if msg.proactive and c.quiet_until and msg.at < c.quiet_until and t < c.quiet_until and msg.kind != "checkin":
                out.append({"case": c.id, "rule": "Family function quiet period", "at": t.isoformat()})
            if msg.proactive and c.sensitive_until and t < c.sensitive_until and t > c.opened_at and msg.kind != "checkin":
                out.append({"case": c.id, "rule": "Sensitive situation", "at": t.isoformat()})
            for o in msg.options:
                if o["id"] not in menu or menu[o["id"]]["requires_human"]:
                    out.append({"case": c.id, "rule": "Lender's menu only", "at": t.isoformat()})
            if guardrails.script_share(msg.text, msg.lang) < 0.6:
                out.append({"case": c.id, "rule": "Merchant's language", "at": t.isoformat()})
        sent_proactive = sorted(x.sent_at for x in c.messages if x.dir == "out" and x.status == "sent" and x.proactive)
        for i, t in enumerate(sent_proactive):
            same_day = [s for s in sent_proactive[:i] if s.date() == t.date()]
            if same_day:
                out.append({"case": c.id, "rule": "No repeated contact", "at": t.isoformat()})
    return out


@lru_cache(maxsize=1)
def run() -> dict:
    w = World(use_llm=False, scripted_ravi=True)
    w.advance(datetime.combine(END, time(23, 0)))
    per = []
    for mid, m in w.merchants.items():
        cases = [c for c in w.cases.values() if c.merchant_id == mid]
        if not cases:
            continue
        c = cases[0]
        actual = [r for r in w.rows[mid] if START <= r["date"] <= END]
        cf = w.counterfactual(mid, START, END)
        a, b = _overdue(actual, w.loans[mid].installment), _overdue(cf, w.loans[mid].installment)
        per.append({
            "merchant_id": mid, "merchant": m.owner, "shop": m.shop, "lang": m.lang,
            "reason": c.reason, "state": c.state, "accepted": c.accepted, "human": c.human,
            "with": a, "without": b,
            "messages_sent": sum(1 for x in c.messages if x.dir == "out" and x.status == "sent"),
            "proactive_sent": sum(1 for x in c.messages if x.dir == "out" and x.status == "sent" and x.proactive),
        })
    v = violations(w)

    def agg(key):
        return {
            "merchants_overdue": sum(1 for p in per if p[key]["overdue_days"] > 0),
            "overdue_days": sum(p[key]["overdue_days"] for p in per),
            "merchants_dpd_3plus": sum(1 for p in per if p[key]["max_dpd"] >= 3),
            "median_peak_multiple": round(median(p[key]["peak_multiple"] for p in per), 2) if per else 0,
            "max_peak_multiple": max((p[key]["peak_multiple"] for p in per), default=0),
        }

    return {
        "window": [START.isoformat(), END.isoformat()], "merchants_total": len(w.merchants),
        "flagged": len(per), "with": agg("with"), "without": agg("without"),
        "relief_accepted": sum(1 for p in per if p["accepted"]),
        "handed_to_person": sum(1 for p in per if p["human"]),
        "proactive_messages": sum(p["proactive_sent"] for p in per),
        "messages_sent": sum(p["messages_sent"] for p in per),
        "still_overdue_with": [{"merchant": p["merchant"], "state": p["state"], "reason": p["reason"]}
                               for p in per if p["with"]["overdue_days"] > 0],
        "violations": v, "per_merchant": per,
        "note": "Synthetic merchants. Same sales replayed with and without Sambhal. Handed-over cases are counted "
                "with no relief, though lender staff would usually help: a conservative comparison.",
    }
