"""Synthetic merchants, loans and daily settlements.

Everything here is invented and deterministic (fixed seed), so every run of the
demo and every test sees the same numbers. Ravi (M01) is the demo merchant and
matches the pitch deck: ₹850 daily installment, ~₹6,000 on a normal Monday,
shop shut Fri-Sun 23-25 Oct for a family wedding.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import median

HISTORY_START = date(2026, 6, 15)
DATA_END = date(2026, 11, 30)
DOW_FACTORS = [1.00, 0.95, 0.95, 1.00, 1.05, 1.15, 1.10]  # Mon..Sun


@dataclass
class Merchant:
    id: str
    owner: str
    first: str
    shop: str
    kind: str
    area: str
    lang: str            # kn | hi | en
    phone: str
    consent: bool        # opted in to Sambhal messages at loan sign-up
    base_sales: int
    script: dict | None = None   # simulated replies for non-demo merchants
    note: str = ""
    first_local: str = ""        # first name in the merchant's own script, for messages


# English meanings of the scripted lines, shown to judges in the lender console.
TRANSLATIONS = {
    "ಮನೆಯಲ್ಲಿ ಮದುವೆ ಇದೆ, ಭಾನುವಾರದವರೆಗೆ ಅಂಗಡಿ ಮುಚ್ಚಿರುತ್ತೆ.": "There's a wedding at home; the shop will be closed till Sunday.",
    "ನಮ್ಮ ಅಪ್ಪ ನಿನ್ನೆ ತೀರಿಕೊಂಡರು. ಅಂಗಡಿ ಮುಚ್ಚಿದೆ.": "My father passed away yesterday. The shop is closed.",
    "सब ठीक है, धंधा नॉर्मल चल रहा है। कोई दिक्कत नहीं।": "All fine, business is running normally. No problem.",
    "ನನ್ನ ಮಗ ಆಸ್ಪತ್ರೆಯಲ್ಲಿ ICU ನಲ್ಲಿ ಇದ್ದಾನೆ, ಅಪಘಾತ ಆಯ್ತು.": "My son is in the ICU in hospital; there was an accident.",
    "बारिश और सड़क के काम की वजह से धंधा बहुत कम है।": "Business is very slow because of the rain and road works.",
    "ಅಂಗಡಿ ರಿಪೇರಿ ನಡೀತಿದೆ, ನಾಲ್ಕು ದಿನ ಮುಚ್ಚಿರುತ್ತೆ.": "The shop is under repair; it'll be closed for four days.",
    "धंधा कम है भाई, ब्याज माफ़ कर दो।": "Business is slow, brother. Please waive the interest.",
    "ಮನೆಯಲ್ಲಿ ಮದುವೆ ಇದೆ, ಮೂರು ದಿನ ಅಂಗಡಿ ಮುಚ್ಚಿರುತ್ತೆ.": "There's a wedding at home; the shop will be closed for three days.",
    "घर में शादी है, तीन दिन दुकान बंद रहेगी।": "There's a wedding at home; the shop will be closed for three days.",
    "ಮಳೆಯಿಂದ ವ್ಯಾಪಾರ ಕಡಿಮೆ ಆಗಿದೆ.": "Business is down because of the rain.",
    "बारिश की वजह से धंधा बहुत कम है।": "Business is very slow because of the rain.",
    "ನನಗೆ ಜ್ವರ, ಹುಷಾರಿಲ್ಲ. ಮೂರು ದಿನ ಅಂಗಡಿ ತೆರೆಯಲ್ಲ.": "I have fever and I'm unwell. I won't open the shop for three days.",
    "मुझे बुखार है, तबीयत खराब है। तीन दिन दुकान नहीं खुलेगी।": "I have fever and I'm unwell. The shop won't open for three days.",
    "ಊರಿಗೆ ಹೋಗಿದ್ದೇನೆ, ಮೂರು ದಿನ ಅಂಗಡಿ ಮುಚ್ಚಿದೆ.": "I've gone to my village; the shop is closed for three days.",
    "गाँव गया हूँ, तीन दिन दुकान बंद है।": "I've gone to my village; the shop is closed for three days.",
}
LOCAL_NAMES = {"Ravi": "ರವಿ", "Lakshmi": "ಲಕ್ಷ್ಮಿ", "Suresh": "ಸುರೇಶ್", "Venkatesh": "ವೆಂಕಟೇಶ್",
               "Imran": "इमरान", "Pooja": "पूजा", "Farhan": "फ़रहान"}


@dataclass
class Loan:
    id: str
    merchant_id: str
    principal: int
    total: int
    installment: int
    tenure_days: int
    disbursed_on: date
    relief_history: list = field(default_factory=list)   # dates relief was granted
    adjustments: dict = field(default_factory=dict)      # date -> {"paused":1} | {"installment":x} | {"catchup":x}


def money(x: float) -> str:
    """Indian digit grouping: 136000 -> '1,36,000'."""
    n = int(round(x))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return ("-" if n < 0 else "") + s


def _days(a: date, b: date):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def same_weekday_baseline(sales: dict, d: date, weeks: int = 8) -> float:
    vals = [sales[d - timedelta(days=7 * k)] for k in range(1, weeks + 1) if (d - timedelta(days=7 * k)) in sales]
    vals = [v for v in vals if v > 0] or vals
    return float(median(vals)) if vals else 0.0


# --------------------------------------------------------------------------
# Named demo merchants. "events" shape sales; "script" is how the simulated
# merchant replies to Sambhal (Ravi has none: the presenter speaks for him).
# --------------------------------------------------------------------------
NAMED = [
    dict(id="M01", owner="Ravi Kumar", first="Ravi", shop="Sri Manjunatha Provisions", kind="Kirana",
         area="Basavanagudi", lang="kn", consent=True, base=6000,
         loan=dict(principal=136000, total=153000, installment=850, tenure=180, disbursed=date(2026, 8, 10)),
         note="Demo merchant. Family wedding; shop half-shut Wed-Thu, shut Fri-Sun."),
    dict(id="M02", owner="Lakshmi Devi", first="Lakshmi", shop="Lakshmi Flower Stall", kind="Flowers",
         area="Malleshwaram", lang="kn", consent=True, base=3800,
         loan=dict(principal=60000, total=67500, installment=380, tenure=180, disbursed=date(2026, 7, 20)),
         events=[(date(2026, 10, 21), 1, 0.30), (date(2026, 10, 22), 6, 0.0)],
         script=dict(text="ನಮ್ಮ ಅಪ್ಪ ನಿನ್ನೆ ತೀರಿಕೊಂಡರು. ಅಂಗಡಿ ಮುಚ್ಚಿದೆ.", delay_min=65),
         note="Bereavement: Sambhal must stop and hand over to a person."),
    dict(id="M03", owner="Imran Pasha", first="Imran", shop="Pasha Mobile Point", kind="Mobile repair",
         area="Shivajinagar", lang="hi", consent=True, base=7200,
         loan=dict(principal=150000, total=168750, installment=940, tenure=180, disbursed=date(2026, 6, 25)),
         events=[(date(2026, 10, 21), 12, 0.12)],
         script=dict(text="सब ठीक है, धंधा नॉर्मल चल रहा है। कोई दिक्कत नहीं।", delay_min=40),
         note="Sales vanish but he says business is normal: possible payments to another QR."),
    dict(id="M04", owner="Suresh Gowda", first="Suresh", shop="Gowda Tea & Snacks", kind="Tea stall",
         area="Rajajinagar", lang="kn", consent=True, base=4200,
         loan=dict(principal=70000, total=78750, installment=440, tenure=180, disbursed=date(2026, 7, 5)),
         events=[(date(2026, 10, 22), 2, 0.25), (date(2026, 10, 24), 7, 0.0)],
         script=dict(text="ನನ್ನ ಮಗ ಆಸ್ಪತ್ರೆಯಲ್ಲಿ ICU ನಲ್ಲಿ ಇದ್ದಾನೆ, ಅಪಘಾತ ಆಯ್ತು.", delay_min=120),
         note="Medical emergency: hand over to a person, no automatic terms."),
    dict(id="M05", owner="Pooja Sharma", first="Pooja", shop="Sharma Sweets", kind="Sweets",
         area="BTM Layout", lang="hi", consent=True, base=9000,
         loan=dict(principal=180000, total=202500, installment=1130, tenure=180, disbursed=date(2026, 6, 20)),
         events=[(date(2026, 10, 20), 16, 0.42)],
         script=dict(text="बारिश और सड़क के काम की वजह से धंधा बहुत कम है।", delay_min=50, accept="HALF_14"),
         note="Slow business (rain + road works): offered half installment for 14 days."),
    dict(id="M06", owner="Venkatesh Rao", first="Venkatesh", shop="Venkateshwara Hardware", kind="Hardware",
         area="Yeshwanthpur", lang="kn", consent=True, base=8000,
         loan=dict(principal=160000, total=180000, installment=1000, tenure=180, disbursed=date(2026, 6, 18)),
         relief=[date(2026, 9, 12)],
         events=[(date(2026, 10, 22), 2, 0.35), (date(2026, 10, 24), 4, 0.0)],
         script=dict(text="ಅಂಗಡಿ ರಿಪೇರಿ ನಡೀತಿದೆ, ನಾಲ್ಕು ದಿನ ಮುಚ್ಚಿರುತ್ತೆ.", delay_min=30),
         note="Already had a pause in September: not eligible again, goes to a person."),
    dict(id="M07", owner="Farhan Ali", first="Farhan", shop="Ali Fruits & Juice", kind="Fruit stall",
         area="Frazer Town", lang="hi", consent=True, base=5000,
         loan=dict(principal=90000, total=101250, installment=560, tenure=180, disbursed=date(2026, 7, 1)),
         events=[(date(2026, 10, 22), 10, 0.40)],
         script=dict(text="धंधा कम है भाई, ब्याज माफ़ कर दो।", delay_min=25, accept="first"),
         note="Asks for an interest waiver: declined kindly, offered only approved options."),
    dict(id="M08", owner="Meena Joseph", first="Meena", shop="Meena Tailoring", kind="Tailor",
         area="Koramangala", lang="en", consent=False, base=3000,
         loan=dict(principal=45000, total=50625, installment=280, tenure=180, disbursed=date(2026, 7, 28)),
         events=[(date(2026, 10, 22), 5, 0.20)],
         note="Did not opt in to Sambhal messages: no outreach, goes to a person."),
    dict(id="M09", owner="Arjun Menon", first="Arjun", shop="Menon Bakery", kind="Bakery",
         area="HSR Layout", lang="en", consent=True, base=7500,
         loan=dict(principal=140000, total=157500, installment=880, tenure=180, disbursed=date(2026, 7, 8)),
         events=[(date(2026, 10, 23), 2, 0.30), (date(2026, 10, 25), 3, 0.0)],
         script=dict(text="You deducted twice last week, I already paid. This is a wrong deduction.", delay_min=35),
         note="Disputes a deduction: goes to the grievance officer; reminders stop."),
]

KN_FIRST = ["Manjunath", "Shivakumar", "Nagaraj", "Prakash", "Girish", "Mahesh", "Shobha", "Kavitha", "Savitha",
            "Raghavendra", "Basavaraj", "Harish", "Lokesh", "Anitha", "Sunitha", "Ganesh", "Srinivas", "Umesh",
            "Chandru", "Roopa", "Deepa", "Naveen"]
KN_LAST = ["Gowda", "Shetty", "Rao", "Hegde", "Naik", "Murthy", "Reddy", "Bhat"]
HI_FIRST = ["Rajesh", "Sunil", "Deepak", "Anil", "Vikas", "Rakesh", "Neha", "Sanjay", "Amit", "Salim", "Rekha",
            "Ashok", "Manoj", "Pankaj", "Nisha", "Rafiq"]
HI_LAST = ["Gupta", "Yadav", "Singh", "Verma", "Khan", "Jain", "Agarwal", "Mishra"]
EN_FIRST = ["Joseph", "Thomas", "Priya", "Ann", "Kevin", "Sneha", "Rohit", "Mary", "Vinod"]
EN_LAST = ["D'Souza", "Mathew", "Pinto", "Fernandes", "Nair", "George"]
KINDS = ["Kirana", "Tea stall", "Medical store", "Bakery", "Tailor", "Mobile repair", "Vegetables", "Sweets",
         "Hardware", "Salon", "Stationery", "Fruit stall"]
AREAS = ["Jayanagar", "Malleshwaram", "Yeshwanthpur", "BTM Layout", "Rajajinagar", "HSR Layout", "Koramangala",
         "Basavanagudi", "Hebbal", "KR Puram", "Whitefield", "Banashankari", "Vijayanagar", "Indiranagar"]

# Simulated replies for the background merchants, by reason and language.
REPLY_BANK = {
    "family_event": {
        "kn": "ಮನೆಯಲ್ಲಿ ಮದುವೆ ಇದೆ, ಮೂರು ದಿನ ಅಂಗಡಿ ಮುಚ್ಚಿರುತ್ತೆ.",
        "hi": "घर में शादी है, तीन दिन दुकान बंद रहेगी।",
        "en": "Wedding in the family, shop closed for 3 days.",
    },
    "business_slow": {
        "kn": "ಮಳೆಯಿಂದ ವ್ಯಾಪಾರ ಕಡಿಮೆ ಆಗಿದೆ.",
        "hi": "बारिश की वजह से धंधा बहुत कम है।",
        "en": "Business is slow because of the rain.",
    },
    "illness": {
        "kn": "ನನಗೆ ಜ್ವರ, ಹುಷಾರಿಲ್ಲ. ಮೂರು ದಿನ ಅಂಗಡಿ ತೆರೆಯಲ್ಲ.",
        "hi": "मुझे बुखार है, तबीयत खराब है। तीन दिन दुकान नहीं खुलेगी।",
        "en": "I have fever and I'm unwell. Shop closed for 3 days.",
    },
    "temporary_closure": {
        "kn": "ಊರಿಗೆ ಹೋಗಿದ್ದೇನೆ, ಮೂರು ದಿನ ಅಂಗಡಿ ಮುಚ್ಚಿದೆ.",
        "hi": "गाँव गया हूँ, तीन दिन दुकान बंद है।",
        "en": "Gone to my village, shop closed for 3 days.",
    },
}

# event shapes: (offset_days, length, factor) relative to a start date
SHAPES = {
    "family_event": [(0, 2, 0.40), (2, 3, 0.0)],
    "business_slow": [(0, 14, 0.40)],
    "illness": [(0, 2, 0.30), (2, 3, 0.0)],
    "temporary_closure": [(0, 2, 0.40), (2, 3, 0.0)],
}


def build(seed: int = 7):
    rng = random.Random(seed)
    merchants: dict[str, Merchant] = {}
    loans: dict[str, Loan] = {}
    sales: dict[str, dict[date, int]] = {}

    def gen_sales(base: int, events: list[tuple[date, int, float]]):
        out = {}
        for d in _days(HISTORY_START, DATA_END):
            v = base * DOW_FACTORS[d.weekday()] * rng.uniform(0.93, 1.07)
            out[d] = int(round(v, -1))
        for start, n, f in events:
            for k in range(n):
                dd = start + timedelta(days=k)
                if dd in out:
                    out[dd] = int(round(out[dd] * f, -1))
        return out

    # --- named merchants
    for i, m in enumerate(NAMED):
        mid = m["id"]
        merchants[mid] = Merchant(
            id=mid, owner=m["owner"], first=m["first"], shop=m["shop"], kind=m["kind"], area=m["area"],
            lang=m["lang"], phone=f"+91 98{40 + i}0 0{10 + i}{20 + i}", consent=m["consent"],
            base_sales=m["base"], script=m.get("script"), note=m.get("note", ""),
            first_local=LOCAL_NAMES.get(m["first"], m["first"]))
        L = m["loan"]
        loans[mid] = Loan(id=f"L-{mid}", merchant_id=mid, principal=L["principal"], total=L["total"],
                          installment=L["installment"], tenure_days=L["tenure"], disbursed_on=L["disbursed"],
                          relief_history=list(m.get("relief", [])))
        sales[mid] = gen_sales(m["base"], m.get("events", []))

    # Ravi's week, set against his own same-weekday baseline so the ratios are exact.
    rs = sales["M01"]
    wed, thu = date(2026, 10, 21), date(2026, 10, 22)
    rs[wed] = int(round(0.48 * same_weekday_baseline(rs, wed), -1))
    rs[thu] = int(round(0.31 * same_weekday_baseline(rs, thu), -1))
    for d in (date(2026, 10, 23), date(2026, 10, 24), date(2026, 10, 25)):
        rs[d] = 0
    rs[date(2026, 10, 26)] = 6000

    # --- background merchants M10..M50
    stressed = set(rng.sample(range(10, 51), 14))
    reasons = ["family_event", "business_slow", "illness", "temporary_closure"]
    for n in range(10, 51):
        mid = f"M{n:02d}"
        lang = rng.choices(["kn", "hi", "en"], weights=[5, 3, 2])[0]
        if lang == "kn":
            first, last = rng.choice(KN_FIRST), rng.choice(KN_LAST)
        elif lang == "hi":
            first, last = rng.choice(HI_FIRST), rng.choice(HI_LAST)
        else:
            first, last = rng.choice(EN_FIRST), rng.choice(EN_LAST)
        kind = rng.choice(KINDS)
        base = rng.randrange(2500, 14000, 100)
        inst = int(round(base * rng.uniform(0.11, 0.15), -1))
        tenure = rng.choice([180, 270])
        total = inst * tenure
        principal = int(round(total / (1 + 0.125 * tenure / 180), -3))
        disbursed = date(2026, 10, 21) - timedelta(days=rng.randrange(25, 160))
        script, events = None, []
        if n in stressed:
            reason = rng.choice(reasons)
            start = date(2026, 10, 20) + timedelta(days=rng.randrange(0, 12))
            events = [(start + timedelta(days=o), ln, f) for o, ln, f in SHAPES[reason]]
            script = dict(text=REPLY_BANK[reason][lang], delay_min=rng.randrange(20, 150), accept="first",
                          reason=reason)
        merchants[mid] = Merchant(
            id=mid, owner=f"{first} {last}", first=first, shop=f"{first}'s {kind}", kind=kind,
            area=rng.choice(AREAS), lang=lang, phone=f"+91 9{rng.randrange(100000000, 999999999)}",
            consent=rng.random() > 0.06, base_sales=base, script=script, first_local=first)
        loans[mid] = Loan(id=f"L-{mid}", merchant_id=mid, principal=principal, total=total, installment=inst,
                          tenure_days=tenure, disbursed_on=disbursed)
        sales[mid] = gen_sales(base, events)

    return merchants, loans, sales
