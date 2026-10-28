"""Scenario suite: every guardrail and rule, replayed as a script with expected outcomes.

Each scenario builds a fresh world, runs its steps, and checks the result.
Run with `python scripts/run_evals.py`, `pytest`, or the Proof tab in the app.
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime

from . import guardrails, nlu, policy, replies, signals, sizer
from .config import DATA_DIR
from .world import World

SUBJECT = "M01"


def load() -> list[dict]:
    return json.loads((DATA_DIR / "scenarios.json").read_text(encoding="utf-8"))


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _setup(w: World, setup: dict):
    m, loan, st = w.merchants[SUBJECT], w.loans[SUBJECT], w.states[SUBJECT]
    for k, v in setup.get("merchant", {}).items():
        setattr(m, k, v)
    for k, v in setup.get("loan", {}).items():
        if k == "relief_history":
            v = [date.fromisoformat(x) for x in v]
        if k == "disbursed_on":
            v = date.fromisoformat(v)
        setattr(loan, k, v)
    for k, v in setup.get("state", {}).items():
        setattr(st, k, v)


def _out_msgs(case):
    return [x for x in case.messages if x.dir == "out"] if case else []


def run_one(sc: dict) -> dict:
    t0 = time.perf_counter()
    w = World(use_llm=False)
    _setup(w, sc.get("setup", {}))
    ctx: dict = {}
    try:
        for s in sc["steps"]:
            do = s["do"]
            if "at" in s and do != "advance":
                w.now = max(w.now, _dt(s["at"]))
            if do == "advance":
                w.advance(_dt(s["to"]))
            elif do == "open_case":
                lvl = s.get("level", "amber")
                sig = {"date": w.now.date(), "ratios": {"Thu": 0.15 if s.get("sharp") else 0.40,
                                                         "Fri": 0.10 if s.get("sharp") else 0.35},
                       "baseline": 5700, "sharp": bool(s.get("sharp")), "level": lvl,
                       "reason": "Scenario trigger"}
                w.open_case(SUBJECT, sig)
            elif do == "inbound":
                ctx["intent"] = w.inbound(SUBJECT, s["text"])["intent"]
            elif do == "accept":
                ctx["accept"] = w.accept(SUBJECT, s["option"])
            elif do == "proactive":
                case = w.case_for(SUBJECT)
                m = w.merchants[SUBJECT]
                w.send(case, [("checkin", {"first": m.first_local, "first_en": m.first,
                                           "installment": str(w.loans[SUBJECT].installment)})],
                       kind="proactive", msg_kind="checkin")
            elif do == "terms":
                t = policy.terms(s["option"], w.loans[SUBJECT], date.fromisoformat(s["start"]), s.get("days"))
                ctx["terms"] = {**t, "catchup_sum": sum(t["catchup"].values()),
                                "catchup_start": t["catchup_start"].isoformat()}
            elif do == "validate":
                ctx["validator"] = guardrails.validate_draft(s["draft"], s["lang"], guardrails.numbers_in(s["template"]))
            elif do == "signal":
                d = date.fromisoformat(s["date"])
                sig = signals.evaluate(w.sales[SUBJECT], w.loans[SUBJECT], w.states[SUBJECT], d)
                ctx["signal"] = {"level": sig["level"] if sig else None, "reason": sig["reason"] if sig else None}
            elif do == "sizer":
                ctx["sizer"] = sizer.size(w.sales[SUBJECT], w.now.date(), s["amount"], s["tenure"])
            elif do == "nlu":
                ctx["nlu"] = nlu.read_rules(s["text"], w.merchants[SUBJECT].lang, w.now.date())
        case = w.case_for(SUBJECT)
        outs = _out_msgs(case)
        last = outs[-1] if outs else None
        if case:
            ctx["case"] = {"state": case.state, "human": case.human, "offered": case.offered,
                           "accepted": case.accepted, "stopped": case.stopped}
            ctx["case"]["offered_contains"] = case.offered
        if last:
            v = last.view()
            failed = [c for c in last.checks if not c["ok"]]
            ctx["last_out"] = {
                "status": last.status, "kind": last.kind, "lang": last.lang,
                "held_until": last.held_until.isoformat() if last.held_until else None,
                "header_has": v["header"], "footer_has": v["footer"],
                "failed_rule": failed[0]["rule"] if failed else (
                    "Grievance open" if last.status == "blocked" else None),
                "option0_has": last.options[0]["text_en"] if last.options else "",
            }
        ctx["out_count"] = len(outs)
        ctx["out_sent"] = sum(1 for x in outs if x.status == "sent")
        rows = [r for r in w.rows[SUBJECT] if r["date"] >= date(2026, 10, 21)]
        ctx["ded"] = {r["date"].isoformat(): r["deducted"] for r in rows}
        ctx["max_dpd"] = max((r["dpd"] for r in rows), default=0)
        checks = [_check(ctx, k, v) for k, v in sc["expect"].items()]
        ok = all(c["ok"] for c in checks)
        err = None
    except Exception as e:  # a crash is a failure, with the reason shown
        checks, ok, err = [], False, f"{type(e).__name__}: {e}"
    return {"id": sc["id"], "group": sc["group"], "title": sc["title"], "ok": ok, "checks": checks, "error": err,
            "ms": round((time.perf_counter() - t0) * 1000, 1)}


def _get(ctx: dict, path: str):
    cur = ctx
    head, _, rest = path.partition(".")
    if head == "ded":
        return ctx.get("ded", {}).get(rest)
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return KeyError
        cur = cur[p]
    return cur


def _check(ctx: dict, key: str, want) -> dict:
    for suffix, fn in (("_contains", lambda g, w: g is not KeyError and w in (g or [])),
                       ("_has", lambda g, w: g is not KeyError and w in (g or "")),
                       ("_not", lambda g, w: g is not KeyError and g != w),
                       ("_lt", lambda g, w: g is not KeyError and g < w)):
        if key.endswith(suffix) and not key.endswith("header_has") and not key.endswith("footer_has") \
                and not key.endswith("option0_has"):
            got = _get(ctx, key[: -len(suffix)])
            return {"key": key, "want": want, "got": _show(got), "ok": bool(fn(got, want))}
    got = _get(ctx, key)
    if key.endswith(("header_has", "footer_has", "option0_has")):
        return {"key": key, "want": want, "got": _show(got), "ok": got is not KeyError and want in (got or "")}
    return {"key": key, "want": want, "got": _show(got), "ok": got == want}


def _show(v):
    return "missing" if v is KeyError else v


def run_all() -> dict:
    t0 = time.perf_counter()
    res = [run_one(sc) for sc in load()]
    return {"total": len(res), "passed": sum(r["ok"] for r in res), "results": res,
            "ms": round((time.perf_counter() - t0) * 1000)}
