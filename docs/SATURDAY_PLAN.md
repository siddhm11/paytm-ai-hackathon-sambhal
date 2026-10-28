# Finale day plan (31 Oct)

The core product is built. Saturday is for proving it works on their network, one visible upgrade,
the video and the deck. Don't start anything new after 3:30 pm.

| Time | Block | Done when |
|---|---|---|
| 9:00–10:00 | Arrive, set up, `python scripts/check_keys.py` on venue wifi **and** on hotspot | Both pass, or you know which one to use |
| 10:00–10:30 | Full run-through of the 9 steps, out loud, with a timer | Under 3 minutes |
| 10:30–1:00 | **One upgrade** (pick from the list below), committed and tested | `pytest -q` green |
| 1:00–1:30 | Lunch + mentor: "What would a lender push back on?" | One change noted |
| 1:30–3:30 | Second upgrade **or** polish from mentor feedback | `pytest -q` green, pushed |
| 3:30 | **Feature freeze** | |
| 3:30–4:30 | Record the demo video (`docs/VIDEO_SHOTLIST.md`) | Uploaded |
| 4:30–5:30 | Deck: real screenshots, "what's real / simulated", replay numbers | Exported |
| 5:30 → | Submit, rehearse once, present | |

## Upgrades to pick from (biggest effect first)

1. **Staff console action (≈1.5 h).** In the lender console, cases "with a person" get an *Approve 7-day pause*
   button. Staff approval writes the terms and Sambhal sends the confirmation. Closes the loop on human handoff.
2. **Lender settings page (≈1.5 h).** Edit `lender_policy.json` from the UI (max days, catch-up days,
   eligibility) and watch offers change. Shows it's configurable per lending partner.
3. **LLM rephrasing on stage (≈30 min).** Set `LLM_REWRITE=1`, re-warm the voice cache, show the violet
   "AI-phrased · checked" tag and one rejected draft in the audit log.
4. **Tamil and Telugu (≈1 h).** Add templates + keywords; Sarvam already speaks both.
5. **Public URL (≈45 min).** Deploy to Render or Railway so judges can open it after the demo.
