/* Sambhal demo UI. Plain JS, no build step. */
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
let S = null;                 // last /api/state snapshot
let focus = "M01";
let tab = "cases";
let ptab = "chat";
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
  if (lastSpoken === Infinity) lastSpoken = maxOutId();
  render();
}
function maxOutId() {
  const c = S?.merchant?.case; if (!c) return 0;
  return Math.max(0, ...c.messages.filter(m => m.dir === "out").map(m => m.id));
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
  cv.textContent = st.voice.on ? "Voice: Sarvam" : st.voice.configured ? "Voice: cached audio" : "Voice: browser";
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
    const li = document.createElement("li");
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
}

// ---------------------------------------------------------------- phone
function renderPhone() {
  const m = S.merchant;
  $("#phAvatar").textContent = m.first[0];
  $("#phName").textContent = m.owner;
  $("#phShop").textContent = `${m.shop} · ${LANG_LABEL[m.lang]}`;
  const showEn = $("#enToggle").checked;
  const chat = $("#chat");
  const atBottom = chat.scrollHeight - chat.scrollTop - chat.clientHeight < 60;
  let html = settleCard(m);
  const c = m.case;
  if (!c || !c.messages.length) {
    html += `<p class="empty">${c && !m.consent ? "No messages: this merchant didn't opt in, so a person at the lender will call instead." : "No messages yet. Sambhal stays quiet until it can help."}</p>`;
  } else {
    let day = null;
    for (const msg of c.messages) {
      const t = msg.sent_at || msg.at;
      if (msg.dir === "out" && msg.status === "held") {
        html += `<div class="sysline hold">⏸ Sambhal has a message ready. Held until ${fmtDayTime(msg.held_until)}: ${esc(HOLD_WHY[msg.held_reason] || msg.held_reason || "contact rules")}.</div>`;
        continue;
      }
      if (msg.dir === "out" && msg.status === "blocked") {
        const why = (msg.checks || []).filter(x => !x.ok).map(x => x.why).join("; ");
        html += `<div class="sysline block">✕ Not sent: ${esc(why || "blocked by a guardrail")}</div>`;
        continue;
      }
      const dk = fmtDay(t);
      if (dk !== day) { html += `<div class="daysep">${dk}</div>`; day = dk; }
      if (msg.dir === "out" && msg.held_once) {
        html += `<div class="sysline info">Waited for ${esc(HOLD_WHY[msg.held_reason] || msg.held_reason)}; delivered ${fmtTime(msg.sent_at)}.</div>`;
      }
      html += msg.dir === "out" ? outBubble(msg, c, showEn) : inBubble(msg, showEn);
    }
  }
  chat.innerHTML = html;
  if (atBottom || busy) chat.scrollTop = chat.scrollHeight;
  $$(".play", chat).forEach(b => (b.onclick = () => playMsg(+b.dataset.id)));
  $$(".opt button", chat).forEach(b => (b.onclick = () => acceptOpt(b.dataset.opt)));
  renderQuick();
}

function settleCard(m) {
  const rows = m.recent.slice(-3);
  if (!rows.length) return "";
  const tr = rows.map(r => {
    const ratio = r.baseline ? r.sales / r.baseline : 1;
    const cls = r.sales === 0 ? "zero" : ratio < 0.5 ? "low" : "";
    const note = r.paused ? `<span class="pz">paused</span>` : r.arrears > 0 ? `<span class="zero">${inr(r.arrears)} due</span>` : inr(r.deducted);
    return `<tr><td>${r.dow} ${D(r.date).getDate()}</td><td class="${cls}">${inr(r.sales)}</td><td class="${cls}">${pct(ratio)}</td><td>${note}</td></tr>`;
  }).join("");
  return `<div class="settle"><h4>Settlements · sales · vs normal · deducted</h4><table>${tr}</table></div>`;
}

function outBubble(msg, c, showEn) {
  const tag = msg.author === "llm" ? `<span class="tag ai">AI-phrased · checked</span>` : `<span class="tag tpl">Approved template</span>`;
  let opts = "";
  for (const o of msg.options || []) {
    const taken = c.accepted === o.id;
    const can = c.state === "offered" && !c.accepted;
    opts += `<div class="opt ${taken ? "taken" : ""}"><b ${langAttr(msg.lang)}>${esc(o.label)}</b>${showEn && msg.lang !== "en" ? `<p>${esc(o.label_en)}</p>` : ""}
      ${taken ? `<b>✓ Accepted</b>` : can ? `<button data-opt="${o.id}" ${langAttr(msg.lang)}>${msg.lang === "kn" ? "ಒಪ್ಪುತ್ತೇನೆ" : msg.lang === "hi" ? "स्वीकार करें" : "Accept"}</button>` : ""}</div>`;
  }
  return `<div class="bubble out">
    <div class="hdr" ${langAttr(msg.lang)}>${esc(msg.header)}</div>
    <div class="body" ${langAttr(msg.lang)}>${esc(msg.text)}</div>
    ${showEn && msg.lang !== "en" ? `<div class="en">${esc(msg.text_en)}</div>` : ""}
    ${opts}
    <div class="ftr">${esc(msg.footer)}</div>
    <div class="meta"><span>${fmtTime(msg.sent_at)} · ${tag}</span><button class="play" data-id="${msg.id}">▶ Play</button></div>
  </div>`;
}

function inBubble(msg, showEn) {
  const via = msg.via === "voice" ? `<span class="tag voice">voice</span>` : msg.via === "tap" ? `<span class="tag voice">tap</span>` : "";
  const sim = msg.simulated ? ` <span class="tag sim">simulated</span>` : "";
  return `<div class="bubble in">
    <div class="body" ${langAttr(msg.lang)}>${esc(msg.text)}</div>
    ${showEn && (msg.lang !== "en" || msg.kind === "accept") && msg.text_en ? `<div class="en">${esc(msg.text_en)}</div>` : ""}
    <div class="meta"><span>${via}${sim}</span><span>${fmtTime(msg.at)}</span></div>
  </div>`;
}

function renderQuick() {
  const q = $("#quick"); q.innerHTML = "";
  const c = S.merchant.case;
  const canReply = c && ["waiting", "offered", "declined"].includes(c.state);
  if (!canReply) return;
  const lines = [];
  if (focus === "M01" && !c.messages.some(m => m.dir === "in")) lines.push({ text: RAVI_LINE, label: `🎙 ${RAVI_LINE}`, main: true });
  if (c.state === "offered") lines.push({ text: S.merchant.lang === "kn" ? "ಸರಿ, ಒಪ್ಪುತ್ತೇನೆ" : S.merchant.lang === "hi" ? "हाँ, ठीक है" : "Yes, okay", label: "Says yes" });
  TRY_LINES.forEach(l => lines.push(l));
  for (const l of lines.slice(0, 4)) {
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
    <div><h2>${esc(m.owner)}</h2><div class="sub">${esc(m.shop)} · ${esc(m.area)} · ${LANG_LABEL[m.lang]}${m.consent ? "" : " · <b>no messaging consent</b>"}</div><div style="margin-top:6px">${status}</div></div>
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
function renderCases() {
  const list = $("#caseList");
  if (!S.cases.length) {
    list.innerHTML = `<p class="muted" style="padding:10px">No cases yet. The early-warning rule runs after every evening settlement across all ${S.counts.merchants} merchants.</p>`;
  } else {
    list.innerHTML = S.cases.map(c => `
      <button class="crow ${c.merchant_id === focus ? "sel" : ""}" data-mid="${c.merchant_id}">
        <span class="nm">${esc(c.merchant)}${c.demo ? '<span class="demo">DEMO</span>' : ""}</span>${pill(c.state)}
        <span class="rs">${esc(c.human_reason || (c.held_until ? `Held until ${fmtDayTime(c.held_until)}` : c.trigger || ""))}</span>
      </button>`).join("");
    $$(".crow", list).forEach(b => (b.onclick = () => { lastSpoken = Infinity; load(b.dataset.mid).then(() => { lastSpoken = maxOutId(); }); }));
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
  const handoff = c.human ? `<div class="handoff"><b>With a person at the lender</b>${esc(c.human_reason || "")}${c.human_options && c.human_options.length ? `<br>Staff may offer: ${c.human_options.map(o => esc(o.id)).join(", ")}` : ""}</div>` : "";
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
  el.innerHTML = `<div class="week">
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

// ---------------------------------------------------------------- proof
async function runEvals() {
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
    $("#evalSummary").innerHTML = `<span class="big ${r.passed === r.total ? "" : "bad"}">${r.passed}/${r.total}</span><span class="muted">passed in ${(r.ms / 1000).toFixed(1)} s · offline, deterministic, runs on every build (<code>pytest</code>)</span>`;
  } catch (e) { toast(`Checks failed to run: ${e.message}`); }
  btn.disabled = false; btn.textContent = "Run all checks";
}

async function runReplay() {
  const out = $("#replayOut"); out.innerHTML = `<p class="muted">Replaying…</p>`;
  try {
    const r = await api("/api/replay");
    const W = r.with, O = r.without;
    const row = (label, a, b, fmt = v => v) => `<span>${label}</span><span class="w">${fmt(a)}</span><span class="wo">${fmt(b)}</span>`;
    out.innerHTML = `
      <div class="cmp"><span class="h">${r.flagged} of ${r.merchants_total} merchants flagged</span><span class="h" style="text-align:right">With</span><span class="h" style="text-align:right">Without</span>
        ${row("Merchants who fell overdue", W.merchants_overdue, O.merchants_overdue)}
        ${row("Merchant-days overdue", W.overdue_days, O.overdue_days)}
        ${row("Merchants 3+ days overdue", W.merchants_dpd_3plus, O.merchants_dpd_3plus)}
        ${row("Biggest single deduction (median)", W.median_peak_multiple, O.median_peak_multiple, v => `${v.toFixed(1)}×`)}
        ${row("Guardrail violations found by audit", r.violations.length, "—")}
      </div>
      <p class="note"><b>${r.relief_accepted}</b> accepted relief from the lender's menu. <b>${r.handed_to_person}</b> went to a person. ${r.messages_sent} messages sent, ${r.proactive_messages} of them unprompted, all re-checked by an independent audit.</p>
      <div><p class="sec-t">Still overdue with Sambhal: each one is with a person, by design</p>
      <ul style="margin:0;padding-left:18px;font-size:13px">${r.still_overdue_with.map(x => `<li>${esc(x.merchant)}: ${esc((x.reason || "").replace(/_/g, " ") || STATE_LABEL[x.state])} (${esc(STATE_LABEL[x.state])})</li>`).join("")}</ul></div>
      <p class="note">${esc(r.note)} Biggest deduction is shown as a multiple of each merchant's normal installment.</p>`;
  } catch (e) { out.innerHTML = `<p class="muted">Replay failed: ${esc(e.message)}</p>`; }
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
    if (n < prevStep) lastSpoken = Infinity;
    S = await post("/api/step", { n }); focus = "M01";
    if (lastSpoken === Infinity) lastSpoken = maxOutId();
    render(); autoSpeak();
  });
}
function sendInbound(text, via = "text") {
  return act(async () => {
    S = await post("/api/inbound", { merchant_id: focus, text, via });
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
function autoSpeak() {
  const c = S.merchant.case; if (!c) return;
  const fresh = c.messages.filter(m => m.dir === "out" && m.status === "sent" && m.id > lastSpoken);
  lastSpoken = maxOutId();
  if (fresh.length) playMsg(fresh[fresh.length - 1].id);
}

// ---------------------------------------------------------------- voice out
let audioEl = null;
async function playMsg(id) {
  const c = S.merchant.case; const msg = c && c.messages.find(m => m.id === id); if (!msg) return;
  const btn = $(`.play[data-id="${id}"]`);
  if (audioEl) { audioEl.pause(); audioEl = null; }
  speechSynthesis.cancel();
  const text = `${msg.header}. ${msg.text}`;
  btn && btn.classList.add("on");
  try {
    const r = await fetch("/api/tts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, lang: msg.lang }) });
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
  const lang = S.merchant.lang;
  if (!S.status.voice.on && ("webkitSpeechRecognition" in window || "SpeechRecognition" in window)) {
    const R = window.SpeechRecognition || window.webkitSpeechRecognition;
    recog = new R(); recog.lang = { kn: "kn-IN", hi: "hi-IN", en: "en-IN" }[lang]; recog.interimResults = false;
    mic.classList.add("rec"); note.hidden = false; note.textContent = "Listening (browser speech)… click again to stop";
    recog.onresult = e => { const t = e.results[0][0].transcript; note.textContent = `Heard: ${t}`; sendInbound(t, "voice"); };
    recog.onerror = e => { note.textContent = `Browser speech failed (${e.error}). Type the reply instead.`; };
    recog.onend = () => { mic.classList.remove("rec"); recog = null; };
    recog.start(); return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const type = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
    rec = new MediaRecorder(stream, type ? { mimeType: type } : undefined); chunks = [];
    rec.ondataavailable = e => e.data.size && chunks.push(e.data);
    rec.onstop = async () => {
      stream.getTracks().forEach(t => t.stop()); mic.classList.remove("rec");
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
    rec.start(); mic.classList.add("rec"); note.hidden = false; note.textContent = "Recording… click the mic again to stop";
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
      <p class="settle" ${langAttr(S.merchant.lang)} style="font-size:13.5px;margin:0">${esc(r.line)}${S.merchant.lang !== "en" ? `<br><span class="muted" lang="en">${esc(r.line_en)}</span>` : ""}</p>
      <div class="kv"><span>Suggested up to</span><span>${inr(r.suggested_max)}</span><span>Slowest week</span><span>${inr(r.worst_week_sales)}</span><span>Typical week</span><span>${inr(r.typical_week_sales)}</span><span>Total repayable</span><span>${inr(r.total)}</span></div>
      <p class="muted" style="font-size:11.5px;margin:0">${esc(r.pricing_note)}</p>`;
  } catch (e) { $("#sizerOut").innerHTML = `<p class="muted">${esc(e.message)}</p>`; }
}

// ---------------------------------------------------------------- wiring
function wire() {
  $("#btnNext").onclick = () => goStep(S.step + 1);
  $("#btnPrev").onclick = () => goStep(S.step - 1);
  $("#btnReset").onclick = () => act(async () => { lastSpoken = Infinity; S = await post("/api/reset"); focus = "M01"; lastSpoken = maxOutId(); proofLoaded = false; render(); });
  $("#btnClock").onclick = () => act(async () => { S = await post("/api/advance", { next_event: true }); render(); autoSpeak(); });
  $("#offlineToggle").onchange = e => act(async () => { await post("/api/offline", { on: e.target.checked }); await load(); toast(e.target.checked ? "Offline: rules, templates and cached audio only" : "Online: Sarvam and the LLM are used if keys are set"); });
  $("#enToggle").onchange = renderPhone;
  $("#auditFocus").onchange = renderAudit;
  $("#sendForm").onsubmit = e => { e.preventDefault(); const t = $("#msgInput").value.trim(); if (t) sendInbound(t, "text"); };
  $("#btnMic").onclick = toggleMic;
  $("#btnEvals").onclick = runEvals;
  $("#btnReplay").onclick = runReplay;
  $("#szAmount").oninput = () => { $("#szAmountOut").textContent = inr(+$("#szAmount").value); clearTimeout(szTimer); szTimer = setTimeout(runSizer, 150); };
  $("#szTenure").onchange = runSizer;
  $$(".tabs button").forEach(b => (b.onclick = () => {
    tab = b.dataset.tab;
    $$(".tabs button").forEach(x => x.classList.toggle("on", x === b));
    ["cases", "week", "proof", "audit"].forEach(t => ($(`#tab-${t}`).hidden = t !== tab));
    if (tab === "week") renderWeek();
    if (tab === "audit") renderAudit();
    if (tab === "proof" && !proofLoaded) { proofLoaded = true; runEvals(); runReplay(); }
  }));
  $$(".ph-tabs button").forEach(b => (b.onclick = () => {
    ptab = b.dataset.ptab;
    $$(".ph-tabs button").forEach(x => x.classList.toggle("on", x === b));
    $("#chat").hidden = ptab !== "chat"; $("#sizerPane").hidden = ptab !== "sizer";
    $("#composer").hidden = ptab !== "chat";
    if (ptab === "sizer") runSizer();
  }));
  document.addEventListener("keydown", e => {
    if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
    if (e.key === "ArrowRight" || e.key === "PageDown") { e.preventDefault(); if (S.step < S.steps.length - 1) goStep(S.step + 1); }
    if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); if (S.step > 0) goStep(S.step - 1); }
  });
  if ("speechSynthesis" in window) speechSynthesis.getVoices();
}

wire();
load().catch(e => toast(`Can't reach the server: ${e.message}`, 8000));
