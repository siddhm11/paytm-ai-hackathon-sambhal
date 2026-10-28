"""Daily-deduction loan mechanics. Pure functions, no I/O.

How merchant loans repaid from settlements behave: each evening the day's due
amount (installment + any catch-up + any unpaid arrears) is deducted from the
day's settlement. If sales don't cover it, the shortfall carries forward and
the loan is overdue (days past due, DPD) until it is cleared.

Pay-ahead cushion (optional, the merchant's choice): on a day when sales reach
the merchant's threshold and nothing is owed, a small amount is paid towards
future installments. On a short day the cushion pays first, before anything can
become overdue. It is installments paid early to the lender, not a deposit.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class LoanState:
    arrears: int = 0          # unpaid amount carried forward
    dpd: int = 0              # consecutive days with arrears
    collected: int = 0
    due_days: int = 0         # days an installment was due
    clean_days: int = 0       # days that ended with nothing overdue
    missed_days: int = 0      # days that ended overdue
    max_dpd: int = 0
    cushion: int = 0          # installments paid ahead, not yet used
    cushion_added: int = 0
    cushion_used: int = 0

    @property
    def paid_ratio(self) -> float:
        return 1.0 if self.due_days == 0 else self.clean_days / self.due_days

    def copy(self) -> "LoanState":
        return LoanState(**self.__dict__)


def day_terms(loan, d: date, adjustments: dict | None = None) -> tuple[int, int, bool]:
    """(installment due, catch-up due, paused?) for day d."""
    adj = (adjustments if adjustments is not None else loan.adjustments).get(d, {})
    if adj.get("paused"):
        return 0, adj.get("catchup", 0), True
    inst = adj.get("installment", loan.installment)
    return inst, adj.get("catchup", 0), False


def run_day(loan, state: LoanState, d: date, sales: int, adjustments: dict | None = None,
            cushion: bool = True) -> dict:
    """Apply one day's deduction. Mutates state, returns the day's record.
    cushion=False replays the plain loan (no pay-ahead), for the 'without' comparison."""
    if d <= loan.disbursed_on:
        return {"date": d, "sales": sales, "due": 0, "deducted": 0, "arrears": state.arrears, "dpd": state.dpd,
                "installment": 0, "catchup": 0, "paused": False, "from_cushion": 0, "to_cushion": 0,
                "cushion": state.cushion}
    inst, catchup, paused = day_terms(loan, d, adjustments)
    due = inst + catchup + state.arrears
    deducted = min(due, max(sales, 0))
    short = due - deducted
    used = min(state.cushion, short) if cushion else 0          # a short day: the cushion pays first
    state.cushion -= used
    state.cushion_used += used
    state.arrears = short - used
    state.collected += deducted
    added = 0
    cs = loan.cushion if cushion else {}
    if cs.get("on") and state.arrears == 0 and sales >= cs["threshold"]:   # a good day: pay a little ahead
        added = min(cs["amount"], sales - deducted)
        state.cushion += added
        state.cushion_added += added
        state.collected += added
    if inst > 0 or catchup > 0:
        state.due_days += 1
        if state.arrears == 0:
            state.clean_days += 1
        else:
            state.missed_days += 1
    state.dpd = state.dpd + 1 if state.arrears > 0 else 0
    state.max_dpd = max(state.max_dpd, state.dpd)
    return {"date": d, "sales": sales, "due": due, "deducted": deducted, "arrears": state.arrears,
            "dpd": state.dpd, "installment": inst, "catchup": catchup, "paused": paused, "from_cushion": used,
            "to_cushion": added, "cushion": state.cushion}


def replay(loan, sales: dict, start: date, end: date, adjustments: dict | None = None,
           state: LoanState | None = None, cushion: bool = True) -> tuple[LoanState, list[dict]]:
    """Run days start..end inclusive. Uses loan.adjustments unless `adjustments` is given."""
    st = state.copy() if state else LoanState()
    rows = []
    d = start
    while d <= end:
        rows.append(run_day(loan, st, d, sales.get(d, 0), adjustments, cushion))
        d += timedelta(days=1)
    return st, rows


def catchup_split(total: int, days: int) -> list[int]:
    """Split a paused amount into `days` daily catch-ups; remainder on the last day.
    2,550 over 14 days -> 13 x 182 + 184."""
    if days <= 0:
        return []
    per = total // days
    out = [per] * days
    out[-1] += total - per * days
    return out
