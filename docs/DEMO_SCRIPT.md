# Demo cue cards (3 minutes, +1 minute "beyond Ravi" if there's time)

Cue points to talk from, not lines to memorise. → advances a step. Each step opens the right phone screen and
console panel by itself and briefly highlights what to point at (gold glow), so you never hunt for a tab.
Tick **Big text** in the header on a projector.

**Before you start:** server running, browser at `localhost:8000`, **Reset** pressed, welcome card closed, volume
up, phone hotspot ready. Header chips should say *Voice: Sarvam* and *AI: sarvam-105b* (or flip **Offline**).
`python scripts/check_mic.py` passed on this network (then Reset). Speak close to the laptop; if the room is loud,
use the 🎙 shortcut instead.

| Step | Glows on | Say (cue points) |
|---|---|---|
| 0 Meet Ravi | Phone home | Kirana, ₹850 a day from his settlement, 71 in a row, never missed. Paytm sees his sales every evening. A bank doesn't. This is his app, in Kannada. |
| 1 Wed | Last-settlement card | One slow day, 48%. Sambhal does nothing. "Not every dip is a crisis." |
| 2 Thu 9 pm | Guardrails, contact hours | Two days below half → case opened **before anything is missed**. It's 9 pm: RBI window is 8–7, so the code holds it. |
| 3 Fri 8 am | Voice note | Kannada, voice. Recording notice, grievance officer. Help, not a demand. One-tap reasons for merchants who'd rather not type. |
| 4 Ravi replies | How Sambhal read it | Speak the line (or tap the 🎙 shortcut). "Wedding at home, shut till Sunday." Family function, 3 days: **the days come from code, not the AI**. |
| 5 Accept | Deduction calendar | The pause comes from the lender's menu file. Fri–Sun paused, ₹1,032 from Monday. Quiet until Monday. |
| 6 Weekend | With vs without | Nothing deducted, nothing overdue, no messages. |
| 7 Monday | Payoff card | **₹1,032 vs ₹3,400.** 17% vs 57% of his sales. Never overdue vs 3 days on his record. |
| 8 Tuesday | Audit log | Recovered, case closed, every decision logged. The closing message offers pay-ahead. |
| 9 Prepare | Third payoff box | Pay-ahead: ₹100 on days he sells ₹6,000+. Had it been on, ₹3,800 would have covered the wedding by itself. "We don't just get him through the bad week. We get him ready for the next one." |

**Close (one line):** Sambhal starts where the risk score stops: the conversation, the fix, proof it worked, and
a merchant ready for the next bad week.

### Beyond Ravi (optional, ~1 minute)

| Step | Say |
|---|---|
| 10 Shobha | She told us *before* the wedding: picked Fri–Sun in the app. Pause booked, no alarm, no check-in. |
| 11 Bellandur | Eight shops down together, the rest of the city normal. A local event, not eight problems: no reminders, one decision. **Only Paytm sees this.** |
| 12 Approve | One click, from the lender's own menu. The notice waits until sales recover. |
| 13 Trust, then check | Shobha reopened on Sunday. Sunday is collected as usual, her catch-up shrinks to the two days she was really shut. |

Then, if asked: **Lender what-if** tab → set "pause up to" to 2 → 5 overdue becomes 13. "Lenders tune the menu
with evidence before it goes live."

## If a judge asks… (cue points)

* **"Isn't this a collections bot?"** It acts before the miss; collections start after. It tells the lender to back off: show Lakshmi (staff can't even call), or Bellandur.
* **"Paytm already has risk scores."** A score says *who*. Sambhal finds out *why* (the wedding), offers the lender's fix, proves recovery, and helps the merchant prepare (pay-ahead).
* **"What if the AI says something wrong?"** The LLM never decides amounts or days. "Yes" only counts without a question or "not". If it rephrases, the check rejects new numbers or threats. Show V01–V05 and the promise panel on the Proof tab.
* **"What about fraud?"** Imran: sales collapse but "all fine" → review, no relief. Shobha: a "closed" shop with normal sales gets its pause cut short.
* **"Isn't pay-ahead just taking money earlier?"** Yes, and that's the point: the same total, moved from his best days to cover his worst. It's his choice, off any time, installments paid early to the lender (not a deposit). The replay's pay-ahead column assumes everyone opts in, so it's an upper bound we'd test in a pilot.
* **"Who pays?"** Lending partners: fewer loans slipping past due, lower cost per case than a call centre, RBI's rules (1 Jan 2027) built in.
* **"What's real?"** Voice (Sarvam), understanding (Sarvam LLM), rules engine, ledger, tests are real and were tested live. Merchants and the settlement feed are synthetic. Say it plainly.
* **"How would you pilot it?"** Merchants with Sambhal vs similar merchants without. Measure: overdue rate, biggest deduction, complaints, cost per case, pay-ahead uptake, violations (target 0).

## If something breaks

| Problem | Do this |
|---|---|
| Wifi dies | Flip **Offline** in the header. Rules + templates + cached audio carry the whole story. |
| Mic doesn't hear | Tap the 🎙 Ravi shortcut under the phone (presenter shortcuts). |
| No sound | Read the English line under the bubble; keep going. |
| Page stuck | Reset, then click step dot 7 (it replays instantly). |
