/* Sambhal demo UI. Plain JS, no build step. */
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
let S = null;                 // last /api/state snapshot
let focus = "M01";
let tab = "cases";
let lastSpoken = Infinity;    // highest outbound message id already spoken (Infinity until first load)
let busy = false;
let proofLoaded = false;

const STATE_LABEL = {
  held: "Message held", waiting: "Waiting for reply", offered: "Offer sent", accepted: "Relief active",
  recovered: "Recovered", closed: "Closed", with_person: "With a person", review: "Review",
  grievance: "Grievance", stopped: "Stopped", declined: "Declined",
};
const LANG_LABEL = { kn: "Kannada", hi: "Hindi", en: "English" };
const HOLD_WHY = { "Contact hours": "RBI contact hours, 8 am–7 pm", "Family function": "the family function to end" };
const RAVI_LINE = "ಮನೆಯಲ್ಲಿ ಮದುವೆ ಇದೆ, ಭಾನುವಾರದವರೆಗೆ ಅಂಗಡಿ ಮುಚ್ಚಿರುತ್ತೆ.";
const TRY_LINES = [
  { text: "Business is slow because of the rain", label: "Business is slow" },
  { text: "Can you waive the interest?", label: "Asks for a waiver" },
  { text: "ನಮ್ಮ ಅಮ್ಮ ನಿನ್ನೆ ತೀರಿಕೊಂಡರು", label: "ನಮ್ಮ ಅಮ್ಮ ತೀರಿಕೊಂಡರು (bereavement)" },
];

// ---------------------------------------------------------------- utils
async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) {
    let e = {};
    try { e = await r.json(); } catch (_) { /* not JSON */ }
    throw new Error(e.detail || e.error || r.statusText);
  }
  return r.json();
}
const post = (p, b) => api(p, { method: "POST", body: JSON.stringify(b || {}) });
function esc(s) { return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function inr(n) {
  const neg = n < 0; let s = String(Math.round(Math.abs(n)));
  if (s.length > 3) { let head = s.slice(0, -3); const tail = s.slice(-3); const parts = []; while (head.length > 2) { parts.unshift(head.slice(-2)); head = head.slice(0, -2); } if (head) parts.unshift(head); s = parts.join(",") + "," + tail; }
  return (neg ? "-₹" : "₹") + s;
}
const D = iso => new Date(iso);
function fmtTime(iso) { const d = D(iso); let h = d.getHours(); const m = d.getMinutes(); const ap = h >= 12 ? "pm" : "am"; h = h % 12 || 12; return `${h}:${String(m).padStart(2, "0")} ${ap}`; }
function fmtDay(iso) { return D(iso).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" }); }
function fmtDayTime(iso) { return `${fmtDay(iso)}, ${fmtTime(iso)}`; }
function pct(x) { return `${Math.round(x * 100)}%`; }
function toast(msg, ms = 3200) { const t = $("#toast"); t.textContent = msg; t.hidden = false; clearTimeout(toast._t); toast._t = setTimeout(() => (t.hidden = true), ms); }
function pill(state) { return `<span class="pill st-${state}">${esc(STATE_LABEL[state] || state)}</span>`; }
function langAttr(l) { return l === "kn" ? 'lang="kn"' : l === "hi" ? 'lang="hi"' : 'lang="en"'; }

// ---------------------------------------------------------------- load & render
async function load(f) {
  if (f) focus = f;
  S = await api(`/api/state?focus=${focus}`);
  focus = S.focus;
  if (lastSpoken === Infinity) lastSpoken = sentOutId();
  if (seenOut[focus] === undefined) seenOut[focus] = maxOutId();
  render();
}
function sentOutId() {         // newest note actually delivered: a held message (Thursday night) isn't heard yet
  const th = S?.merchant?.thread || [];
  return Math.max(0, ...th.filter(m => m.dir === "out" && m.status === "sent").map(m => m.id));
}
function maxOutId() {
  const th = S?.merchant?.thread || [];
  return Math.max(0, ...th.filter(m => m.dir === "out").map(m => m.id));
}
function render() {
  renderTop(); renderStory(); renderPhone(); renderMCard(); renderCases();
  $("#caseCount").textContent = S.counts.cases;
  $("#auditCount").textContent = S.audit_count;
  if (tab === "week") renderWeek();
  if (tab === "audit") renderAudit();
}

function renderTop() {
  $("#clockDay").textContent = fmtDay(S.now);
  $("#clockTime").textContent = fmtTime(S.now);
  const h = D(S.now).getHours(); const open = h >= 8 && h < 19;
  const w = $("#clockWin"); w.textContent = open ? "Contact window open" : "Outside 8 am–7 pm"; w.classList.toggle("closed", !open);
  const st = S.status;
  const cv = $("#chipVoice");
  cv.textContent = st.voice.on ? "Voice: Sarvam" : st.sarvam_out ? "Voice: cached (no Sarvam credits)" : st.voice.configured ? "Voice: cached audio" : "Voice: browser";
  cv.className = "chip " + (st.voice.on ? "on" : "off");
  cv.title = st.voice.on ? `${st.voice.stt} · ${st.voice.tts} (${st.voice.speaker})` : "No Sarvam key, or offline mode: cached audio and the browser's own voice";
  const ca = $("#chipAI");
  ca.textContent = st.llm.on ? `AI: ${st.llm.model}` : "AI: rules only";
  ca.className = "chip " + (st.llm.on ? "on" : "off");
  ca.title = st.llm.on ? `${st.llm.provider} · understanding replies${st.llm.rewrite ? " · phrasing messages (checked)" : ""}` : "Multilingual rules reader. Add an LLM key for free-form understanding.";
  $("#offlineToggle").checked = st.offline;
}

function renderStory() {
  const ol = $("#stepDots"); ol.innerHTML = "";
  S.steps.forEach(s => {
    if (s.extra && !S.steps[s.n - 1].extra) { const sep = document.createElement("li"); sep.className = "sep"; sep.title = "Beyond Ravi (optional)"; ol.appendChild(sep); }
    const li = document.createElement("li");
    if (s.extra) li.className = "extra";
    const b = document.createElement("button");
    b.textContent = s.n; b.title = s.title;
    b.className = s.n < S.step ? "done" : s.n === S.step ? "now" : "";
    b.onclick = () => goStep(s.n);
    li.appendChild(b); ol.appendChild(li);
  });
  const cur = S.steps[S.step];
  $("#capNum").textContent = `${S.step} / ${S.steps.length - 1}`;
  $("#capTitle").textContent = cur.title;
  $("#capText").textContent = cur.caption;
  $("#btnPrev").disabled = S.step === 0;
  $("#btnNext").disabled = S.step >= S.steps.length - 1;
  $("#btnNext").textContent = S.step >= S.steps.length - 1 ? "End" : "Next ▶";
  document.documentElement.style.setProperty("--story-h", `${$(".story").offsetHeight}px`);
}

// ---------------------------------------------------------------- phone: the merchant's app
// Words on the merchant's screens, in their language. English shows underneath when EN is on.
const UI = {
  en: {
    home: "Home", messages: "Messages", loan: "My loan", hello: "Namaste", last_day: "Last settlement", sales: "Sales",
    deducted: "Deducted", next_ded: "Next deduction", paused: "Paused", catchup: "incl. catch-up", pending: "incl. pending",
    tell_closure: "Tell us about a closure", ask_loan: "Ask about my loan", talk_person: "Talk to a person",
    msg_waiting: "Sambhal has a message for you", open: "Open", pause_on: "Your pause is on",
    person_call: "A person from the lender will call you, 8 am–7 pm", recovered: "Sales are back to normal",
    tap_speak: "Tap to speak", stop_rec: "Tap to stop", what_happened: "Tell us what happened",
    family: "Family function", illness: "Unwell", closed: "Shop closed", slow: "Sales slow", hospital: "Hospital",
    fine: "All fine", more: "Need more days", person: "Talk to a person", accept: "Accept", accepted: "Accepted",
    outstanding: "Left to repay", paid: "paid", ends: "Last installment, about", daily: "Daily installment",
    last7: "Last 7 days", next7: "Next 7 days", no_msgs: "No messages. Sambhal only writes when it can help.",
    type_here: "Type a reply…", l_ok: "Deducted", l_pz: "Paused", l_od: "Overdue", l_cu: "With catch-up",
    new_loan: "Thinking of a new loan? Check what fits",
    payahead: "Pay-ahead", turn_on: "Turn on", turn_off: "Turn off", is_on: "On", paid_ahead: "Paid ahead",
    covers: "covers about {n} days", pa_rule: "₹{a} on days you sell ₹{t} or more", pa_pitch: "Be ready for slow days",
    l_cs: "From pay-ahead",
    promise: "Sambhal's promise", listen: "Listen", consent_yes: "You said yes to Sambhal messages",
    consent_no: "Sambhal messages are off", stop_msgs: "Stop Sambhal messages", start_help: "Turn on Sambhal help",
    help_off_note: "A person from the lender will call if needed.",
    pick_reason: "Reason", from_day: "From", how_many: "How many days", send_plan: "Send to Sambhal",
  },
  kn: {
    home: "ಮುಖಪುಟ", messages: "ಸಂದೇಶಗಳು", loan: "ನನ್ನ ಸಾಲ", hello: "ನಮಸ್ಕಾರ", last_day: "ಕೊನೆಯ ದಿನದ ಲೆಕ್ಕ", sales: "ಮಾರಾಟ",
    deducted: "ಕಡಿತ", next_ded: "ಮುಂದಿನ ಕಡಿತ", paused: "ವಿರಾಮ", catchup: "ಬಾಕಿ ಕಂತು ಸೇರಿ", pending: "ಬಾಕಿ ಸೇರಿ",
    tell_closure: "ಅಂಗಡಿ ಮುಚ್ಚುವ ಬಗ್ಗೆ ತಿಳಿಸಿ", ask_loan: "ನನ್ನ ಸಾಲದ ಬಗ್ಗೆ ಕೇಳಿ", talk_person: "ಒಬ್ಬ ವ್ಯಕ್ತಿಯೊಂದಿಗೆ ಮಾತನಾಡಿ",
    msg_waiting: "ಸಂಭಾಲ್‌ನಿಂದ ನಿಮಗೆ ಸಂದೇಶ ಬಂದಿದೆ", open: "ತೆರೆಯಿರಿ", pause_on: "ನಿಮ್ಮ ವಿರಾಮ ಜಾರಿಯಲ್ಲಿದೆ",
    person_call: "ಸಾಲದಾತರ ಕಡೆಯಿಂದ ಒಬ್ಬರು ಬೆಳಿಗ್ಗೆ 8 ರಿಂದ ಸಂಜೆ 7 ರ ನಡುವೆ ಕರೆ ಮಾಡುತ್ತಾರೆ", recovered: "ವ್ಯಾಪಾರ ಮತ್ತೆ ಸಾಮಾನ್ಯವಾಗಿದೆ",
    tap_speak: "ಮಾತನಾಡಲು ಒತ್ತಿ", stop_rec: "ನಿಲ್ಲಿಸಲು ಒತ್ತಿ", what_happened: "ಏನಾಯಿತು ಎಂದು ತಿಳಿಸಿ",
    family: "ಮನೆಯಲ್ಲಿ ಕಾರ್ಯಕ್ರಮ", illness: "ಹುಷಾರಿಲ್ಲ", closed: "ಅಂಗಡಿ ಮುಚ್ಚಿದೆ", slow: "ವ್ಯಾಪಾರ ಕಡಿಮೆ", hospital: "ಆಸ್ಪತ್ರೆ",
    fine: "ಎಲ್ಲಾ ಸರಿ", more: "ಇನ್ನೂ ಹೆಚ್ಚು ದಿನ ಬೇಕು", person: "ವ್ಯಕ್ತಿಯೊಂದಿಗೆ ಮಾತನಾಡಿ", accept: "ಒಪ್ಪುತ್ತೇನೆ", accepted: "ಒಪ್ಪಿದ್ದೀರಿ",
    outstanding: "ಇನ್ನೂ ಪಾವತಿಸಬೇಕಾದದ್ದು", paid: "ಪಾವತಿಸಲಾಗಿದೆ", ends: "ಕೊನೆಯ ಕಂತು, ಸುಮಾರು", daily: "ದಿನದ ಕಂತು",
    last7: "ಕಳೆದ 7 ದಿನಗಳು", next7: "ಮುಂದಿನ 7 ದಿನಗಳು", no_msgs: "ಯಾವುದೇ ಸಂದೇಶವಿಲ್ಲ. ಸಹಾಯ ಮಾಡಲು ಸಾಧ್ಯವಾದಾಗ ಮಾತ್ರ ಸಂಭಾಲ್ ಬರೆಯುತ್ತದೆ.",
    type_here: "ಉತ್ತರ ಬರೆಯಿರಿ…", l_ok: "ಕಡಿತವಾಗಿದೆ", l_pz: "ವಿರಾಮ", l_od: "ಬಾಕಿ", l_cu: "ಬಾಕಿ ಕಂತು ಸೇರಿ",
    new_loan: "ಹೊಸ ಸಾಲ ಬೇಕೇ? ಎಷ್ಟು ಸರಿ ಎಂದು ನೋಡಿ",
    payahead: "ಮುಂಗಡ ಕಂತು", turn_on: "ಆನ್ ಮಾಡಿ", turn_off: "ಆಫ್ ಮಾಡಿ", is_on: "ಆನ್ ಆಗಿದೆ", paid_ahead: "ಮುಂಚಿತವಾಗಿ ಕಟ್ಟಿದ್ದು",
    covers: "ಸುಮಾರು {n} ದಿನದ ಕಂತು", pa_rule: "₹{t} ಅಥವಾ ಹೆಚ್ಚು ಮಾರಾಟವಾದ ದಿನ ₹{a}", pa_pitch: "ಕಡಿಮೆ ವ್ಯಾಪಾರದ ದಿನಗಳಿಗೆ ಸಿದ್ಧರಾಗಿ",
    l_cs: "ಮುಂಗಡದಿಂದ",
    promise: "ಸಂಭಾಲ್‌ನ ಭರವಸೆ", listen: "ಕೇಳಿ", consent_yes: "ನೀವು ಸಂಭಾಲ್ ಸಂದೇಶಗಳಿಗೆ ಒಪ್ಪಿದ್ದೀರಿ",
    consent_no: "ಸಂಭಾಲ್ ಸಂದೇಶಗಳು ಆಫ್ ಆಗಿವೆ", stop_msgs: "ಸಂಭಾಲ್ ಸಂದೇಶಗಳನ್ನು ನಿಲ್ಲಿಸಿ", start_help: "ಸಂಭಾಲ್ ಸಹಾಯ ಆನ್ ಮಾಡಿ",
    help_off_note: "ಅಗತ್ಯವಿದ್ದರೆ ಸಾಲದಾತರ ಕಡೆಯಿಂದ ಒಬ್ಬರು ಕರೆ ಮಾಡುತ್ತಾರೆ.",
    pick_reason: "ಕಾರಣ", from_day: "ಯಾವ ದಿನದಿಂದ", how_many: "ಎಷ್ಟು ದಿನ", send_plan: "ಸಂಭಾಲ್‌ಗೆ ಕಳುಹಿಸಿ",
  },
  hi: {
    home: "होम", messages: "संदेश", loan: "मेरा लोन", hello: "नमस्ते", last_day: "पिछले दिन का हिसाब", sales: "बिक्री",
    deducted: "कटौती", next_ded: "अगली कटौती", paused: "छूट", catchup: "बकाया सहित", pending: "बाकी सहित",
    tell_closure: "दुकान बंद होने के बारे में बताएँ", ask_loan: "मेरे लोन के बारे में पूछें", talk_person: "किसी व्यक्ति से बात करें",
    msg_waiting: "संभाल से आपके लिए संदेश आया है", open: "खोलें", pause_on: "आपकी छूट चालू है",
    person_call: "लेंडर की ओर से कोई सुबह 8 से शाम 7 बजे के बीच कॉल करेगा", recovered: "बिक्री फिर से सामान्य है",
    tap_speak: "बोलने के लिए दबाएँ", stop_rec: "रोकने के लिए दबाएँ", what_happened: "बताइए क्या हुआ",
    family: "घर में समारोह", illness: "तबीयत खराब", closed: "दुकान बंद", slow: "धंधा कम", hospital: "अस्पताल",
    fine: "सब ठीक", more: "और दिन चाहिए", person: "किसी से बात करें", accept: "स्वीकार करें", accepted: "स्वीकार किया",
    outstanding: "चुकाना बाकी", paid: "चुकाया", ends: "आख़िरी किस्त, लगभग", daily: "रोज़ की किस्त",
    last7: "पिछले 7 दिन", next7: "अगले 7 दिन", no_msgs: "कोई संदेश नहीं। संभाल तभी लिखता है जब मदद कर सके।",
    type_here: "जवाब लिखें…", l_ok: "कटा", l_pz: "छूट", l_od: "बाकी", l_cu: "बकाया सहित",
    new_loan: "नया लोन चाहिए? देखें कितना सही है",
    payahead: "अग्रिम किस्त", turn_on: "चालू करें", turn_off: "बंद करें", is_on: "चालू है", paid_ahead: "पहले से जमा",
    covers: "लगभग {n} दिन की किस्त", pa_rule: "₹{t} या ज़्यादा बिक्री वाले दिन ₹{a}", pa_pitch: "धीमे दिनों के लिए तैयार रहें",
    l_cs: "अग्रिम से",
    promise: "संभाल का वादा", listen: "सुनें", consent_yes: "आपने संभाल संदेशों के लिए हाँ कहा है",
    consent_no: "संभाल संदेश बंद हैं", stop_msgs: "संभाल संदेश बंद करें", start_help: "संभाल मदद चालू करें",
    help_off_note: "ज़रूरत हो तो लेंडर की ओर से कोई कॉल करेगा।",
    pick_reason: "कारण", from_day: "किस दिन से", how_many: "कितने दिन", send_plan: "संभाल को भेजें",
  },
};
const LOCALE = { kn: "kn-IN", hi: "hi-IN", en: "en-IN" };
const ICON = { family: "🎉", illness: "🤒", closed: "🔒", slow: "📉", hospital: "🏥", fine: "👍", more: "⏳", person: "📞" };
let screen = "home";        // merchant app screen: home | chat | loan
let reasonMode = false;     // "Tell us about a closure" opens the reason picker
const seenOut = {};         // per merchant: newest outbound message seen on the Messages screen

// The phone's language for the audience: "en" (the default, so judges can read it) or "local" (the merchant's own).
// The merchant's language never changes on the server, and every message is stored in it and in English, so
// switching only changes what the phone shows and which voice note plays.
let dispLang = "en";
const LOCAL_NAME = { kn: "ಕನ್ನಡ", hi: "हिंदी" };
const ownLang = () => S.merchant._own || S.merchant.lang;
const INDIC = /[ऀ-ॿಀ-೿]/;
function localize() {
  const m = S?.merchant; if (!m) return;
  if (!m._own) m._own = m.lang;
  const en = dispLang === "en" && m._own !== "en";
  m.lang = en ? "en" : m._own;
  for (const msg of m.thread || []) {
    if (!msg._o) msg._o = { lang: msg.lang, text: msg.text, header: msg.header, labels: (msg.options || []).map(o => o.label) };
    // Outbound: the English version. Inbound: English only if the merchant didn't already write or speak English.
    const sw = en && msg._o.lang !== "en" && !!msg.text_en && (msg.dir === "out" || INDIC.test(msg._o.text));
    msg.lang = sw ? "en" : msg._o.lang;
    msg.text = sw ? msg.text_en : msg._o.text;
    msg.header = sw && msg.header_en ? msg.header_en : msg._o.header;
    msg.said = sw && msg.dir === "in" ? { lang: msg._o.lang, text: msg._o.text } : null;
    (msg.options || []).forEach((o, i) => { o.label = sw && o.label_en ? o.label_en : msg._o.labels[i]; });
  }
}
function setLang(l) {
  if (l === dispLang || !S) return;
  dispLang = l; stopVoice(); render();
  if (l === "local" && screen === "chat") {      // "this is what Ravi hears": play the latest note in his language
    const last = [...S.merchant.thread].reverse().find(x => x.dir === "out");
    if (last) playMsg(last.id);
  }
}
const ML = () => S.merchant.lang;
function t(k, lang = ML()) { return (UI[lang] || UI.en)[k] ?? UI.en[k] ?? k; }
function tf(k, vars, lang = ML()) { return t(k, lang).replace(/\{(\w+)\}/g, (_, v) => vars[v] ?? ""); }
function tt(k) {
  const lang = ML(), en = lang !== "en";
  return `<span ${langAttr(lang)}>${esc(t(k))}</span>${en ? `<small class="en-sub">${esc(t(k, "en"))}</small>` : ""}`;
}
function ldate(iso, opts = { weekday: "short", day: "numeric", month: "short" }) {
  return D(iso).toLocaleDateString(LOCALE[ML()] || "en-IN", opts);
}
const lday = iso => `${ldate(iso, { weekday: "short" })} ${D(iso).getDate()}`;

function setScreen(s) { screen = s; if (s !== "chat") reasonMode = false; renderPhone(); }

function renderPhone() {
  localize();
  const m = S.merchant, own = ownLang();
  $("#phAvatar").textContent = m.first[0];
  $("#phName").textContent = m.owner;
  $("#phShop").textContent = own === "en" ? `${m.shop} · English` : m.shop;     // the switch names his language
  $("#langSw").hidden = own === "en";
  $("#langLocal").textContent = LOCAL_NAME[own] || "";
  $$("#langSw button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.l === dispLang)));
  $$(".ph-nav button").forEach(b => {
    b.classList.toggle("on", b.dataset.scr === screen);
    b.querySelector("span").innerHTML = tt({ home: "home", chat: "messages", loan: "loan" }[b.dataset.scr]);
  });
  $("#scrHome").hidden = screen !== "home";
  $("#chat").hidden = screen !== "chat";
  $("#scrLoan").hidden = screen !== "loan";
  $("#composer").hidden = screen !== "chat";
  if (screen === "chat") seenOut[m.id] = maxOutId();
  $("#msgDot").hidden = screen === "chat" || maxOutId() <= (seenOut[m.id] ?? 0);
  $("#sizerSum").innerHTML = tt("new_loan");
  renderHome(); renderChat(); renderLoan(); renderComposer(); renderQuick();
}

function renderHome() {
  const m = S.merchant, c = m.case, last = m.recent[m.recent.length - 1], next = m.upcoming[0];
  const first = m.lang === "kn" || m.lang === "hi" ? (m.first_local || m.first) : m.first;
  let alert = "";
  if (c) {
    const sent = c.messages.some(x => x.dir === "out" && x.status === "sent");
    const paused = m.upcoming.filter(u => u.paused);
    if (c.state === "offered" || (c.state === "waiting" && sent)) {
      alert = `<button class="h-alert info" data-go="chat"><span class="ic">💬</span><span>${tt("msg_waiting")}</span></button>`;
    } else if (c.state === "accepted" && paused.length) {
      const span = paused.length > 1 ? `${lday(paused[0].date)} – ${lday(paused[paused.length - 1].date)}` : lday(paused[0].date);
      alert = `<button class="h-alert good" data-go="loan"><span class="ic">⏸</span><span><b>${tt("pause_on")}</b><span ${langAttr(m.lang)}>${esc(span)}</span></span></button>`;
    } else if (c.state === "recovered") {
      alert = `<div class="h-alert good"><span class="ic">🌱</span><span>${tt("recovered")}</span></div>`;
    } else if (c.human && ["with_person", "review", "grievance"].includes(c.state)) {
      alert = `<div class="h-alert person"><span class="ic">📞</span><span>${tt("person_call")}</span></div>`;
    }
  }
  const lastDed = last && (last.paused ? `<span ${langAttr(m.lang)}>${esc(t("paused"))}</span>` : last.from_cushion ? `<span ${langAttr(m.lang)}>${esc(t("l_cs"))}</span>` : inr(last.deducted));
  const lastCard = last ? `<div class="h-card h-last"><h4>${tt("last_day")}</h4><div class="h-date" ${langAttr(m.lang)}>${esc(ldate(last.date))}</div>
      <div class="h-row"><span class="lbl">${tt("sales")}</span><span class="h-big">${inr(last.sales)}</span></div>
      <div class="h-row"><span class="lbl">${tt("deducted")}</span><span class="h-big ${last.paused || last.from_cushion ? "zero" : ""}">${lastDed}</span></div></div>` : "";
  let nextVal = next.paused ? `<span ${langAttr(m.lang)}>${esc(t("paused"))}</span>` : inr(next.due);
  let nextNote = next.paused ? "" : next.arrears ? `${t("pending")} ${inr(next.arrears)}` : next.catchup ? `${inr(next.installment)} + ${inr(next.catchup)} ${t("catchup")}` : "";
  const nextCard = `<div class="h-card h-next"><h4>${tt("next_ded")}</h4><div class="h-date" ${langAttr(m.lang)}>${esc(ldate(next.date))}</div>
      <div class="h-row"><span class="h-big ${next.paused ? "zero" : ""}">${nextVal}</span></div>${nextNote ? `<div class="h-note" ${langAttr(m.lang)}>${esc(nextNote)}</div>` : ""}</div>`;
  const acts = [["closure", "tell_closure", "🗓️"], ["ask", "ask_loan", "❓"], ["person", "talk_person", "📞"]]
    .map(([k, label, ic]) => `<button class="h-act ${k}" data-act="${k}"><span class="ic">${ic}</span><span>${tt(label)}</span></button>`).join("");
  const cu = m.cushion;
  let cush = "";
  if (cu.on) {
    cush = `<div class="h-card h-cush"><h4>${tt("payahead")} · ${tt("is_on")}</h4>
      <div class="h-row"><span class="lbl">${tt("paid_ahead")}</span><span class="h-big">${inr(cu.balance)}</span></div>
      <div class="h-note" ${langAttr(m.lang)}>${cu.covers_days ? esc(tf("covers", { n: cu.covers_days })) + " · " : ""}${esc(tf("pa_rule", { a: inr(cu.amount).slice(1), t: inr(cu.threshold).slice(1) }))}</div>
      <button class="linkish" data-cush="off" ${langAttr(m.lang)}>${esc(t("turn_off"))}</button></div>`;
  } else if (cu.suggest && m.thread.some(x => (x.options || []).some(o => o.kind === "payahead"))) {   // after Sambhal offered it
    cush = `<div class="h-card h-cush off"><h4>${tt("pa_pitch")}</h4>
      <div class="h-note" ${langAttr(m.lang)}>${esc(t("payahead"))}: ${esc(tf("pa_rule", { a: inr(cu.suggest.amount).slice(1), t: inr(cu.suggest.threshold).slice(1) }))}</div>
      <button class="cush-on" data-cush="on" ${langAttr(m.lang)}>${esc(t("turn_on"))}</button></div>`;
  }
  const consent = m.consent ? "" : `<div class="h-card h-consent"><h4>${tt("consent_no")}</h4><div class="h-note" ${langAttr(m.lang)}>${esc(t("help_off_note"))}</div>
      <button class="cush-on" data-consent="on" ${langAttr(m.lang)}>${esc(t("start_help"))}</button></div>`;
  const promise = `<button class="h-promise" data-sheet="promise"><span class="ic">🤝</span><span>${tt("promise")}</span><span class="chev">›</span></button>`;
  $("#scrHome").innerHTML = `<div class="h-greet" ${langAttr(m.lang)}>${esc(t("hello"))}, ${esc(first)}</div>${consent}${alert}<div class="h-pair">${lastCard}${nextCard}</div>${cush}<div class="h-acts">${acts}</div>${promise}`;
  $$("[data-consent]", $("#scrHome")).forEach(b => (b.onclick = () => setConsent(b.dataset.consent === "on")));
  $$("[data-sheet]", $("#scrHome")).forEach(b => (b.onclick = () => openPromise()));
  $$("[data-cush]", $("#scrHome")).forEach(b => (b.onclick = () => setCushion(b.dataset.cush === "on")));
  $$("[data-go]", $("#scrHome")).forEach(b => (b.onclick = () => setScreen(b.dataset.go)));
  $$("[data-act]", $("#scrHome")).forEach(b => (b.onclick = () => homeAction(b.dataset.act)));
}

function openPromise() {
  const m = S.merchant, lang = m.lang, showEn = lang !== "en";
  const items = S.promises.map(p => `<li><span class="ic">${p.icon}</span><span><span ${langAttr(lang)}>${esc(p.text[lang])}</span>${showEn ? `<small class="en-sub">${esc(p.text.en)}</small>` : ""}</span></li>`).join("");
  const sheet = $("#sheet");
  sheet.innerHTML = `<div class="sh-head"><b>${tt("promise")}</b><button class="sh-x" aria-label="Close">✕</button></div>
    <button class="vn" id="promiseListen"><span class="pl"></span><span class="wave">${wave(7)}</span><span class="dur" ${langAttr(lang)}>${esc(t("listen"))}</span></button>
    <ul class="promises">${items}</ul>
    <div class="sh-consent"><span>${tt(m.consent ? "consent_yes" : "consent_no")}</span>
      <button data-consent="${m.consent ? "off" : "on"}" ${langAttr(lang)}>${esc(t(m.consent ? "stop_msgs" : "start_help"))}</button></div>`;
  sheet.hidden = false;
  $(".sh-x", sheet).onclick = () => (sheet.hidden = true);
  $("#promiseListen").onclick = () => playText(S.promises.map(p => p.text[lang]).join(" "), lang, $("#promiseListen"));
  $$("[data-consent]", sheet).forEach(b => (b.onclick = () => { sheet.hidden = true; setConsent(b.dataset.consent === "on"); }));
}

const PLAN_ICON = { family_event: "🎉", illness: "🤒", temporary_closure: "🧳", medical_emergency: "🏥" };
const plan = { reason: "family_event", start: null, days: 3 };
function openPlanner() {
  const m = S.merchant, lang = m.lang, sheet = $("#sheet");
  const first = m.upcoming[0].date;
  if (!plan.start || plan.start < first) plan.start = first;
  const dates = Array.from({ length: 10 }, (_, k) => { const d = D(first); d.setDate(d.getDate() + k); return d.toISOString().slice(0, 10); });
  const end = (() => { const d = D(plan.start); d.setDate(d.getDate() + plan.days - 1); return d.toISOString().slice(0, 10); })();
  const chip = (attr, val, on, label) => `<button class="pchip ${on ? "on" : ""}" data-${attr}="${val}" ${langAttr(lang)}>${label}</button>`;
  sheet.innerHTML = `<div class="sh-head"><b>${tt("tell_closure")}</b><button class="sh-x" aria-label="Close">✕</button></div>
    <p class="r-title">${tt("pick_reason")}</p>
    <div class="r-row r-2">${Object.entries(S.plan_reasons).map(([k, v]) => `<button type="button" class="r-btn ${plan.reason === k ? "on" : ""}" data-reason="${k}"><span class="ic">${PLAN_ICON[k]}</span><span><span ${langAttr(lang)}>${esc(v[lang])}</span>${lang !== "en" ? `<small class="en-sub">${esc(v.en)}</small>` : ""}</span></button>`).join("")}</div>
    <p class="r-title">${tt("from_day")}</p>
    <div class="pchips">${dates.map(d => chip("start", d, d === plan.start, esc(lday(d)))).join("")}</div>
    <p class="r-title">${tt("how_many")}</p>
    <div class="pchips">${[1, 2, 3, 4, 5, 7].map(n => chip("days", n, n === plan.days, n)).join("")}</div>
    <div class="plan-sum" ${langAttr(lang)}>${esc(S.plan_reasons[plan.reason][lang])}: ${esc(lday(plan.start))}${plan.days > 1 ? ` – ${esc(lday(end))}` : ""}</div>
    <button class="primary plan-send" ${langAttr(lang)}>${esc(t("send_plan"))}</button>`;
  sheet.hidden = false;
  $(".sh-x", sheet).onclick = () => (sheet.hidden = true);
  $$("[data-reason]", sheet).forEach(b => (b.onclick = () => { plan.reason = b.dataset.reason; openPlanner(); }));
  $$("[data-start]", sheet).forEach(b => (b.onclick = () => { plan.start = b.dataset.start; openPlanner(); }));
  $$("[data-days]", sheet).forEach(b => (b.onclick = () => { plan.days = +b.dataset.days; openPlanner(); }));
  $(".plan-send", sheet).onclick = () => act(async () => {
    sheet.hidden = true;
    S = await post("/api/plan", { merchant_id: focus, ...plan });
    if (!S.result.ok) toast(S.result.why);
    screen = "chat"; render(); autoSpeak();
  });
}

function homeAction(k) {
  if (k === "closure") { openPlanner(); return; }
  sendInbound(S.quick[k === "ask" ? "ask" : "person"][ML()], "tap");
}

function renderChat() {
  const m = S.merchant, c = m.case, showEn = true;
  const chat = $("#chat");
  const atBottom = chat.scrollHeight - chat.scrollTop - chat.clientHeight < 60;
  let html = "";
  if (!m.thread.length) {
    html = `<p class="empty">${!m.consent ? "No messages: this merchant didn't opt in, so a person at the lender will call instead." : tt("no_msgs")}</p>`;
  } else {
    let day = null;
    for (const msg of m.thread) {
      const at = msg.sent_at || msg.at;
      if (msg.dir === "out" && msg.status === "held") {
        html += `<div class="sysline hold">⏸ Sambhal has a message ready. Held until ${fmtDayTime(msg.held_until)}: ${esc(HOLD_WHY[msg.held_reason] || msg.held_reason || "contact rules")}.</div>`;
        continue;
      }
      if (msg.dir === "out" && msg.status === "blocked") {
        const why = (msg.checks || []).filter(x => !x.ok).map(x => x.why).join("; ");
        html += `<div class="sysline block">✕ Not sent: ${esc(why || "blocked by a guardrail")}</div>`;
        continue;
      }
      const dk = fmtDay(at);
      if (dk !== day) { html += `<div class="daysep">${dk}</div>`; day = dk; }
      if (msg.dir === "out" && msg.held_once) {
        html += `<div class="sysline info">Waited for ${esc(HOLD_WHY[msg.held_reason] || msg.held_reason)}; delivered ${fmtTime(msg.sent_at)}.</div>`;
      }
      html += msg.dir === "out" ? outBubble(msg, showEn) : inBubble(msg, showEn);
    }
  }
  chat.innerHTML = html;
  if (atBottom || busy) chat.scrollTop = chat.scrollHeight;
  $$(".vn", chat).forEach(b => (b.onclick = () => playMsg(+b.dataset.id)));
  $$(".opt button.accept[data-opt]", chat).forEach(b => (b.onclick = () => acceptOpt(b.dataset.opt)));
  $$(".opt button.accept[data-cush]", chat).forEach(b => (b.onclick = () => setCushion(true)));
}

function wave(id) {
  let x = id * 9301 + 49297, out = "";
  for (let i = 0; i < 26; i++) { x = (x * 9301 + 49297) % 233280; out += `<i style="height:${30 + Math.round((x / 233280) * 70)}%"></i>`; }
  return out;
}
function fmtDur(s) { return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; }

function outBubble(msg, showEn) {
  const tag = msg.author === "llm" ? `<span class="tag ai">AI-phrased · checked</span>` : `<span class="tag tpl">Approved template</span>`;
  const secs = Math.max(4, Math.round(((msg.header || "").length + msg.text.length) / 14));
  let opts = "";
  for (const o of msg.options || []) {
    if (o.kind === "payahead") {
      const on = S.merchant.cushion.on;
      opts += `<div class="opt ${on ? "taken" : ""}"><b ${langAttr(msg.lang)}>${esc(o.label)}</b>${showEn && msg.lang !== "en" ? `<p>${esc(o.label_en)}</p>` : ""}
        ${on ? `<span class="ok">✓ ${tt("is_on")}</span>` : `<button class="accept" data-cush="on" ${langAttr(msg.lang)}>${esc(t("turn_on", msg.lang))}</button>`}</div>`;
      continue;
    }
    const taken = msg.case_accepted === o.id, can = msg.case_state === "offered" && !msg.case_accepted;
    const pv = (o.preview || []).slice(0, 5).map(p => `<span class="pv-c ${p.kind}"><i ${langAttr(msg.lang)}>${esc(lday(p.date))}</i><b>${p.amount ? inr(p.amount) : "₹0"}</b></span>`).join("");
    opts += `<div class="opt ${taken ? "taken" : ""}"><b ${langAttr(msg.lang)}>${esc(o.label)}</b>${showEn && msg.lang !== "en" ? `<p>${esc(o.label_en)}</p>` : ""}
      ${pv ? `<div class="pv">${pv}</div>` : ""}
      ${taken ? `<span class="ok">✓ ${tt("accepted")}</span>` : can ? `<button class="accept" data-opt="${o.id}" ${langAttr(msg.lang)}>${esc(t("accept", msg.lang))}</button>` : ""}</div>`;
  }
  return `<div class="bubble out">
    <button class="vn" data-id="${msg.id}" aria-label="Play voice message"><span class="pl"></span><span class="wave">${wave(msg.id)}</span><span class="dur">${fmtDur(secs)}</span></button>
    <div class="hdr" ${langAttr(msg.lang)}>${esc(msg.header)}</div>
    <div class="body" ${langAttr(msg.lang)}>${esc(msg.text)}</div>
    ${showEn && msg.lang !== "en" ? `<div class="en">${esc(msg.text_en)}</div>` : ""}
    ${opts}
    <div class="ftr">${esc(msg.footer)}</div>
    <div class="meta"><span>${fmtTime(msg.sent_at)} · ${tag}</span></div>
  </div>`;
}

function inBubble(msg, showEn) {
  const via = msg.via === "voice" ? `<span class="tag voice">voice</span>` : msg.via === "tap" ? `<span class="tag voice">tap</span>` : "";
  const sim = msg.simulated ? ` <span class="tag sim">simulated</span>` : "";
  return `<div class="bubble in">
    <div class="body" ${langAttr(msg.lang)}>${esc(msg.text)}</div>
    ${showEn && (msg.lang !== "en" || msg.kind === "accept") && msg.text_en && msg.text_en !== msg.text ? `<div class="en">${esc(msg.text_en)}</div>` : ""}
    ${msg.said ? `<div class="en" ${langAttr(msg.said.lang)}>${esc(msg.said.text)}</div>` : ""}
    <div class="meta"><span>${via}${sim}</span><span>${fmtTime(msg.at)}</span></div>
  </div>`;
}

function renderComposer() {
  const c = S.merchant.case, lang = ML();
  const sent = c && c.messages.some(x => x.dir === "out" && x.status === "sent");
  const btn = (k, cls = "r-btn") => `<button type="button" class="${cls}" data-q="${k}"><span class="ic">${ICON[k]}</span><span>${tt(k)}</span></button>`;
  let html = "";
  if (c && c.state === "offered") html = `<div class="r-row">${btn("more")}${btn("person")}</div>`;
  else if (reasonMode || (c && c.state === "waiting" && sent)) {
    html = `<p class="r-title">${tt("what_happened")}</p><div class="r-grid">${["family", "illness", "closed", "slow", "hospital", "fine"].map(k => btn(k)).join("")}</div>`;
  }
  $("#reasons").innerHTML = html;
  $$("[data-q]", $("#reasons")).forEach(b => (b.onclick = () => { reasonMode = false; sendInbound(S.quick[b.dataset.q][lang], "tap"); }));
  $("#micLabel").innerHTML = `<span ${langAttr(lang)}>${esc(t((rec && rec.state === "recording") || recog ? "stop_rec" : "tap_speak"))}</span>`;
  $("#msgInput").placeholder = t("type_here");
}

function renderLoan() {
  const m = S.merchant, Lo = m.loan;
  const paid = Lo.total ? Lo.collected / Lo.total : 0;
  const past = m.recent.slice(-7).map(r => {
    const cls = r.paused ? "pz" : r.arrears > 0 ? "od" : r.from_cushion ? "cs" : "ok";
    const val = r.paused ? t("paused") : r.arrears > 0 ? inr(r.arrears) : r.from_cushion ? inr(r.from_cushion + r.deducted) : inr(r.deducted);
    return `<div class="cal-c ${cls}"><i ${langAttr(m.lang)}>${esc(ldate(r.date, { weekday: "short" }))}</i><b>${D(r.date).getDate()}</b><em ${langAttr(m.lang)}>${esc(val)}</em></div>`;
  }).join("");
  const fut = m.upcoming.slice(0, 7).map((u, i) => {
    const cls = (u.paused ? "pz" : u.catchup ? "cu" : "up") + (i === 0 ? " today" : "");
    const val = u.paused ? t("paused") : inr(u.due);
    return `<div class="cal-c ${cls}"><i ${langAttr(m.lang)}>${esc(ldate(u.date, { weekday: "short" }))}</i><b>${D(u.date).getDate()}</b><em ${langAttr(m.lang)}>${esc(val)}</em></div>`;
  }).join("");
  const lg = ["ok", "pz", "od", "cu", "cs"].map(k => `<span class="l-${k}" ${langAttr(m.lang)}>${esc(t("l_" + k))}</span>`).join("");
  $("#loanOut").innerHTML = `
    <div class="h-card ln-sum"><h4>${tt("outstanding")}</h4><div class="h-big">${inr(Lo.outstanding)}</div>
      <div class="ln-bar"><i style="width:${(paid * 100).toFixed(1)}%"></i></div>
      <div class="ln-kv"><span>${tt("daily")}</span><b>${inr(Lo.installment)}</b><span>${tt("paid")}</span><b>${inr(Lo.collected)} · ${pct(paid)}</b><span>${tt("ends")}</span><b ${langAttr(m.lang)}>${esc(ldate(m.ends_on, { day: "numeric", month: "short", year: "numeric" }))}</b></div></div>
    <div class="h-card"><h4>${tt("last7")}</h4><div class="cal">${past}</div></div>
    <div class="h-card"><h4>${tt("next7")}</h4><div class="cal">${fut}</div><div class="cal-lg">${lg}</div></div>`;
}

function renderQuick() {
  const q = $("#quick"); q.innerHTML = "";
  const c = S.merchant.case;
  const canReply = c && ["waiting", "offered", "declined"].includes(c.state);
  if (!canReply) return;
  const lines = [];
  if (focus === "M01" && !c.messages.some(m => m.dir === "in")) lines.push({ text: RAVI_LINE, label: `🎙 Ravi: ${RAVI_LINE}`, main: true });
  if (c.state === "offered") lines.push({ text: ML() === "kn" ? "ಸರಿ, ಒಪ್ಪುತ್ತೇನೆ" : ML() === "hi" ? "हाँ, ठीक है" : "Yes, okay", label: "Says yes" });
  if (c.state === "offered") lines.push({ text: "ok but why only 3 days?", label: "“Why only 3 days?”" });
  TRY_LINES.forEach(l => lines.push(l));
  for (const l of lines.slice(0, 5)) {
    const b = document.createElement("button");
    b.type = "button"; b.textContent = l.label; b.title = l.text;
    if (/[ಀ-೿]/.test(l.label)) b.lang = "kn";
    b.onclick = () => sendInbound(l.text, l.main ? "voice" : "text");
    q.appendChild(b);
  }
}

// ---------------------------------------------------------------- console: merchant card
function renderMCard() {
  const m = S.merchant, L = m.loan, c = m.case;
  const status = c ? pill(c.state) : `<span class="pill st-ok">No open case</span>`;
  $("#mCard").innerHTML = `
    <div><h2>${esc(m.owner)}</h2><div class="sub">${esc(m.shop)} · ${esc(m.area)} · ${LANG_LABEL[ownLang()]}${m.consent ? "" : " · <b>no messaging consent</b>"}</div><div style="margin-top:6px">${status}</div></div>
    <div class="facts">
      <div class="fact"><span>Daily installment</span><b>${inr(L.installment)}</b></div>
      <div class="fact"><span>Outstanding</span><b>${inr(L.outstanding)}</b></div>
      <div class="fact"><span>Overdue now</span><b class="${L.arrears ? "bad" : "good"}">${L.arrears ? `${inr(L.arrears)} · ${L.dpd}d` : "Nothing"}</b></div>
      <div class="fact"><span>On-time days</span><b>${pct(L.paid_ratio)}</b></div>
      <div class="fact"><span>Loan age</span><b>${L.age_days} days</b></div>
      <div class="fact"><span>Days ever overdue</span><b class="${L.missed_days ? "bad" : ""}">${L.missed_days}</b></div>
    </div>
    <div class="spark-box">${spark(m.recent)}<div class="spark-cap"><span>Last 14 days: sales vs this shop's normal</span><span>${m.recent.length ? fmtDay(m.recent[m.recent.length - 1].date) : ""}</span></div></div>`;
}

function spark(rows) {
  if (!rows.length) return "";
  const W = 420, H = 76, pad = 4, n = rows.length, bw = (W - pad * 2) / n;
  const max = Math.max(...rows.map(r => Math.max(r.sales, r.baseline)), 1);
  const y = v => H - 14 - (v / max) * (H - 20);
  let bars = "", line = "";
  rows.forEach((r, i) => {
    const x = pad + i * bw;
    const ratio = r.baseline ? r.sales / r.baseline : 1;
    const col = r.paused ? "var(--teal)" : r.sales === 0 ? "var(--red)" : ratio < 0.5 ? "#d9a43a" : "#9fb3c8";
    const h = Math.max(H - 14 - y(r.sales), r.sales ? 1 : 0);
    bars += `<rect x="${(x + 2).toFixed(1)}" y="${(H - 14 - h).toFixed(1)}" width="${(bw - 4).toFixed(1)}" height="${h.toFixed(1)}" rx="2" fill="${col}"><title>${r.dow} ${r.date.slice(5)}: ${inr(r.sales)} (${pct(ratio)} of normal)${r.paused ? ", paused" : ""}</title></rect>`;
    if (r.sales === 0) bars += `<rect x="${(x + 2).toFixed(1)}" y="${H - 16}" width="${(bw - 4).toFixed(1)}" height="2" fill="var(--red)"/>`;
    line += `${i ? "L" : "M"}${(x + bw / 2).toFixed(1)},${y(r.baseline).toFixed(1)}`;
    bars += `<text x="${(x + bw / 2).toFixed(1)}" y="${H - 2}" font-size="9" text-anchor="middle" fill="var(--ink-3)">${r.dow[0]}</text>`;
  });
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" role="img" aria-label="Daily sales for the last 14 days">${bars}<path d="${line}" fill="none" stroke="var(--ink-2)" stroke-width="1.2" stroke-dasharray="3 3"/></svg>`;
}

// ---------------------------------------------------------------- console: cases
function renderAlerts() {
  const el = $("#alerts");
  el.innerHTML = (S.alerts || []).map(a => {
    const down = a.shops.length, when = fmtDay(a.date);
    const status = a.approved
      ? `<span class="pill st-accepted">Area pause approved · ${a.approved.count} shops</span>`
      : a.quiet ? `<button class="primary" data-area="${a.id}">Approve a 3-day pause for ${down} shops</button>`
        : `<span class="pill st-ok">Sales recovered</span>`;
    return `<div class="alert-card ${a.quiet ? "live" : ""}">
      <div class="ac-head"><div><b>⚠ Neighbourhood alert · ${esc(a.area)}</b>
        <span>${down} of ${a.of} shops at ${pct(a.avg)} of normal on ${when}, while ${pct(a.rest)} of shops elsewhere were down. Likely a local event (rain, road closure, power cut).</span>
        <span class="muted">${a.quiet ? "Sambhal has paused reminders there (RBI: no recovery contact during calamities) and asks the lender for one decision instead of separate check-ins." : `Reminders resumed after sales recovered${a.recovered_on ? ` on ${fmtDay(a.recovered_on)}` : ""}.`}</span></div>${status}</div>
      <div class="ac-shops">${a.shops.map(s => `<button class="ac-shop" data-mid="${s.id}" title="${esc(s.shop)}">${esc(s.name)} <i>${pct(s.ratio)}</i>${s.overdue ? ' <em>overdue</em>' : ""}</button>`).join("")}</div>
    </div>`;
  }).join("");
  $$("[data-area]", el).forEach(b => (b.onclick = () => act(async () => { S = await post("/api/area", { alert_id: b.dataset.area, days: 3 }); render(); })));
  $$(".ac-shop", el).forEach(b => (b.onclick = () => { lastSpoken = Infinity; load(b.dataset.mid).then(() => { lastSpoken = sentOutId(); }); }));
}

function renderCases() {
  renderAlerts();
  const list = $("#caseList");
  if (!S.cases.length) {
    list.innerHTML = `<p class="muted" style="padding:10px">No cases yet. The early-warning rule runs after every evening settlement across all ${S.counts.merchants} merchants.</p>`;
  } else {
    list.innerHTML = S.cases.map(c => `
      <button class="crow ${c.merchant_id === focus ? "sel" : ""}" data-mid="${c.merchant_id}">
        <span class="nm">${esc(c.merchant)}${c.demo ? '<span class="demo">DEMO</span>' : ""}</span>${pill(c.state)}
        <span class="rs">${esc(c.human_reason || (c.held_until ? `Held until ${fmtDayTime(c.held_until)}` : c.trigger || ""))}</span>
      </button>`).join("");
    $$(".crow", list).forEach(b => (b.onclick = () => { lastSpoken = Infinity; load(b.dataset.mid).then(() => { lastSpoken = sentOutId(); }); }));
  }
  renderCaseDetail();
}

function renderCaseDetail() {
  const el = $("#caseDetail"), m = S.merchant, c = m.case;
  if (!c) {
    el.innerHTML = `<div><h3>${esc(m.owner)}</h3><p class="muted">No open case. Sambhal is watching the daily settlements.</p></div>${m.note && m.id !== "M01" ? `<p class="note">${esc(m.note)}</p>` : ""}`;
    return;
  }
  const lastOut = [...c.messages].reverse().find(x => x.dir === "out" && x.checks && x.checks.length);
  const lastIn = [...c.messages].reverse().find(x => x.dir === "in" && x.nlu);
  const checks = lastOut ? lastOut.checks.map(k => {
    const cls = k.ok ? "ok" : k.hold_until ? "hold" : "no";
    return `<div class="check ${cls}"><span class="ic">${k.ok ? "✓" : k.hold_until ? "⏸" : "✕"}</span><div><b>${esc(k.rule)}</b><span>${esc(k.why)}</span></div></div>`;
  }).join("") : "";
  const acts = (c.staff_actions || []).map(a => `<button class="${a.action === "approve" ? "primary" : "ghost"}" data-staff="${a.action}" data-opt="${a.option || ""}" data-days="${a.days || ""}" ${a.disabled ? `disabled title="${esc(a.why)}"` : ""}>${esc(a.label)}${a.disabled ? ` <small>(${esc(a.why)})</small>` : ""}</button>`).join("");
  const handoff = c.human || c.review || c.grievance ? `<div class="handoff"><b>With a person at the lender</b>${esc(c.human_reason || "")}${c.human_options && c.human_options.length ? `<br>Staff may offer: ${c.human_options.map(o => esc(o.id)).join(", ")}` : ""}${acts ? `<div class="staff-acts">${acts}</div>` : ""}</div>`
    : c.accepted_by === "lender staff" ? `<div class="handoff done"><b>Approved by lender staff</b>${esc(c.accepted || "")}</div>` : "";
  const reading = lastIn ? `<div><p class="sec-t">How Sambhal read the last reply</p><div class="reading">
      <span>Intent: <b>${esc(lastIn.nlu.intent.replace(/_/g, " "))}</b></span>
      ${lastIn.nlu.secondary ? `<span>Also: <b>${esc(lastIn.nlu.secondary.replace(/_/g, " "))}</b></span>` : ""}
      ${lastIn.nlu.event_days ? `<span>Days: <b>${lastIn.nlu.event_days}</b></span>` : ""}
      <span>Language: <b>${LANG_LABEL[lastIn.nlu.language] || lastIn.nlu.language}</b></span>
      <span>Read by: <b>${esc(lastIn.nlu.source)}</b></span>
      ${Object.keys(lastIn.nlu.matched || {}).length ? `<span>Keywords: <code ${langAttr(lastIn.lang)}>${esc(Object.values(lastIn.nlu.matched).flat().slice(0, 4).join(", "))}</code></span>` : ""}
    </div></div>` : "";
  el.innerHTML = `
    <div class="cd-head"><div><h3>${esc(c.merchant)} · case ${esc(c.id)}</h3><span class="muted" style="font-size:13px">Opened ${fmtDayTime(c.opened_at)}${c.trigger ? ` · ${esc(c.trigger.reason)}` : ""}</span></div>${pill(c.state)}</div>
    ${handoff}
    ${m.note && m.id !== "M01" ? `<p class="note">Demo note: ${esc(m.note)}</p>` : ""}
    <div><p class="sec-t">Timeline</p><ol class="timeline">${c.timeline.map(t => `<li class="k-${t.kind}"><time>${fmtTime(t.at)}<br>${fmtDay(t.at).split(" ").slice(0, 1)}</time><i></i><span>${esc(t.text)}</span></li>`).join("")}</ol></div>
    ${checks ? `<div><p class="sec-t">Guardrails on the last outbound message</p><div class="checks">${checks}</div></div>` : ""}
    ${reading}`;
  $$("[data-staff]", el).forEach(b => (b.onclick = () => act(async () => {
    const r = await post("/api/staff", { merchant_id: m.id, action: b.dataset.staff, option: b.dataset.opt || null, days: +b.dataset.days || null });
    S = r; if (!r.result.ok) toast(r.result.why); render(); autoSpeak();
  })));
}

// ---------------------------------------------------------------- week
async function renderWeek() {
  const el = $("#tab-week");
  const wk = await api(`/api/week/${focus}`);
  const rows = wk.rows, inst = wk.installment;
  const settled = rows.filter(r => r.settled);
  if (!settled.length) { el.innerHTML = `<div class="week"><p class="muted">No days settled yet in this window. Step forward to see the week build up.</p></div>`; return; }
  const withMax = settled.reduce((a, r) => (r.with.deducted > a.with.deducted ? r : a));
  const woMax = settled.reduce((a, r) => (r.without.deducted > a.without.deducted ? r : a));
  const odW = settled.filter(r => r.with.arrears > 0).length, odWo = settled.filter(r => r.without.arrears > 0).length;
  const shareW = woMax.sales ? woMax.with.deducted / woMax.sales : 0, shareWo = woMax.sales ? woMax.without.deducted / woMax.sales : 0;
  const maxV = Math.max(...settled.map(r => Math.max(r.with.deducted, r.without.deducted)), inst * 2);
  const Wd = 760, H = 260, L = 56, R = 12, T = 22, B = 46, n = rows.length, gw = (Wd - L - R) / n, bw = Math.min(26, gw / 3);
  const y = v => T + (H - T - B) * (1 - v / maxV);
  let g = "";
  const ticks = [0, maxV / 2, maxV].map(v => Math.round(v / 100) * 100);
  ticks.forEach(t => { g += `<line x1="${L}" x2="${Wd - R}" y1="${y(t)}" y2="${y(t)}" stroke="var(--rule)"/><text x="${L - 6}" y="${y(t) + 4}" text-anchor="end" font-size="11" fill="var(--ink-3)" font-family="var(--f-num)">${inr(t)}</text>`; });
  g += `<line x1="${L}" x2="${Wd - R}" y1="${y(inst)}" y2="${y(inst)}" stroke="var(--teal)" stroke-dasharray="4 4"/><text x="${Wd - R}" y="${y(inst) - 5}" text-anchor="end" font-size="11" fill="var(--teal-2)">normal installment ${inr(inst)}</text>`;
  rows.forEach((r, i) => {
    const cx = L + gw * i + gw / 2;
    if (r.settled) {
      const a = r.with.deducted, b = r.without.deducted;
      g += `<rect x="${cx - bw - 2}" y="${y(b)}" width="${bw}" height="${y(0) - y(b)}" fill="var(--red)" opacity=".85" rx="2"><title>Without: ${inr(b)}</title></rect>`;
      g += `<rect x="${cx + 2}" y="${y(a)}" width="${bw}" height="${y(0) - y(a)}" fill="var(--teal)" rx="2"><title>With Sambhal: ${inr(a)}</title></rect>`;
      if (b !== a || b > inst) g += `<text x="${cx - bw / 2 - 2}" y="${y(b) - 5}" text-anchor="middle" font-size="11" fill="var(--red)" font-family="var(--f-num)">${b ? inr(b) : "₹0"}</text>`;
      g += `<text x="${cx + bw / 2 + 2}" y="${y(a) - 5}" text-anchor="middle" font-size="11" fill="var(--teal-2)" font-family="var(--f-num)">${a ? inr(a) : "₹0"}</text>`;
      if (r.without.arrears > 0) g += `<text x="${cx}" y="${H - B + 30}" text-anchor="middle" font-size="10" fill="var(--red)">${r.without.dpd}d overdue</text>`;
      if (r.with.paused) g += `<text x="${cx}" y="${H - B + 42}" text-anchor="middle" font-size="10" fill="var(--teal-2)">paused</text>`;
    } else {
      g += `<rect x="${cx - bw - 2}" y="${T + 20}" width="${bw * 2 + 4}" height="${y(0) - T - 20}" fill="none" stroke="var(--rule)" stroke-dasharray="3 3" rx="3"/><text x="${cx}" y="${y(0) - 8}" text-anchor="middle" font-size="10" fill="var(--ink-3)">not yet</text>`;
    }
    g += `<text x="${cx}" y="${H - B + 16}" text-anchor="middle" font-size="12" fill="var(--ink)">${r.dow} ${D(r.date).getDate()}</text>`;
  });
  const table = rows.map(r => `<tr><td>${r.dow} ${D(r.date).getDate()}</td>
      <td class="n">${r.settled ? inr(r.sales) : "—"}</td><td class="n">${r.settled && r.baseline ? pct(r.sales / r.baseline) : "—"}</td>
      <td class="n">${r.settled ? inr(r.with.deducted) : "—"}</td><td>${r.settled ? (r.with.paused ? "paused" : r.with.arrears ? `${inr(r.with.arrears)} overdue` : r.with.catchup ? `incl. ${inr(r.with.catchup)} catch-up` : "") : ""}</td>
      <td class="n">${r.settled ? inr(r.without.deducted) : "—"}</td><td>${r.settled && r.without.arrears ? `${inr(r.without.arrears)} overdue · ${r.without.dpd}d` : ""}</td></tr>`).join("");
  const plural = n => `${n} day${n === 1 ? "" : "s"}`;
  const payoff = woMax.without.deducted > woMax.with.deducted ? `<div>
      <p class="po-head">${fmtDay(woMax.date)}: the day the backlog lands <span>· same sales, same day · the sweep is our model, as PhonePe documents</span></p>
      <div class="payoff">
        <div class="po wo"><span class="k">Without Sambhal</span><span class="v">${inr(woMax.without.deducted)}</span>
          <span class="s">${pct(shareWo)} of the day's sales, taken in one go</span><span class="s">${plural(odWo)} overdue on the record</span></div>
        <div class="po-arrow">→</div>
        <div class="po w"><span class="k">With Sambhal</span><span class="v">${inr(woMax.with.deducted)}</span>
          <span class="s">${pct(shareW)} of the day's sales</span><span class="s">${odW ? `${plural(odW)} overdue` : "Never overdue"}</span></div>
        ${cushionBox(wk, woMax)}
      </div></div>` : "";
  el.innerHTML = `<div class="week">${payoff}
    <div class="week-kpis">
      <div class="wk"><span>Biggest single deduction</span><div class="pair"><b class="a">${inr(withMax.with.deducted)}</b><b class="b">${inr(woMax.without.deducted)}</b></div></div>
      <div class="wk"><span>Share of that day's sales (${woMax.dow})</span><div class="pair"><b class="a">${pct(shareW)}</b><b class="b">${pct(shareWo)}</b></div></div>
      <div class="wk"><span>Days overdue on record</span><div class="pair"><b class="a">${odW}</b><b class="b">${odWo}</b></div></div>
    </div>
    <div class="legend"><span><i style="background:var(--teal)"></i>With Sambhal</span><span><i style="background:var(--red)"></i>Without: same sales, plain daily deduction</span></div>
    <div class="chartwrap"><svg viewBox="0 0 ${Wd} ${H}" role="img" aria-label="Daily deduction with and without Sambhal">${g}</svg></div>
    <div class="tablewrap"><table class="grid"><thead><tr><th>Day</th><th>Sales</th><th>vs normal</th><th>With: deducted</th><th></th><th>Without: deducted</th><th></th></tr></thead><tbody>${table}</tbody></table></div>
  </div>`;
}

function cushionBox(wk, day) {
  if (!wk.cushion || !day.cushion) return "";
  const rows = wk.rows.filter(r => r.cushion), used = rows.filter(r => r.cushion.from_cushion > 0);
  if (!used.length) return "";
  const before = rows[rows.indexOf(used[0]) - 1];
  const ahead = before ? before.cushion.cushion : used[0].cushion.cushion + used[0].cushion.from_cushion;
  const span = used.length > 1 ? `${used[0].dow}–${used[used.length - 1].dow}` : used[0].dow;
  const share = day.sales ? day.cushion.deducted / day.sales : 0;
  return `<div class="po-arrow">→</div>
    <div class="po cu"><span class="k">With pay-ahead, on from the start</span><span class="v">${inr(day.cushion.deducted)}</span>
      <span class="s">${pct(share)} of the day's sales${day.cushion.to_cushion ? ` (+ ${inr(day.cushion.to_cushion)} paid ahead)` : ""}</span>
      <span class="s">${inr(ahead)} paid ahead covered ${span}. No pause, nothing overdue.</span></div>`;
}

// ---------------------------------------------------------------- proof
function renderPromiseProof(results) {
  const ok = Object.fromEntries((results || []).map(r => [r.id, r.ok]));
  $("#promiseProof").innerHTML = `<p class="sec-t">Sambhal's promise to merchants, and what proves each one</p>` + S.promises.map(p => `
    <div class="pp"><span class="ic">${p.icon}</span><div><b>${esc(p.text.en)}</b><span class="muted">Rule: ${esc(p.rule)}</span></div>
      <div class="pp-ids">${p.checks.map(id => `<code class="${id in ok ? (ok[id] ? "ok" : "no") : ""}">${id}</code>`).join("")}${p.tests.length ? `<code title="${esc(p.tests.join(", "))}">+${p.tests.length} test${p.tests.length > 1 ? "s" : ""}</code>` : ""}</div></div>`).join("");
}

async function runEvals() {
  renderPromiseProof();
  const btn = $("#btnEvals"); btn.disabled = true; btn.textContent = "Running…";
  $("#evalSummary").innerHTML = ""; $("#evalList").innerHTML = `<p class="muted">Building a fresh world for each scenario…</p>`;
  try {
    const r = await api("/api/evals");
    const groups = {};
    r.results.forEach(x => (groups[x.group] = groups[x.group] || []).push(x));
    $("#evalList").innerHTML = Object.entries(groups).map(([g, xs]) => `<div class="eg"><h4>${esc(g)}</h4>${xs.map(x => `
      <div class="ev wait" data-id="${x.id}"><code>${x.id}</code><span class="r">·</span><span>${esc(x.title)}</span>
      ${x.ok ? "" : `<span class="why">${esc(x.error || x.checks.filter(c => !c.ok).map(c => `${c.key}: wanted ${JSON.stringify(c.want)}, got ${JSON.stringify(c.got)}`).join("; "))}</span>`}</div>`).join("")}</div>`).join("");
    const rows = $$(".ev", $("#evalList"));
    for (let i = 0; i < rows.length; i++) {
      const x = r.results[i];
      rows[i].className = `ev ${x.ok ? "pass" : "fail"}`; rows[i].querySelector(".r").textContent = x.ok ? "✓" : "✕";
      if (i % 3 === 0) await new Promise(res => setTimeout(res, 18));
    }
    renderPromiseProof(r.results);
    $("#evalSummary").innerHTML = `<span class="big ${r.passed === r.total ? "" : "bad"}">${r.passed}/${r.total}</span><span class="muted">passed in ${(r.ms / 1000).toFixed(1)} s · offline, deterministic, runs on every build (<code>pytest</code>)</span>`;
  } catch (e) { toast(`Checks failed to run: ${e.message}`); }
  btn.disabled = false; btn.textContent = "Run all checks";
}

async function runReplay() {
  const out = $("#replayOut"); out.innerHTML = `<p class="muted">Replaying…</p>`;
  try {
    const r = await api("/api/replay");
    const W = r.with, O = r.without, P = r.pay_ahead;
    const row = (label, a, b, fmt = v => v, c = "") => `<span>${label}</span><span class="w">${fmt(a)}</span><span class="wo">${fmt(b)}</span><span class="pa">${c === "—" ? c : fmt(c)}</span>`;
    out.innerHTML = `
      <div class="cmp"><span class="h">${r.flagged} of ${r.merchants_total} merchants flagged</span><span class="h" style="text-align:right">With</span><span class="h" style="text-align:right">Without</span><span class="h" style="text-align:right">Pay-ahead*</span>
        ${row("Merchants who fell overdue", W.merchants_overdue, O.merchants_overdue, v => v, P.merchants_overdue)}
        ${row("Merchant-days overdue", W.overdue_days, O.overdue_days, v => v, P.overdue_days)}
        ${row("Merchants 3+ days overdue", W.merchants_dpd_3plus, O.merchants_dpd_3plus, v => v, P.merchants_dpd_3plus)}
        ${row("Biggest single deduction (median)", W.median_peak_multiple, O.median_peak_multiple, v => `${v.toFixed(1)}×`, P.median_peak_multiple)}
        ${row("Guardrail violations found by audit", r.violations.length, "—", v => v, "—")}
      </div>
      <p class="note">* Pay-ahead only: the plain loan with the merchant's own pay-ahead switched on since the loan began, and no other help. It assumes every merchant opts in, so it is an upper bound to test in a pilot, not a forecast. Merchants pay the same total, just earlier, on good days.</p>
      <p class="note"><b>${r.relief_accepted}</b> accepted relief from the lender's menu. <b>${r.handed_to_person}</b> went to a person. ${r.messages_sent} messages sent, ${r.proactive_messages} of them unprompted, all re-checked by an independent audit.</p>
      <div><p class="sec-t">Still overdue with Sambhal: each one is with a person, by design</p>
      <ul style="margin:0;padding-left:18px;font-size:13px">${r.still_overdue_with.map(x => `<li>${esc(x.merchant)}: ${esc((x.reason || "").replace(/_/g, " ") || STATE_LABEL[x.state])} (${esc(STATE_LABEL[x.state])})</li>`).join("")}</ul></div>
      <p class="note">${esc(r.note)} Biggest deduction is shown as a multiple of each merchant's normal installment.</p>`;
  } catch (e) { out.innerHTML = `<p class="muted">Replay failed: ${esc(e.message)}</p>`; }
}

// ---------------------------------------------------------------- lender what-if
let wiChanges = {};
async function renderWhatIf() {
  const el = $("#tab-whatif");
  if (!el.innerHTML) el.innerHTML = `<p class="muted">Replaying 50 merchants…</p>`;
  let r;
  try { r = await post("/api/whatif", { changes: wiChanges }); } catch (e) { el.innerHTML = `<p class="muted">What-if failed: ${esc(e.message)}</p>`; return; }
  const C = r.current, P = r.proposed;
  const rows = [
    ["Merchants who fell overdue", C.with.merchants_overdue, P.with.merchants_overdue, v => v, true],
    ["Merchant-days overdue", C.with.overdue_days, P.with.overdue_days, v => v, true],
    ["Shops given relief", C.relief_accepted, P.relief_accepted, v => v, null],
    ["Handed to a person", C.handed_to_person, P.handed_to_person, v => v, null],
    ["Money paused, repaid later", C.relief_value, P.relief_value, inr, null],
    ["Heaviest deduction day (median, × installment)", C.with.median_peak_multiple, P.with.median_peak_multiple, v => `${v.toFixed(2)}×`, true],
    ["Rule violations found by audit", C.violations.length, P.violations.length, v => v, true],
  ];
  const delta = (a, b, fmt, lowerBetter) => {
    if (a === b) return `<span class="muted">same</span>`;
    const worse = lowerBetter === null ? null : (b > a) === lowerBetter;
    const d = typeof a === "number" && typeof b === "number" ? b - a : 0;
    const txt = fmt === inr ? `${d > 0 ? "+" : "−"}${inr(Math.abs(d))}` : `${d > 0 ? "+" : "−"}${fmt(Math.abs(d))}`;
    return `<span class="${worse === null ? "" : worse ? "bad" : "good"}">${txt}</span>`;
  };
  const notes = [];
  if (P.with.merchants_overdue > C.with.merchants_overdue) notes.push(`${P.with.merchants_overdue - C.with.merchants_overdue} more merchants fall overdue: the menu no longer covers their closures.`);
  if (P.with.merchants_overdue < C.with.merchants_overdue) notes.push(`${C.with.merchants_overdue - P.with.merchants_overdue} fewer merchants fall overdue.`);
  if (P.with.median_peak_multiple > C.with.median_peak_multiple) notes.push(`Faster catch-up returns money sooner but makes the heaviest day heavier for the merchant.`);
  if (P.with.median_peak_multiple < C.with.median_peak_multiple) notes.push(`Gentler catch-up days for merchants; the lender waits longer for the paused money.`);
  if (P.relief_value !== C.relief_value) notes.push(`${inr(Math.abs(P.relief_value - C.relief_value))} ${P.relief_value > C.relief_value ? "more" : "less"} is paused and repaid later.`);
  if (!notes.length && Object.keys(wiChanges).length) notes.push("No effect on these merchants: their closures and records are already inside the menu either way.");
  el.innerHTML = `<div class="whatif">
    <div class="wi-head"><div><h3>Lender what-if</h3><p class="muted">Change the relief menu and replay the same 50 merchants and days before it goes live. Sambhal can only ever offer what this menu allows; the live demo keeps using today's menu.</p></div>
      <button class="ghost" id="wiReset" ${Object.keys(wiChanges).length ? "" : "disabled"}>Back to today's menu</button></div>
    <div class="wi-controls">${Object.entries(r.tunable).map(([k, tn]) => `<div class="wi-ctl"><span>${esc(tn.label)}</span>
      <div class="seg">${tn.values.map(v => `<button data-k="${k}" data-v="${v}" class="${r.settings[k] === v ? "on" : ""} ${r.now[k] === v ? "cur" : ""}" title="${r.now[k] === v ? "Today's setting" : ""}">${v}</button>`).join("")}</div><small>${esc(tn.unit)}</small></div>`).join("")}</div>
    <table class="wi-table"><thead><tr><th></th><th>Today's menu</th><th>Proposed</th><th>Change</th></tr></thead><tbody>
      ${rows.map(([l, a, b, fmt, lb]) => `<tr><td>${l}</td><td class="n">${fmt(a)}</td><td class="n">${fmt(b)}</td><td class="n">${delta(a, b, fmt, lb)}</td></tr>`).join("")}</tbody></table>
    ${notes.length ? `<p class="note">${notes.map(esc).join(" ")}</p>` : `<p class="note">Pick a setting above to compare. The underlined value is today's.</p>`}
  </div>`;
  $$(".seg button", el).forEach(b => (b.onclick = () => {
    const k = b.dataset.k, v = +b.dataset.v;
    if (r.now[k] === v) delete wiChanges[k]; else wiChanges[k] = v;
    renderWhatIf();
  }));
  $("#wiReset").onclick = () => { wiChanges = {}; renderWhatIf(); };
}

// ---------------------------------------------------------------- audit
async function renderAudit() {
  const only = $("#auditFocus").checked;
  const r = await api(`/api/audit${only ? `?merchant=${focus}` : ""}`);
  $("#auditBody").innerHTML = r.rows.map(a => `<tr><td>${fmtDay(a.at)} ${fmtTime(a.at)}</td><td>${esc(a.merchant)}</td><td>${esc(a.rule)}</td><td class="d-${esc(a.decision.split(" ")[0])}">${esc(a.decision)}</td><td>${esc(a.detail)}</td></tr>`).join("") || `<tr><td colspan="5" class="muted">Nothing yet.</td></tr>`;
}

// ---------------------------------------------------------------- actions
async function act(fn) {
  if (busy) return; busy = true;
  try { await fn(); } catch (e) { toast(e.message); } finally { busy = false; }
}
function goStep(n) {
  return act(async () => {
    const prevStep = S.step;
    stopVoice();                // a note from the last step never talks over the next one
    if (n < prevStep) lastSpoken = Infinity;
    S = await post("/api/step", { n }); focus = S.focus;
    $("#sheet").hidden = true;
    if (lastSpoken === Infinity) lastSpoken = sentOutId();
    render(); await applyStep(); autoSpeak();
  });
}
const SPOT = {
  home: ["#phone"], settle: ["#scrHome .h-last"], guard: ["#caseDetail .checks"], voice: ["#chat .vn", true],
  reading: ["#caseDetail .reading"], calendar: ["#scrLoan .cal", true], week: ["#tab-week .chartwrap"],
  payoff: ["#tab-week .payoff"], audit: ["#tab-audit .tablewrap"], cushion: ["#tab-week .po.cu"],
  offer: ["#chat .opt", true], alert: ["#alerts .alert-card"], timeline: ["#caseDetail .timeline"],
};
async function applyStep() {
  const st = S.steps[S.step];
  if (st.phone) { screen = st.phone; reasonMode = false; renderPhone(); }
  if (st.tab === "audit") $("#auditFocus").checked = true;
  if (st.tab) await setTab(st.tab);
  if (st.spot && SPOT[st.spot]) spot(...SPOT[st.spot]);
}
function spot(sel, last = false) {
  const els = $$(sel), el = last ? els[els.length - 1] : els[0];
  if (!el) return;
  el.scrollIntoView({ block: "nearest", behavior: "smooth" });
  el.classList.remove("spot"); void el.offsetWidth; el.classList.add("spot");
  setTimeout(() => el.classList.remove("spot"), 2700);
}
async function setTab(name) {
  tab = name;
  $$(".tabs button").forEach(x => x.classList.toggle("on", x.dataset.tab === name));
  ["cases", "week", "proof", "audit", "whatif"].forEach(t2 => ($(`#tab-${t2}`).hidden = t2 !== name));
  if (name === "whatif") await renderWhatIf();
  if (name === "week") await renderWeek();
  if (name === "audit") await renderAudit();
  if (name === "proof" && !proofLoaded) { proofLoaded = true; runEvals(); runReplay(); }
}
function sendInbound(text, via = "text") {
  return act(async () => {
    S = await post("/api/inbound", { merchant_id: focus, text, via });
    screen = "chat";
    $("#msgInput").value = ""; render(); autoSpeak();
  });
}
function acceptOpt(opt) {
  return act(async () => {
    const r = await post("/api/accept", { merchant_id: focus, option_id: opt });
    S = r; if (!r.result.ok) toast(`Not accepted: ${r.result.why}`);
    render(); autoSpeak();
  });
}
function setConsent(on) {
  return act(async () => {
    S = await post("/api/consent", { merchant_id: focus, on });
    screen = "chat"; render(); autoSpeak();
  });
}
function setCushion(on) {
  return act(async () => {
    const r = await post("/api/cushion", { merchant_id: focus, on });
    S = r; if (!r.result.ok) toast(`Pay-ahead: ${r.result.why}`);
    render(); autoSpeak();
  });
}
function autoSpeak() {
  const fresh = S.merchant.thread.filter(m => m.dir === "out" && m.status === "sent" && m.id > lastSpoken);
  lastSpoken = sentOutId();
  // Only the check-in plays by itself (Friday 8 am, the demo's voice moment). Other notes wait for ▶: they run
  // 15-35 s each, and playing every one would talk over the presenter for two minutes of a three-minute demo.
  const last = fresh[fresh.length - 1];
  if (last && last.kind === "checkin") playMsg(last.id);
}

// ---------------------------------------------------------------- voice out
let audioEl = null;
function stopVoice() {
  if (audioEl) { audioEl.pause(); audioEl = null; }
  if ("speechSynthesis" in window) speechSynthesis.cancel();
  $$(".vn.on, #promiseListen.on").forEach(b => b.classList.remove("on"));
}
async function playMsg(id) {
  const msg = S.merchant.thread.find(m => m.id === id); if (!msg) return;
  return playText(`${msg.header}. ${msg.text}`, msg.lang, $(`.vn[data-id="${id}"]`));
}
async function playText(text, lang, btn) {
  const msg = { lang };
  if (audioEl) { audioEl.pause(); audioEl = null; }
  speechSynthesis.cancel();
  btn && btn.classList.add("on");
  try {
    const r = await fetch("/api/tts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, lang }) });
    if (!r.ok) throw new Error("tts");
    const blob = await r.blob();
    audioEl = new Audio(URL.createObjectURL(blob));
    audioEl.onended = () => btn && btn.classList.remove("on");
    await audioEl.play();
  } catch (_) {
    const code = { kn: "kn", hi: "hi", en: "en" }[msg.lang];
    const v = speechSynthesis.getVoices().find(x => x.lang.toLowerCase().startsWith(code));
    if (!v) { toast(`No ${LANG_LABEL[msg.lang]} voice available. Add SARVAM_API_KEY to .env, or run scripts/warm_voice_cache.py once.`); btn && btn.classList.remove("on"); return; }
    const u = new SpeechSynthesisUtterance(text); u.voice = v; u.lang = v.lang;
    u.onend = () => btn && btn.classList.remove("on");
    speechSynthesis.speak(u);
  }
}

// ---------------------------------------------------------------- voice in
let rec = null, chunks = [], recog = null;
async function toggleMic() {
  const mic = $("#btnMic"), note = $("#recNote");
  if (rec && rec.state === "recording") { rec.stop(); return; }
  if (recog) { recog.stop(); return; }
  const lang = dispLang === "en" ? "" : ownLang();     // English on screen: let speech-to-text detect the language
  if (!S.status.voice.on && ("webkitSpeechRecognition" in window || "SpeechRecognition" in window)) {
    const R = window.SpeechRecognition || window.webkitSpeechRecognition;
    recog = new R(); recog.lang = { kn: "kn-IN", hi: "hi-IN", en: "en-IN" }[lang] || "en-IN"; recog.interimResults = false;
    mic.classList.add("rec"); note.hidden = false; note.textContent = "Listening (browser speech)… click again to stop";
    recog.onresult = e => { const t = e.results[0][0].transcript; note.textContent = `Heard: ${t}`; sendInbound(t, "voice"); };
    recog.onerror = e => { note.textContent = `Browser speech failed (${e.error}). Type the reply instead.`; };
    recog.onend = () => { mic.classList.remove("rec"); recog = null; renderComposer(); };
    recog.start(); renderComposer(); return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const type = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
    rec = new MediaRecorder(stream, type ? { mimeType: type } : undefined); chunks = [];
    rec.ondataavailable = e => e.data.size && chunks.push(e.data);
    rec.onstop = async () => {
      stream.getTracks().forEach(t => t.stop()); mic.classList.remove("rec"); renderComposer();
      const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
      note.textContent = "Transcribing with Sarvam…";
      const fd = new FormData(); fd.append("file", blob, "reply.webm"); fd.append("lang", lang);
      try {
        const r = await fetch("/api/stt", { method: "POST", body: fd });
        const j = await r.json();
        if (!r.ok || !j.transcript) throw new Error(j.error || j.detail || "No speech heard");
        note.textContent = `Heard (${j.ms} ms): ${j.transcript}`;
        await sendInbound(j.transcript, "voice");
      } catch (e) { note.textContent = `Couldn't transcribe: ${e.message}. Type the reply or use a quick reply.`; }
    };
    rec.start(); mic.classList.add("rec"); renderComposer(); note.hidden = false; note.textContent = "Recording… tap the mic again to stop";
  } catch (e) { note.hidden = false; note.textContent = `Microphone not available: ${e.message}`; }
}

// ---------------------------------------------------------------- sizer
let szTimer = null;
async function runSizer() {
  const amount = +$("#szAmount").value, tenure = +$("#szTenure").value;
  $("#szAmountOut").textContent = inr(amount);
  try {
    const r = await post("/api/sizer", { merchant_id: focus, amount, tenure_days: tenure });
    const vLabel = { comfortable: "Comfortable", tight: "Tight", risky: "Risky" }[r.verdict];
    $("#sizerOut").innerHTML = `
      <div class="verdict ${r.verdict}"><span class="v">${vLabel}</span><span class="big">${inr(r.installment)} a day</span>
        <span>${pct(r.share_of_worst_week)} of your slowest week's sales (keep it under ${pct(r.safe_share)})</span></div>
      <p class="settle" ${langAttr(S.merchant.lang)} style="font-size:13.5px;margin:0">${esc(S.merchant.lang === "en" ? r.line_en || r.line : r.line)}${S.merchant.lang !== "en" ? `<br><span class="muted" lang="en">${esc(r.line_en)}</span>` : ""}</p>
      <div class="kv"><span>Suggested up to</span><span>${inr(r.suggested_max)}</span><span>Slowest week</span><span>${inr(r.worst_week_sales)}</span><span>Typical week</span><span>${inr(r.typical_week_sales)}</span><span>Total repayable</span><span>${inr(r.total)}</span></div>
      <p class="muted" style="font-size:11.5px;margin:0">${esc(r.pricing_note)}</p>`;
  } catch (e) { $("#sizerOut").innerHTML = `<p class="muted">${esc(e.message)}</p>`; }
}

// ---------------------------------------------------------------- wiring
function wire() {
  $("#btnNext").onclick = () => goStep(S.step + 1);
  $("#btnPrev").onclick = () => goStep(S.step - 1);
  $("#btnReset").onclick = () => act(async () => { lastSpoken = Infinity; S = await post("/api/reset"); focus = "M01"; dispLang = "en"; lastSpoken = sentOutId(); proofLoaded = false; render(); });
  $("#btnClock").onclick = () => act(async () => { S = await post("/api/advance", { next_event: true }); render(); autoSpeak(); });
  $("#offlineToggle").onchange = e => act(async () => { await post("/api/offline", { on: e.target.checked }); await load(); toast(e.target.checked ? "Offline: rules, templates and cached audio only" : "Online: Sarvam and the LLM are used if keys are set"); });
  $$("#langSw button").forEach(b => (b.onclick = () => setLang(b.dataset.l)));
  $("#auditFocus").onchange = renderAudit;
  $("#sendForm").onsubmit = e => { e.preventDefault(); const t = $("#msgInput").value.trim(); if (t) sendInbound(t, "text"); };
  $("#btnMic").onclick = toggleMic;
  $("#btnEvals").onclick = runEvals;
  $("#btnReplay").onclick = runReplay;
  $("#szAmount").oninput = () => { $("#szAmountOut").textContent = inr(+$("#szAmount").value); clearTimeout(szTimer); szTimer = setTimeout(runSizer, 150); };
  $("#szTenure").onchange = runSizer;
  $$(".tabs button").forEach(b => (b.onclick = () => setTab(b.dataset.tab)));
  $$(".ph-nav button").forEach(b => (b.onclick = () => setScreen(b.dataset.scr)));
  $("#sizerBox").ontoggle = () => { if ($("#sizerBox").open) runSizer(); };
  const big = (() => { try { return localStorage.getItem("sambhal.big") === "1"; } catch (_) { return false; } })();
  $("#bigToggle").checked = big; document.body.classList.toggle("big", big);
  $("#bigToggle").onchange = e => {
    document.body.classList.toggle("big", e.target.checked);
    try { localStorage.setItem("sambhal.big", e.target.checked ? "1" : "0"); } catch (_) { /* private mode */ }
  };
  const closeWelcome = () => { $("#welcome").hidden = true; try { localStorage.setItem("sambhal.welcomed", "1"); } catch (_) { /* private mode */ } };
  $("#btnAbout").onclick = () => ($("#welcome").hidden = false);
  $("#wExplore").onclick = closeWelcome;
  $("#wStart").onclick = () => { closeWelcome(); goStep(0); };
  $("#welcome").onclick = e => { if (e.target.id === "welcome") closeWelcome(); };
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !$("#welcome").hidden) closeWelcome(); });
  try { if (localStorage.getItem("sambhal.welcomed") !== "1") $("#welcome").hidden = false; } catch (_) { $("#welcome").hidden = false; }
  document.addEventListener("keydown", e => {
    if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName) || !$("#welcome").hidden) return;
    if (e.key === "ArrowRight" || e.key === "PageDown") { e.preventDefault(); if (S.step < S.steps.length - 1) goStep(S.step + 1); }
    if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); if (S.step > 0) goStep(S.step - 1); }
  });
  if ("speechSynthesis" in window) speechSynthesis.getVoices();
}

// Deep links, for screenshots and sharing a moment of the demo:
//   ?step=7&tab=week   ?step=9&focus=M01&screen=home   ?sheet=promise|plan   ?phone=1 (the app alone)   ?welcome=0
//   ?lang=kn (the phone in the merchant's own language instead of English)
async function deepLink() {
  const q = new URLSearchParams(location.search);
  if (![...q.keys()].length) return;
  if (q.get("phone") === "1") document.body.classList.add("phone-only");
  if (q.get("welcome") === "0" || q.get("phone") === "1") $("#welcome").hidden = true;
  if (q.has("lang")) { dispLang = q.get("lang") === "en" ? "en" : "local"; render(); }
  if (q.has("step")) await goStep(+q.get("step"));
  if (q.has("focus")) await load(q.get("focus"));
  if (q.has("screen")) setScreen(q.get("screen"));
  if (q.has("wi")) wiChanges = Object.fromEntries(q.get("wi").split(",").map(kv => kv.split("=")).map(([k, v]) => [k, +v]));
  if (q.has("tab")) await setTab(q.get("tab"));
  if (q.get("sheet") === "promise") openPromise();
  if (q.get("sheet") === "plan") openPlanner();
  if (q.has("scroll")) $(`#${q.get("scroll")}`)?.scrollIntoView({ block: "start" });
}

wire();
load().then(deepLink).catch(e => toast(`Can't reach the server: ${e.message}`, 8000));
