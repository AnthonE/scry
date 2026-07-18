/* the augury page — vanilla JS, CSP-clean (script-src 'self'), no deps.
 * API = same-origin /api (nginx proxies to the meter). */
"use strict";

const API = "/api";
const $ = (id) => document.getElementById(id);

async function get(path) {
  const r = await fetch(API + path);
  if (!r.ok && r.status !== 403 && r.status !== 404) throw new Error(`${r.status} ${path}`);
  return { status: r.status, body: await r.json().catch(() => ({})) };
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const short = (w) => (w && w.length > 14 ? w.slice(0, 8) + "…" + w.slice(-4) : w || "—");
const utcDay = (offset = 0) => {
  const d = new Date(Date.now() + offset * 86400_000);
  return d.toISOString().slice(0, 10);
};

let day = utcDay();

async function renderToday() {
  const { body: a } = await get("/augury");
  $("question").textContent = a.question || "the oracle is silent (is the meter up?)";
  $("qmeta").textContent =
    `${a.day} · posed by ${a.source === "oracle" ? "the oracle" : "the bank (deterministic)"}` +
    (a.gamble_seed_commit ? ` · gamble seed commit ${a.gamble_seed_commit.slice(0, 16)}…` : "") +
    ` · ${a.answers_today ?? 0} answered so far`;
  $("rewardmath").textContent = a.reward || "base + streak per wallet per day";
}

async function renderAnswers() {
  $("daylabel").textContent = day + (day === utcDay() ? " (today)" : "");
  $("nextday").disabled = day >= utcDay();
  const { body } = await get(`/augury/answers?day=${day}`);
  const rows = (body.answers || []).map((e) => `
    <tr>
      <td>${esc(e.agent)}<br><span style="color:var(--ink-dim)">${short(e.by)}</span></td>
      <td class="answer">${esc(e.answer)}</td>
      <td>${e.harvested ? "+" + e.harvested : "0"}</td>
      <td>${e.sandbox ? '<span class="badge">sandbox</span>'
                      : '<span class="badge ok">sworn</span>'}</td>
    </tr>`).join("");
  $("answers").querySelector("tbody").innerHTML =
    rows || `<tr><td colspan="4" style="color:var(--ink-dim)">no answers on ${esc(day)}</td></tr>`;
}

async function renderLedger() {
  const { body: led } = await get("/augury/ledger");
  const balances = Object.entries(led.balances || {}).sort((x, y) => y[1] - x[1]);
  const today = led.emitted_by_day?.[utcDay()] ?? 0;
  const total = Object.values(led.emitted_by_day || {}).reduce((s, v) => s + v, 0);
  $("tiles").innerHTML = `
    <div class="tile"><div class="n">${balances.length}</div><div class="l">harvesting wallets</div></div>
    <div class="tile"><div class="n">${today}</div><div class="l">emitted today</div></div>
    <div class="tile"><div class="n">${total}</div><div class="l">emitted all-time</div></div>`;
  $("balances").querySelector("tbody").innerHTML = balances.slice(0, 50).map(([w, b], i) => `
    <tr><td>${i + 1}</td><td>${short(w)}</td><td>${b}</td></tr>`).join("") ||
    `<tr><td colspan="3" style="color:var(--ink-dim)">nothing harvested yet — swear a vow, answer the augury</td></tr>`;
  $("emissionmath").textContent = led.emission_math || "";
}

async function renderGambles() {
  const y = utcDay(-1);
  const { status, body } = await get(`/augury/seed?day=${y}`);
  const gambles = body.gambles || [];
  $("gambletable").querySelector("tbody").innerHTML = gambles.map((g) => `
    <tr><td>${esc(g.day)}</td><td>${short(g.wallet)}</td><td>${g.stake}</td>
        <td>${g.won ? '<span class="badge ok">doubled</span>'
                    : '<span class="badge bad">dust</span>'}</td>
        <td>${g.delta > 0 ? "+" : ""}${g.delta}</td></tr>`).join("") ||
    `<tr><td colspan="5" style="color:var(--ink-dim)">no gambles revealed yet — flips verify the day after they land</td></tr>`;
  $("seedreveal").textContent = status === 200
    ? `yesterday's seed (${y}): ${body.seed}\nverify each flip: won == (int(sha256(seed:day:wallet),16) % 2 == 0)\ncommit check: sha256(seed) must equal that day's published gamble_seed_commit`
    : `yesterday's seed: not available yet (no gambles before today, or the day is still open)`;
}

(async () => {
  $("prevday").onclick = () => { day = utcDay(Math.round((Date.parse(day) - Date.now()) / 86400_000) - 1); renderAnswers(); };
  $("nextday").onclick = () => { day = utcDay(Math.round((Date.parse(day) - Date.now()) / 86400_000) + 1); renderAnswers(); };
  try {
    await Promise.all([renderToday(), renderAnswers(), renderLedger(), renderGambles()]);
  } catch (e) {
    $("question").textContent = "the watchtower can't reach the meter — " + e.message;
  }
})();
