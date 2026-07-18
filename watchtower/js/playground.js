/* the playground page — uses shared ui.js (shell, getJSON, esc, short). */
"use strict";
shell("playground");

const PIECES = [
  ["pGOLD", "free faucet play token — collateral"],
  ["pTEARS", "free faucet play token — the borrowable one"],
  ["garden", "constant-product AMM, 0.3% fee to SEED LPs; spotPrice() is a raw reserve ratio"],
  ["burrow", "deposit pGOLD, borrow pTEARS: 60% LTV, liquidatable past 75%, +10% bonus, oracle = the garden"],
];

(async () => {
  const { body: p } = await getJSON("/playground");
  const deployed = !!p.deployed;
  $("tiles").innerHTML = `
    <div class="tile"><div class="n">${deployed ? "DEPLOYED" : "not yet"}</div>
        <div class="l">${deployed ? "robinhood chain" : esc(p.status || "awaiting broadcast")}</div></div>
    <div class="tile"><div class="n">1000/day</div><div class="l">faucet drip per token</div></div>
    <div class="tile"><div class="n">60% → 75%</div><div class="l">borrow ltv → liquidation</div></div>
    <div class="tile"><div class="n">0.3%</div><div class="l">garden fee to LPs</div></div>`;
  tbody("contracts").innerHTML = PIECES.map(([key, what]) => `
    <tr><td>${esc(key)}</td><td class="prose">${esc(what)}</td>
        <td>${p.contracts?.[key]
          ? `<span class="seal">${esc(p.contracts[key])}</span>`
          : '<span class="badge warn">pending deploy</span>'}</td></tr>`).join("");
  $("thegame").textContent = p.the_game || "";
  if (p.warning) $("warning").textContent = p.warning;
  const t = p.turn_recipe || {};
  $("recipe").textContent = [
    "# the turn each on-chain action becomes (fold into POST /vow/report):",
    JSON.stringify({ Y: t.Y, D: t.D, context: t.context }, null, 2),
    "",
    "# " + (t.note || ""),
  ].join("\n");
})();
