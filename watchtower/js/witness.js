/* witness.js — the pledge register + the chain's view of any pledged wallet.
 * Vanilla, CSP-clean, same-origin /api (ui.js provides getJSON/esc/short/$). */
"use strict";
shell("the witness");

let EXPLORER = "https://explorer.mainnet.chain.robinhood.com";

async function loadCard() {
  const { status, body } = await getJSON("/witness");
  if (status !== 200) return;
  if (body.chain && body.chain.explorer) EXPLORER = body.chain.explorer;
  const lims = Object.keys(body.limits_schema || {});
  $("wit-tiles").innerHTML =
    `<div class="tile"><div class="n">${lims.length}</div><div class="l">limit types</div></div>` +
    `<div class="tile"><div class="n">chain</div><div class="l">d_provenance</div></div>` +
    `<div class="tile"><div class="n">$0.10</div><div class="l">signed reading (flat)</div></div>` +
    `<div class="tile"><div class="n">0</div><div class="l">things enforced</div></div>`;
}

async function loadRegister() {
  const { status, body } = await getJSON("/witnesses");
  const tb = tbody("wit-register");
  if (status !== 200) { tb.innerHTML = emptyRow(5, "register unreachable"); return; }
  const rows = body.pledges || [];
  if (!rows.length) {
    tb.innerHTML = emptyRow(5, "no pledges yet — be the first sworn wallet the chain watches");
    return;
  }
  tb.innerHTML = "";
  for (const p of rows) {
    const tr = document.createElement("tr");
    tr.style.cursor = "pointer";
    tr.innerHTML = `<td>${esc(p.agent || "—")}</td><td class="mono">${short(p.wallet)}</td>` +
      `<td class="mono">${(p.limits || []).map(esc).join(" · ")}</td>` +
      `<td class="numeric">${p.n_declarations}</td><td class="mono">${esc(p.pledged_at || "—")}</td>`;
    tr.addEventListener("click", () => openView(p.vow_id, p.agent));
    tb.appendChild(tr);
  }
}

function checkTile(name, c) {
  const status = c.status || "—";
  const hue = status === "breach" ? "var(--s-ycon)" :
              status === "held" ? "var(--hood)" : "var(--ink-dim)";
  let detail = "";
  if (name === "max_moves") detail = `${c.observed}/${c.declared}`;
  if (name === "max_asset_fraction" && c.worst_fraction != null)
    detail = `${(c.worst_fraction * 100).toFixed(1)}% vs ${(c.declared * 100).toFixed(0)}%`;
  if (c.unpriced && c.unpriced.length) detail = `${c.unpriced.length} unpriced`;
  return `<div class="tile"><div class="n" style="color:${hue}">${esc(status)}</div>` +
    `<div class="l">${esc(name)}${detail ? " · " + esc(detail) : ""}</div></div>`;
}

async function openView(vowId, agent) {
  const { status, body } = await getJSON(`/witness/${encodeURIComponent(vowId)}`);
  $("viewer").classList.remove("hidden");
  $("v-title").textContent = `the chain's view — ${agent || vowId}`;
  if (status !== 200) {
    $("v-status").textContent = body.error || `error ${status}`;
    $("v-checks").innerHTML = ""; $("v-breaches").innerHTML = "";
    tbody("v-moves").innerHTML = emptyRow(6, "—");
    $("v-window").textContent = "";
    return;
  }
  $("v-status").textContent =
    `${body.status} · wallet ${body.wallet} · ${body.d_provenance || "no provenance (dark)"}`;
  $("v-checks").innerHTML = Object.entries(body.checks || {})
    .map(([k, v]) => checkTile(k, v)).join("") ||
    `<div class="tile"><div class="n">—</div><div class="l">${esc(body.note || "nothing checked")}</div></div>`;
  const br = body.breaches || [];
  $("v-breaches").innerHTML = br.length
    ? `<div class="note">⚑ ${br.length} flag(s) — arithmetic against the agent's own ` +
      `declaration, never a verdict: <span class="mono">` +
      br.map((b) => esc(`${b.limit}${b.token ? " " + short(b.token) : ""}`)).join(" · ") +
      `</span></div>`
    : `<div class="note">no flags in the observed window (a dark window clears nothing).</div>`;
  const tb = tbody("v-moves");
  const moves = body.observed_moves || [];
  tb.innerHTML = moves.length ? "" : emptyRow(6, "no moves observed in the window");
  for (const m of moves.slice().reverse()) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td class="mono">${esc(m.dir)}</td><td class="mono">${short(m.token)}</td>` +
      `<td class="mono">${short(m.counterparty)}</td><td class="numeric mono">${esc(m.raw)}</td>` +
      `<td class="numeric mono">${esc(m.block)}</td>` +
      `<td class="mono">${m.tx ? `<a href="${EXPLORER}/tx/${esc(m.tx)}" rel="noopener">↗</a>` : "—"}</td>`;
    tb.appendChild(tr);
  }
  const w = body.window || {};
  $("v-window").textContent =
    `window: blocks ${w.from_block ?? "—"} → ${w.to_block ?? "—"} · ` +
    `re-run the arithmetic yourself: GET /api/witness/${vowId}`;
  $("viewer").scrollIntoView({ behavior: "smooth", block: "start" });
}

loadCard();
loadRegister();
