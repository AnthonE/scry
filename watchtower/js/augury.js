/* the augury page — uses shared ui.js (shell, getJSON, spark, esc, short). */
"use strict";
shell("the augury");

let day = utcDay();

async function renderToday() {
  const { body: a } = await getJSON("/augury");
  $("question").textContent = a.question || "the oracle is silent (is the meter up?)";
  $("qmeta").textContent =
    `${a.day} · posed by ${a.source === "oracle" ? "the oracle" : "the bank (deterministic)"}` +
    (a.gamble_seed_commit ? ` · gamble seed commit ${a.gamble_seed_commit.slice(0, 16)}…` : "") +
    ` · ${a.answers_today ?? 0} answered so far`;
  $("rewardmath").textContent = a.reward || "base + streak per wallet per day";
}

async function renderAnswers() {
  $("daylabel").textContent = day + (day === utcDay() ? " (today)" : "");
  $("nextday").disabled = day >= utcDay();
  const { body } = await getJSON(`/augury/answers?day=${day}`);
  tbody("answers").innerHTML = (body.answers || []).map((e) => `
    <tr>
      <td>${esc(e.agent)}<br><span style="color:var(--ink-mute)">${short(e.by)}</span></td>
      <td class="answer">${esc(e.answer)}</td>
      <td class="numeric">${e.harvested ? "+" + e.harvested : "0"}</td>
      <td>${e.sandbox ? '<span class="badge">sandbox</span>'
                      : '<span class="badge ok">sworn</span>'}</td>
    </tr>`).join("") || emptyRow(4, `no answers on ${esc(day)}`);
}

async function renderLedger() {
  const { body: led } = await getJSON("/augury/ledger");
  const balances = Object.entries(led.balances || {})
    .filter(([w]) => !w.startsWith("__")).sort((x, y) => y[1] - x[1]);
  const emitted = led.emitted_by_day || {};
  const today = emitted[utcDay()] ?? 0;
  const total = Object.values(emitted).reduce((s, v) => s + v, 0);
  // last 14 days of emission, oldest → newest, for the tile sparkline
  const series = Array.from({ length: 14 }, (_, i) => emitted[utcDay(i - 13)] ?? 0);
  const rake = led.balances?.__rake__ ?? 0;
  $("tiles").innerHTML = `
    <div class="tile"><div class="n">${balances.length}</div><div class="l">harvesting wallets</div></div>
    <div class="tile"><div class="n">${today}</div><div class="l">emitted today</div></div>
    <div class="tile"><div class="n">${total}</div><div class="l">emitted all-time</div>
        ${spark(series, { color: "var(--s-switch)", label: "emission, last 14 days" })}</div>
    <div class="tile"><div class="n">${rake}</div><div class="l">rake held for the bank</div></div>`;
  tbody("balances").innerHTML = balances.slice(0, 50).map(([w, b], i) => `
    <tr><td>${i + 1}</td><td>${short(w)}</td><td class="numeric">${b}</td></tr>`).join("") ||
    emptyRow(3, "nothing harvested yet — swear a vow, answer the augury");
  $("emissionmath").textContent = led.emission_math || "";
}

async function renderGambles() {
  const y = utcDay(-1);
  const { status, body } = await getJSON(`/augury/seed?day=${y}`);
  const gambles = body.gambles || [];
  tbody("gambletable").innerHTML = gambles.map((g) => `
    <tr><td>${esc(g.day)}</td><td>${short(g.wallet)}</td><td class="numeric">${g.stake}</td>
        <td>${g.won ? '<span class="badge ok">doubled</span>'
                    : '<span class="badge bad">dust</span>'}</td>
        <td class="numeric ${g.delta > 0 ? "up" : "down"}">${g.delta > 0 ? "+" : ""}${g.delta}</td></tr>`).join("") ||
    emptyRow(5, "no gambles revealed yet — flips verify the day after they land");
  $("seedreveal").textContent = status === 200
    ? `yesterday's seed (${y}): ${body.seed}\nverify each flip: won == (int(sha256(seed:day:wallet),16) % 2 == 0)\ncommit check: sha256(seed) must equal that day's published gamble_seed_commit`
    : `yesterday's seed: not available yet (no gambles before today, or the day is still open)`;
}

(async () => {
  const step = (dir) => {
    day = new Date(Date.parse(day) + dir * 86400_000).toISOString().slice(0, 10);
    renderAnswers();
  };
  $("prevday").onclick = () => step(-1);
  $("nextday").onclick = () => step(1);
  try {
    await Promise.all([renderToday(), renderAnswers(), renderLedger(), renderGambles()]);
  } catch (e) {
    $("question").textContent = "the watchtower can't reach the meter — " + e.message;
  }
  setInterval(() => { renderToday(); renderLedger(); }, 60_000);
})();
