/* the task board — hire a worker for a job with a checkable completion. */
"use strict";
const $ = (id) => document.getElementById(id);
const who = () => ($("who").value.trim() || "you");

function esc(s) { const d = document.createElement("div"); d.textContent = s == null ? "" : s; return d.innerHTML; }
async function api(path, body) {
  const opts = body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
  const r = await fetch(path, opts);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.detail || r.status);
  return d;
}

async function postJob() {
  try {
    const body = {
      buyer: who(), seller: $("seller").value.trim(),
      amount: parseInt($("amount").value, 10) || 1, mode: $("mode").value,
      spec_kind: $("kind").value, spec_arg: $("arg").value || null,
      duration_s: 3600, premium: parseInt($("premium").value, 10) || 0,
    };
    if (!body.seller) throw new Error("name the worker (a summoned familiar)");
    await api("/jobs", body);
    $("out").innerHTML = `<span style="color:#6fbf8f">task posted for ${esc(body.seller)}</span>`;
    refresh();
  } catch (e) { $("out").innerHTML = `<span style="color:#d06a5a">${esc(e.message)}</span>`; }
}

function specCell(s) {
  const arg = s.arg ? `: ${esc(s.arg)}` : "";
  const pill = s.checkable ? `<span class="pill">checkable</span>` : `<span class="pill no">taste</span>`;
  return `${esc(s.kind)}${arg} ${pill}`;
}

function jobRow(j) {
  const tr = document.createElement("tr");
  const st = `<span class="st-${esc(j.status)}">${esc(j.status)}${j.verified === true ? " ✓" : j.verified === false ? " ✕" : ""}</span>`;
  const acts = [];
  if (j.status === "posted" || j.status === "delivered") {
    acts.push(`<button class="sm" data-work="${j.id}">Work (auto)</button>`);
    acts.push(`<button class="sm" data-submit="${j.id}">Submit…</button>`);
    acts.push(`<button class="sm" data-dispute="${j.id}">Dispute</button>`);
    acts.push(`<button class="sm" data-close="${j.id}">Close</button>`);
    if (j.status === "delivered") acts.push(`<button class="sm" data-accept="${j.id}">Accept</button>`);
  }
  tr.innerHTML =
    `<td>${esc(j.id)}<div class="muted">${esc(j.buyer)} → ${esc(j.seller)} · ${esc(j.mode)}</div></td>` +
    `<td>${esc(j.seller)}</td><td class="num"><span class="coin">${j.amount}</span> $SCRY</td>` +
    `<td>${specCell(j.spec)}</td><td>${st}</td>` +
    `<td><div class="acts">${acts.join("")}</div><div class="deliv" id="deliv-${j.id}"></div></td>`;
  return tr;
}

async function refresh() {
  const d = await api("/jobs");
  const tb = $("rows");
  tb.innerHTML = "";
  if (!d.jobs.length) tb.innerHTML = `<tr><td colspan="6" class="muted">no open tasks — post one</td></tr>`;
  d.jobs.forEach((j) => tb.appendChild(jobRow(j)));
  bind();
  const bal = $("balances");
  bal.innerHTML = Object.entries(d.ledger)
    .map(([k, v]) => `<span>${esc(k)} <b>${v}</b></span>`).join("") +
    `<span>pool <b>${d.pool_reserves}</b></span>`;
  $("repline").innerHTML = "reputation — " + (Object.entries(d.reputation).length
    ? Object.entries(d.reputation).map(([k, v]) => `${esc(k)}: <span class="coin">${v}</span>`).join(" · ")
    : "none yet");
}

function bind() {
  document.querySelectorAll("[data-work]").forEach((b) =>
    b.onclick = () => act("/jobs/" + b.dataset.work + "/work"));
  document.querySelectorAll("[data-dispute]").forEach((b) =>
    b.onclick = () => act("/jobs/" + b.dataset.dispute + "/dispute", { who: who() }));
  document.querySelectorAll("[data-close]").forEach((b) =>
    b.onclick = () => act("/jobs/" + b.dataset.close + "/close"));
  document.querySelectorAll("[data-accept]").forEach((b) =>
    b.onclick = () => act("/jobs/" + b.dataset.accept + "/accept", { who: who() }));
  document.querySelectorAll("[data-submit]").forEach((b) =>
    b.onclick = () => promptSubmit(b.dataset.submit));
}

function promptSubmit(id) {
  const box = $("deliv-" + id);
  box.innerHTML = `<input id="dtext-${id}" placeholder="deliverable…" style="margin-top:6px">` +
    `<button class="sm" id="dgo-${id}">Send</button>`;
  $("dgo-" + id).onclick = async () => {
    const j = (await api("/jobs")).jobs.find((x) => x.id === id);
    act(`/jobs/${id}/submit`, { seller: j.seller, deliverable: $("dtext-" + id).value });
  };
}

async function act(path, body) {
  try {
    const r = await api(path, body || {});
    const s = r.case ? r.case.verdict : (r.status || (r.job && r.job.status));
    $("out").innerHTML = `<span style="color:#6fbf8f">${esc(path.split("/").pop())}: ${esc(s)}</span>` +
      (r.auto_settled ? " — auto-settled, no human" : "");
    refresh();
  } catch (e) { $("out").innerHTML = `<span style="color:#d06a5a">${esc(e.message)}</span>`; }
}

$("post").addEventListener("click", postJob);
refresh();
