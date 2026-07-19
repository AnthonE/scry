/* deck-radio.js — the deck radio. Manifest-driven (/radio/manifest.json),
   user-initiated only (no autoplay, ever), credits rendered per track —
   see watchtower/radio/RADIO.md for the OC ReMix Terms-of-Use compliance
   rules (credit ocremix.org AND the artist; files keep names + tags).
   Depends on deck-ui.js (Deck.$, Deck.prefs, Deck.sfx). */
"use strict";
(() => {
  const { $, prefs, sfx } = Deck;
  let stations = [], si = 0, ti = 0, audio = null, playing = false;

  function creditHTML(t, st) {
    if (st.type === "stream") return `${st.name} <a href="${st.info || "#"}" target="_blank" rel="noopener">stream info</a>`;
    const via = t.via || "https://ocremix.org";
    return `${t.title} — ${t.artist} · <a href="${t.url || via}" target="_blank" rel="noopener">track</a> · <a href="${via}" target="_blank" rel="noopener">ocremix.org</a>`;
  }
  function setNow(html) { const n = $("#nowplaying"); if (n) n.innerHTML = html; }

  function srcFor() {
    const st = stations[si]; if (!st) return null;
    if (st.type === "stream") return { src: st.src, t: null, st };
    if (!st.tracks || !st.tracks.length) return null;
    ti = ti % st.tracks.length;
    return { src: st.tracks[ti].src, t: st.tracks[ti], st };
  }
  function play() {
    const cur = srcFor(); if (!cur) { setNow("no stations loaded — see RADIO.md"); return; }
    if (!audio) {
      audio = new Audio(); audio.volume = prefs.get("radio_vol", 0.45);
      audio.addEventListener("ended", () => { ti++; play(); });
      audio.addEventListener("error", () => setNow("station unreachable"));
    }
    audio.src = cur.src;
    audio.play().then(() => { playing = true; pressed(true);
      setNow(creditHTML(cur.t || {}, cur.st));
    }).catch(() => setNow("press again — browser blocked audio"));
  }
  function stop() { if (audio) audio.pause(); playing = false; pressed(false); setNow(""); }
  function pressed(v) { const b = $("#tog-radio"); if (b) b.setAttribute("aria-pressed", String(v)); }

  async function boot() {
    const b = $("#tog-radio"), nx = $("#radio-next");
    if (!b) return;
    try {
      const r = await fetch("/radio/manifest.json");
      if (r.ok) stations = ((await r.json()).stations || []).filter(s =>
        s && (s.type === "stream" ? s.src : (s.tracks || []).length));
    } catch {}
    si = Math.min(prefs.get("radio_station", 0), Math.max(0, stations.length - 1));
    if (!stations.length) { b.title = "no stations loaded — see radio/RADIO.md"; }
    b.addEventListener("click", () => { playing ? stop() : play(); sfx.confirm(); });
    if (nx) nx.addEventListener("click", () => {
      if (!stations.length) return;
      const st = stations[si];
      if (st.type === "files" && st.tracks.length > 1) { ti++; }
      else { si = (si + 1) % stations.length; ti = 0; prefs.set("radio_station", si); }
      if (playing) play(); sfx.move();
    });
  }
  document.addEventListener("DOMContentLoaded", boot);
})();
