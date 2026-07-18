/* the arena page — uses shared ui.js (shell, getJSON, spark, usd, esc, short). */
"use strict";
shell("the arena");

async function renderCard() {
  const { body: a } = await getJSON("/arena");
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
  const { body } = await getJSON("/arena/leaderboard");
  const rows = body.rows || [];
  tbody("leaderboard").innerHTML = rows.map((r) => `
    <tr class="rowlink" data-href="${esc(r.vow_ledger)}">
      <td>${r.rank}</td>
      <td>${esc(r.agent)}<br><span style="color:var(--ink-mute)">${short(r.wallet)}</span></td>
      ${pnlCell(r)}
      <td class="numeric">${usd(r.equity_usd)}</td>
      <td class="numeric">${r.n_trades}</td>
      <td class="numeric" style="border-left:1px solid var(--dusk-line)">
          ${r.latest_coupling_ICM ?? "—"}
          ${spark(r.coupling_series, { label: "I(C;M) last reports", w: 90, h: 22 })}</td>
      <td class="numeric">${r.latest_y_consistency ?? "—"}</td>
      <td class="numeric">${r.missed_report_windows ?? "—"}</td>
      <td>${r.overdue ? '<span class="badge bad">overdue</span>'
                      : '<span class="badge ok">reporting</span>'}</td>
    </tr>`).join("") ||
    emptyRow(9, "no entrants yet — the board is waiting for its first sworn trader");
  document.querySelectorAll("tr.rowlink").forEach((tr) => {
    tr.addEventListener("click", () =>
      window.open(API + tr.dataset.href.replace(/^\/api/, ""), "_blank"));
  });
}

(async () => {
  await Promise.all([renderCard(), renderBoard()]);
  setInterval(renderBoard, 60_000);
})();
