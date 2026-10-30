# Changelog

## Before the event (built 28-30 Oct 2026; pre-built code confirmed allowed by the organisers)
- Synthetic world: 50 merchants, loans, daily settlements; Ravi's week as the demo story
- Daily-deduction ledger, early-warning rule, lender policy engine, RBI guardrails
- Multilingual understanding (Kannada, Hindi, English, romanised) with optional LLM; approved templates
- Sarvam speech-to-text and text-to-speech with audio cache
- Merchant phone + lender console UI, presenter mode, loan right-sizer
- 40 scenario checks, with/without replay with independent audit, 62 tests
- 29 Oct fixes: server failed to start on Python 3.9; a reply with a question, "not" or "but" can no longer
  count as Accept; new "needs more time" reading (routes to lender staff, offer stays open); festivals, "no",
  "not now", "loss" understood offline; fonts bundled (no internet needed to load the page); LLM token limit
  raised for reasoning models; both Sarvam auth headers sent. 80 tests
- 29 Oct, first run with a real Sarvam key: voice out, voice in and the LLM all pass. Fixes from it: the model's
  thinking step is off (0.5 s per reply instead of 6-9 s, and no empty answers); day counts come from code, not
  the model (it read Friday "till Sunday" as 2 days); background shops' scripted replies use the rules, so
  stepping through the week makes 1 AI call instead of 15; tests never touch the network. 48 demo voice lines
  cached. 83 tests
- 29 Oct, merchant app and stage flow: the phone is now an app with Home, Messages and My loan screens in the
  merchant's language; voice-note bubbles; one-tap reasons (each tested to read correctly in kn/hi/en); offers
  show a day-by-day preview; "talk to a person" always works; 14-day deduction calendar. Each presenter step opens
  the right screens and highlights what to point at; step 7 has a payoff card; caption bar stays on screen; Big
  text mode; welcome card. 112 tests
- 29 Oct, prepare and beyond Ravi:
  - Pay-ahead: on good days a little goes towards future installments; on a short day it pays first. Offered after
    recovery (new step 9 "Prepare"); Ravi's what-if shows ₹3,800 paid ahead would have covered the wedding. The
    replay gains a "pay-ahead only" column (labelled as an upper bound).
  - Sambhal's promise: six promises in kn/hi/en, read aloud, each mapped to its rule and the checks that prove it.
    Consent can be switched off and on in the app.
  - Tell us first: a merchant plans a closure (reason + dates) and the lender's pause is booked for those days.
  - Trust, then check: normal sales on a paused day end the pause early and shrink the catch-up.
  - Neighbourhood alerts: many shops in one area down together → no check-ins there, one lender decision (area
    pause). New demo shops: Shobha (M42) and eight in Bellandur (M43-M50), replacing the last background slots so
    the total stays 50.
  - Staff actions for cases with a person (approve a staff-only option, resolve a grievance, clear a review, log a
    call), inside the same rules (no calls at night or in a bereavement).
  - Lender what-if: change the relief menu and replay the same 50 merchants before it goes live.
  - Fixes: a question or setting the merchant started used to leave a case open that hid later early-warning
    flags; 9 loans started before the sales history and showed phantom missed payments (could fail eligibility).
  - Replay now: 29 of 50 flagged; with Sambhal 5 overdue, without 22; 0 violations in 73 messages. 125 tests.
- 29 Oct, end-to-end voice test (`scripts/check_mic.py`: a recorded Kannada reply played into the app's own mic
  button). Found and fixed: Sarvam rejected every browser recording (`audio/webm;codecs=opus` label); with hint
  words, Sarvam returned "ಕಂತು" for silence and the agent closed Ravi's case on it (hints removed: silence is now
  empty and the app asks to try again); the model sometimes read the wedding line as "shop closed" (an explicit
  hardship keyword now outranks a vaguer reading). Now: Ravi's line, an off-script fever reply and "okay, but why
  only 3 days?" are all heard word for word in ~0.3 s and handled correctly. 126 tests.
- 29 Oct, Sambhal's own voice, checked by ear: a Wispr Flow listening test, confirmed with Sarvam speech-to-text on
  the clean files, found the Kannada voice speaking ₹850 as 800 (any amount ending in fifty), "rupees" in English,
  Hindi lines cut off before the end, and "सब ठीक है?" sounding like a statement. Fixed: amounts spoken in Kannada
  words with ರೂಪಾಯಿ, sentence-by-sentence speech, क्या in Hindi questions, "Sambhaal" for the English voice;
  `warm_voice_cache.py` listens back to every line and remakes faulty ones (`--remake kn,en`); on a 402 (no
  credits) the app falls back to saved audio, browser speech and rules instead of failing. Audio not yet
  regenerated: Sarvam credits ran out during testing. 145 tests.
- 29 Oct: the name is spelled संभाल / ಸಂಭಾಲ್ in Hindi and Kannada, as in the deck. `warm_voice_cache.py --story`
  makes only the 28 lines the presenter can play (Ravi, Shobha, Bellandur, Ravi's replies, the Kannada promise);
  all 28 regenerated and pass listening back. The checker now reads Kannada number words, not just digits (six
  first-pass "wrong amount" flags were the checker's, not the voice's); one genuinely misspoken amount (₹182
  heard as 152) was remade. 146 tests.
- 29 Oct, second Wispr listening test on the regenerated Kannada: every amount heard right (₹850, ₹2,550, ₹182,
  ₹1,032, ₹6,000, ₹100) and ಕಂತಿಗೆ heard correctly. New finds, fixed in what the voice is given: "ಅಕ್ಟೋಬರ್ 23–25"
  was heard as "23 and 25" (the dash is silent, so Saturday sounds deducted) -> spoken "ಇಪ್ಪತ್ತಮೂರರಿಂದ
  ಇಪ್ಪತ್ತೈದರವರೆಗೆ" (Hindi "से", English "to"); case endings join the number ("ಎಂಟರಿಂದ", "ಇಪ್ಪತ್ತಾರರವರೆಗೆ");
  "+" was read as English "plus" -> ಮತ್ತು / और; "ಸಂಭಾಲ್ · ಈ" ran together into "ಸಂಭಾಷಣಾ" -> a full stop after the
  name. 156 tests. Remade on free credit (~₹5): the 5 lines the presenter plays with a date range (Ravi's offer
  and confirmation, Shobha's offer and confirmation, the Bellandur notice). Still the older audio, by choice:
  4 lines with only "+", 2 with only the header pause, 4 that play only if a quick-reply chip is tapped.
- 31 Oct, 2 am, third Wispr listening test on those 5 lines: all 5 date ranges heard as "from X to Y"
  (23ರಿಂದ 25ರವರೆಗೆ, 30ರಿಂದ 1ರವರೆಗೆ, 29ರಿಂದ 31ರವರೆಗೆ), every amount right (₹2,550, ₹182, ₹850, ₹1,680, ₹120,
  ₹560, ₹3,300, ₹235), "+" heard as ಮತ್ತು, the name never mistaken for ಸಂಭಾಷಣಾ. Story audio frozen; a copy
  of data/tts_cache (not in git) is in ../tts_cache_backup_31oct.

## On the day (31 Oct 2026)
- 
