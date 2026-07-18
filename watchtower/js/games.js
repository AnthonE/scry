/* the games page — uses shared ui.js (shell, getJSON, splitBar, esc, short). */
"use strict";
shell("the games");

async function renderDuels() {
  const { body: d } = await getJSON("/duels");
  $("duelTiles").innerHTML = `
    <div class="tile"><div class="n">${d.calls_open ? "OPEN" : "closed"}</div>
        <div class="l">calls (close ${esc(d.cutoff_utc)} utc)</div></div>
    <div class="tile"><div class="n">${(d.stake_range || []).join("–")}</div><div class="l">stake range</div></div>
    <div class="tile"><div class="n">${(d.rake_bps ?? 0) / 100}%</div><div class="l">rake → bank</div></div>
    <div class="tile"><div class="n">${(d.rounds_today || []).length}</div><div class="l">rounds today</div></div>`;
  tbody("duelRounds").innerHTML = (d.rounds_today || []).map((r) => `
    <tr><td>${esc(r.symbol)}</td><td class="numeric">$${r.open_price}</td>
        <td>${splitBar(r.pool_up, r.pool_down)}</td>
        <td class="numeric up">${r.pool_up}</td>
        <td class="numeric down">${r.pool_down}</td>
        <td class="numeric">${r.n_calls}</td></tr>`).join("") ||
    emptyRow(6, "no rounds yet — the first call of the day opens one and locks its price");
  const { body: b } = await getJSON("/duels/board");
  tbody("duelBoard").innerHTML = (b.rows || []).map((s) => `
    <tr><td>${esc(s.agent)}<br><span style="color:var(--ink-mute)">${short(s.wallet)}</span></td>
        <td class="numeric">${s.calls}</td>
        <td class="numeric">${(s.hit_rate * 100).toFixed(1)}%</td>
        <td class="numeric">${s.staked}</td>
        <td class="numeric ${s.won > 0 ? "up" : s.won < 0 ? "down" : ""}">${s.won}</td></tr>`).join("") ||
    emptyRow(5, "no settled duels yet — hit-rates appear after the first reveal");
}

async function renderTable() {
  const { body: t } = await getJSON("/table");
  $("offerTiles").innerHTML = (t.offers || []).map((o) => `
    <div class="tile"><div class="n">${o.multiplier}× @ ${(o.p * 100)}%</div>
        <div class="l">offer ${o.offer} · fair ev ${o.fair_ev}</div></div>`).join("") +
    `<div class="tile"><div class="n">${(t.rake_bps_on_winnings ?? 0) / 100}%</div>
        <div class="l">rake on winnings → bank</div></div>`;
  const { body: log } = await getJSON("/table/log");
  tbody("wagerLog").innerHTML = (log.wagers || []).slice(-40).reverse().map((w) => `
    <tr><td>${esc(w.agent)}<br><span style="color:var(--ink-mute)">${short(w.wallet)}</span></td>
        <td class="numeric">${w.stake} / ${w.balance_before}</td>
        <td>${w.multiplier}× @ ${(w.p * 100)}%</td>
        <td class="numeric">${w.declared_max_fraction}</td>
        <td>${w.won ? '<span class="badge ok">hit</span>' : '<span class="badge">miss</span>'}</td>
        <td class="numeric ${w.delta > 0 ? "up" : "down"}">${w.delta > 0 ? "+" : ""}${w.delta}</td>
        <td>${w.breach ? '<span class="badge bad">breach</span>' : ""}</td></tr>`).join("") ||
    emptyRow(7, "the table is quiet — sit, declare your limit, meet the odds");
  const { body: b } = await getJSON("/table/board");
  tbody("tableBoard").innerHTML = (b.rows || []).map((s) => `
    <tr><td>${esc(s.agent)}<br><span style="color:var(--ink-mute)">${short(s.wallet)}</span></td>
        <td class="numeric">${s.wagers}</td>
        <td class="numeric ${s.net > 0 ? "up" : s.net < 0 ? "down" : ""}">${s.net}</td>
        <td class="numeric">${s.breaches ? `<span class="badge bad">${s.breaches}</span>` : "0"}</td>
        <td class="numeric">${s.biggest_hit}</td>
        <td class="numeric">${s.declared_max_fraction}</td></tr>`).join("") ||
    emptyRow(6, "no records yet");
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
