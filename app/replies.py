"""Approved message templates in Kannada, Hindi and English.

Every message Sambhal sends starts from one of these. When an LLM is on, it may
rephrase the body more warmly, but the result must pass guardrails.validate_draft
(same numbers, same language, no threats) or the template is sent instead.
"""
from __future__ import annotations

from datetime import date, datetime

from .config import GRIEVANCE_OFFICER, LENDER_NAME

MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "hi": ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"],
    "kn": ["ಜನವರಿ", "ಫೆಬ್ರವರಿ", "ಮಾರ್ಚ್", "ಏಪ್ರಿಲ್", "ಮೇ", "ಜೂನ್", "ಜುಲೈ", "ಆಗಸ್ಟ್", "ಸೆಪ್ಟೆಂಬರ್", "ಅಕ್ಟೋಬರ್",
           "ನವೆಂಬರ್", "ಡಿಸೆಂಬರ್"],
}
WEEKDAYS = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "hi": ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"],
    "kn": ["ಸೋಮವಾರ", "ಮಂಗಳವಾರ", "ಬುಧವಾರ", "ಗುರುವಾರ", "ಶುಕ್ರವಾರ", "ಶನಿವಾರ", "ಭಾನುವಾರ"],
}


def fdate(d: date, lang: str, weekday: bool = False) -> str:
    m = MONTHS[lang][d.month - 1]
    core = f"{m} {d.day}" if lang == "kn" else f"{d.day} {m}"
    return f"{WEEKDAYS[lang][d.weekday()]} {core}" if weekday else core


def frange(d0: date, d1: date, lang: str) -> str:
    if d0 == d1:
        return fdate(d0, lang)
    if d0.month == d1.month:
        m = MONTHS[lang][d0.month - 1]
        return f"{m} {d0.day}–{d1.day}" if lang == "kn" else f"{d0.day}–{d1.day} {m}"
    return f"{fdate(d0, lang)} – {fdate(d1, lang)}"


HEADER = {
    "en": "Sambhal for {lender} · this message is recorded",
    "hi": "{lender} की ओर से संभल · यह संदेश रिकॉर्ड किया जाता है",
    "kn": "{lender} ಪರವಾಗಿ ಸಂಭಲ್ · ಈ ಸಂದೇಶವನ್ನು ದಾಖಲಿಸಲಾಗುತ್ತದೆ",
}

T: dict[str, dict[str, str]] = {
    "checkin": {
        "en": "Namaste {first}. Sales at your shop have been lower than usual for the last 2 days. Is everything okay? "
              "If the shop is closed or business is slow, tell us. We can help with your ₹{installment} daily installment.",
        "hi": "नमस्ते {first} जी। पिछले 2 दिनों से आपकी दुकान की बिक्री सामान्य से कम है। क्या सब ठीक है? "
              "अगर दुकान बंद है या धंधा कम है तो बताइए। आपकी ₹{installment} की रोज़ की किस्त में हम मदद कर सकते हैं।",
        "kn": "ನಮಸ್ಕಾರ {first} ಅವರೇ. ಕಳೆದ 2 ದಿನಗಳಿಂದ ನಿಮ್ಮ ಅಂಗಡಿಯ ವ್ಯಾಪಾರ ಸಾಮಾನ್ಯಕ್ಕಿಂತ ಕಡಿಮೆ ಇದೆ. ಎಲ್ಲಾ ಸರಿ ಇದೆಯಾ? "
              "ಅಂಗಡಿ ಮುಚ್ಚಿದ್ದರೆ ಅಥವಾ ವ್ಯಾಪಾರ ಕಡಿಮೆ ಇದ್ದರೆ ತಿಳಿಸಿ. ನಿಮ್ಮ ₹{installment} ದಿನದ ಕಂತಿಗೆ ನಾವು ಸಹಾಯ ಮಾಡಬಹುದು.",
    },
    "checkin_red": {
        "en": "Namaste {first}. ₹{arrears} of your installment is pending because sales were low. Is everything okay? "
              "If the shop is closed or business is slow, tell us. We can help.",
        "hi": "नमस्ते {first} जी। बिक्री कम होने से आपकी किस्त के ₹{arrears} बाकी हैं। क्या सब ठीक है? "
              "अगर दुकान बंद है या धंधा कम है तो बताइए, हम मदद कर सकते हैं।",
        "kn": "ನಮಸ್ಕಾರ {first} ಅವರೇ. ವ್ಯಾಪಾರ ಕಡಿಮೆ ಆಗಿದ್ದರಿಂದ ನಿಮ್ಮ ಕಂತಿನ ₹{arrears} ಬಾಕಿ ಇದೆ. ಎಲ್ಲಾ ಸರಿ ಇದೆಯಾ? "
              "ಅಂಗಡಿ ಮುಚ್ಚಿದ್ದರೆ ಅಥವಾ ವ್ಯಾಪಾರ ಕಡಿಮೆ ಇದ್ದರೆ ತಿಳಿಸಿ, ನಾವು ಸಹಾಯ ಮಾಡಬಹುದು.",
    },
    "pre_family_event": {"en": "Best wishes for the function at home.", "hi": "घर के समारोह के लिए शुभकामनाएँ।",
                         "kn": "ಮನೆಯ ಕಾರ್ಯಕ್ರಮಕ್ಕೆ ಶುಭಾಶಯಗಳು."},
    "pre_illness": {"en": "Get well soon.", "hi": "जल्दी ठीक हो जाइए।", "kn": "ಬೇಗ ಗುಣಮುಖರಾಗಿ."},
    "pre_temporary_closure": {"en": "Thanks for letting us know.", "hi": "बताने के लिए धन्यवाद।",
                              "kn": "ತಿಳಿಸಿದ್ದಕ್ಕೆ ಧನ್ಯವಾದಗಳು."},
    "pre_business_slow": {"en": "Sorry to hear business is slow.", "hi": "धंधा कम होने का हमें अफ़सोस है।",
                          "kn": "ವ್ಯಾಪಾರ ಕಡಿಮೆ ಆಗಿರುವುದಕ್ಕೆ ಬೇಸರವಾಗಿದೆ."},
    "offer_intro": {"en": "Your lender allows:", "hi": "आपके लेंडर ने यह अनुमति दी है:",
                    "kn": "ನಿಮ್ಮ ಸಾಲದಾತರು ಇದಕ್ಕೆ ಅನುಮತಿ ನೀಡಿದ್ದಾರೆ:"},
    "opt_pause": {
        "en": "{days}-day pause: no deduction on {range}. The ₹{paused} is collected as ₹{per_day} extra a day for "
              "{catchup_days} days from {start}.",
        "hi": "{days} दिन की छूट: {range} को कोई कटौती नहीं। ₹{paused} की रकम {start} से {catchup_days} दिन तक रोज़ "
              "₹{per_day} अतिरिक्त कटेगी।",
        "kn": "{days} ದಿನಗಳ ವಿರಾಮ: {range} ರಂದು ಕಡಿತ ಇಲ್ಲ. ₹{paused} ಮೊತ್ತವನ್ನು {start} ರಿಂದ {catchup_days} ದಿನಗಳವರೆಗೆ "
              "ದಿನಕ್ಕೆ ₹{per_day} ಹೆಚ್ಚುವರಿಯಾಗಿ ಕಡಿತ ಮಾಡಲಾಗುತ್ತದೆ.",
    },
    "opt_reduce": {
        "en": "Half installment: ₹{half} a day instead of ₹{installment} for {days} days from {start}. The remaining "
              "₹{deferred} is added as {extra_days} extra days at the end of the loan.",
        "hi": "आधी किस्त: {start} से {days} दिन तक ₹{installment} की जगह रोज़ ₹{half}। बाकी ₹{deferred} लोन के अंत में "
              "{extra_days} अतिरिक्त दिनों में जुड़ेगा।",
        "kn": "ಅರ್ಧ ಕಂತು: {start} ರಿಂದ {days} ದಿನಗಳವರೆಗೆ ₹{installment} ಬದಲು ದಿನಕ್ಕೆ ₹{half}. ಉಳಿದ ₹{deferred} ಸಾಲದ "
              "ಕೊನೆಯಲ್ಲಿ {extra_days} ಹೆಚ್ಚುವರಿ ದಿನಗಳಾಗಿ ಸೇರುತ್ತದೆ.",
    },
    "offer_close": {"en": "Tap Accept to confirm.", "hi": "पुष्टि के लिए 'स्वीकार करें' दबाइए।",
                    "kn": "ಒಪ್ಪಲು 'ಒಪ್ಪುತ್ತೇನೆ' ಒತ್ತಿ."},
    "confirm_pause": {
        "en": "Done. No deduction on {range}. From {start}: ₹{installment} + ₹{per_day} a day for {catchup_days} days.",
        "hi": "हो गया। {range} को कोई कटौती नहीं होगी। {start} से {catchup_days} दिन तक रोज़ ₹{installment} + ₹{per_day} कटेगा।",
        "kn": "ಆಯ್ತು. {range} ರಂದು ಯಾವುದೇ ಕಡಿತ ಇರುವುದಿಲ್ಲ. {start} ರಿಂದ {catchup_days} ದಿನಗಳವರೆಗೆ ದಿನಕ್ಕೆ ₹{installment} + "
              "₹{per_day} ಕಡಿತವಾಗುತ್ತದೆ.",
    },
    "confirm_reduce": {
        "en": "Done. From {start}, ₹{half} a day for {days} days. The remaining ₹{deferred} is added as {extra_days} "
              "days at the end.",
        "hi": "हो गया। {start} से {days} दिन तक रोज़ ₹{half} कटेगा। बाकी ₹{deferred} अंत में {extra_days} दिनों में जुड़ेगा।",
        "kn": "ಆಯ್ತು. {start} ರಿಂದ {days} ದಿನಗಳವರೆಗೆ ದಿನಕ್ಕೆ ₹{half} ಕಡಿತವಾಗುತ್ತದೆ. ಉಳಿದ ₹{deferred} ಕೊನೆಯಲ್ಲಿ "
              "{extra_days} ದಿನಗಳಾಗಿ ಸೇರುತ್ತದೆ.",
    },
    "quiet": {"en": "We won't message you again until {resume}.",
              "hi": "{resume} तक हम आपको कोई संदेश नहीं भेजेंगे।",
              "kn": "{resume} ವರೆಗೆ ನಾವು ನಿಮಗೆ ಯಾವುದೇ ಸಂದೇಶ ಕಳುಹಿಸುವುದಿಲ್ಲ."},
    "best": {"en": "All the best.", "hi": "शुभकामनाएँ।", "kn": "ಶುಭವಾಗಲಿ."},
    "handoff_bereavement": {
        "en": "We are very sorry for your loss. We have stopped all reminders. A person from {lender} will contact you "
              "only when you are ready. You don't need to do anything now.",
        "hi": "आपके नुकसान का हमें बहुत दुख है। हमने सभी रिमाइंडर रोक दिए हैं। {lender} से कोई व्यक्ति तभी संपर्क करेगा "
              "जब आप तैयार हों। अभी आपको कुछ करने की ज़रूरत नहीं है।",
        "kn": "ನಿಮ್ಮ ನಷ್ಟಕ್ಕೆ ನಮಗೆ ತುಂಬಾ ದುಃಖವಿದೆ. ನಾವು ಎಲ್ಲಾ ಜ್ಞಾಪನೆಗಳನ್ನು ನಿಲ್ಲಿಸಿದ್ದೇವೆ. ನೀವು ಸಿದ್ಧರಾದಾಗ ಮಾತ್ರ {lender} "
              "ನಿಂದ ಒಬ್ಬರು ನಿಮ್ಮನ್ನು ಸಂಪರ್ಕಿಸುತ್ತಾರೆ. ಈಗ ನೀವು ಏನೂ ಮಾಡಬೇಕಾಗಿಲ್ಲ.",
    },
    "handoff_medical": {
        "en": "We hope your family member recovers soon. We have stopped reminders and passed your case to a person at "
              "{lender}, who can give you more time. You don't need to do anything now.",
        "hi": "हम आशा करते हैं कि आपके परिवार के सदस्य जल्दी ठीक हो जाएँ। हमने रिमाइंडर रोक दिए हैं और आपका मामला {lender} "
              "के एक व्यक्ति को सौंप दिया है, जो आपको और समय दे सकते हैं। अभी आपको कुछ करने की ज़रूरत नहीं है।",
        "kn": "ನಿಮ್ಮ ಕುಟುಂಬದವರು ಬೇಗ ಗುಣಮುಖರಾಗಲಿ. ನಾವು ಜ್ಞಾಪನೆಗಳನ್ನು ನಿಲ್ಲಿಸಿ, ನಿಮ್ಮ ವಿಷಯವನ್ನು {lender} ನ ಒಬ್ಬ ವ್ಯಕ್ತಿಗೆ "
              "ಒಪ್ಪಿಸಿದ್ದೇವೆ. ಅವರು ನಿಮಗೆ ಹೆಚ್ಚಿನ ಸಮಯ ನೀಡಬಹುದು. ಈಗ ನೀವು ಏನೂ ಮಾಡಬೇಕಾಗಿಲ್ಲ.",
    },
    "waiver_decline": {
        "en": "I can't waive or reduce dues. Only {lender}'s team can decide that, and I've sent them your request.",
        "hi": "मैं बकाया माफ़ या कम नहीं कर सकता। यह फ़ैसला केवल {lender} की टीम ले सकती है, और मैंने आपका अनुरोध उन्हें "
              "भेज दिया है।",
        "kn": "ಬಾಕಿ ಮನ್ನಾ ಮಾಡಲು ಅಥವಾ ಕಡಿಮೆ ಮಾಡಲು ನನಗೆ ಸಾಧ್ಯವಿಲ್ಲ. ಅದನ್ನು {lender} ತಂಡ ಮಾತ್ರ ನಿರ್ಧರಿಸಬಹುದು, ನಿಮ್ಮ "
              "ವಿನಂತಿಯನ್ನು ಅವರಿಗೆ ಕಳುಹಿಸಿದ್ದೇನೆ.",
    },
    "dispute": {
        "en": "Thanks for telling us. I've sent this to {lender}'s grievance officer and stopped reminders about it until "
              "it's resolved.",
        "hi": "बताने के लिए धन्यवाद। मैंने यह मामला {lender} के शिकायत अधिकारी को भेज दिया है और इसके हल होने तक इससे जुड़े "
              "रिमाइंडर रोक दिए हैं।",
        "kn": "ತಿಳಿಸಿದ್ದಕ್ಕೆ ಧನ್ಯವಾದಗಳು. ಈ ವಿಷಯವನ್ನು {lender} ನ ಕುಂದುಕೊರತೆ ಅಧಿಕಾರಿಗೆ ಕಳುಹಿಸಿದ್ದೇನೆ. ಇದು ಬಗೆಹರಿಯುವವರೆಗೆ "
              "ಇದರ ಬಗ್ಗೆ ಜ್ಞಾಪನೆಗಳನ್ನು ನಿಲ್ಲಿಸಿದ್ದೇನೆ.",
    },
    "stop_ack": {
        "en": "Understood. We won't message you again. If you need help with your installment, reply HELP any time.",
        "hi": "समझ गए। हम आपको दोबारा संदेश नहीं भेजेंगे। किस्त में मदद चाहिए तो कभी भी HELP लिखें।",
        "kn": "ಅರ್ಥವಾಯಿತು. ನಾವು ಮತ್ತೆ ಸಂದೇಶ ಕಳುಹಿಸುವುದಿಲ್ಲ. ಕಂತಿನ ಬಗ್ಗೆ ಸಹಾಯ ಬೇಕಿದ್ದರೆ ಯಾವಾಗ ಬೇಕಾದರೂ HELP ಎಂದು ಉತ್ತರಿಸಿ.",
    },
    "normal_ack": {
        "en": "Thanks, good to hear. Nothing changes on your loan.",
        "hi": "धन्यवाद, यह सुनकर अच्छा लगा। आपके लोन में कुछ नहीं बदलेगा।",
        "kn": "ಧನ್ಯವಾದಗಳು, ಕೇಳಿ ಸಂತೋಷವಾಯಿತು. ನಿಮ್ಮ ಸಾಲದಲ್ಲಿ ಏನೂ ಬದಲಾಗುವುದಿಲ್ಲ.",
    },
    "decline_ack": {
        "en": "Okay. Your installments continue as usual. If things change, just reply and I'll check what's possible.",
        "hi": "ठीक है। आपकी किस्तें पहले की तरह चलेंगी। अगर कुछ बदले तो बस जवाब दीजिए, मैं देखूँगा क्या हो सकता है।",
        "kn": "ಸರಿ. ನಿಮ್ಮ ಕಂತುಗಳು ಎಂದಿನಂತೆ ಮುಂದುವರಿಯುತ್ತವೆ. ಏನಾದರೂ ಬದಲಾದರೆ ಉತ್ತರಿಸಿ, ಏನು ಸಾಧ್ಯ ಎಂದು ನೋಡುತ್ತೇನೆ.",
    },
    "ask_reason": {
        "en": "Sorry, I didn't catch that. Is the shop closed, or is business slow? You can reply by voice.",
        "hi": "माफ़ कीजिए, मैं समझ नहीं पाया। क्या दुकान बंद है, या धंधा कम है? आप आवाज़ में भी जवाब दे सकते हैं।",
        "kn": "ಕ್ಷಮಿಸಿ, ನನಗೆ ಅರ್ಥವಾಗಲಿಲ್ಲ. ಅಂಗಡಿ ಮುಚ್ಚಿದೆಯಾ, ಅಥವಾ ವ್ಯಾಪಾರ ಕಡಿಮೆಯಾ? ನೀವು ಧ್ವನಿಯಲ್ಲೂ ಉತ್ತರಿಸಬಹುದು.",
    },
    "payahead_offer": {
        "en": "Want to be ready for the next slow week? Turn on pay-ahead: on days you sell ₹{threshold} or more, "
              "₹{amount} goes towards future installments. On a slow day, your installment is paid from it first. You "
              "can turn it off any time.",
        "hi": "क्या आप अगले धीमे हफ़्ते के लिए तैयार रहना चाहते हैं? अग्रिम किस्त चालू करें: जिस दिन बिक्री ₹{threshold} या उससे "
              "ज़्यादा हो, उस दिन ₹{amount} आगे की किस्तों में पहले से जमा होगा। कम बिक्री वाले दिन आपकी किस्त पहले उसी से "
              "कटेगी। इसे कभी भी बंद कर सकते हैं।",
        "kn": "ಮುಂದಿನ ಕಡಿಮೆ ವ್ಯಾಪಾರದ ವಾರಕ್ಕೆ ಸಿದ್ಧರಾಗಲು ಮುಂಗಡ ಕಂತು ಆನ್ ಮಾಡಿ: ₹{threshold} ಅಥವಾ ಹೆಚ್ಚು ಮಾರಾಟವಾದ ದಿನ, "
              "₹{amount} ಮುಂದಿನ ಕಂತುಗಳಿಗೆ ಮುಂಚಿತವಾಗಿ ಜಮೆಯಾಗುತ್ತದೆ. ವ್ಯಾಪಾರ ಕಡಿಮೆ ಇದ್ದ ದಿನ ನಿಮ್ಮ ಕಂತು ಮೊದಲು ಅದರಿಂದಲೇ "
              "ಕಟ್ಟಲಾಗುತ್ತದೆ. ಯಾವಾಗ ಬೇಕಾದರೂ ಆಫ್ ಮಾಡಬಹುದು.",
    },
    "payahead_on": {
        "en": "Pay-ahead is on. On days you sell ₹{threshold} or more, ₹{amount} goes towards future installments. You "
              "can turn it off any time from your home screen.",
        "hi": "अग्रिम किस्त चालू हो गई है। जिस दिन बिक्री ₹{threshold} या उससे ज़्यादा हो, ₹{amount} आगे की किस्तों में जमा "
              "होगा। इसे कभी भी होम स्क्रीन से बंद कर सकते हैं।",
        "kn": "ಮುಂಗಡ ಕಂತು ಆನ್ ಆಗಿದೆ. ₹{threshold} ಅಥವಾ ಹೆಚ್ಚು ಮಾರಾಟವಾದ ದಿನ ₹{amount} ಮುಂದಿನ ಕಂತುಗಳಿಗೆ ಜಮೆಯಾಗುತ್ತದೆ. "
              "ಮುಖಪುಟದಿಂದ ಯಾವಾಗ ಬೇಕಾದರೂ ಆಫ್ ಮಾಡಬಹುದು.",
    },
    "payahead_off": {
        "en": "Pay-ahead is off. The ₹{balance} already paid ahead still counts towards your loan.",
        "hi": "अग्रिम किस्त बंद कर दी गई है। पहले से जमा ₹{balance} आपके लोन में गिना जाएगा।",
        "kn": "ಮುಂಗಡ ಕಂತು ಆಫ್ ಆಗಿದೆ. ಈಗಾಗಲೇ ಮುಂಚಿತವಾಗಿ ಕಟ್ಟಿದ ₹{balance} ನಿಮ್ಮ ಸಾಲಕ್ಕೆ ಸೇರುತ್ತದೆ.",
    },
    "consent_on": {
        "en": "Thank you. Sambhal will watch your daily sales and message you only when it can help, between 8 am and "
              "7 pm.",
        "hi": "धन्यवाद। संभल आपकी रोज़ की बिक्री पर नज़र रखेगा और सिर्फ़ तभी, सुबह 8 से शाम 7 बजे के बीच, संदेश भेजेगा जब "
              "मदद कर सके।",
        "kn": "ಧನ್ಯವಾದಗಳು. ಸಂಭಲ್ ನಿಮ್ಮ ದಿನದ ಮಾರಾಟವನ್ನು ಗಮನಿಸುತ್ತದೆ ಮತ್ತು ಸಹಾಯ ಮಾಡಲು ಸಾಧ್ಯವಾದಾಗ ಮಾತ್ರ, ಬೆಳಿಗ್ಗೆ 8 ರಿಂದ ಸಂಜೆ "
              "7 ರ ನಡುವೆ ಸಂದೇಶ ಕಳುಹಿಸುತ್ತದೆ.",
    },
    "consent_off": {
        "en": "Okay. Sambhal will not send you messages. If needed, a person from {lender} may call you between 8 am and "
              "7 pm.",
        "hi": "ठीक है। संभल आपको संदेश नहीं भेजेगा। ज़रूरत हो तो {lender} से कोई सुबह 8 से शाम 7 बजे के बीच कॉल कर सकता है।",
        "kn": "ಸರಿ. ಸಂಭಲ್ ನಿಮಗೆ ಸಂದೇಶ ಕಳುಹಿಸುವುದಿಲ್ಲ. ಅಗತ್ಯವಿದ್ದರೆ {lender} ನ ಒಬ್ಬರು ಬೆಳಿಗ್ಗೆ 8 ರಿಂದ ಸಂಜೆ 7 ರ ನಡುವೆ ಕರೆ "
              "ಮಾಡಬಹುದು.",
    },
    "plan_in": {"en": "Shop closed {range}.", "hi": "{range} दुकान बंद रहेगी।", "kn": "{range} ಅಂಗಡಿ ಮುಚ್ಚಿರುತ್ತದೆ."},
    "plan_thanks": {"en": "Thanks for telling us early.", "hi": "पहले से बताने के लिए धन्यवाद।",
                    "kn": "ಮುಂಚಿತವಾಗಿ ತಿಳಿಸಿದ್ದಕ್ಕೆ ಧನ್ಯವಾದಗಳು."},
    "pause_ended": {
        "en": "Your shop was open on {open_day}, so the pause ended early and there is less to catch up. From {start}: "
              "₹{installment} + ₹{per_day} a day for {catchup_days} days.",
        "hi": "{open_day} को आपकी दुकान खुली थी, इसलिए छूट जल्दी खत्म हो गई और बकाया कम हो गया। {start} से {catchup_days} दिन "
              "तक रोज़ ₹{installment} + ₹{per_day} कटेगा।",
        "kn": "{open_day} ರಂದು ನಿಮ್ಮ ಅಂಗಡಿ ತೆರೆದಿತ್ತು, ಆದ್ದರಿಂದ ವಿರಾಮ ಬೇಗ ಮುಗಿದಿದೆ ಮತ್ತು ಬಾಕಿ ಕಂತು ಕಡಿಮೆಯಾಗಿದೆ. {start} ರಿಂದ "
              "{catchup_days} ದಿನಗಳವರೆಗೆ ದಿನಕ್ಕೆ ₹{installment} + ₹{per_day} ಕಡಿತವಾಗುತ್ತದೆ.",
    },
    "pause_cancelled": {
        "en": "Your shop was open on {open_day}, so the pause wasn't needed. Your installments continue as usual.",
        "hi": "{open_day} को आपकी दुकान खुली थी, इसलिए छूट की ज़रूरत नहीं पड़ी। आपकी किस्तें पहले की तरह चलेंगी।",
        "kn": "{open_day} ರಂದು ನಿಮ್ಮ ಅಂಗಡಿ ತೆರೆದಿತ್ತು, ಆದ್ದರಿಂದ ವಿರಾಮದ ಅಗತ್ಯ ಬರಲಿಲ್ಲ. ನಿಮ್ಮ ಕಂತುಗಳು ಎಂದಿನಂತೆ ಮುಂದುವರಿಯುತ್ತವೆ.",
    },
    "staff_pause": {
        "en": "{lender}'s team has approved a {days}-day pause: no deduction on {range}. The ₹{paused} is collected as "
              "₹{per_day} extra a day for {catchup_days} days from {start}.",
        "hi": "{lender} की टीम ने {days} दिन की छूट मंज़ूर की है: {range} को कोई कटौती नहीं। ₹{paused} की रकम {start} से "
              "{catchup_days} दिन तक रोज़ ₹{per_day} अतिरिक्त कटेगी।",
        "kn": "{lender} ತಂಡ {days} ದಿನಗಳ ವಿರಾಮವನ್ನು ಒಪ್ಪಿದೆ: {range} ರಂದು ಕಡಿತ ಇಲ್ಲ. ₹{paused} ಮೊತ್ತವನ್ನು {start} ರಿಂದ "
              "{catchup_days} ದಿನಗಳವರೆಗೆ ದಿನಕ್ಕೆ ₹{per_day} ಹೆಚ್ಚುವರಿಯಾಗಿ ಕಡಿತ ಮಾಡಲಾಗುತ್ತದೆ.",
    },
    "area_relief": {
        "en": "Because of the disruption in {area}, {lender} has paused your deductions on {range}. The ₹{paused} is "
              "collected as ₹{per_day} extra a day for {catchup_days} days from {start}. Reply any time if you need help.",
        "hi": "{area} इलाके में आई परेशानी की वजह से {lender} ने {range} को आपकी कटौती रोक दी है। ₹{paused} की रकम {start} से "
              "{catchup_days} दिन तक रोज़ ₹{per_day} अतिरिक्त कटेगी। मदद चाहिए तो कभी भी जवाब दीजिए।",
        "kn": "{area} ಪ್ರದೇಶದಲ್ಲಿನ ತೊಂದರೆಯಿಂದಾಗಿ {lender} ನಿಮ್ಮ ಕಡಿತವನ್ನು {range} ರಂದು ನಿಲ್ಲಿಸಿದೆ. ₹{paused} ಮೊತ್ತವನ್ನು {start} "
              "ರಿಂದ {catchup_days} ದಿನಗಳವರೆಗೆ ದಿನಕ್ಕೆ ₹{per_day} ಹೆಚ್ಚುವರಿಯಾಗಿ ಕಡಿತ ಮಾಡಲಾಗುತ್ತದೆ. ಸಹಾಯ ಬೇಕಿದ್ದರೆ ಯಾವಾಗ ಬೇಕಾದರೂ "
              "ಉತ್ತರಿಸಿ.",
    },
    "human_ack": {
        "en": "Sure. I've asked a person from {lender} to call you. They call only between 8 am and 7 pm.",
        "hi": "ज़रूर। मैंने {lender} के एक व्यक्ति से आपको कॉल करने को कहा है। वे सिर्फ़ सुबह 8 से शाम 7 बजे के बीच कॉल "
              "करते हैं।",
        "kn": "ಖಂಡಿತ. {lender} ನ ಒಬ್ಬರು ನಿಮಗೆ ಕರೆ ಮಾಡುವಂತೆ ಕೇಳಿದ್ದೇನೆ. ಅವರು ಬೆಳಿಗ್ಗೆ 8 ರಿಂದ ಸಂಜೆ 7 ರ ನಡುವೆ ಮಾತ್ರ ಕರೆ "
              "ಮಾಡುತ್ತಾರೆ.",
    },
    "ask_reason_help": {
        "en": "We can help. To find the right option, tell us: is the shop closed, or is business slow? You can reply "
              "by voice.",
        "hi": "हम मदद कर सकते हैं। सही विकल्प के लिए बताइए: क्या दुकान बंद है, या धंधा कम है? आप आवाज़ में भी जवाब दे "
              "सकते हैं।",
        "kn": "ನಾವು ಸಹಾಯ ಮಾಡಬಹುದು. ಸರಿಯಾದ ಆಯ್ಕೆಗಾಗಿ ತಿಳಿಸಿ: ಅಂಗಡಿ ಮುಚ್ಚಿದೆಯಾ, ಅಥವಾ ವ್ಯಾಪಾರ ಕಡಿಮೆಯಾ? ನೀವು ಧ್ವನಿಯಲ್ಲೂ "
              "ಉತ್ತರಿಸಬಹುದು.",
    },
    "more_time_staff": {
        "en": "I can't give more days myself. I've asked {lender}'s team about a longer pause. They will contact you "
              "between 8 am and 7 pm.",
        "hi": "मैं खुद और दिन नहीं दे सकता। मैंने {lender} की टीम से लंबी छूट के बारे में पूछा है। वे सुबह 8 से शाम 7 बजे के "
              "बीच संपर्क करेंगे।",
        "kn": "ಹೆಚ್ಚು ದಿನಗಳನ್ನು ನಾನೇ ಕೊಡಲು ಸಾಧ್ಯವಿಲ್ಲ. ದೀರ್ಘ ವಿರಾಮದ ಬಗ್ಗೆ {lender} ತಂಡವನ್ನು ಕೇಳಿದ್ದೇನೆ. ಅವರು ಬೆಳಿಗ್ಗೆ 8 "
              "ರಿಂದ ಸಂಜೆ 7 ರ ನಡುವೆ ಸಂಪರ್ಕಿಸುತ್ತಾರೆ.",
    },
    "offer_still_open": {"en": "The option above is still open if you want it.",
                         "hi": "ऊपर वाला विकल्प अभी भी खुला है, अगर आप चाहें।",
                         "kn": "ಮೇಲಿನ ಆಯ್ಕೆ ಈಗಲೂ ಲಭ್ಯವಿದೆ."},
    "no_option_human": {
        "en": "Right now your loan doesn't qualify for an automatic change. I've sent your case to a person at {lender}, "
              "who will contact you between 8 am and 7 pm.",
        "hi": "अभी आपका लोन अपने-आप बदलाव के लिए योग्य नहीं है। मैंने आपका मामला {lender} के एक व्यक्ति को भेज दिया है, जो "
              "सुबह 8 से शाम 7 बजे के बीच संपर्क करेंगे।",
        "kn": "ಈಗ ನಿಮ್ಮ ಸಾಲ ಸ್ವಯಂಚಾಲಿತ ಬದಲಾವಣೆಗೆ ಅರ್ಹವಾಗಿಲ್ಲ. ನಿಮ್ಮ ವಿಷಯವನ್ನು {lender} ನ ಒಬ್ಬ ವ್ಯಕ್ತಿಗೆ ಕಳುಹಿಸಿದ್ದೇನೆ. "
              "ಅವರು ಬೆಳಿಗ್ಗೆ 8 ರಿಂದ ಸಂಜೆ 7 ರ ನಡುವೆ ಸಂಪರ್ಕಿಸುತ್ತಾರೆ.",
    },
    "balance": {
        "en": "You have ₹{outstanding} left to repay: about {left} daily installments of ₹{installment}.",
        "hi": "आपको अभी ₹{outstanding} चुकाने हैं: ₹{installment} की लगभग {left} रोज़ की किस्तें।",
        "kn": "ನೀವು ಇನ್ನೂ ₹{outstanding} ಪಾವತಿಸಬೇಕಿದೆ: ₹{installment} ನ ಸುಮಾರು {left} ದಿನದ ಕಂತುಗಳು.",
    },
    "welcome_pause": {
        "en": "Welcome back, {first}. Sales are back to normal. Yesterday's deduction was ₹{deducted} (₹{installment} + "
              "₹{per_day} catch-up). We're closing this case now. Reply any time if you need help.",
        "hi": "वापसी पर स्वागत है {first} जी। बिक्री फिर से सामान्य है। कल की कटौती ₹{deducted} थी (₹{installment} + "
              "₹{per_day} बकाया)। अब हम यह मामला बंद कर रहे हैं। मदद चाहिए तो कभी भी जवाब दीजिए।",
        "kn": "ಮರಳಿ ಸ್ವಾಗತ {first} ಅವರೇ. ವ್ಯಾಪಾರ ಮತ್ತೆ ಸಾಮಾನ್ಯವಾಗಿದೆ. ನಿನ್ನೆಯ ಕಡಿತ ₹{deducted} (₹{installment} + "
              "₹{per_day} ಬಾಕಿ ಕಂತು). ಈ ವಿಷಯವನ್ನು ಈಗ ಮುಕ್ತಾಯಗೊಳಿಸುತ್ತಿದ್ದೇವೆ. ಸಹಾಯ ಬೇಕಿದ್ದರೆ ಯಾವಾಗ ಬೇಕಾದರೂ ಉತ್ತರಿಸಿ.",
    },
    "welcome_generic": {
        "en": "Welcome back, {first}. Sales are back to normal. Yesterday's deduction was ₹{deducted}. We're closing "
              "this case now. Reply any time if you need help.",
        "hi": "वापसी पर स्वागत है {first} जी। बिक्री फिर से सामान्य है। कल की कटौती ₹{deducted} थी। अब हम यह मामला बंद कर रहे "
              "हैं। मदद चाहिए तो कभी भी जवाब दीजिए।",
        "kn": "ಮರಳಿ ಸ್ವಾಗತ {first} ಅವರೇ. ವ್ಯಾಪಾರ ಮತ್ತೆ ಸಾಮಾನ್ಯವಾಗಿದೆ. ನಿನ್ನೆಯ ಕಡಿತ ₹{deducted}. ಈ ವಿಷಯವನ್ನು ಈಗ "
              "ಮುಕ್ತಾಯಗೊಳಿಸುತ್ತಿದ್ದೇವೆ. ಸಹಾಯ ಬೇಕಿದ್ದರೆ ಯಾವಾಗ ಬೇಕಾದರೂ ಉತ್ತರಿಸಿ.",
    },
}


# One-tap replies on the merchant's phone. Each is a plain sentence the reader understands (tested), so a tap
# goes through exactly the same path as a spoken or typed reply.
QUICK_REPLIES = {
    "family": {"kn": "ಮನೆಯಲ್ಲಿ ಕಾರ್ಯಕ್ರಮ ಇದೆ, ಅಂಗಡಿ ಮುಚ್ಚಿರುತ್ತೆ", "hi": "घर में समारोह है, दुकान बंद रहेगी",
               "en": "Family function at home, shop closed"},
    "illness": {"kn": "ನನಗೆ ಹುಷಾರಿಲ್ಲ", "hi": "मेरी तबीयत खराब है", "en": "I am unwell"},
    "closed": {"kn": "ಅಂಗಡಿ ಕೆಲವು ದಿನ ಮುಚ್ಚಿದೆ", "hi": "दुकान कुछ दिन बंद है", "en": "Shop is closed for a few days"},
    "slow": {"kn": "ವ್ಯಾಪಾರ ಕಡಿಮೆ ಇದೆ", "hi": "धंधा कम है", "en": "Business is slow"},
    "hospital": {"kn": "ಮನೆಯವರು ಆಸ್ಪತ್ರೆಯಲ್ಲಿ ಇದ್ದಾರೆ", "hi": "घर में कोई अस्पताल में भर्ती है",
                 "en": "Someone in my family is in hospital"},
    "fine": {"kn": "ಎಲ್ಲಾ ಸರಿ ಇದೆ", "hi": "सब ठीक है", "en": "All fine"},
    "more": {"kn": "ಇನ್ನೂ ಹೆಚ್ಚು ದಿನ ಬೇಕು", "hi": "और दिन चाहिए", "en": "I need more days"},
    "ask": {"kn": "ಇನ್ನೂ ಎಷ್ಟು ಬಾಕಿ ಇದೆ?", "hi": "अभी कितना बाकी है?", "en": "How much is left to pay?"},
    "person": {"kn": "ನಾನು ಒಬ್ಬ ವ್ಯಕ್ತಿಯೊಂದಿಗೆ ಮಾತನಾಡಬೇಕು", "hi": "मुझे किसी व्यक्ति से बात करनी है",
               "en": "I want to talk to a person"},
}
# Sambhal's promise to the merchant. Each one is a rule in code (guardrails.py, nlu.py, world.py) and is proven by
# the scenario checks and unit tests listed with it (the Proof tab shows them passing).
PROMISES = [
    {"key": "family", "icon": "🏠", "rule": "Borrower only · AI message check", "checks": ["V02", "V03"],
     "tests": ["test_never_contacts_or_mentions_family"],
     "text": {"en": "We never contact your family, friends or neighbours.",
              "hi": "हम आपके परिवार, दोस्तों या पड़ोसियों से कभी संपर्क नहीं करेंगे।",
              "kn": "ನಿಮ್ಮ ಕುಟುಂಬ, ಸ್ನೇಹಿತರು ಅಥವಾ ನೆರೆಹೊರೆಯವರನ್ನು ನಾವು ಎಂದಿಗೂ ಸಂಪರ್ಕಿಸುವುದಿಲ್ಲ."}},
    {"key": "hours", "icon": "🕗", "rule": "Contact hours", "checks": ["C01", "C02", "C03", "C04"], "tests": [],
     "text": {"en": "We contact you only between 8 am and 7 pm.",
              "hi": "हम सिर्फ़ सुबह 8 से शाम 7 बजे के बीच संपर्क करेंगे।",
              "kn": "ಬೆಳಿಗ್ಗೆ 8 ರಿಂದ ಸಂಜೆ 7 ರ ನಡುವೆ ಮಾತ್ರ ನಿಮ್ಮನ್ನು ಸಂಪರ್ಕಿಸುತ್ತೇವೆ."}},
    {"key": "quiet", "icon": "🤫", "rule": "Sensitive situation · Family function",
     "checks": ["S01", "S02", "S05", "S07", "S08"], "tests": [],
     "text": {"en": "We stay quiet during a death, a hospital stay or a wedding in your family.",
              "hi": "परिवार में मृत्यु, अस्पताल या शादी के समय हम चुप रहेंगे।",
              "kn": "ಕುಟುಂಬದಲ್ಲಿ ಸಾವು, ಆಸ್ಪತ್ರೆ ಅಥವಾ ಮದುವೆ ಇದ್ದಾಗ ನಾವು ಸುಮ್ಮನಿರುತ್ತೇವೆ."}},
    {"key": "person", "icon": "📞", "rule": "Talk to a person", "checks": [],
     "tests": ["test_talk_to_a_person_keeps_the_offer_open", "test_one_tap_replies_read_correctly"],
     "text": {"en": "You can always talk to a person. Just ask.",
              "hi": "आप कभी भी किसी व्यक्ति से बात कर सकते हैं। बस कहिए।",
              "kn": "ನೀವು ಯಾವಾಗ ಬೇಕಾದರೂ ಒಬ್ಬ ವ್ಯಕ್ತಿಯೊಂದಿಗೆ ಮಾತನಾಡಬಹುದು. ಕೇಳಿದರೆ ಸಾಕು."}},
    {"key": "menu", "icon": "🧾", "rule": "Lender's menu only", "checks": ["P01", "P02", "P06", "P07", "P10"], "tests": [],
     "text": {"en": "Help from Sambhal never costs extra, and every change to your loan is explained in your language.",
              "hi": "संभल की मदद का कोई अतिरिक्त शुल्क नहीं है, और लोन में हर बदलाव आपकी भाषा में समझाया जाएगा।",
              "kn": "ಸಂಭಲ್ ಸಹಾಯಕ್ಕೆ ಯಾವುದೇ ಹೆಚ್ಚುವರಿ ಶುಲ್ಕವಿಲ್ಲ. ನಿಮ್ಮ ಸಾಲದಲ್ಲಿನ ಪ್ರತಿಯೊಂದು ಬದಲಾವಣೆಯನ್ನು ನಿಮ್ಮ ಭಾಷೆಯಲ್ಲಿ "
                    "ವಿವರಿಸುತ್ತೇವೆ."}},
    {"key": "stop", "icon": "✋", "rule": "Stop request · Consent", "checks": ["S09", "I01"],
     "tests": ["test_consent_can_be_withdrawn_and_given"],
     "text": {"en": "Say STOP, or switch Sambhal off, any time, and we stop.",
              "hi": "कभी भी STOP कहिए या संभल बंद कीजिए, हम रुक जाएँगे।",
              "kn": "ಯಾವಾಗ ಬೇಕಾದರೂ STOP ಎಂದು ಹೇಳಿ ಅಥವಾ ಸಂಭಲ್ ಆಫ್ ಮಾಡಿ, ನಾವು ನಿಲ್ಲಿಸುತ್ತೇವೆ."}},
]

PAYAHEAD_LABEL = {"kn": "ಮುಂಗಡ ಕಂತು", "hi": "अग्रिम किस्त", "en": "Pay-ahead"}
QUICK_INTENT = {"family": "family_event", "illness": "illness", "closed": "temporary_closure", "slow": "business_slow",
                "hospital": "medical_emergency", "fine": "business_normal", "more": "need_time", "ask": "question",
                "person": "talk_to_person"}


# Place and reason names in the merchant's language.
AREA_LOCAL = {"Bellandur": {"en": "Bellandur", "kn": "ಬೆಳ್ಳಂದೂರು", "hi": "बेलंदूर"}}
PLAN_REASON = {
    "family_event": {"en": "Family function", "kn": "ಮನೆಯಲ್ಲಿ ಕಾರ್ಯಕ್ರಮ", "hi": "घर में समारोह"},
    "illness": {"en": "Unwell", "kn": "ಹುಷಾರಿಲ್ಲ", "hi": "तबीयत खराब"},
    "temporary_closure": {"en": "Travel or repairs", "kn": "ಪ್ರಯಾಣ ಅಥವಾ ರಿಪೇರಿ", "hi": "यात्रा या मरम्मत"},
    "medical_emergency": {"en": "Hospital", "kn": "ಆಸ್ಪತ್ರೆ", "hi": "अस्पताल"},
}


def _fmt_facts(f: dict, lang: str) -> dict:
    out = {"lender": LENDER_NAME}
    for k, v in f.items():
        if isinstance(v, dict) and lang in v:          # already in each language
            out[k] = v[lang]
        elif isinstance(v, datetime):
            out[k] = fdate(v.date(), lang, weekday=True)
        elif isinstance(v, date):
            out[k] = fdate(v, lang)
        else:
            out[k] = v
    if lang == "en" and "first_en" in f:
        out["first"] = f["first_en"]
    if "pause_from" in f and "pause_to" in f:
        out["range"] = frange(f["pause_from"], f["pause_to"], lang)
    return out


def line(kind: str, lang: str, **facts) -> str:
    lang = lang if lang in ("en", "hi", "kn") else "en"
    return T[kind][lang].format(**_fmt_facts(facts, lang))


def compose(parts: list[tuple[str, dict]], lang: str) -> dict:
    """Join several template lines; return the text in the merchant's language and in English."""
    return {
        "text": " ".join(line(k, lang, **f) for k, f in parts),
        "text_en": " ".join(line(k, "en", **f) for k, f in parts),
    }


def header(lang: str) -> str:
    return HEADER.get(lang, HEADER["en"]).format(lender=LENDER_NAME)


def footer() -> str:
    return GRIEVANCE_OFFICER
