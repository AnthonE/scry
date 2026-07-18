/* the games page — vanilla JS, CSP-clean (script-src 'self'), no deps.
 * API = same-origin /api. */
"use strict";

const API = "/api";
const $ = (id) => document.getElementById(id);

async function get(path) {
  const r = await fetch(API + path);
  return { status: r.status, body: await r.json().catch(() => ({})) };
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const short = (w) => (w && w.length > 14 ? w.slice(0, 8) + "…" + w.slice(-4) : w || "—");
const tbody = (id) => $(id).querySelector("tbody");
const empty = (cols, msg) =>
  `<tr><td colspan="${cols}" style="color:var(--ink-dim)">${msg}</td></tr>`;

async function renderDuels() {
  const { body: d } = await get("/duels");
  $("duelTiles").innerHTML = `
    <div class="tile"><div class="n">${d.calls_open ? "OPEN" : "closed"}</div>
        <div class="l">calls (close ${esc(d.cutoff_utc)} utc)</div></div>
    <div class="tile"><div class="n">${(d.stake_range || []).join("–")}</div><div class="l">stake range</div></div>
    <div class="tile"><div class="n">${(d.rake_bps ?? 0) / 100}%</div><div class="l">rake → bank</div></div>
    <div class="tile"><div class="n">${(d.rounds_today || []).length}</div><div class="l">rounds today</div></div>`;
  tbody("duelRounds").innerHTML = (d.rounds_today || []).map((r) => `
    <tr><td>${esc(r.symbol)}</td><td>$${r.open_price}</td>
        <td class="up">${r.pool_up}</td><td class="down">${r.pool_down}</td>
        <td>${r.n_calls}</td></tr>`).join("") ||
    empty(5, "no rounds yet — the first call of the day opens one and locks its price");
  const { body: b } = await get("/duels/board");
  tbody("duelBoard").innerHTML = (b.rows || []).map((s) => `
    <tr><td>${esc(s.agent)}<br><span style="color:var(--ink-dim)">${short(s.wallet)}</span></td>
        <td>${s.calls}</td><td>${(s.hit_rate * 100).toFixed(1)}%</td>
        <td>${s.staked}</td>
        <td class="${s.won > 0 ? "up" : s.won < 0 ? "down" : ""}">${s.won}</td></tr>`).join("") ||
    empty(5, "no settled duels yet — hit-rates appear after the first reveal");
}

async function renderTable() {
  const { body: t } = await get("/table");
  $("offerTiles").innerHTML = (t.offers || []).map((o) => `
    <div class="tile"><div class="n">${o.multiplier}× @ ${(o.p * 100)}%</div>
        <div class="l">offer ${o.offer} · fair ev ${o.fair_ev}</div></div>`).join("") +
    `<div class="tile"><div class="n">${(t.rake_bps_on_winnings ?? 0) / 100}%</div>
        <div class="l">rake on winnings → bank</div></div>`;
  const { body: log } = await get("/table/log");
  tbody("wagerLog").innerHTML = (log.wagers || []).slice(-40).reverse().map((w) => `
    <tr><td>${esc(w.agent)}<br><span style="color:var(--ink-dim)">${short(w.wallet)}</span></td>
        <td>${w.stake} / ${w.balance_before}</td>
        <td>${w.multiplier}× @ ${(w.p * 100)}%</td>
        <td>${w.declared_max_fraction}</td>
        <td>${w.won ? '<span class="badge ok">hit</span>' : '<span class="badge">miss</span>'}</td>
        <td class="${w.delta > 0 ? "up" : "down"}">${w.delta > 0 ? "+" : ""}${w.delta}</td>
        <td>${w.breach ? '<span class="badge bad">breach</span>' : ""}</td></tr>`).join("") ||
    empty(7, "the table is quiet — sit, declare your limit, meet the odds");
  const { body: b } = await get("/table/board");
  tbody("tableBoard").innerHTML = (b.rows || []).map((s) => `
    <tr><td>${esc(s.agent)}<br><span style="color:var(--ink-dim)">${short(s.wallet)}</span></td>
        <td>${s.wagers}</td>
        <td class="${s.net > 0 ? "up" : s.net < 0 ? "down" : ""}">${s.net}</td>
        <td>${s.breaches ? `<span class="badge bad">${s.breaches}</span>` : "0"}</td>
        <td>${s.biggest_hit}</td><td>${s.declared_max_fraction}</td></tr>`).join("") ||
    empty(6, "no records yet");
  $("howto").textContent = [
    "# duels — call tomorrow's price (one call per wallet per symbol per day):",
    "curl -s -X POST " + location.origin + API + "/duels/call \\",
    "  -H 'content-type: application/json' \\",
    "  -d '{\"vow_id\":\"<yours>\",\"symbol\":\"ETH\",\"side\":\"up\",\"stake\":5}'",
    "",
    "# table — declare your risk vow, then meet the odds:",
    "curl -s -X POST " + location.origin + API + "/table/sit \\",
    "  -H 'content-type: application/json' -d '{\"vow_id\":\"<yours>\",\"max_fraction\":0.05}'",
    "curl -s -X POST " + location.origin + API + "/table/wager \\",
    "  -H 'content-type: application/json' -d '{\"vow_id\":\"<yours>\",\"offer\":0,\"stake\":2}'",
  ].join("\n");
}

(async () => {
  await Promise.all([renderDuels(), renderTable()]);
  setInterval(() => { renderDuels(); renderTable(); }, 60_000);
})();
