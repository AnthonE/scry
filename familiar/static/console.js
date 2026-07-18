/* the familiar keep — console. Vanilla, no deps, no inline script. */
"use strict";

const $ = (id) => document.getElementById(id);
let current = null; // familiar_id open in the detail panel

async function api(path, body) {
  const opts = body ? { method: "POST", headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(body) } : {};
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || r.status);
  return data;
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = String(s == null ? "" : s);
  return d.innerHTML;
}

async function refreshHealth() {
  try {
    const h = await api("/health");
    $("healthLine").textContent =
      `mode: ${h.mode} · roster ${h.roster}/${h.cap}` +
      (h.auto_tick_minutes ? ` · auto-tick every ${h.auto_tick_minutes}m` : " · manual ticks");
  } catch (e) { $("healthLine").textContent = "keep unreachable: " + e.message; }
}

async function refreshCrew() {
  try {
    const { crew } = await api("/crew");
    const box = $("crewGrid");
    box.innerHTML = "";
    crew.forEach((c) => {
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML =
        `<div class="name">${esc(c.name)}</div>` +
        `<div class="vow">${esc(c.title)}</div>` +
        `<span class="badge">flat price</span>` +
        (c.tools || []).map((t) => `<span class="badge">${esc(t)}</span>`).join("");
      card.addEventListener("click", () => hireCrew(c.slug));
      box.appendChild(card);
    });
  } catch (e) { /* crew is optional chrome */ }
}

async function hireCrew(slug) {
  const out = $("hireOut");
  out.innerHTML = "";
  try {
    const rec = await api("/hire", { slug });
    out.innerHTML =
      `<div class="token">hired <b>${esc(rec.archetype)}</b> as ${esc(rec.familiar_id)}<br>` +
      `owner token (shown ONCE):<br><b>${esc(rec.owner_token)}</b></div>`;
    await refreshRoster();
    await refreshHealth();
  } catch (e) { out.innerHTML = `<div class="err">${esc(e.message)}</div>`; }
}

async function refreshRoster() {
  const { roster, cap } = await api("/familiars");
  const box = $("roster");
  box.innerHTML = "";
  roster.forEach((f) => {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML =
      `<div class="name">${esc(f.name)}${f.dismissed ? " · dismissed" : ""}</div>` +
      `<div class="vow">${esc(f.vow)}</div>` +
      `<span class="badge">ticks ${f.ticks}</span><span class="badge">${esc(f.brain)}</span>`;
    card.addEventListener("click", () => openDetail(f.familiar_id));
    box.appendChild(card);
  });
  $("rosterNote").textContent = roster.length
    ? `${roster.length}/${cap} slots — the record is public by design; the token only drives.`
    : "no familiars yet — summon the first (the operator's own goes first: Mithra).";
}

function evLine(e) {
  const div = document.createElement("div");
  div.className = "ev " + esc(e.kind);
  let body = "";
  if (e.kind === "born") body = `vow_id ${esc(e.vow_id)} · brain ${esc(e.brain)}`;
  else if (e.kind === "tick") body = `${esc(e.action)} — ${esc(e.say)}`;
  else if (e.kind === "augury") body = esc(e.answer);
  else if (e.kind === "reading") body = `profile ${esc(JSON.stringify(e.profile))} (unsigned demo)`;
  else if (e.kind === "report") body = `entry ${esc(JSON.stringify(e.entry))}`;
  else if (e.kind === "ward") body = `flags: ${esc((e.flags || []).join(" · "))}`;
  else if (e.kind === "error") body = `<span class="err">${esc(e.where)}: ${esc(e.detail)}</span>`;
  else body = esc(JSON.stringify(Object.fromEntries(
    Object.entries(e).filter(([k]) => !["t", "kind"].includes(k)))));
  div.innerHTML = `<span class="k">${esc(e.kind)}</span><span class="t">${esc(e.t)}</span>${body}`;
  return div;
}

async function openDetail(fid) {
  current = fid;
  const f = await api("/familiar/" + fid);
  $("detail").classList.remove("hidden");
  $("dName").textContent = f.name + (f.dismissed ? " · dismissed" : "");
  $("dVow").textContent = "vow: " + f.vow;
  $("dMeta").textContent =
    `${f.familiar_id} · vow_id ${f.vow_id} · ticks ${f.ticks} · brain ${f.brain}` +
    ` · self-read every ${f.self_read_every} · report every ${f.report_every}`;
  const feed = $("dFeed");
  feed.innerHTML = "";
  [...f.life].reverse().forEach((e) => feed.appendChild(evLine(e)));
  $("detail").scrollIntoView({ behavior: "smooth" });
}

$("btnSummon").addEventListener("click", async () => {
  const out = $("summonOut");
  out.innerHTML = "";
  try {
    const body = {
      name: $("sName").value.trim(),
      vow_text: $("sVow").value.trim(),
      self_read_every: parseInt($("sSelfRead").value, 10) || 7,
      report_every: parseInt($("sReport").value, 10) || 3,
    };
    if (!body.name || !body.vow_text) throw new Error("name and vow are both required");
    if ($("sBrainUrl").value.trim() && $("sBrainModel").value.trim()) {
      body.brain_url = $("sBrainUrl").value.trim();
      body.brain_model = $("sBrainModel").value.trim();
      body.brain_key = $("sBrainKey").value;
    }
    const rec = await api("/summon", body);
    out.innerHTML =
      `<div class="token">born: <b>${esc(rec.familiar_id)}</b> · vow ${esc(rec.vow_id)}<br>` +
      `owner token (shown ONCE, the keep stores only its hash):<br><b>${esc(rec.owner_token)}</b></div>`;
    await refreshRoster();
    await refreshHealth();
  } catch (e) { out.innerHTML = `<div class="err">${esc(e.message)}</div>`; }
});

$("btnTick").addEventListener("click", async () => {
  if (!current) return;
  const out = $("dOut");
  try {
    const r = await api(`/familiar/${current}/tick`, { owner_token: $("dToken").value });
    out.innerHTML = `<span class="ok">${esc(r.action)}</span> — ${esc(r.say)}`;
    await openDetail(current);
    await refreshRoster();
  } catch (e) { out.innerHTML = `<span class="err">${esc(e.message)}</span>`; }
});

$("btnRun").addEventListener("click", async () => {
  if (!current) return;
  const out = $("dOut");
  const goal = $("dGoal").value.trim();
  if (!goal) { out.innerHTML = `<span class="err">give it a goal first</span>`; return; }
  out.innerHTML = "running…";
  try {
    const r = await api(`/familiar/${current}/autonomy`, {
      owner_token: $("dToken").value, goal,
      max_steps: parseInt($("dSteps").value, 10) || 6,
    });
    out.innerHTML = `<span class="ok">${r.done ? "goal handled" : "budget spent"}</span> — ` +
      `${esc(r.spent)}/${esc(r.budget)} steps: ${esc(r.steps.map((s) => s.action).join(" → "))}`;
    await openDetail(current);
    await refreshRoster();
  } catch (e) { out.innerHTML = `<span class="err">${esc(e.message)}</span>`; }
});

$("btnDismiss").addEventListener("click", async () => {
  if (!current) return;
  if (!window.confirm("Dismiss this familiar? Its record freezes; the slot frees.")) return;
  const out = $("dOut");
  try {
    await api(`/familiar/${current}/direct`,
              { owner_token: $("dToken").value, dismiss: true });
    out.innerHTML = `<span class="ok">dismissed — the record stands.</span>`;
    await openDetail(current);
    await refreshRoster();
    await refreshHealth();
  } catch (e) { out.innerHTML = `<span class="err">${esc(e.message)}</span>`; }
});

refreshHealth();
refreshCrew();
refreshRoster();
