/* deck-ui.js — the ONE engine behind every Deck screen. CSP-clean, no deps.
   Provides: Deck.fetchJSON (never fakes a number), menu-window <dialog>
   manager, SNES keyboard cursor (arrows + Enter/Z confirm, Esc/X cancel),
   WebAudio SFX synth (default OFF), CRT toggle, prefs. Radio: deck-radio.js. */
"use strict";
const Deck = (() => {
  const API = "/api";
  const $ = (s, el) => (el || document).querySelector(s);
  const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
  const prefs = {
    get: (k, d) => { try { const v = localStorage.getItem("scry_" + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
    set: (k, v) => { try { localStorage.setItem("scry_" + k, JSON.stringify(v)); } catch {} },
  };

  /* ── data: live or sealed, never invented ── */
  async function fetchJSON(path, opts) {
    try {
      const r = await fetch(path.startsWith("http") ? path : API + path, opts);
      if (!r.ok) return { ok: false, status: r.status, err: (await r.text()).slice(0, 300) };
      return { ok: true, data: await r.json() };
    } catch (e) { return { ok: false, status: 0, err: String(e) }; }
  }
  const postJSON = (path, body) => fetchJSON(path, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body) });
  /* stat(el, value) — value==null renders the honest em-dash */
  function stat(el, value, digits) {
    if (typeof el === "string") el = $(el);
    if (!el) return;
    el.textContent = (value === null || value === undefined || value === "")
      ? "—" : (typeof value === "number" && digits !== undefined ? value.toFixed(digits) : String(value));
  }
  function bars(el, series, max) {
    if (typeof el === "string") el = $(el);
    if (!el) return;
    const m = max || Math.max(0.0001, ...series);
    el.innerHTML = "";
    series.forEach(v => { const i = document.createElement("i");
      i.style.height = Math.max(4, Math.round((v / m) * 100)) + "%"; el.appendChild(i); });
  }
  function verdict(el, state, label) { /* state: concord|delib|breach */
    if (typeof el === "string") el = $(el);
    if (!el) return;
    el.className = "verdict" + (state === "concord" ? "" : " " + state);
    el.textContent = label || { concord: "CONCORD", delib: "DELIBERATING", breach: "BREACH" }[state];
    if (state === "breach") sfx.breach(); else if (state === "concord") sfx.confirm();
  }

  /* ── menu windows (native <dialog class="menu-window">) ── */
  function openWindow(id) {
    const d = document.getElementById(id);
    if (!d) return; d.showModal(); sfx.confirm();
  }
  function wireWindows() {
    $$("[data-window]").forEach(b => b.addEventListener("click", e => {
      e.preventDefault(); openWindow(b.dataset.window); }));
    $$("dialog.menu-window").forEach(d => {
      d.addEventListener("cancel", () => sfx.cancel());
      $$("[data-close]", d).forEach(c => c.addEventListener("click", e => {
        e.preventDefault(); d.close(); sfx.cancel(); }));
      d.addEventListener("click", e => { if (e.target === d) { d.close(); sfx.cancel(); } });
    });
  }

  /* ── the SNES cursor: arrows walk [data-cursor], Enter/Z opens, Esc/X closes ── */
  let cursorAt = -1;
  function cursorTargets() { return $$("[data-cursor]").filter(el => el.offsetParent); }
  function cursorSet(i) {
    const t = cursorTargets(); if (!t.length) return;
    if (cursorAt >= 0 && t[cursorAt]) t[cursorAt].classList.remove("cursor-on");
    cursorAt = ((i % t.length) + t.length) % t.length;
    const el = t[cursorAt]; el.classList.add("cursor-on");
    el.focus({ preventScroll: false }); sfx.move();
  }
  function cursorStep(dx, dy) {
    const t = cursorTargets(); if (!t.length) return;
    if (cursorAt < 0) return cursorSet(0);
    const cur = t[cursorAt].getBoundingClientRect();
    let best = -1, bestScore = Infinity;
    t.forEach((el, i) => {
      if (i === cursorAt) return;
      const r = el.getBoundingClientRect();
      const ddx = (r.left + r.width / 2) - (cur.left + cur.width / 2);
      const ddy = (r.top + r.height / 2) - (cur.top + cur.height / 2);
      if (dx && Math.sign(ddx) !== dx) return;
      if (dy && Math.sign(ddy) !== dy) return;
      const score = Math.abs(ddx) * (dy ? 2.2 : 1) + Math.abs(ddy) * (dx ? 2.2 : 1);
      if (score < bestScore) { bestScore = score; best = i; }
    });
    if (best >= 0) cursorSet(best); else sfx.cancel();
  }
  function wireCursor() {
    document.addEventListener("keydown", e => {
      if (e.target.matches("input, textarea, select")) return;
      if ($$("dialog[open]").length) { if (e.key === "x" || e.key === "X") $$("dialog[open]").forEach(d => d.close()); return; }
      const k = e.key;
      if (k === "ArrowLeft") { e.preventDefault(); cursorStep(-1, 0); }
      else if (k === "ArrowRight") { e.preventDefault(); cursorStep(1, 0); }
      else if (k === "ArrowUp") { e.preventDefault(); cursorStep(0, -1); }
      else if (k === "ArrowDown") { e.preventDefault(); cursorStep(0, 1); }
      else if (k === "Enter" || k === "z" || k === "Z") {
        const t = cursorTargets()[cursorAt];
        if (t) { const w = t.dataset.window || ($("[data-window]", t) || {}).dataset?.window;
          if (w) { e.preventDefault(); openWindow(w); } else if (t.tagName === "A") t.click(); }
      }
    });
  }

  /* ── SFX: synthesized, zero assets, default OFF, master toggle persists ── */
  const sfx = (() => {
    let ctx = null, on = prefs.get("sfx", false);
    const ac = () => (ctx = ctx || new (window.AudioContext || window.webkitAudioContext)());
    function blip(freq, dur, type, gain, sweep) {
      if (!on) return;
      try {
        const a = ac(), o = a.createOscillator(), g = a.createGain();
        o.type = type || "square"; o.frequency.value = freq;
        if (sweep) o.frequency.exponentialRampToValueAtTime(sweep, a.currentTime + dur);
        g.gain.value = gain || 0.03;
        g.gain.exponentialRampToValueAtTime(0.0001, a.currentTime + dur);
        o.connect(g).connect(a.destination); o.start(); o.stop(a.currentTime + dur);
      } catch {}
    }
    return {
      get on() { return on; },
      toggle() { on = !on; prefs.set("sfx", on); if (on) blip(660, .06); return on; },
      move: () => blip(520, .045),
      confirm: () => blip(440, .09, "triangle", .04, 880),
      cancel: () => blip(300, .09, "triangle", .04, 150),
      breach: () => { blip(196, .22, "sawtooth", .05); setTimeout(() => blip(147, .3, "sawtooth", .05), 180); },
    };
  })();

  /* ── toggles: sfx / crt (both persisted, both default off) ── */
  function wireToggles() {
    const s = $("#tog-sfx"), c = $("#tog-crt");
    if (s) { s.setAttribute("aria-pressed", String(sfx.on));
      s.addEventListener("click", () => s.setAttribute("aria-pressed", String(sfx.toggle()))); }
    if (c) { const set = v => { document.body.classList.toggle("crt", v);
        c.setAttribute("aria-pressed", String(v)); prefs.set("crt", v); };
      set(prefs.get("crt", false));
      c.addEventListener("click", () => set(!document.body.classList.contains("crt"))); }
  }

  function boot() { wireWindows(); wireCursor(); wireToggles(); }
  document.addEventListener("DOMContentLoaded", boot);
  return { API, $, $$, prefs, fetchJSON, postJSON, stat, bars, verdict, openWindow, sfx };
})();
