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

// ── who am I (P1 has no wallet auth — a name stands in) ──────────────────
const who = () => ($("who").value.trim() || "you");

// ── tabs ────────────────────────────────────────────────────────────────
let tab = "browse";
function showTab(t) {
  tab = t;
  document.querySelectorAll("#tabs .tab").forEach((el) =>
    el.classList.toggle("on", el.dataset.tab === t));
  ["browse", "auctions", "bids"].forEach((p) =>
    $("panel-" + p).style.display = p === t ? "" : "none");
  if (t === "browse") refresh();
  if (t === "auctions") loadAuctions();
  if (t === "bids") loadBids();
}
document.querySelectorAll("#tabs .tab").forEach((el) =>
  el.addEventListener("click", () => showTab(el.dataset.tab)));

function closesIn(sec) {
  if (sec <= 0) return "closing";
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60);
  return h ? `${h}h ${m}m` : `${m}m`;
}

// ── auctions ──────────────────────────────────────────────────────────────
async function fillPostItems() {
  const sel = $("pItem");
  if (sel.dataset.filled) return;
  const { listings } = await api("/market");
  sel.innerHTML = "";
  listings.filter((L) => L.pricing !== "flat").forEach((L) => {
    const o = document.createElement("option");
    o.value = L.id; o.textContent = `${L.name} (${L.rarity})`;
    sel.appendChild(o);
  });
  sel.dataset.filled = "1";
}

async function loadAuctions() {
  await fillPostItems();
  const { auctions } = await api("/auctions");
  const tb = $("aucRows");
  tb.innerHTML = "";
  if (!auctions.length) tb.innerHTML = `<tr><td colspan="6" class="sub">no live auctions — post one above</td></tr>`;
  auctions.forEach((a) => {
    const mine = a.seller === who();
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td><span class="nm">${esc(a.item.name)}</span> <span class="sub">${esc(a.item.rarity || "")}</span></td>` +
      `<td>${esc(a.seller)}</td><td>${closesIn(a.closes_in)}</td>` +
      `<td class="num"><span class="coin">${a.current_bid}</span> $SCRY<div class="sub">min next ${a.min_next_bid}</div></td>` +
      `<td class="num">${a.buyout ? `<span class="coin">${a.buyout}</span> $SCRY` : "—"}</td>` +
      `<td>${mine ? '<span class="sub">yours</span>' :
        `<button class="hire" data-bid="${a.id}">Bid ${a.min_next_bid}</button>` +
        (a.buyout ? ` <button class="hire" data-buy="${a.id}">Buyout</button>` : "")}</td>`;
    tb.appendChild(tr);
  });
  tb.querySelectorAll("[data-bid]").forEach((b) =>
    b.addEventListener("click", () => bid(b.dataset.bid)));
  tb.querySelectorAll("[data-buy]").forEach((b) =>
    b.addEventListener("click", () => buyout(b.dataset.buy)));
}

$("pGo").addEventListener("click", async () => {
  try {
    const body = { seller: who(), listing_id: $("pItem").value,
      starting_bid: parseInt($("pStart").value, 10) || 1, duration: $("pDur").value };
    const bo = parseInt($("pBuy").value, 10);
    if (bo) body.buyout = bo;
    await api("/auctions", body);
    $("out").innerHTML = `<span style="color:#6fbf8f">posted — you set the price; the house takes 5% on sale</span>`;
    loadAuctions();
  } catch (e) { $("out").innerHTML = `<span style="color:#d06a5a">${esc(e.message)}</span>`; }
});

async function bid(id) {
  try {
    const a = (await api("/auctions")).auctions.find((x) => x.id === id);
    const r = await api(`/auctions/${id}/bid`, { bidder: who(), amount: a.min_next_bid });
    $("out").innerHTML = r.settled
      ? `<span style="color:#6fbf8f">won by buyout at ${r.settled.price} $SCRY</span>`
      : `<span style="color:#6fbf8f">bid ${r.current_bid} $SCRY — you lead</span>`;
    loadAuctions();
  } catch (e) { $("out").innerHTML = `<span style="color:#d06a5a">${esc(e.message)}</span>`; }
}

async function buyout(id) {
  try {
    const r = await api(`/auctions/${id}/buyout`, { bidder: who() });
    const s = r.settled;
    $("out").innerHTML = `<span style="color:#6fbf8f">bought for ${s.price} $SCRY</span> — ` +
      `seller gets ${s.seller_proceeds}, house cut ${s.house_cut}` +
      (s.summoned ? ` · summoned ${esc(s.summoned.familiar_id)}` : "");
    loadAuctions();
  } catch (e) { $("out").innerHTML = `<span style="color:#d06a5a">${esc(e.message)}</span>`; }
}

async function loadBids() {
  const { selling, bidding } = await api("/auctions/mine?who=" + encodeURIComponent(who()));
  const tb = $("bidRows");
  tb.innerHTML = "";
  const rows = [...bidding.map((a) => ({ a, role: "bid" })), ...selling.map((a) => ({ a, role: "sell" }))];
  if (!rows.length) tb.innerHTML = `<tr><td colspan="5" class="sub">nothing yet — bid or post in the Auctions tab</td></tr>`;
  rows.forEach(({ a, role }) => {
    const status = a.status !== "open" ? a.status
      : role === "sell" ? "listing" : (a.you_lead ? "leading" : "outbid");
    const cls = status === "leading" ? "lead" : status === "outbid" ? "outbid" : "";
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td><span class="nm">${esc(a.item.name)}</span></td><td>${esc(a.seller)}</td>` +
      `<td>${a.status === "open" ? closesIn(a.closes_in) : "—"}</td>` +
      `<td class="num"><span class="coin">${a.current_bid}</span> $SCRY</td>` +
      `<td class="${cls}">${status}</td>`;
    tb.appendChild(tr);
  });
}

refresh();
