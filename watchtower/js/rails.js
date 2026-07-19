/* rails.js — page wiring for rails.html. Renders the LIVE rail list from
   /.well-known/x402.json and the meter health chip; everything else on the
   page is copy with honest seals. No invented numbers. */
"use strict";
(() => {
  const { $, fetchJSON, stat } = Deck;

  function railTile(a) {
    const net = a.network || a.chain || "?";
    const asset = (a.extra && (a.extra.name || a.extra.assetName)) || a.asset_symbol || a.asset || "";
    const scheme = a.scheme || "";
    const payTo = (a.payTo || a.pay_to || "").slice(0, 10);
    const el = document.createElement("div");
    el.className = "panel inst"; el.tabIndex = 0; el.dataset.cursor = "";
    el.innerHTML =
      '<div class="klabel">' + net + ' <span class="seal live">live</span></div>' +
      '<div class="num" style="color:var(--settle-green); font-size:20px;">' + (String(asset).slice(0, 18) || "rail") + "</div>" +
      '<div class="sub">' + scheme + (payTo ? " · " + payTo + "…" : "") + "</div>" +
      '<div class="inspect">Straight from the live 402 manifest — network <b>' + net +
      "</b>, scheme " + (scheme || "?") +
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
    const accepts = d.accepts || (d.x402 && d.x402.accepts) || [];
    if (!accepts.length) {
      const el = document.createElement("div");
      el.className = "panel inst";
      el.innerHTML = '<div class="klabel">rails</div><div class="num">0</div><div class="sub">manifest loaded, no rails listed</div>';
      grid.appendChild(el);
      return;
    }
    accepts.slice(0, 6).forEach(a => grid.appendChild(railTile(a)));
  }

  async function loadHealth() {
    const r = await fetchJSON("/health");
    const chip = $("#meter-chip");
    if (r.ok) { chip.textContent = "METER UP"; chip.className = "verdict"; }
    else { chip.textContent = "METER —"; chip.className = "verdict delib"; }
  }

  document.addEventListener("DOMContentLoaded", () => { loadRails(); loadHealth(); });
})();
