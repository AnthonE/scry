/* rails.js — page wiring for rails.html. Renders the LIVE rail list from
   /.well-known/x402.json and the meter health chip; everything else on the
   page is copy with honest seals. No invented numbers. */
"use strict";
(() => {
  const { $, fetchJSON, stat } = Deck;

  /* CAIP-2 network id → display; asset line is descriptive copy for the
     known rails (USDG on RH-Chain, USDC via CDP) — the LIVE fact is the
     network's presence in the manifest. */
  const NETS = {
    "eip155:4663": { name: "rh-chain", asset: "USDG", note: "self-hosted Permit2 facilitator" },
    "eip155:8453": { name: "base", asset: "USDC", note: "CDP facilitator · gas-sponsored" },
  };
  function railTile(net, scheme) {
    const info = NETS[net] || (String(net).startsWith("solana")
      ? { name: "solana", asset: "USDC", note: "CDP facilitator · gas-sponsored" }
      : { name: String(net), asset: "rail", note: "" });
    const el = document.createElement("div");
    el.className = "panel inst"; el.tabIndex = 0; el.dataset.cursor = "";
    el.innerHTML =
      '<div class="klabel">' + info.name + ' <span class="seal live">live</span></div>' +
      '<div class="num" style="color:var(--settle-green); font-size:20px;">' + info.asset + "</div>" +
      '<div class="sub">' + (scheme || "") + " · " + net.slice(0, 22) + "</div>" +
      '<div class="inspect">In the live 402 manifest — network <b>' + net +
      "</b>, scheme " + (scheme || "?") + ". " + info.note +
      '. Prices live on the API card, never beside meter numbers (score-blind).</div>';
    return el;
  }

  async function loadRails() {
    const grid = $("#rail-grid");
    const r = await fetchJSON("/.well-known/x402.json");
    grid.innerHTML = "";
    if (!r.ok) {
      $("#rails-seal").className = "seal"; $("#rails-seal").textContent = "unreachable from this page";
      const el = document.createElement("div");
      el.className = "panel inst";
      el.innerHTML = '<div class="klabel">rails</div><div class="num">—</div><div class="sub">manifest unreachable — see the API card</div>';
      grid.appendChild(el);
      return;
    }
    const d = r.data;
    const accepts = (d.resources || []).flatMap(x => x.accepts || []).concat(d.accepts || []);
    if (!accepts.length) {
      const el = document.createElement("div");
      el.className = "panel inst";
      el.innerHTML = '<div class="klabel">rails</div><div class="num">0</div><div class="sub">manifest loaded, no rails listed</div>';
      grid.appendChild(el);
      return;
    }
    const seen = new Map();
    accepts.forEach(a => { const n = a.network || a.chain || "?";
      if (!seen.has(n)) seen.set(n, a.scheme || ""); });
    [...seen].slice(0, 6).forEach(([n, s]) => grid.appendChild(railTile(n, s)));
  }

  async function loadHealth() {
    const r = await fetchJSON("/health");
    const chip = $("#meter-chip");
    if (r.ok) { chip.textContent = "METER UP"; chip.className = "verdict"; }
    else { chip.textContent = "METER —"; chip.className = "verdict delib"; }
  }

  document.addEventListener("DOMContentLoaded", () => { loadRails(); loadHealth(); });
})();
