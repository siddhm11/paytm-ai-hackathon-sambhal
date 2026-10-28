"""Early-warning rule: plain, explainable, testable.

AMBER: sales below half of this shop's normal for that weekday, two days running.
RED:   an installment was not fully collected (something is overdue).
SHARP: today, or the two-day average, below 20% of normal (shop shut, or sales moved
       to another QR; only the merchant's answer tells which).
"""
from __future__ import annotations

from datetime import date, timedelta

from .data import same_weekday_baseline

LOW = 0.50
SHARP = 0.20


def ratio(sales: dict, d: date) -> float:
    b = same_weekday_baseline(sales, d)
    return 1.0 if b <= 0 else sales.get(d, 0) / b


def evaluate(sales: dict, loan, state, d: date) -> dict | None:
    r1, r0 = ratio(sales, d - timedelta(days=1)), ratio(sales, d)
    day0, day1 = d.strftime("%a"), (d - timedelta(days=1)).strftime("%a")
    base = {"date": d, "ratios": {day1: round(r1, 2), day0: round(r0, 2)},
            "baseline": round(same_weekday_baseline(sales, d)), "sharp": r0 < SHARP or (r0 + r1) / 2 < SHARP}
    if state.arrears > 0:
        return {**base, "level": "red",
                "reason": f"Installment not fully collected: ₹{state.arrears:,} overdue ({state.dpd} day{'s' if state.dpd != 1 else ''})"}
    if r0 < LOW and r1 < LOW:
        return {**base, "level": "amber",
                "reason": f"Sales below half of normal two days running: {r1:.0%} {day1}, {r0:.0%} {day0}"}
    return None


def projection(sales: dict, loan, d: date, days: int = 3) -> dict:
    """If the last two days' level continues: what share of sales would the installment take?"""
    lvl = (ratio(sales, d) + ratio(sales, d - timedelta(days=1))) / 2
    out = []
    for k in range(1, days + 1):
        dd = d + timedelta(days=k)
        exp = same_weekday_baseline(sales, dd) * lvl
        out.append({"date": dd.isoformat(), "expected_sales": round(exp),
                    "installment_share": None if exp <= 0 else round(loan.installment / exp, 2)})
    normal = same_weekday_baseline(sales, d + timedelta(days=1))
    return {"level": round(lvl, 2), "days": out,
            "normal_share": round(loan.installment / normal, 2) if normal else None}
