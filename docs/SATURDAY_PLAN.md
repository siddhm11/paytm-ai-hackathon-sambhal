# Finale day plan (Sat 31 Oct)

The product is built: merchant app, the 10-step story, beyond-Ravi steps, pay-ahead, promise, neighbourhood
alerts, staff actions and the lender what-if. Saturday is for proving it works on their network, rehearsing, the
video and the deck. **No new features after 1 pm.**

| Time | Block | Done when |
|---|---|---|
| 9:00–9:45 | Arrive, set up, `python scripts/check_keys.py` on venue wifi **and** on hotspot | Both pass, or you know which one to use |
| 9:45–10:30 | Full run-through, out loud, with a timer: steps 0–9 | Under 3 minutes |
| 10:30–11:00 | Beyond Ravi (10–13) and the what-if, out loud | Under 1 minute |
| 11:00–1:00 | Mentor: "What would a lender push back on?" Fix copy or numbers only, `pytest -q` green | Noted and fixed |
| 1:00 | **Feature freeze** | |
| 1:00–2:00 | Lunch; Kannada and Hindi lines checked by a native speaker | Any fixes in `app/replies.py`, then `python scripts/warm_voice_cache.py` again |
| 2:00–3:00 | Record the demo video (`docs/VIDEO_SHOTLIST.md`) | Uploaded |
| 3:00–4:00 | Deck: final screenshots if anything changed | Exported |
| 4:00 → | Submit, rehearse twice (once Offline), present | |

## If something must change on the day

1. Edit, then `pytest -q` (all green) and `python scripts/run_evals.py`.
2. If any message text changed: `python scripts/warm_voice_cache.py` (needs the Sarvam key and internet).
3. Write it in `CHANGELOG.md` under "On the day".
