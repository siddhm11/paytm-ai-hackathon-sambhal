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

## On the day (31 Oct 2026)
- 
