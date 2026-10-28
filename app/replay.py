"""With vs without Sambhal: replay the same 50 synthetic merchants through both.

"With" runs the full agent (rules reader, templates, guardrails) with every
merchant replying as scripted. "Without" replays the identical sales through
the plain daily-deduction loan. Same data, same days; only Sambhal differs.
This shows how a pilot would be measured. It is not a result from real merchants.
"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from statistics import median

from . import guardrails, ledger, policy
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
    pol = policy.load_policy()
    menu = {o["id"]: o for o in pol["options"]}
    if (pol.get("pay_ahead") or {}).get("enabled"):      # the merchant's own opt-in, offered after recovery
        menu["PAYAHEAD"] = {"requires_human": False}
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
            for a in w.alerts.values():
                quiet_end = datetime.combine(a.get("recovered_on") or END, time(21, 0))
                if msg.proactive and c.merchant_id in a["merchants"] and a["opened_at"] <= t < quiet_end:
                    out.append({"case": c.id, "rule": "Local event quiet period", "at": t.isoformat()})
        sent_proactive = sorted(x.sent_at for x in c.messages if x.dir == "out" and x.status == "sent" and x.proactive)
        for i, t in enumerate(sent_proactive):
            same_day = [s for s in sent_proactive[:i] if s.date() == t.date()]
            if same_day:
                out.append({"case": c.id, "rule": "No repeated contact", "at": t.isoformat()})
    return out


def run() -> dict:
    return _run(json.dumps(policy.load_policy(), sort_keys=True))


def what_if(changes: dict) -> dict:
    """Replay the same merchants under a changed relief menu, next to the lender's current one."""
    proposed = policy.with_settings(changes)
    with policy.using(proposed):
        new = _run(json.dumps(proposed, sort_keys=True))
    return {"current": run(), "proposed": new, "settings": policy.current_settings(proposed),
            "now": policy.current_settings(), "tunable": policy.TUNABLE}


@lru_cache(maxsize=8)
def _run(policy_key: str) -> dict:
    w = World(use_llm=False, autopilot=True)
    w.advance(datetime.combine(END, time(23, 0)))
    in_alert = {x for a in w.alerts.values() for x in a["merchants"]}
    per = []
    for mid, m in w.merchants.items():
        cases = [c for c in w.cases.values() if c.merchant_id == mid]
        if not cases and mid not in in_alert:      # shops covered by an area alert always count
            continue
        c = cases[0] if cases else None
        actual = [r for r in w.rows[mid] if START <= r["date"] <= END]
        cf = w.counterfactual(mid, START, END)
        a, b = _overdue(actual, w.loans[mid].installment), _overdue(cf, w.loans[mid].installment)
        # Pay-ahead only: the plain loan with the cushion on since disbursal and no other help. Settings come from
        # sales before the window, so nothing is learnt from the days being tested.
        loan = w.loans[mid]
        cs = policy.pay_ahead(loan, w.sales[mid], START)
        ghost = replace(loan, adjustments={}, cushion={"on": True, "threshold": cs["threshold"], "amount": cs["amount"]})
        _, prow = ledger.replay(ghost, w.sales[mid], loan.disbursed_on + timedelta(days=1), END, {})
        pa = _overdue([r for r in prow if START <= r["date"] <= END], loan.installment)
        per.append({
            "merchant_id": mid, "merchant": m.owner, "shop": m.shop, "lang": m.lang,
            "reason": c and c.reason, "state": c.state if c else "area alert", "accepted": c and c.accepted,
            "human": bool(c and c.human), "area_alert": mid in in_alert, "planned": bool(c and c.planned),
            "with": a, "without": b, "pay_ahead": pa,
            "messages_sent": sum(1 for cc in cases for x in cc.messages if x.dir == "out" and x.status == "sent"),
            "proactive_sent": sum(1 for cc in cases for x in cc.messages
                                  if x.dir == "out" and x.status == "sent" and x.proactive),
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
        "flagged": len(per), "with": agg("with"), "without": agg("without"), "pay_ahead": agg("pay_ahead"),
        "relief_accepted": sum(1 for p in per if p["accepted"]),
        "relief_value": sum((c.accepted_terms or {}).get("paused_total") or (c.accepted_terms or {}).get("deferred_total") or 0
                            for c in w.cases.values() if c.accepted and c.accepted != "PAYAHEAD"),
        "area_alerts": [{"area": a["area"], "shops": len(a["merchants"]), "date": a["date"].isoformat(),
                         "approved": bool(a["approved"])} for a in w.alerts.values()],
        "planned_ahead": sum(1 for p in per if p["planned"]),
        "handed_to_person": sum(1 for p in per if p["human"]),
        "proactive_messages": sum(p["proactive_sent"] for p in per),
        "messages_sent": sum(p["messages_sent"] for p in per),
        "still_overdue_with": [{"merchant": p["merchant"], "state": p["state"], "reason": p["reason"]}
                               for p in per if p["with"]["overdue_days"] > 0],
        "violations": v, "per_merchant": per,
        "note": "Synthetic merchants. Same sales replayed with and without Sambhal. Individual cases handed to a "
                "person are counted with no relief, though staff would usually help: a conservative comparison. "
                "Area alerts assume the lender approves the area pause the next morning.",
    }
