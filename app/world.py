"""The simulated world and the Sambhal agent.

A clock moves through days. Every evening at 9 pm settlements land and the
installment is deducted. The early-warning rule runs after each settlement.
When it fires, Sambhal opens a case and talks to the merchant, with every
outbound message passing the guardrails first.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from . import config, guardrails, llm, nlu, policy, replies, signals
from .data import TRANSLATIONS, build, money, same_weekday_baseline
from .ledger import LoanState, replay, run_day

OPEN_STATES = {"held", "waiting", "offered", "accepted", "with_person", "review", "grievance", "stopped", "declined"}
REASON_LABEL = {
    "family_event": "Family function", "illness": "Illness", "temporary_closure": "Shop closed for a while",
    "business_slow": "Business slow", "bereavement": "Bereavement", "medical_emergency": "Medical emergency",
}
INTENT_GLOSS = {
    "bereavement": "Says someone in the family has died.",
    "medical_emergency": "Says a family member is in hospital.",
    "stop_contact": "Asks us to stop messaging.",
    "dispute": "Says a deduction was wrong or already paid.",
    "request_waiver": "Asks to waive or reduce the dues.",
    "family_event": "Says there is a family function; shop affected.",
    "illness": "Says they are unwell.",
    "temporary_closure": "Says the shop is closed for a few days.",
    "business_slow": "Says business is slow.",
    "need_time": "Asks for more time to pay.",
    "business_normal": "Says business is normal, no problem.",
    "decline": "Says no thanks.",
    "accept": "Says yes.",
    "question": "Asks how much is left.",
    "unclear": "Reply not understood.",
}
LANG_NAME = {"kn": "Kannada", "hi": "Hindi", "en": "English"}
KIND_LABEL = {"checkin": "check-in", "offer": "offer", "confirm": "confirmation", "handoff": "handover message",
              "waiver_decline": "waiver reply", "dispute": "grievance acknowledgement", "stop_ack": "stop confirmation",
              "ack": "acknowledgement", "no_option": "not-eligible reply", "balance": "balance answer",
              "ask_reason": "clarifying question", "welcome_back": "recovery message",
              "more_time": "longer-pause request reply"}


@dataclass
class Message:
    id: int
    at: datetime
    dir: str                  # out | in
    lang: str
    text: str
    text_en: str
    kind: str
    status: str               # sent | held | blocked | received
    via: str = "text"         # text | voice | tap | system
    author: str = "template"  # template | llm | merchant
    held_until: datetime | None = None
    sent_at: datetime | None = None
    options: list = field(default_factory=list)
    checks: list = field(default_factory=list)
    nlu: dict | None = None
    draft: dict | None = None  # LLM draft and its check result
    proactive: bool = False
    simulated: bool = False
    held_once: datetime | None = None   # set if the message ever waited for the contact window
    held_reason: str | None = None

    def view(self) -> dict:
        return {
            "id": self.id, "at": self.at.isoformat(), "dir": self.dir, "lang": self.lang, "text": self.text,
            "text_en": self.text_en, "kind": self.kind, "status": self.status, "via": self.via,
            "author": self.author, "held_until": self.held_until.isoformat() if self.held_until else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None, "options": self.options,
            "checks": [{**c, "hold_until": c["hold_until"].isoformat() if c.get("hold_until") else None}
                       for c in self.checks],
            "nlu": self.nlu, "draft": self.draft,
            "held_once": self.held_once.isoformat() if self.held_once else None, "held_reason": self.held_reason,
            "header": replies.header(self.lang) if self.dir == "out" else None,
            "footer": replies.footer() if self.dir == "out" else None,
        }


@dataclass
class Case:
    id: str
    merchant_id: str
    opened_at: datetime
    trigger: dict | None
    state: str = "waiting"
    reason: str | None = None
    offered: list = field(default_factory=list)
    offered_terms: dict = field(default_factory=dict)
    accepted: str | None = None
    accepted_terms: dict | None = None
    relief_end: date | None = None
    quiet_until: datetime | None = None
    sensitive_until: datetime | None = None
    stopped: bool = False
    grievance: bool = False
    human: bool = False
    human_reason: str | None = None
    human_options: list = field(default_factory=list)
    review: bool = False
    proactive_sent: list = field(default_factory=list)
    last_inbound_at: datetime | None = None
    messages: list = field(default_factory=list)
    timeline: list = field(default_factory=list)
    verify_at: datetime | None = None
    closed_at: datetime | None = None
    outcome: str | None = None
    cards: list = field(default_factory=list)

    def last_inbound_recent(self, now: datetime, minutes: int) -> bool:
        return self.last_inbound_at is not None and timedelta(0) <= now - self.last_inbound_at <= timedelta(minutes=minutes)

    @property
    def is_open(self) -> bool:
        return self.state in OPEN_STATES


class World:
    def __init__(self, use_llm: bool | None = None, scripted_ravi: bool = False):
        self.use_llm_override = use_llm
        self.scripted_ravi = scripted_ravi
        self.reset()

    # ------------------------------------------------------------------ setup
    def reset(self):
        self.merchants, self.loans, self.sales = build()
        if self.scripted_ravi:
            self.merchants["M01"].script = {"text": RAVI_REPLY, "delay_min": 20, "accept": "first"}
        self.now = config.DEMO_START
        self.processed = self.now.date() - timedelta(days=1)  # settled through Tue 20 Oct
        self.states: dict[str, LoanState] = {}
        self.rows: dict[str, list] = {}
        for mid, loan in self.loans.items():
            st, rows = replay(loan, self.sales[mid], loan.disbursed_on + timedelta(days=1), self.processed)
            self.states[mid], self.rows[mid] = st, rows
        self.cases: dict[str, Case] = {}
        self.case_by_merchant: dict[str, str] = {}
        self.closed_cases: list[Case] = []
        self.outbox: list[tuple[datetime, str, int]] = []     # held messages: (release_at, case_id, msg_id)
        self.scripted: list[tuple[datetime, str, str, dict]] = []  # (at, merchant_id, action, payload)
        self.audit_log: list[dict] = []
        self.msg_seq = 0
        self.case_seq = 0
        self.step = 0

    @property
    def use_llm(self) -> bool:
        return llm.available() if self.use_llm_override is None else (self.use_llm_override and llm.available())

    # ------------------------------------------------------------------ helpers
    def audit(self, mid: str, rule: str, decision: str, detail: str, at: datetime | None = None):
        self.audit_log.append({"at": (at or self.now).isoformat(), "merchant_id": mid,
                               "merchant": self.merchants[mid].owner if mid in self.merchants else mid,
                               "rule": rule, "decision": decision, "detail": detail})

    def case_for(self, mid: str) -> Case | None:
        cid = self.case_by_merchant.get(mid)
        return self.cases.get(cid) if cid else None

    def note(self, case: Case, text: str, kind: str = "info"):
        case.timeline.append({"at": self.now.isoformat(), "text": text, "kind": kind})

    def today_deduction_date(self) -> date:
        """First day whose deduction is still ahead (deduction runs at 9 pm)."""
        return self.now.date() if self.now.time() < config.SETTLEMENT_TIME else self.now.date() + timedelta(days=1)

    # ------------------------------------------------------------------ clock
    def next_event_time(self) -> datetime:
        times = [datetime.combine(self.processed + timedelta(days=1), config.SETTLEMENT_TIME)]
        times += [t for t, _, _ in self.outbox]
        times += [t for t, _, _, _ in self.scripted]
        times += [c.verify_at for c in self.cases.values() if c.verify_at]
        return min(times)

    def advance(self, to: datetime):
        guard = 0
        while guard < 10000:
            guard += 1
            settle_at = datetime.combine(self.processed + timedelta(days=1), config.SETTLEMENT_TIME)
            events = [(settle_at, 0, "settle", None)]
            events += [(t, 1, "release", (cid, mid)) for t, cid, mid in self.outbox]
            events += [(t, 2, "script", (mid, act, payload)) for t, mid, act, payload in self.scripted]
            events += [(c.verify_at, 3, "verify", c.id) for c in self.cases.values() if c.verify_at]
            t, _, kind, payload = min(events, key=lambda e: (e[0], e[1]))
            if t > to:
                break
            self.now = max(self.now, t)
            if kind == "settle":
                self.settle(self.processed + timedelta(days=1))
            elif kind == "release":
                self.outbox = [o for o in self.outbox if not (o[1] == payload[0] and o[2] == payload[1])]
                self.release(*payload)
            elif kind == "script":
                self.scripted = [s for s in self.scripted if not (s[0] == t and s[1] == payload[0] and s[2] == payload[1])]
                self.run_script(*payload)
            elif kind == "verify":
                self.verify(self.cases[payload])
        self.now = max(self.now, to)

    # ------------------------------------------------------------------ daily batch
    def settle(self, d: date):
        self.processed = d
        for mid, loan in self.loans.items():
            st = self.states[mid]
            row = run_day(loan, st, d, self.sales[mid].get(d, 0))
            self.rows[mid].append(row)
            case = self.case_for(mid)
            sig = signals.evaluate(self.sales[mid], loan, st, d)
            if case and case.is_open:
                self.watch_case(case, d, sig, row)
            elif sig:
                recent = [c for c in self.closed_cases if c.merchant_id == mid and c.closed_at
                          and self.now - c.closed_at < timedelta(days=7)]
                if not recent:
                    self.open_case(mid, sig)

    def watch_case(self, case: Case, d: date, sig: dict | None, row: dict):
        mid = case.merchant_id
        if case.state == "accepted" and case.relief_end and d > case.relief_end and not case.verify_at:
            r = signals.ratio(self.sales[mid], d)
            if r >= 0.8 and row["arrears"] == 0:
                case.verify_at = guardrails.next_contact_time(self.now) if not guardrails.in_hours(self.now) else self.now
                self.note(case, f"Sales back to {r:.0%} of normal on {d:%a %d %b}; deduction ₹{money(row['deducted'])} "
                                f"collected. Recovery check scheduled.", "good")
        if case.state == "waiting" and case.trigger and case.trigger.get("sharp") and not case.review:
            first_out = next((m.sent_at for m in case.messages if m.dir == "out" and m.sent_at), None)
            if first_out and self.now - first_out >= timedelta(hours=48) and not case.last_inbound_at:
                case.review, case.state, case.human = True, "review", True
                case.human_reason = "Sales nearly stopped and no reply in 48 hours: check for payments moved to another QR"
                self.note(case, case.human_reason, "warn")
                self.audit(mid, "Possible diversion", "review", case.human_reason)

    # ------------------------------------------------------------------ cases
    def open_case(self, mid: str, sig: dict | None, inbound: bool = False) -> Case:
        self.case_seq += 1
        m, loan = self.merchants[mid], self.loans[mid]
        case = Case(id=f"C{self.case_seq:03d}", merchant_id=mid, opened_at=self.now, trigger=sig)
        self.cases[case.id] = case
        self.case_by_merchant[mid] = case.id
        if inbound:
            self.note(case, "Merchant wrote to Sambhal.", "info")
            return case
        level = "Red" if sig["level"] == "red" else "Amber"
        self.note(case, f"{level} flag: {sig['reason']}.", "flag")
        self.audit(mid, "Early warning", "flagged", sig["reason"])
        if not m.consent:
            case.state, case.human = "with_person", True
            case.human_reason = "No messaging consent: a person at the lender should call during 8 am–7 pm"
            self.note(case, "No consent for Sambhal messages. Nothing sent; handed to a person.", "block")
            self.audit(mid, "Consent", "blocked", "Merchant did not opt in to Sambhal messages; case sent to a person")
            return case
        kind = "checkin_red" if sig["level"] == "red" else "checkin"
        facts = {"first": m.first_local if m.lang != "en" else m.first, "first_en": m.first, "installment": money(loan.installment), "arrears": money(self.states[mid].arrears)}
        self.send(case, [(kind, facts)], kind="proactive", msg_kind="checkin")
        return case

    def compose(self, case: Case, parts: list, lang: str) -> tuple[str, str, str, dict | None]:
        c = replies.compose(parts, lang)
        text, author, draft = c["text"], "template", None
        if self.use_llm and config.LLM_REWRITE:
            try:
                res = llm.chat_json(REWRITE_SYSTEM.format(lang=LANG_NAME[lang]), c["text"])
                cand = (res.get("text") or "").strip()
                chk = guardrails.validate_draft(cand, lang, guardrails.numbers_in(c["text"]))
                draft = {"text": cand, "ok": chk["ok"], "problems": chk["problems"]}
                if chk["ok"]:
                    text, author = cand, "llm"
                else:
                    self.audit(case.merchant_id, "AI message check", "rejected",
                               "LLM draft rejected (" + "; ".join(chk["problems"]) + "): approved template sent instead")
            except Exception as e:
                draft = {"text": None, "ok": False, "problems": [f"LLM unavailable: {str(e)[:80]}"]}
        return text, c["text_en"], author, draft

    def send(self, case: Case, parts: list, kind: str, msg_kind: str, options: list | None = None,
             lang: str | None = None) -> Message:
        m = self.merchants[case.merchant_id]
        lang = lang or m.lang
        text, text_en, author, draft = self.compose(case, parts, lang)
        self.msg_seq += 1
        msg = Message(id=self.msg_seq, at=self.now, dir="out", lang=lang, text=text, text_en=text_en, kind=msg_kind,
                      status="pending", author=author, options=options or [], draft=draft)
        msg.proactive = kind == "proactive"
        case.messages.append(msg)
        self.deliver(case, msg)
        return msg

    def deliver(self, case: Case, msg: Message):
        m = self.merchants[case.merchant_id]
        kind = "proactive" if msg.proactive else "reply"
        results = guardrails.check_outbound(case, m, self.now, kind)
        if case.grievance and kind == "proactive":
            results.append(guardrails.decide("Grievance open", False, "Reminders paused until the grievance is resolved",
                                             block=True))
        v = guardrails.verdict(results)
        msg.checks = results
        if v["action"] == "send":
            msg.status, msg.sent_at, msg.held_until = "sent", self.now, None
            if kind == "proactive":
                case.proactive_sent.append(self.now)
            if case.state == "held":
                case.state = "waiting"
            self.audit(case.merchant_id, "Outbound", "sent",
                       f"{msg.kind} in {LANG_NAME[msg.lang]} ({'AI-phrased, checked' if msg.author == 'llm' else 'template'})")
            self.after_sent(case, msg)
        elif v["action"] == "hold":
            msg.status, msg.held_until = "held", v["hold_until"]
            msg.held_once = v["hold_until"]
            msg.held_reason = v["failed"][0]["rule"]
            self.outbox.append((v["hold_until"], case.id, msg.id))
            if case.state == "waiting" and not any(x.status == "sent" for x in case.messages if x.dir == "out"):
                case.state = "held"
            why = "; ".join(r["why"] for r in v["failed"])
            self.note(case, f"Message held: {why}.", "hold")
            self.audit(case.merchant_id, v["failed"][0]["rule"], "held", why)
        else:
            msg.status = "blocked"
            why = "; ".join(r["why"] for r in v["failed"])
            self.note(case, f"Message blocked: {why}.", "block")
            self.audit(case.merchant_id, v["failed"][0]["rule"], "blocked", why)

    def release(self, case_id: str, msg_id: int):
        case = self.cases.get(case_id)
        if not case:
            return
        msg = next((x for x in case.messages if x.id == msg_id), None)
        if msg and msg.status == "held":
            self.deliver(case, msg)

    def after_sent(self, case: Case, msg: Message):
        m = self.merchants[case.merchant_id]
        self.note(case, f"Sent {KIND_LABEL.get(msg.kind, msg.kind)} in {LANG_NAME[msg.lang]}"
                        f"{' (AI-phrased, checked)' if msg.author == 'llm' else ''}.", "sent")
        if not m.script or case.merchant_id == "M01" and not self.scripted_ravi:
            return
        if msg.kind in ("checkin",) and not case.last_inbound_at:
            at = self.now + timedelta(minutes=m.script.get("delay_min", 30))
            self.scripted.append((at, case.merchant_id, "reply", {"text": m.script["text"]}))
        if msg.kind == "offer" and m.script.get("accept") and case.offered:
            want = m.script["accept"]
            opt = case.offered[0] if want == "first" else (want if want in case.offered else None)
            if opt:
                self.scripted.append((self.now + timedelta(minutes=6), case.merchant_id, "accept", {"option": opt}))

    def run_script(self, mid: str, action: str, payload: dict):
        if action == "reply":
            self.inbound(mid, payload["text"], via="voice", simulated=True)
        elif action == "accept":
            self.accept(mid, payload["option"], simulated=True)

    # ------------------------------------------------------------------ merchant input
    def inbound(self, mid: str, text: str, via: str = "text", simulated: bool = False) -> dict:
        m, loan, st = self.merchants[mid], self.loans[mid], self.states[mid]
        case = self.case_for(mid)
        if not case or not case.is_open:
            case = self.open_case(mid, None, inbound=True)
        today = self.now.date()
        reading = nlu.read(text, m.lang, today) if self.use_llm else nlu.read_rules(text, m.lang, today)
        indic = any("\u0900" <= c <= "\u097f" or "\u0c80" <= c <= "\u0cff" for c in text)
        lang = reading["language"] if indic else m.lang
        self.msg_seq += 1
        msg = Message(id=self.msg_seq, at=self.now, dir="in", lang=lang, text=text,
                      text_en=TRANSLATIONS.get(text.strip()) or reading.get("summary_en") or gloss(reading),
                      kind="reply",
                      status="received", via=via, author="merchant", nlu=reading, sent_at=self.now)
        msg.simulated = simulated
        case.messages.append(msg)
        case.last_inbound_at = self.now
        intent = reading["intent"]
        self.note(case, f"Merchant replied{' (simulated)' if simulated else ''}: {msg.text_en} "
                        f"[read as {intent.replace('_', ' ')} by {reading['source']}]", "in")
        self.audit(mid, "Understanding", intent, f"{reading['source']}: {msg.text_en}")
        self.respond(case, reading, lang)
        return {"case": case.id, "intent": intent}

    def offer_parts(self, case: Case, reason: str, days: int | None) -> tuple[list, list]:
        mid = case.merchant_id
        loan, st = self.loans[mid], self.states[mid]
        el = policy.eligible_options(loan, st, reason, self.now.date())
        case.human_options = el["human"]
        if not el["offer"]:
            return [], el["blocked"]
        start = self.today_deduction_date()
        parts, cards = [("offer_intro", {})], []
        case.offered, case.offered_terms = [], {}
        for oid in el["offer"]:
            t = policy.terms(oid, loan, start, days)
            f = policy.facts(t)
            k = "opt_pause" if t["kind"] == "pause" else "opt_reduce"
            parts.append((k, f))
            case.offered.append(oid)
            case.offered_terms[oid] = t
            opt = policy.option(oid)
            lang = self.merchants[mid].lang
            cards.append({"id": oid, "label": opt["label"][lang], "label_en": opt["label"]["en"],
                          "text": replies.line(k, lang, **f), "text_en": replies.line(k, "en", **f)})
        parts.append(("offer_close", {}))
        case.cards = cards
        return parts, el["blocked"]

    def respond(self, case: Case, r: dict, lang: str):
        mid = case.merchant_id
        m, loan, st = self.merchants[mid], self.loans[mid], self.states[mid]
        intent = r["intent"]
        say = lambda parts, k, **kw: self.send(case, parts, kind="reply", msg_kind=k, lang=lang, **kw)

        if intent in ("bereavement", "medical_emergency"):
            case.reason = intent
            case.sensitive_until = self.now + timedelta(days=14)
            case.state, case.human = "with_person", True
            case.human_reason = ("Bereavement" if intent == "bereavement" else "Medical emergency") + \
                ": all reminders stopped for 14 days; staff may offer the 7-day pause"
            self.cancel_held(case)
            el = policy.eligible_options(loan, st, intent, self.now.date())
            case.human_options = el["human"]
            self.note(case, case.human_reason + ".", "block")
            self.audit(mid, "Sensitive situation", "handed to a person", case.human_reason)
            say([("handoff_bereavement" if intent == "bereavement" else "handoff_medical", {})], "handoff")
            return
        if intent == "stop_contact":
            case.stopped, case.state, case.human = True, "stopped", True
            case.human_reason = "Merchant asked Sambhal to stop messaging"
            self.cancel_held(case)
            self.audit(mid, "Stop request", "stopped", "No further proactive messages")
            say([("stop_ack", {})], "stop_ack")
            return
        if intent == "dispute":
            case.grievance, case.state, case.human = True, "grievance", True
            case.human_reason = "Disputes a deduction: sent to the grievance officer; reminders paused"
            self.cancel_held(case)
            self.audit(mid, "Grievance", "routed", case.human_reason)
            say([("dispute", {})], "dispute")
            return
        if intent == "request_waiver":
            case.human = True
            case.human_reason = "Asked for a waiver or lower interest: only lender staff can decide"
            self.audit(mid, "Lender's menu only", "declined waiver", "Agent cannot waive or change terms; request sent to staff")
            reason = r.get("secondary")
            parts = [("waiver_decline", {})]
            if reason:
                case.reason = reason
                op, _ = self.offer_parts(case, reason, r.get("event_days"))
                if op:
                    case.state = "offered"
                    say(parts + op, "offer", options=case.cards)
                    return
            case.state = "with_person"
            say(parts, "waiver_decline")
            return
        if intent in ("family_event", "illness", "temporary_closure", "business_slow"):
            case.reason = intent
            days = r.get("event_days")
            if intent == "family_event":
                n = max(1, min(days or 3, 7))
                end = self.today_deduction_date() + timedelta(days=n - 1)
                case.quiet_until = datetime.combine(end + timedelta(days=1), config.CONTACT_START)
                self.note(case, f"Family function: no proactive messages until {guardrails.t12(case.quiet_until, day=True)}.", "quiet")
            op, blocked = self.offer_parts(case, intent, days)
            pre = [(f"pre_{intent}", {})]
            if op:
                case.state = "offered"
                self.note(case, "Offered from the lender's menu: " + ", ".join(case.offered) + ".", "offer")
                self.audit(mid, "Lender's menu only", "offered", ", ".join(case.offered) +
                           (f" (not eligible: {'; '.join(b['id'] + ': ' + ', '.join(b['why']) for b in blocked)})" if blocked else ""))
                say(pre + op, "offer", options=case.cards)
            else:
                case.state, case.human = "with_person", True
                why = "; ".join(f"{b['id']}: {', '.join(b['why'])}" for b in blocked) or "no option for this reason"
                case.human_reason = f"{REASON_LABEL[intent]}, but no automatic option ({why})"
                self.note(case, case.human_reason + ".", "block")
                self.audit(mid, "Eligibility", "not eligible", why)
                say(pre + [("no_option_human", {})], "no_option")
            return
        if intent == "need_time":
            if case.offered or case.accepted:
                # More than the automatic menu allows: only lender staff can decide. The offer stays open.
                case.human = True
                staff = ", ".join(o["id"] for o in case.human_options) or "a longer pause"
                case.human_reason = f"Asked for more time than the automatic options allow: staff may consider {staff}"
                self.note(case, case.human_reason + ".", "block")
                self.audit(mid, "Lender's menu only", "routed to staff", case.human_reason)
                still_open = [("offer_still_open", {})] if case.state == "offered" else []
                say([("more_time_staff", {})] + still_open, "more_time")
            else:
                say([("ask_reason_help", {})], "ask_reason")
            return
        if intent == "business_normal":
            if case.trigger and (case.trigger.get("sharp") or case.trigger.get("level") == "red"):
                case.review, case.state, case.human = True, "review", True
                lvl = list(case.trigger["ratios"].values())[-1]
                case.human_reason = (f"Sales at {lvl:.0%} of normal and installment short, but merchant says business "
                                     "is normal: check for payments moved to another QR. No relief offered.")
                self.note(case, case.human_reason, "warn")
                self.audit(mid, "Possible diversion", "review", case.human_reason)
            else:
                case.state, case.outcome, case.closed_at = "closed", "No help needed", self.now
            say([("normal_ack", {})], "ack")
            if case.state == "closed":
                self.close(case)
            return
        if intent == "accept" and case.state == "offered" and case.offered:
            self.accept(mid, case.offered[0], via="voice")
            return
        if intent == "decline" and case.state == "offered":
            case.state = "declined"
            self.audit(mid, "Merchant choice", "declined", "Merchant declined the offer")
            say([("decline_ack", {})], "ack")
            return
        if intent == "question":
            out = max(loan.total - st.collected, 0)
            say([("balance", {"outstanding": money(out), "left": -(-out // loan.installment),
                              "installment": money(loan.installment)})], "balance")
            return
        say([("ask_reason", {})], "ask_reason")

    def accept(self, mid: str, option_id: str, via: str = "tap", simulated: bool = False) -> dict:
        case = self.case_for(mid)
        if not case or option_id not in (case.offered or []) or case.accepted:
            why = "no open offer" if not case else ("already accepted" if case.accepted else f"{option_id} was not offered")
            if case:
                self.note(case, f"Rejected accept of {option_id}: {why}.", "block")
            self.audit(mid, "Lender's menu only", "rejected", f"Accept {option_id}: {why}")
            return {"ok": False, "why": why}
        loan, st = self.loans[mid], self.states[mid]
        fails = policy.check(policy.option(option_id), loan, st, self.now.date())
        if fails:
            self.audit(mid, "Eligibility", "rejected", f"{option_id} no longer eligible: {', '.join(fails)}")
            return {"ok": False, "why": ", ".join(fails)}
        t = case.offered_terms[option_id]
        start = self.today_deduction_date()
        if (t.get("pause_dates") or t.get("reduced_dates"))[0] < start:   # accepted late: shift to the next deduction
            t = policy.terms(option_id, loan, start, t.get("days"))
        policy.apply(loan, t, self.now.date())
        case.accepted, case.accepted_terms, case.state = option_id, t, "accepted"
        case.relief_end = t["pause_dates"][-1] if t["kind"] == "pause" else t["reduced_dates"][-1]
        lang = self.merchants[mid].lang
        self.msg_seq += 1
        opt = policy.option(option_id)
        tap = Message(id=self.msg_seq, at=self.now, dir="in", lang=lang, text=f"✓ {opt['label'][lang]}",
                      text_en=f"Accepted: {opt['label']['en']}", kind="accept", status="received", via=via,
                      author="merchant", sent_at=self.now)
        tap.simulated = simulated
        case.messages.append(tap)
        case.last_inbound_at = self.now
        f = policy.facts(t)
        self.note(case, f"Accepted {option_id}. Applied to the loan's deduction calendar.", "good")
        self.audit(mid, "Relief applied", option_id,
                   (f"No deduction {f['pause_from']:%d %b}-{f['pause_to']:%d %b}; ₹{f['per_day']}/day catch-up for "
                    f"{f['catchup_days']} days from {f['start']:%d %b}") if t["kind"] == "pause" else
                   f"₹{f['half']}/day for {f['days']} days from {f['start']:%d %b}; +{f['extra_days']} days at end")
        parts = [("confirm_pause" if t["kind"] == "pause" else "confirm_reduce", f)]
        if case.quiet_until and case.quiet_until > self.now:
            parts.append(("quiet", {"resume": case.quiet_until}))
        parts.append(("best", {}))
        self.send(case, parts, kind="reply", msg_kind="confirm", lang=lang)
        return {"ok": True, "terms": option_id}

    def verify(self, case: Case):
        case.verify_at = None
        mid = case.merchant_id
        m, loan = self.merchants[mid], self.loans[mid]
        last = self.rows[mid][-1]
        t = case.accepted_terms or {}
        if t.get("kind") == "pause":
            first = m.first_local if m.lang != "en" else m.first
            parts = [("welcome_pause", {"first": first, "first_en": m.first, "deducted": money(last["deducted"]),
                                        "installment": money(loan.installment), "per_day": money(t["catchup_per_day"])})]
        else:
            parts = [("welcome_generic", {"first": m.first_local if m.lang != "en" else m.first, "first_en": m.first, "deducted": money(last["deducted"])})]
        self.send(case, parts, kind="proactive", msg_kind="welcome_back")
        case.state, case.outcome, case.closed_at = "recovered", "Recovered without a missed installment", self.now
        self.note(case, "Case closed: recovered. Catch-up continues automatically.", "good")
        self.audit(mid, "Outcome", "recovered", f"Back to normal sales; {st_missed(self.states[mid])}")
        self.close(case)

    def close(self, case: Case):
        self.closed_cases.append(case)

    def cancel_held(self, case: Case):
        held = [o for o in self.outbox if o[1] == case.id]
        if held:
            self.outbox = [o for o in self.outbox if o[1] != case.id]
            for _, _, mid in held:
                msg = next((x for x in case.messages if x.id == mid), None)
                if msg:
                    msg.status = "blocked"
            self.note(case, f"Cancelled {len(held)} held message(s).", "block")

    # ------------------------------------------------------------------ views
    def counterfactual(self, mid: str, start: date, end: date) -> list[dict]:
        """Same days, same sales, no Sambhal (no adjustments from `start`)."""
        loan = self.loans[mid]
        pre = {d: a for d, a in loan.adjustments.items() if d < start}
        st, _ = replay(loan, self.sales[mid], loan.disbursed_on + timedelta(days=1), start - timedelta(days=1), pre)
        _, rows = replay(loan, self.sales[mid], start, end, pre, st)
        return rows

    def week(self, mid: str, start: date | None = None, days: int = 8) -> dict:
        start = start or date(2026, 10, 21)
        end = start + timedelta(days=days - 1)
        actual = {r["date"]: r for r in self.rows[mid] if start <= r["date"] <= end}
        cf = {r["date"]: r for r in self.counterfactual(mid, start, end)}
        out = []
        for k in range(days):
            d = start + timedelta(days=k)
            a, c = actual.get(d), cf[d]
            out.append({
                "date": d.isoformat(), "dow": d.strftime("%a"), "settled": a is not None,
                "sales": self.sales[mid].get(d, 0) if a else None, "baseline": round(same_weekday_baseline(self.sales[mid], d)),
                "with": None if not a else {k2: a[k2] for k2 in ("deducted", "arrears", "dpd", "paused", "catchup", "installment")},
                "without": None if not a else {k2: c[k2] for k2 in ("deducted", "arrears", "dpd")},
            })
        return {"merchant_id": mid, "rows": out}

    def case_view(self, c: Case) -> dict:
        m = self.merchants[c.merchant_id]
        return {
            "id": c.id, "merchant_id": c.merchant_id, "merchant": m.owner, "shop": m.shop, "lang": m.lang,
            "opened_at": c.opened_at.isoformat(), "state": c.state, "reason": c.reason,
            "reason_label": REASON_LABEL.get(c.reason or "", None),
            "trigger": None if not c.trigger else {**c.trigger, "date": c.trigger["date"].isoformat()},
            "offered": c.offered, "accepted": c.accepted, "human": c.human, "human_reason": c.human_reason,
            "human_options": c.human_options, "review": c.review, "grievance": c.grievance, "stopped": c.stopped,
            "quiet_until": c.quiet_until.isoformat() if c.quiet_until else None,
            "sensitive_until": c.sensitive_until.isoformat() if c.sensitive_until else None,
            "messages": [x.view() | {"simulated": x.simulated} for x in c.messages],
            "timeline": c.timeline, "outcome": c.outcome,
            "closed_at": c.closed_at.isoformat() if c.closed_at else None,
        }

    def merchant_view(self, mid: str) -> dict:
        m, loan, st = self.merchants[mid], self.loans[mid], self.states[mid]
        recent = [r for r in self.rows[mid][-14:]]
        case = self.case_for(mid)
        return {
            "id": mid, "owner": m.owner, "first": m.first, "shop": m.shop, "kind": m.kind, "area": m.area,
            "lang": m.lang, "phone": m.phone, "consent": m.consent, "note": m.note,
            "loan": {"principal": loan.principal, "total": loan.total, "installment": loan.installment,
                     "tenure_days": loan.tenure_days, "disbursed_on": loan.disbursed_on.isoformat(),
                     "collected": st.collected, "outstanding": max(loan.total - st.collected, 0),
                     "arrears": st.arrears, "dpd": st.dpd, "paid_ratio": round(st.paid_ratio, 3),
                     "missed_days": st.missed_days, "age_days": (self.now.date() - loan.disbursed_on).days},
            "recent": [{"date": r["date"].isoformat(), "dow": r["date"].strftime("%a"), "sales": r["sales"],
                        "baseline": round(same_weekday_baseline(self.sales[mid], r["date"])),
                        "deducted": r["deducted"], "arrears": r["arrears"], "paused": r["paused"]} for r in recent],
            "case": self.case_view(case) if case else None,
        }


def gloss(r: dict) -> str:
    g = INTENT_GLOSS[r["intent"]]
    if r.get("event_days") and r["intent"] in ("family_event", "illness", "temporary_closure"):
        g = g.rstrip(".") + f" for about {r['event_days']} days."
    return g


def st_missed(st: LoanState) -> str:
    return f"{st.missed_days} overdue day(s) since disbursal; {st.dpd} day(s) overdue now"


RAVI_REPLY = "ಮನೆಯಲ್ಲಿ ಮದುವೆ ಇದೆ, ಭಾನುವಾರದವರೆಗೆ ಅಂಗಡಿ ಮುಚ್ಚಿರುತ್ತೆ."
RAVI_REPLY_EN = "There's a wedding at home; the shop will be closed till Sunday."

REWRITE_SYSTEM = (
    "You rewrite one short message from a loan-help assistant to a small shop owner in India. Write in {lang} only, "
    "warm, simple and respectful, like a WhatsApp message from a helpful person. Keep every number, amount and date "
    "exactly as given, in the same digits. Do not add any new number, date, condition, promise or threat. Do not "
    "mention anyone other than the shop owner. Keep 'Accept' instructions if present. Under 90 words. "
    'Return JSON: {{"text": "<message>"}}'
)
