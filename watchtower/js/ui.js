/* ui.js — shared shell + helpers for the scry fun-layer pages.
 * Vanilla, CSP-clean (script-src 'self'), no deps. API = same-origin /api. */
"use strict";

const API = "/api";
const $ = (id) => document.getElementById(id);

async function getJSON(path) {
  const r = await fetch(API + path);
  return { status: r.status, body: await r.json().catch(() => ({})) };
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const short = (w) => (w && w.length > 14 ? w.slice(0, 8) + "…" + w.slice(-4) : w || "—");
const usd = (n) => (n == null ? "—" :
  (n < 0 ? "−$" : "$") + Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 2 }));
const utcDay = (offset = 0) =>
  new Date(Date.now() + offset * 86400_000).toISOString().slice(0, 10);

/* The shared header: wordmark + fun-layer nav. Marks `active` current. */
function shell(active) {
  const pages = [
    ["scry-watch.html", "watchtower"],
    ["augury.html", "the augury"],
    ["arena.html", "the arena"],
    ["games.html", "the games"],
    ["playground.html", "playground"],
  ];
  const el = document.createElement("header");
  el.className = "site";
  el.innerHTML =
    '<div class="wordmark"><a href="scry-watch.html">scry<span class="sig">.</span></a></div>' +
    '<nav class="fun">' + pages.map(([href, label]) =>
      `<a href="${href}"${label === active ? ' class="active"' : ""}>${label}</a>`).join("") +
    "</nav>";
  document.body.querySelector(".wrap").prepend(el);
}

/* Sparkline: thin 2px line, last point marked, per-point <title> hover.
 * `label` feeds aria; the page must also show the numbers in a table. */
function spark(values, { color = "var(--s-coupling)", w = 120, h = 26, label = "" } = {}) {
  const vs = (values || []).filter((v) => v != null);
  if (vs.length < 2) return "";
  const lo = Math.min(...vs), hi = Math.max(...vs), span = hi - lo || 1;
  const px = (i) => (i / (vs.length - 1)) * (w - 6) + 3;
  const py = (v) => h - 4 - ((v - lo) / span) * (h - 8);
  const pts = vs.map((v, i) => `${px(i).toFixed(1)},${py(v).toFixed(1)}`).join(" ");
  const lastX = px(vs.length - 1), lastY = py(vs.at(-1));
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)}">` +
    `<title>${esc(label)}: ${vs.map((v) => +v.toFixed ? v : v).join(" → ")}</title>` +
    `<polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2" ` +
    `stroke-linecap="round" stroke-linejoin="round"/>` +
    `<circle cx="${lastX}" cy="${lastY}" r="3" fill="${color}"/></svg>`;
}

/* Two-value split bar (e.g. duel pools). Green/red carry polarity WITH the
 * numbers printed beside them — never color alone. */
function splitBar(a, b) {
  const total = (a || 0) + (b || 0);
  if (!total) return '<div class="split" aria-hidden="true"></div>';
  const pa = Math.max(4, Math.round((a / total) * 100));
  return `<div class="split" role="img" aria-label="up ${a} vs down ${b}">` +
    `<div class="a" style="width:${pa}%"></div>` +
    `<div class="b" style="flex:1"></div></div>`;
}

const tbody = (id) => $(id).querySelector("tbody");
const emptyRow = (cols, msg) =>
  `<tr><td colspan="${cols}" style="color:var(--ink-dim)">${msg}</td></tr>`;
