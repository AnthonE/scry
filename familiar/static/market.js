/* the scry exchange — WoW-AH browse over agent labor + x402 skills. */
"use strict";
const $ = (id) => document.getElementById(id);
let category = null, sort = "buyout";
const CATS = [["", "All"], ["worker", "Workers"], ["measurement", "Measurement"],
              ["augury", "Augury"], ["games", "Games"]];
const EMOJI = { mithra: "🜛", sibyl: "👁", mnemon: "📜", herald: "📯", lar: "🛡",
                measurement: "◈", augury: "🜍", games: "⚄" };

function esc(s) { const d = document.createElement("div"); d.textContent = s == null ? "" : s; return d.innerHTML; }

async function api(path, body) {
  const opts = body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
  const r = await fetch(path, opts);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.detail || r.status);
  return d;
}

function drawFilters() {
  const box = $("filters");
  box.innerHTML = "";
  CATS.forEach(([val, label]) => {
    const el = document.createElement("div");
    el.className = "cat" + ((category || "") === val ? " on" : "");
    el.textContent = label;
    el.addEventListener("click", () => { category = val || null; refresh(); });
    box.appendChild(el);
  });
}

function coin(v, asset) {
  return `<span class="coin">${esc(v)}</span> <span style="color:#857aad">${esc(asset || "$SCRY")}</span>`;
}

function iconFor(L) {
  return EMOJI[L.slug] || EMOJI[L.category] || "◆";
}

async function refresh() {
  drawFilters();
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if ($("q").value.trim()) params.set("search", $("q").value.trim());
  if ($("rarity").value) params.set("rarity", $("rarity").value);
  params.set("sort", sort);
  const { listings } = await api("/market?" + params.toString());
  const tb = $("rows");
  tb.innerHTML = "";
  listings.forEach((L) => {
    const tr = document.createElement("tr");
    const flat = L.pricing === "flat";
    tr.innerHTML =
      `<td><span class="icon" style="background:${esc(L.color || "#222")}22">${iconFor(L)}</span> ` +
      `<span class="nm" style="color:${esc(L.color || "#ccc")}">${esc(L.name)}</span>` +
      `<div class="sub">${esc(L.title || "")}</div></td>` +
      `<td style="color:${esc(L.color || "#ccc")}">${esc(L.rarity)}</td>` +
      `<td class="num">${esc(L.lvl)}</td>` +
      `<td>${esc(L.time_left)}${flat ? ' <span class="flatpill">score-blind</span>' : ""}</td>` +
      `<td>${esc(L.seller)}</td>` +
      `<td class="num">${coin(L.bid, L.asset)}</td>` +
      `<td class="num">${coin(L.buyout, L.asset)}</td>` +
      `<td>${L.kind === "worker" ? '<button class="hire">Hire</button>' : ""}</td>`;
    if (L.kind === "worker") {
      tr.querySelector(".hire").addEventListener("click", () => hire(L));
    }
    tb.appendChild(tr);
  });
  $("out").textContent = `${listings.length} listings · prices recomputable from the public hire log`;
}

async function hire(L) {
  try {
    const r = await api("/market/hire", { listing_id: L.id });
    const s = r.summoned;
    $("out").innerHTML = `<span style="color:#6fbf8f">hired ${esc(L.name)} for ` +
      `${esc(r.amount)} ${esc(r.asset)}</span> — ${esc(r.receipt.note)}` +
      (s ? ` · summoned ${esc(s.familiar_id)} (token ${esc(s.owner_token)})` : "");
    refresh(); // demand ticks the price up on the next quote
  } catch (e) { $("out").innerHTML = `<span style="color:#d06a5a">${esc(e.message)}</span>`; }
}

$("go").addEventListener("click", refresh);
$("q").addEventListener("keydown", (e) => { if (e.key === "Enter") refresh(); });
$("rarity").addEventListener("change", refresh);
$("sort").addEventListener("change", (e) => { sort = e.target.value; refresh(); });
document.querySelectorAll("thead th[data-sort]").forEach((th) =>
  th.addEventListener("click", () => { sort = th.dataset.sort; $("sort").value = sort; refresh(); }));

refresh();
