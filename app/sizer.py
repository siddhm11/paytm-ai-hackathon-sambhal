"""Loan right-sizer: test a daily installment against the merchant's own worst weeks before the loan."""
from __future__ import annotations

from datetime import date, timedelta
from statistics import median

from .data import money
from .replies import WEEKDAYS, fdate

FEE_PER_180_DAYS = 0.125     # illustrative flat pricing, same as the demo loans
SAFE_SHARE = 0.20            # installment should stay under 20% of the worst week's sales
TIGHT_SHARE = 0.30
LOOKBACK_DAYS = 84           # 12 weeks

LINE = {
    "en": "On your slowest {weekday} in the last 12 weeks you sold ₹{sales}. After the ₹{inst} installment you'd keep ₹{keep}.",
    "hi": "पिछले 12 हफ़्तों में आपके सबसे कम बिक्री वाले {weekday} को ₹{sales} की बिक्री हुई। ₹{inst} की किस्त के बाद आपके पास ₹{keep} बचते।",
    "kn": "ಕಳೆದ 12 ವಾರಗಳಲ್ಲಿ ನಿಮ್ಮ ಅತಿ ಕಡಿಮೆ ವ್ಯಾಪಾರದ {weekday} ದಿನ ₹{sales} ಮಾರಾಟವಾಗಿತ್ತು. ₹{inst} ಕಂತಿನ ನಂತರ ನಿಮ್ಮ ಬಳಿ ₹{keep} ಉಳಿಯುತ್ತಿತ್ತು.",
}


def installment_for(amount: int, tenure_days: int) -> int:
    return int(round(amount * (1 + FEE_PER_180_DAYS * tenure_days / 180) / tenure_days))


def max_amount_for(installment: float, tenure_days: int, step: int = 5000) -> int:
    raw = installment * tenure_days / (1 + FEE_PER_180_DAYS * tenure_days / 180)
    return int(raw // step * step)


def size(sales: dict, today: date, amount: int, tenure_days: int, lang: str = "en") -> dict:
    days = [today - timedelta(days=k) for k in range(LOOKBACK_DAYS, 0, -1)]
    vals = [sales.get(d, 0) for d in days]
    weeks = [sum(vals[i:i + 7]) for i in range(0, len(vals) - 6)]
    worst_week, typical_week = min(weeks), median(weeks)
    open_days = [(d, v) for d, v in zip(days, vals) if v > 0]
    worst_day, worst_val = min(open_days, key=lambda x: x[1])
    closed = len(vals) - len(open_days)
    inst = installment_for(amount, tenure_days)
    share = inst * 7 / worst_week if worst_week else 1.0
    verdict = "comfortable" if share <= SAFE_SHARE else ("tight" if share <= TIGHT_SHARE else "risky")
    safe_inst = SAFE_SHARE * worst_week / 7
    suggest = max_amount_for(safe_inst, tenure_days)
    keep = worst_val - inst
    lang = lang if lang in LINE else "en"
    f = {"weekday": WEEKDAYS[lang][worst_day.weekday()] if lang != "en" else worst_day.strftime("%A"),
         "sales": money(worst_val), "inst": money(inst), "keep": money(keep)}
    return {
        "amount": amount, "tenure_days": tenure_days, "installment": inst, "total": inst * tenure_days,
        "worst_week_sales": worst_week, "typical_week_sales": round(typical_week),
        "share_of_worst_week": round(share, 3), "share_of_typical_week": round(inst * 7 / typical_week, 3),
        "verdict": verdict, "safe_share": SAFE_SHARE, "suggested_max": suggest,
        "worst_day": {"date": worst_day.isoformat(), "label": fdate(worst_day, "en", weekday=True), "sales": worst_val,
                      "keep": keep},
        "closed_days": closed, "line": LINE[lang].format(**f), "line_en": LINE["en"].format(
            **{**f, "weekday": worst_day.strftime("%A")}),
        "weekly": [{"end": days[i + 6].isoformat(), "sales": w} for i, w in enumerate(weeks)][::7],
        "pricing_note": "Illustrative pricing: flat 12.5% per 180 days, same as the demo loans.",
    }
