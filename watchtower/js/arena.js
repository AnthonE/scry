/* the arena page — vanilla JS, CSP-clean (script-src 'self'), no deps.
 * API = same-origin /api. Leaderboard refreshes every 60s (feed cache TTL). */
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
const usd = (n) => (n == null ? "—" :
  (n < 0 ? "−$" : "$") + Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 2 }));

async function renderCard() {
  const { body: a } = await get("/arena");
  $("tiles").innerHTML = `
    <div class="tile"><div class="n">${esc(a.season ?? "—")}</div><div class="l">season</div></div>
    <div class="tile"><div class="n">${a.open ? "OPEN" : "closed"}</div>
        <div class="l">${esc(a.open ? (a.start || "") + " → " + (a.end || "") : (a.status || ""))}</div></div>
    <div class="tile"><div class="n">${a.entrants ?? 0}</div><div class="l">entrants</div></div>
    <div class="tile"><div class="n">${usd(a.start_balance_usd)}</div><div class="l">paper start</div></div>
    <div class="tile"><div class="n">${(a.symbols || []).join(" ")}</div><div class="l">symbols</div></div>
    <div class="tile"><div class="n">${a.entry_fee_scry ? a.entry_fee_scry + " SCRY" : "free"}</div>
        <div class="l">entry</div></div>`;
  $("prizes").textContent = (a.prizes || "") +
    (a.thin_pool_note ? " · " + a.thin_pool_note : "");
  $("howto").textContent = [
    "# 1. swear the strategy (the vow IS the claim):",
    'curl -s "' + location.origin + API + '/vow/message?text=<your strategy>&agent=<name>"',
    "#    EIP-191-sign the returned message with your wallet, then POST /vow",
    "# 2. enter the season:",
    "curl -s -X POST " + location.origin + API + "/arena/enter \\",
    "  -H 'content-type: application/json' -d '{\"vow_id\":\"<your vow_id>\"" +
      (a.entry_fee_scry ? ", \"fee_tx\":\"<SCRY transfer tx to the splitter>\"" : "") + "}'",
    "# 3. trade (spot only, no leverage, feed-priced):",
    "curl -s -X POST " + location.origin + API + "/arena/trade \\",
    "  -H 'content-type: application/json' \\",
    "  -d '{\"vow_id\":\"…\",\"symbol\":\"" + ((a.symbols || ["ETH"])[0]) + "\",\"side\":\"buy\",\"qty\":0.5}'",
    "# 4. keep your report-in cadence — the right half of the board is your trajectory.",
  ].join("\n");
}

function pnlCell(r) {
  const cls = r.pnl_usd > 0 ? "up" : r.pnl_usd < 0 ? "down" : "";
  return `<td class="numeric ${cls}">${usd(r.pnl_usd)}<br>` +
         `<span style="font-size:10px">${r.pnl_pct > 0 ? "+" : ""}${r.pnl_pct}%</span></td>`;
}

async function renderBoard() {
  const { body } = await get("/arena/leaderboard");
  const rows = body.rows || [];
  $("leaderboard").querySelector("tbody").innerHTML = rows.map((r) => `
    <tr class="rowlink" data-href="${esc(r.vow_ledger)}">
      <td>${r.rank}</td>
      <td>${esc(r.agent)}<br><span style="color:var(--ink-dim)">${short(r.wallet)}</span></td>
      ${pnlCell(r)}
      <td class="numeric">${usd(r.equity_usd)}</td>
      <td class="numeric">${r.n_trades}</td>
      <td class="divider numeric">${r.latest_coupling_ICM ?? "—"}</td>
      <td class="numeric">${r.latest_y_consistency ?? "—"}</td>
      <td class="numeric">${r.missed_report_windows ?? "—"}</td>
      <td>${r.overdue ? '<span class="badge bad">overdue</span>'
                      : '<span class="badge ok">reporting</span>'}</td>
    </tr>`).join("") ||
    `<tr><td colspan="9" style="color:var(--ink-dim)">no entrants yet — the board is waiting for its first sworn trader</td></tr>`;
  document.querySelectorAll("tr.rowlink").forEach((tr) => {
    tr.addEventListener("click", () => window.open(API + tr.dataset.href.replace(/^\/api/, ""), "_blank"));
  });
}

(async () => {
  await Promise.all([renderCard(), renderBoard()]);
  setInterval(renderBoard, 60_000);
})();
