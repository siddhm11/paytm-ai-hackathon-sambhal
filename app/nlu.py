"""Understanding the merchant's reply.

Two readers:
  * rules: multilingual keyword reader (Kannada, Hindi, English, and romanised
    Kannada/Hindi). Works offline and makes the test suite deterministic.
  * llm:   the language model, when a key is configured.

Safety net: the rules reader can only escalate. If it spots a bereavement,
medical emergency, stop request or dispute, that wins over the model's reading.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from . import llm

INTENTS = ["bereavement", "medical_emergency", "stop_contact", "dispute", "request_waiver", "family_event",
           "illness", "temporary_closure", "business_slow", "need_time", "business_normal", "decline", "accept",
           "question", "unclear"]
SAFETY_INTENTS = {"bereavement", "medical_emergency", "stop_contact", "dispute"}
HARDSHIP = {"family_event", "illness", "temporary_closure", "business_slow", "medical_emergency", "bereavement"}

# Latin-script entries are matched as whole words; Indic-script entries as substrings.
KEYWORDS: dict[str, list[str]] = {
    "bereavement": [
        "died", "passed away", "death", "funeral", "demise", "expired yesterday",
        "guzar gaye", "guzar gayi", "gujar gaye", "nahi rahe", "nahin rahe", "maut", "antim sanskar", "dehant",
        "teerikondru", "teerikondaru", "tirikondaru", "nidhana", "saavu",
        "गुज़र", "गुजर", "निधन", "मृत्यु", "मौत", "देहांत", "नहीं रहे", "अंतिम संस्कार",
        "ತೀರಿಕೊಂಡ", "ನಿಧನ", "ಸಾವು", "ಮರಣ", "ಅಂತ್ಯಕ್ರಿಯೆ", "ಇನ್ನಿಲ್ಲ", "ಸತ್ತ",
    ],
    "medical_emergency": [
        "hospital", "icu", "admitted", "accident", "surgery", "operation", "emergency", "ambulance",
        "aspatal", "haspatal", "bharti", "aaspatre", "aspatre",
        "अस्पताल", "आईसीयू", "भर्ती", "दुर्घटना", "ऑपरेशन", "एक्सीडेंट",
        "ಆಸ್ಪತ್ರೆ", "ಐಸಿಯು", "ಅಪಘಾತ", "ಆಪರೇಷನ್", "ಅಡ್ಮಿಟ್",
    ],
    "stop_contact": [
        "stop calling", "stop messaging", "stop messages", "don't call", "do not call", "dont call",
        "don't message", "do not message", "unsubscribe", "leave me alone",
        "call mat karo", "message mat bhejo", "pareshan mat karo", "phone mat karo",
        "कॉल मत", "मैसेज मत", "फोन मत", "परेशान मत",
        "ಕರೆ ಮಾಡಬೇಡಿ", "ಮೆಸೇಜ್ ಮಾಡಬೇಡಿ", "ಫೋನ್ ಮಾಡಬೇಡಿ", "ತೊಂದರೆ ಕೊಡಬೇಡಿ",
    ],
    "dispute": [
        "wrong deduction", "deducted twice", "double deduction", "already paid", "not my loan", "wrongly deducted",
        "extra deducted", "galat kata", "do baar kata", "pehle hi de diya", "galat katauti",
        "गलत कटौती", "दो बार कटा", "दो बार काटा", "पहले ही दे दिया", "गलत कटा",
        "ಎರಡು ಸಲ ಕಟ್", "ತಪ್ಪಾಗಿ ಕಟ್", "ಈಗಾಗಲೇ ಕಟ್ಟಿದ್ದೇನೆ", "ತಪ್ಪು ಕಡಿತ",
    ],
    "request_waiver": [
        "waive", "waiver", "forgive", "reduce interest", "reduce the interest", "cancel the loan", "write off",
        "discount", "settle for less", "maaf", "maafi", "byaaj kam", "byaj kam", "byaaj maaf",
        "माफ़", "माफ", "ब्याज कम", "छूट दे",
        "ಮನ್ನಾ", "ಬಡ್ಡಿ ಕಡಿಮೆ", "ರಿಯಾಯಿತಿ", "manna", "baddi kadime",
    ],
    "family_event": [
        "wedding", "marriage", "function", "ceremony", "engagement", "naming ceremony", "puja at home",
        "shaadi", "shadi", "byah", "sagai", "maduve", "nischitartha", "habba",
        "शादी", "विवाह", "सगाई", "समारोह", "फंक्शन",
        "ಮದುವೆ", "ನಿಶ್ಚಿತಾರ್ಥ", "ಕಾರ್ಯಕ್ರಮ", "ಫಂಕ್ಷನ್", "ಗೃಹಪ್ರವೇಶ", "ನಾಮಕರಣ",
        "festival", "pooja", "tyohar", "tyohaar", "त्योहार", "पूजा", "ಹಬ್ಬ", "ಪೂಜೆ",
    ],
    "illness": [
        "fever", "sick", "unwell", "not well", "ill", "bimar", "bukhar", "tabiyat", "hushaarilla", "jvara", "jwara",
        "बीमार", "बुखार", "तबीयत", "ಹುಷಾರಿಲ್ಲ", "ಜ್ವರ", "ಆರೋಗ್ಯ ಸರಿಯಿಲ್ಲ",
    ],
    "temporary_closure": [
        "shop closed", "shop is closed", "closed", "renovation", "repair", "out of town", "village", "travelling",
        "dukaan band", "dukan band", "band hai", "gaon", "angadi muchchide", "muchchirutte", "oorige",
        "दुकान बंद", "बंद है", "बंद रहेगी", "गाँव", "गांव", "मरम्मत",
        "ಅಂಗಡಿ ಮುಚ್ಚ", "ಮುಚ್ಚಿದೆ", "ಮುಚ್ಚಿರುತ್ತೆ", "ರಿಪೇರಿ", "ಊರಿಗೆ", "ಬಂದ್",
    ],
    "business_slow": [
        "business is slow", "slow", "no customers", "sales down", "less sales", "low sales", "rain", "road work",
        "construction", "dhandha kam", "dhanda kam", "dhandha bahut kam", "grahak nahi", "bikri kam", "mandi",
        "barish", "baarish", "vyapara kadime", "vyapara illa", "giraki illa",
        "धंधा कम", "धंधा बहुत कम", "बिक्री कम", "ग्राहक नहीं", "मंदा", "बारिश",
        "ವ್ಯಾಪಾರ ಕಡಿಮೆ", "ವ್ಯಾಪಾರ ಇಲ್ಲ", "ಗಿರಾಕಿ ಇಲ್ಲ", "ಗಿರಾಕಿ ಕಡಿಮೆ", "ಮಳೆ",
        "no sales", "loss", "nuksan", "nuksaan", "नुकसान", "ನಷ್ಟ",
    ],
    "need_time": [
        "more time", "more days", "extra days", "some time", "few days", "why only", "pay later", "pay tomorrow",
        "pay next week", "next week", "no money", "thoda time", "kuch din", "aur din", "zyada din", "baad mein",
        "kal dunga", "paisa nahi", "paise nahi", "swalpa samaya", "duddu illa",
        "थोड़ा समय", "समय चाहिए", "और दिन", "ज़्यादा दिन", "कुछ दिन", "बाद में", "पैसे नहीं", "पैसा नहीं",
        "ಸಮಯ ಬೇಕು", "ಸ್ವಲ್ಪ ಸಮಯ", "ಹೆಚ್ಚು ದಿನ", "ಇನ್ನೂ ಕೆಲವು ದಿನ", "ನಂತರ ಕಟ್ಟುತ್ತೇನೆ", "ದುಡ್ಡು ಇಲ್ಲ",
    ],
    "business_normal": [
        "all good", "all fine", "everything is fine", "everything fine", "business is fine", "business is normal",
        "business normal", "no problem", "all ok", "sab theek", "sab badhiya", "dhandha theek", "koi dikkat nahi",
        "normal chal raha", "सब ठीक", "कोई दिक्कत नहीं", "कोई समस्या नहीं", "नॉर्मल चल रहा", "धंधा ठीक",
        "ಎಲ್ಲಾ ಸರಿ ಇದೆ", "ಏನೂ ತೊಂದರೆ ಇಲ್ಲ", "ವ್ಯಾಪಾರ ಚೆನ್ನಾಗಿದೆ", "ella sari ide", "chennagide",
    ],
    "decline": [
        "no thanks", "don't want", "do not want", "not needed", "no need", "nahi chahiye", "nahin chahiye",
        "नहीं चाहिए", "ज़रूरत नहीं", "ಬೇಡ", "ಬೇಕಿಲ್ಲ", "beda", "bekilla",
        "not now", "abhi nahi", "अभी नहीं", "ಈಗ ಬೇಡ",
    ],
    "accept": [
        "yes", "ok", "okay", "accept", "agree", "sure", "confirm", "haan", "han", "theek hai", "chalega", "manzoor",
        "houdu", "sari", "aytu", "oppide",
        "हाँ", "हां", "ठीक है", "मंज़ूर", "मंजूर", "स्वीकार",
        "ಹೌದು", "ಸರಿ", "ಆಯ್ತು", "ಒಪ್ಪುತ್ತೇನೆ", "ಓಕೆ",
    ],
    "question": [
        "how much", "balance", "outstanding", "how many", "remaining", "kitna", "kitne", "baaki", "eshtu",
        "कितना", "कितने", "बाकी", "ಎಷ್ಟು", "ಬಾಕಿ",
    ],
}

WEEKDAYS = {
    0: ["monday", "somvar", "सोमवार", "ಸೋಮವಾರ", "somavara"],
    5: ["saturday", "shanivar", "शनिवार", "ಶನಿವಾರ", "shanivara"],
    6: ["sunday", "ravivar", "itvaar", "इतवार", "रविवार", "ಭಾನುವಾರ", "bhanuvara"],
}
NUMBER_WORDS = {
    1: ["one", "ek", "एक", "ಒಂದು", "ondu"], 2: ["two", "do", "दो", "ಎರಡು", "eradu"],
    3: ["three", "teen", "तीन", "ಮೂರು", "mooru"], 4: ["four", "char", "चार", "ಚಾರ್", "ನಾಲ್ಕು", "nalku"],
    5: ["five", "paanch", "पाँच", "पांच", "ಐದು", "aidu"], 7: ["seven", "saat", "सात", "ಏಳು", "elu"],
}
DAY_WORDS = r"(days?|dina|din|दिन|ದಿನ)"

HINGLISH = {"hai", "nahi", "kar", "karo", "dukaan", "dukan", "dhandha", "bhai", "ji", "mera", "meri", "ghar", "kam",
            "bahut", "shaadi", "hoon", "hu", "raha", "rahi"}
KANGLISH = {"ide", "illa", "maduve", "angadi", "beda", "houdu", "nanna", "namma", "aytu", "agide", "hogide",
            "muchchide", "vyapara", "swalpa"}


def _match(kw: str, text: str, low: str) -> bool:
    if kw.isascii():
        return re.search(r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])", low) is not None
    return kw in text


def detect_language(text: str, fallback: str) -> str:
    kn = sum(1 for c in text if "ಀ" <= c <= "೿")
    hi = sum(1 for c in text if "ऀ" <= c <= "ॿ")
    if kn or hi:
        return "kn" if kn >= hi else "hi"
    words = set(re.findall(r"[a-z]+", text.lower()))
    if len(words & KANGLISH) > len(words & HINGLISH):
        return "kn"
    if words & HINGLISH:
        return "hi"
    return "en" if words else fallback


def event_days(text: str, today: date) -> int | None:
    low = text.lower()
    m = re.search(r"(\d+)\s*" + DAY_WORDS, low)
    if m:
        return int(m.group(1))
    for n, words in NUMBER_WORDS.items():
        for w in words:
            pat = (r"(?<![a-z])" + re.escape(w) + r"\s*" + DAY_WORDS) if w.isascii() else (re.escape(w) + r"\s*" + DAY_WORDS)
            if re.search(pat, low if w.isascii() else text):
                return n
    for wd, words in WEEKDAYS.items():
        if any(_match(w, text, low) for w in words):
            return (wd - today.weekday()) % 7 + 1
    return None


# Accepting changes the loan, so a reply only counts as "yes" if it has no question, "not" or "but" in it.
# "I am not ok" and "ok but why only 3 days?" must never apply a pause.
NOT_A_YES = ["not", "no", "don't", "dont", "nahi", "nahin", "mat", "illa", "beda", "but", "lekin", "magar", "aadre",
             "नहीं", "मत", "लेकिन", "मगर", "ಇಲ್ಲ", "ಬೇಡ", "ಆಗಲ್ಲ", "ಆದರೆ"]
BARE_NO = {"no", "nope", "nahi", "nahin", "illa", "nahi ji", "नहीं", "ಇಲ್ಲ", "ಬೇಡ"}


def read_rules(text: str, merchant_lang: str, today: date) -> dict:
    low = text.lower().strip()
    bare = low.strip(" .!,।")
    hits = {i: [k for k in KEYWORDS[i] if _match(k, text, low)] for i in KEYWORDS}
    if bare in {"stop", "रोको", "ನಿಲ್ಲಿಸಿ"}:
        hits["stop_contact"].append(bare)
    if bare in BARE_NO:
        hits["decline"].append(bare)
    if hits["accept"] and ("?" in text or any(_match(w, text, low) for w in NOT_A_YES)):
        hits["accept"] = []
    found = [i for i in INTENTS if hits.get(i)]
    intent = found[0] if found else "unclear"
    secondary = next((i for i in found[1:] if i in HARDSHIP), None)
    return {
        "intent": intent, "secondary": secondary, "language": detect_language(text, merchant_lang),
        "event_days": event_days(text, today), "matched": {i: hits[i] for i in found}, "source": "rules",
        "summary_en": None,
    }


LLM_SYSTEM = """You read short replies from small shop owners in India (Kannada, Hindi, English, or romanised \
Kannada/Hindi) about their daily loan installment. Classify the reply.
Return JSON only: {"intent": one of %s,
 "secondary": a hardship intent also mentioned, or null,
 "language": "kn" | "hi" | "en",
 "event_days": integer number of days the shop is closed or affected if stated or implied, else null,
 "summary_en": one short English sentence saying what the merchant said}
Definitions: bereavement = a death; medical_emergency = hospital/ICU/accident/surgery; illness = fever/unwell, not \
hospital; family_event = wedding/function/ceremony at home; temporary_closure = shop shut for repair/travel; \
business_slow = fewer customers/sales; business_normal = says everything is fine; request_waiver = asks to waive \
or cut dues/interest; need_time = asks for more time or more days (including "why only N days?"), or to pay \
later, without giving a reason; \
dispute = says a deduction is wrong or already paid; stop_contact = asks us to stop messaging; accept/decline = \
answering an offer (a question or a "but" is not an accept); question = asks how much is left to repay or what \
an amount is; unclear = none of these.
If several apply, pick the most serious in this order: %s."""


def read(text: str, merchant_lang: str, today: date) -> dict:
    rules = read_rules(text, merchant_lang, today)
    if not llm.available():
        return rules
    try:
        res = llm.chat_json(LLM_SYSTEM % (INTENTS, " > ".join(INTENTS)),
                            f"Today is {today:%A}. Merchant's message:\n{text}")
        intent = res.get("intent") if res.get("intent") in INTENTS else "unclear"
        out = {
            "intent": intent,
            "secondary": res.get("secondary") if res.get("secondary") in HARDSHIP else None,
            "language": res.get("language") if res.get("language") in ("kn", "hi", "en") else rules["language"],
            # Days are a number, and code decides numbers: the rules' calendar maths wins when it found one
            # (the model counted Friday "till Sunday" as 2 days; it is 3).
            "event_days": rules["event_days"] if rules["event_days"] is not None else (
                res.get("event_days") if isinstance(res.get("event_days"), int) else None),
            "summary_en": res.get("summary_en"), "matched": rules["matched"], "source": "llm",
        }
        # Safety net: keywords may escalate, never de-escalate.
        if rules["intent"] in SAFETY_INTENTS and INTENTS.index(rules["intent"]) < INTENTS.index(intent):
            out["intent"], out["source"] = rules["intent"], "llm+safety-net"
        if intent == "unclear" and rules["intent"] != "unclear":
            out["intent"], out["source"] = rules["intent"], "llm+rules"
        return out
    except Exception as e:  # network, quota, bad JSON: fall back
        rules["llm_error"] = str(e)[:200]
        return rules
