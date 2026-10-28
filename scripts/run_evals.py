"""Print the scenario suite and the with/without replay:  python scripts/run_evals.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from app import evals, replay  # noqa: E402

r = evals.run_all()
group = None
for x in r["results"]:
    if x["group"] != group:
        group = x["group"]
        print(f"\n{group}")
    print(f"  {'PASS' if x['ok'] else 'FAIL'}  {x['id']}  {x['title']}")
    if not x["ok"]:
        print("        ", x["error"] or [c for c in x["checks"] if not c["ok"]])
print(f"\n{r['passed']}/{r['total']} passed in {r['ms']} ms")

p = replay.run()
w, o = p["with"], p["without"]
print(f"\nReplay, {p['flagged']} of {p['merchants_total']} merchants flagged ({p['window'][0]} to {p['window'][1]})")
print(f"  {'':34}{'with':>8}{'without':>10}{'pay-ahead*':>12}")
for label, k in [("Merchants who fell overdue", "merchants_overdue"), ("Merchant-days overdue", "overdue_days"),
                 ("Merchants 3+ days overdue", "merchants_dpd_3plus"),
                 ("Biggest deduction (median, x inst.)", "median_peak_multiple")]:
    print(f"  {label:34}{w[k]:>8}{o[k]:>10}{p['pay_ahead'][k]:>12}")
print(f"  Guardrail violations found by audit: {len(p['violations'])} across {p['messages_sent']} messages")
for a in p["area_alerts"]:
    print(f"  Neighbourhood alert: {a['area']}, {a['shops']} shops on {a['date']} (area pause approved: {a['approved']})")
print("  * pay-ahead only: the plain loan with pay-ahead on since the loan began; assumes everyone opts in (upper bound)")
sys.exit(0 if r["passed"] == r["total"] and not p["violations"] else 1)
