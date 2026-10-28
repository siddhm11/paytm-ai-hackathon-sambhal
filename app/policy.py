"""Policy engine: which relief the lender allows, and the exact maths.

The agent can only offer what `eligible_options` returns. Terms are computed
here in code; the language model only ever sees the finished numbers.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from statistics import median

from .config import DATA_DIR
from .data import money
from .ledger import catchup_split


@lru_cache(maxsize=1)
def load_policy() -> dict:
    return json.loads((DATA_DIR / "lender_policy.json").read_text(encoding="utf-8"))


def option(opt_id: str) -> dict | None:
    return next((o for o in load_policy()["options"] if o["id"] == opt_id), None)


def check(opt: dict, loan, state, today: date) -> list[str]:
    """Return the reasons this loan fails the option's eligibility (empty = eligible)."""
    e = opt["eligibility"]
    fails = []
    age = (today - loan.disbursed_on).days
    if age < e["min_loan_age_days"]:
        fails.append(f"loan is {age} days old (needs {e['min_loan_age_days']})")
    if state.dpd > e["max_dpd"]:
        fails.append(f"{state.dpd} days overdue (max {e['max_dpd']})")
    if state.paid_ratio < e["min_paid_ratio"]:
        fails.append(f"paid on time {state.paid_ratio:.0%} of days (needs {e['min_paid_ratio']:.0%})")
    w = e.get("no_relief_within_days", 0)
    recent = [r for r in loan.relief_history if (today - r).days < w]
    if w and recent:
        fails.append(f"already had relief on {recent[-1].strftime('%d %b')} (once per {w} days)")
    return fails


def eligible_options(loan, state, reason: str, today: date) -> dict:
    """Split the menu for this reason into: offer now / blocked (with why) / for a person to decide."""
    pol = load_policy()
    offer, blocked, human = [], [], []
    for opt in pol["options"]:
        if reason not in opt["reasons"]:
            continue
        fails = check(opt, loan, state, today)
        if opt["requires_human"]:
            (human if not fails else blocked).append({"id": opt["id"], "why": fails})
        elif fails:
            blocked.append({"id": opt["id"], "why": fails})
        else:
            offer.append(opt["id"])
    return {"offer": offer[: pol["max_options_per_message"]], "blocked": blocked, "human": human}


def terms(opt_id: str, loan, start: date, days: int | None = None) -> dict:
    """Exact terms for an option starting on `start` (first day with no/low deduction)."""
    opt = option(opt_id)
    inst = loan.installment
    if opt["kind"] == "pause":
        n = max(1, min(days or opt["max_days"], opt["max_days"]))
        pause_dates = [start + timedelta(days=k) for k in range(n)]
        paused_total = inst * n
        catch_start = pause_dates[-1] + timedelta(days=1)
        split = catchup_split(paused_total, opt["repay_over_days"])
        schedule = {catch_start + timedelta(days=k): amt for k, amt in enumerate(split)}
        return {
            "option": opt_id, "kind": "pause", "pause_dates": pause_dates, "days": n,
            "paused_total": paused_total, "catchup_start": catch_start,
            "catchup_days": opt["repay_over_days"], "catchup_per_day": split[0],
            "catchup_last": split[-1], "catchup": schedule, "installment": inst,
            "first_day_after": inst + split[0],
        }
    if opt["kind"] == "reduce":
        n = opt["days"]
        low = int(round(inst * opt["fraction"]))
        deferred = (inst - low) * n
        extra_days = -(-deferred // inst)
        return {
            "option": opt_id, "kind": "reduce", "start": start, "days": n, "reduced_installment": low,
            "deferred_total": deferred, "extra_days": extra_days, "installment": inst,
            "reduced_dates": [start + timedelta(days=k) for k in range(n)],
        }
    raise ValueError(f"unknown option kind {opt['kind']}")


def apply(loan, t: dict, today: date) -> None:
    """Write accepted terms into the loan's adjustment calendar."""
    if t["kind"] == "pause":
        for d in t["pause_dates"]:
            loan.adjustments.setdefault(d, {})["paused"] = 1
        for d, amt in t["catchup"].items():
            loan.adjustments.setdefault(d, {})["catchup"] = amt
    elif t["kind"] == "reduce":
        for d in t["reduced_dates"]:
            loan.adjustments.setdefault(d, {})["installment"] = t["reduced_installment"]
        loan.tenure_days += t["extra_days"]
    loan.relief_history.append(today)


def pay_ahead(loan, sales: dict, today: date) -> dict | None:
    """Suggested pay-ahead settings from the merchant's own last 8 weeks: a 'good day' is one above their usual
    (median) open day; the amount is about an eighth of the installment."""
    cfg = load_policy().get("pay_ahead") or {}
    if not cfg.get("enabled"):
        return None
    days = [sales.get(today - timedelta(days=k), 0) for k in range(1, cfg["lookback_days"] + 1)]
    open_days = [v for v in days if v > 0]
    if not open_days:
        return None
    threshold = int(round(median(open_days) / 100) * 100)
    step = cfg["round_to"]
    amount = max(step, int(round(loan.installment * cfg["share_of_installment"] / step) * step))
    good = sum(1 for v in days[:28] if v >= threshold)
    return {"threshold": threshold, "amount": amount, "good_days_4w": good, "per_4w": good * amount}


def facts(t: dict) -> dict:
    """Numbers a message about these terms may contain (for templates and the output check)."""
    f = {"installment": money(t["installment"])}
    if t["kind"] == "pause":
        d0, d1 = t["pause_dates"][0], t["pause_dates"][-1]
        f.update(pause_from=d0, pause_to=d1, days=t["days"], paused=money(t["paused_total"]),
                 per_day=money(t["catchup_per_day"]), catchup_days=t["catchup_days"],
                 start=t["catchup_start"], first_day=money(t["first_day_after"]))
    else:
        f.update(start=t["start"], days=t["days"], half=money(t["reduced_installment"]),
                 deferred=money(t["deferred_total"]), extra_days=t["extra_days"])
    return f
