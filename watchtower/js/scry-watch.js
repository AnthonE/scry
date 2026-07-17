/* scry watchtower — oversee your agents' vows, chains, trajectories.
 * Vanilla JS, CSP-clean (script-src 'self'), no deps. API = same-origin /api.
 * Series hues are validated (6-check palette validator, dark surface #150e28):
 *   I(C;M) #4f8fd9 · switch #b5811f · y_consistency #b8619e — color follows the
 * measure everywhere; status colors (ok/warn) are separate and always labeled. */
"use strict";

const API = "/api";
const HUES = { coupling: "#4f8fd9", sw: "#b5811f", ycon: "#b8619e" };
const $ = (id) => document.getElementById(id);

let wallet = null;
let vows = [];
let current = null;

// ── tiny helpers ─────────────────────────────────────────────────────────────
async function jget(path) {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}
async function jpost(path, body) {
  const r = await fetch(API + path, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `${path} -> ${r.status}`);
  return j;
}
function esc(s) {
  const d = document.createElement("span"); d.textContent = String(s ?? "");
  return d.innerHTML;
}
function msg(el, text, ok) {
  el.textContent = text; el.className = "msg " + (ok ? "ok" : "err");
}

// ── wallet ───────────────────────────────────────────────────────────────────
async function connectWallet() {
  if (!window.ethereum) {
    msg($("vow-result"), "no wallet extension found — unsigned sandbox vows still work", false);
    return;
  }
  const accts = await window.ethereum.request({ method: "eth_requestAccounts" });
  wallet = accts[0];
  $("wallet-label").textContent = wallet.slice(0, 6) + "…" + wallet.slice(-4);
  $("btn-wallet").textContent = "connected";
  renderRegister();
}

// ── the register ─────────────────────────────────────────────────────────────
async function loadRegister() {
  const j = await jget("/vows");
  vows = j.vows || [];
  renderRegister();
}
function renderRegister() {
  const mine = $("filter-mine").checked;
  const tb = $("tbl-register").querySelector("tbody");
  tb.innerHTML = "";
  let rows = vows;
  if (mine && wallet)
    rows = rows.filter((v) => (v.wallet || "").toLowerCase() === wallet.toLowerCase());
  for (const v of rows) {
    const tr = document.createElement("tr");
    tr.className = "rowlink";
    const status = v.overdue
      ? '<span class="badge warn">⚠ overdue</span>'
      : '<span class="badge ok">✓ current</span>';
    tr.innerHTML =
      `<td>${esc(v.agent)}</td>` +
      `<td>${v.sealed ? '🔒 <span class="mono-note">sealed · sha ' + esc((v.text_sha256 || "").slice(0, 12)) + '…</span>' : esc(v.text)}</td>` +
      `<td>${v.sandbox ? '<span class="badge">sandbox</span>' : '<span class="badge ok">✓ signed</span>'}</td>` +
      `<td>${v.n_reports}</td><td>${v.missed_windows}</td>` +
      `<td>${v.n_reports ? status : '<span class="badge">no reports yet</span>'}</td>` +
      `<td>${esc((v.created_at || "").slice(0, 10))}</td>`;
    tr.addEventListener("click", () => openVow(v.vow_id));
    tb.appendChild(tr);
  }
  if (!rows.length) tb.innerHTML = '<tr><td colspan="7" class="mono-note">no vows yet — take the first one below</td></tr>';
}

// ── the ledger detail ────────────────────────────────────────────────────────
async function openVow(vowId) {
  const led = await jget(`/vow/${vowId}`);
  current = led;
  const v = led.vow, t = led.trajectory;
  $("sec-detail").classList.remove("hidden");
  $("d-title").textContent = `ledger — ${v.vow.agent}`;
  $("d-vowtext").textContent = v.vow.text
    ? `"${v.vow.text}"`
    : `🔒 sealed vow — committed by sha256 ${(v.vow.text_sha256 || "").slice(0, 16)}… ` +
      `(verify a candidate text at /api/vow/${v.vow_id}/verify_text?text=…)`;
  $("d-meta").textContent =
    `vow ${v.vow_id} · ${v.sandbox ? "SANDBOX (unsigned)" : "signed by " + v.vow.wallet} · ` +
    `cadence every ${v.vow.cadence_hours}h · taken ${v.vow.created_at} · ` +
    `chain ${t.chain_verified_locally ? "VERIFIED ✓" : "FAILED VERIFICATION ✗"}`;

  const tiles = [
    ["reports", `${t.n_reports}`],
    ["attested / sandbox", `${t.n_attested} / ${t.n_sandbox}`],
    ["missed windows", `${t.missed_windows}`],
    ["hours since last", t.hours_since_last_report == null ? "—" : `${t.hours_since_last_report}`],
    ["status", t.n_reports === 0 ? "no reports" : (t.overdue ? "⚠ OVERDUE" : "✓ current")],
  ];
  $("d-tiles").innerHTML = tiles.map(([k, val]) =>
    `<div class="tile"><div class="k">${k}</div><div class="v">${esc(val)}</div></div>`).join("");

  const sp = $("d-sparks");
  sp.innerHTML = "";
  spark(sp, "I(C;M) coupling — bits", t.coupling_ICM_series, HUES.coupling);
  spark(sp, "switch signature — bits", t.switch_signature_series, HUES.sw);
  spark(sp, "y_consistency — 0..1", t.y_consistency_series, HUES.ycon);

  const tb = $("tbl-chain").querySelector("tbody");
  tb.innerHTML = "";
  for (const e of [...(led.chain || [])].reverse()) {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${e.seq}</td><td>${esc(e.issued_at)}</td>` +
      `<td>${e.profile["I(C;M) bits"] ?? "—"}</td>` +
      `<td>${e.profile["I(C;M | D-clean) bits  [switch signature]"] ?? "—"}</td>` +
      `<td>${e.y_consistency ?? "—"}</td>` +
      `<td>${e.attested ? '<span class="badge ok">✓ paid</span>' : '<span class="badge">sandbox</span>'}</td>` +
      `<td>${esc((e.entry_hash || "").slice(0, 12))}…</td>`;
    tb.appendChild(tr);
  }
  $("d-reading").innerHTML = "";
  $("sec-detail").scrollIntoView({ behavior: "smooth" });
}

// ── sparkline (inline SVG, hover tooltip, direct last-value label) ───────────
function spark(container, title, series, hue) {
  const wrapEl = document.createElement("div");
  wrapEl.className = "spark";
  const data = (series || []).filter((x) => x != null);
  const head = `<div class="t"><span class="dot" style="background:${hue}"></span>${esc(title)}</div>`;
  if (data.length < 2) {
    wrapEl.innerHTML = head + `<div class="mono-note">not enough reports yet (${data.length})</div>`;
    container.appendChild(wrapEl);
    return;
  }
  const W = 300, H = 74, P = 8;
  const min = Math.min(...data), max = Math.max(...data);
  const span = (max - min) || 1;
  const x = (i) => P + (i * (W - 2 * P)) / (data.length - 1);
  const y = (v) => H - P - ((v - min) * (H - 2 * P)) / span;
  const pts = data.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const last = data[data.length - 1];
  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.innerHTML =
    `<line x1="${P}" y1="${y(min)}" x2="${W - P}" y2="${y(min)}" stroke="rgba(242,236,224,0.12)" stroke-width="1"/>` +
    `<polyline points="${pts}" fill="none" stroke="${hue}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>` +
    `<circle cx="${x(data.length - 1)}" cy="${y(last)}" r="3.5" fill="${hue}"/>` +
    `<text x="${W - P}" y="${y(last) < 22 ? y(last) + 16 : y(last) - 8}" text-anchor="end" ` +
    `fill="#b9b0cc" font-family="JetBrains Mono, monospace" font-size="10.5">${last}</text>`;
  // hover: nearest-point tooltip, hit target = whole svg (bigger than the mark)
  const tip = $("tooltip");
  svg.addEventListener("mousemove", (ev) => {
    const r = svg.getBoundingClientRect();
    const px = ((ev.clientX - r.left) / r.width) * W;
    const i = Math.max(0, Math.min(data.length - 1,
      Math.round(((px - P) / (W - 2 * P)) * (data.length - 1))));
    tip.style.display = "block";
    tip.style.left = ev.clientX + 12 + "px";
    tip.style.top = ev.clientY - 10 + "px";
    tip.textContent = `#${i + 1} of ${data.length}: ${data[i]}`;
  });
  svg.addEventListener("mouseleave", () => { tip.style.display = "none"; });
  wrapEl.innerHTML = head;
  wrapEl.appendChild(svg);
  container.appendChild(wrapEl);
}

// ── the oracle ───────────────────────────────────────────────────────────────
async function consultOracle() {
  if (!current) return;
  $("d-reading").innerHTML = '<p class="mono-note">consulting…</p>';
  try {
    const r = await jget(`/vow/${current.vow.vow_id}/reading`);
    const prose = r.interpretation
      ? `<div class="oracle-prose">${esc(r.interpretation)}</div>`
      : "";
    $("d-reading").innerHTML = prose +
      `<p class="mono-note">${esc(r.interpretation_note || "")} · measurement signed ` +
      `(ed25519) — verify against <a href="/api/pubkey">/api/pubkey</a></p>`;
  } catch (e) {
    $("d-reading").innerHTML = `<p class="msg err">${esc(e.message)}</p>`;
  }
}

// ── take a vow ───────────────────────────────────────────────────────────────
function vowInputs() {
  return { text: $("v-text").value.trim(), agent: $("v-agent").value.trim(),
           cadence_hours: parseInt($("v-cadence").value, 10) || 24,
           sealed: $("v-sealed").checked };
}
async function takeVowSandbox() {
  const v = vowInputs();
  if (!v.text || !v.agent) return msg($("vow-result"), "need agent name + vow text", false);
  if (v.sealed) return msg($("vow-result"), "sealed vows need a wallet signature — use 'bind with wallet signature'", false);
  try {
    const j = await jpost("/vow", v);
    msg($("vow-result"), `vow taken (sandbox) — vow_id ${j.vow_id}`, true);
    loadRegister();
  } catch (e) { msg($("vow-result"), e.message, false); }
}
async function takeVowSigned() {
  const v = vowInputs();
  if (!v.text || !v.agent) return msg($("vow-result"), "need agent name + vow text", false);
  if (!window.ethereum) return msg($("vow-result"), "no wallet — use sandbox instead", false);
  try {
    if (!wallet) await connectWallet();
    const m = await jget(`/vow/message?text=${encodeURIComponent(v.text)}` +
      `&agent=${encodeURIComponent(v.agent)}&cadence_hours=${v.cadence_hours}`);
    const hex = "0x" + Array.from(new TextEncoder().encode(m.sign_this))
      .map((b) => b.toString(16).padStart(2, "0")).join("");
    const sig = await window.ethereum.request({
      method: "personal_sign", params: [hex, wallet] });
    const j = await jpost("/vow", { ...v, wallet, signature: sig });
    msg($("vow-result"), `vow BOUND by ${wallet.slice(0, 8)}… — vow_id ${j.vow_id}`, true);
    loadRegister();
  } catch (e) { msg($("vow-result"), e.message, false); }
}

// ── wire up ──────────────────────────────────────────────────────────────────
$("btn-wallet").addEventListener("click", connectWallet);
$("btn-vow-signed").addEventListener("click", takeVowSigned);
$("btn-vow-sandbox").addEventListener("click", takeVowSandbox);
$("btn-reading").addEventListener("click", consultOracle);
$("btn-back").addEventListener("click", () => {
  $("sec-detail").classList.add("hidden");
  $("sec-register").scrollIntoView({ behavior: "smooth" });
});
$("btn-chain").addEventListener("click", () => {
  if (current) window.open(`${API}/vow/${current.vow.vow_id}/chain`, "_blank");
});
$("filter-mine").addEventListener("change", renderRegister);
loadRegister().catch((e) => {
  $("tbl-register").querySelector("tbody").innerHTML =
    `<tr><td colspan="7" class="msg err">register unavailable: ${esc(e.message)}</td></tr>`;
});
