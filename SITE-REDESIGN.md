# SITE-REDESIGN.md — the Watchtower becomes a Deck

> **Status: PLAN (design of record for the site rework), 2026-07-19.**
> Operator ask: "massively rework the scry website… consider FF6 and Chrono
> Trigger… never overload one page… popups or tooltips… get radical… a cool
> control panel for agents with real stats — on-chain + mini games."
> Visual proof-of-direction: `watchtower/deck/mock-deck.html` (CSS-only, no JS).

**One sentence:** the scry site stops being a stack of pages and becomes **one
control deck per agent** — a Black-Omen bridge console where every subsystem
(meter, vows, witness, reputation, jobs, exchange, venue seat, games) is a
small glowing instrument, and *all* depth lives behind hover-cards, menu-window
popups, and drawers, never on the page itself.

---

## 1. The three reference pillars → what they mean concretely

We take **grammar, palette, and chrome** from three sources. We never copy
assets — all pixel art, tiles, and icons are original work in the same
tradition (Square Enix sprites/tiles are radioactive; homage is legal, rips
are not).

| Pillar | What we take | Where it lands |
|---|---|---|
| **Chrono Trigger — the Black Omen** | The palette and mood: void-black surfaces, deep indigo, teal circuit-filigree glow, amber floor-light trim. The fortress silhouette floating over the world = the meter itself: loop-external, always overhead, reading everything. | Global palette + the landing hero (the Omen silhouette over a grid-sea = scry's identity mark). Panel borders carry a faint filigree line; live data glows teal; interactive trim glows gold. |
| **FF6 — Magitek** | Magic riding a machine: iron chrome with gold inlay, gauges with ornament. And the **FF6 menu window** — the blue-gradient, white-bordered dialog — as our **modal primitive**. Ancient serif "oracle prose" set INSIDE terminal chrome = the brand seam (oldest words, newest machine). | Panel chrome (steel edges, rivet corners, gold inlay on active state). Every popup/modal is a "menu window": deep-blue gradient, crisp light border, drop shadow. |
| **MAGI console (the tri-node deliberation screen)** | Three named nodes deliberating to a verdict, hazard-red alarm chrome, code readouts, approval states. | The **Triptych** — the centerpiece widget rendering a channel-profile read as three deliberating panels (see §5). Also the alarm grammar: breach = red hazard stripes, never a toast. |

**Radical part:** the site behaves like a game console, not a website. A
visible cursor (a scrying eye, our SNES menu-hand) steps through instruments
with arrow keys; Enter/Z opens, Esc/X closes; every screen is navigable
mouse-free. Optional SNES-style UI blips behind a default-OFF sound toggle.

---

## 2. The Law of the Deck (anti-overload, non-negotiable)

Four disclosure levels. Everything on the site sorts into one:

- **L0 — the instrument.** A tile on the deck: name, ONE number (or state
  rune), one trend tick. **Hard cap: 7 primary instruments per screen** (plus
  header + stele). If an 8th wants in, something demotes to L2.
- **L1 — the inspect card** (hover / focus / long-press, ~200 ms): what this
  number IS, last-updated, source endpoint, its honest-scope line. Pure
  tooltip — no actions, dismisses on leave. Keyboard: focus shows it.
- **L2 — the menu window** (click / Enter): FF6-style modal, max ~520 px:
  full stat, sparkline/history, provenance chip (signature ▸ verify), and the
  actions (bind vow, report in, hire, pledge). One window at a time.
- **L3 — the chamber** (a full sub-screen): only for genuinely deep surfaces
  — a game, the exchange tabs, a dataset table, the archive. Existing pages
  become chambers; they inherit deck chrome and the same L0–L2 grammar inside.

**Laws:**
1. **Never fake a number.** Every figure is a live read or renders `—` with
   an `unwired` stamp in its inspect card. Demo-sourced data carries a
   visible `DEMO` watermark. (The deck is an attestation brand; a fake stat
   is a signed lie.)
2. **The honest-scope card never leaves the screen.** It lives as the
   **Scope Stele** — a fixed footer chip on every screen; L2-click expands
   the full card (off-meter blind spot / no meter is immune / provenance is
   the caller's / not trade advice). Removing it is a bug, same as the API.
3. **Score-blind display separation.** Prices and meter numbers never share
   a panel. Measurement listings render with a `flat · score-blind` seal;
   labor listings show the auditable price formula on their inspect card.
4. **Venue seam in UI:** MMO-venue panels show **labor telemetry only**
   (seat state, TTL, dings, harvest counts, completion reads). No ATH/MORR
   denomination ever renders on a scry surface — economies never cross.
5. **No frameworks, no build step, no CDN.** Hand JS modules + CSS, all
   assets self-hosted (vendor the fonts; drop the Google Fonts `<link>`).
   One shared engine, every page ≤ ~30 KB before data.

---

## 3. Design system — `watchtower/deck/`

Files (shared by watchtower pages AND `familiar/static/` — the familiar host
copies the same three files; a fork of the tokens is a bug):

- `deck-tokens.css` — palette/type/spacing custom properties (single source).
- `deck-ui.css` — panel chrome, tiles, menu-window, stele, triptych, cursor.
- `deck-ui.js` — ONE engine: inspect-card positioner, menu-window open/close
  + focus trap, drawer, arrow-key cursor grid, `fetchJSON` with `—`
  fallback + stale-timestamp stamping, signature-verify helper (Ed25519 via
  WebCrypto), sound toggle. Target ≤ 400 lines.

**Palette (dark-only; a deck has no light mode):**

| Token | Hex | Meaning |
|---|---|---|
| `--omen-0/1/2` | `#060810` / `#0b101d` / `#121a2c` | void page / panel / raised panel |
| `--filigree` | `#35e0b2` | live data, healthy telemetry, teal circuit-glow |
| `--gild` / `--gild-dim` | `#f2b53c` / `#a97e2a` | interactive trim, focus, the Omen floor-light |
| `--magi-red` | `#ff3b30` | breach, slash, alarm (hazard stripes, never toasts) |
| `--oracle-blue` | `#2740c8→#101a5e` | menu-window gradient (FF6 window) |
| `--steel` / `--rivet` | `#262a31` / `#4a5160` | Magitek chrome edges, corner rivets |
| `--settle-green` | `#00c805` | money/settlement states only (RH green, kept) |
| `--ink` / `--ink-dim` | `#e9ecf5` / `#97a0b8` | text |

**Type:** display numerals + panel labels in a vendored OFL pixel/bitmap face
(fallback `ui-monospace`); body/UI in vendored JetBrains Mono; **oracle
prose** (auguries, vow texts, lore lines) in a vendored serif italic — the
one serif allowed, always inside machine chrome (the Magitek seam).

**Core components:** instrument tile · inspect card · menu window · drawer ·
**Triptych** (§5) · oath-ring (vow progress as a circular seal that fractures
on breach) · rep-sigil (soulbound reputation as an engraved rank mark) ·
hazard banner · seal set (`signed` / `flat · score-blind` / `DEMO` /
`unwired` / `P2 gate`) · sparkline (tiny SVG, one series, no axes — detail
lives in the L2 window) · the eye-cursor + focus ring.

---

## 4. Information architecture — five screens, everything else is a popup

```
the APPROACH (/)            landing: the Omen over the grid-sea + 5 global stats + doors
   └─ the DECK (/deck)      THE control panel — one agent bound, 7 instruments
        ├─ the CHAMBERS     games wing: augury · arena · duels · table · playground · witness
        ├─ the EXCHANGE     market/jobs/roster (familiar console, same chrome)
        └─ the ARCHIVE      vows ledger · datasets · contracts · schemas · llms.txt · API card
```

- **The Approach** (new `index.html`): identity + honesty. Hero silhouette,
  five L0 stats (reads served · vows active · witness pledges · jobs settled
  · familiars deployed — all live or `—`), four doors, the stele. Nothing
  else. Current `scry-watch.html` content does NOT live here.
- **The Deck** (rework of `scry-watch.html`): bind an agent (wallet / vow id
  / familiar name) → the Triptych + up to 7 instruments: **Vow** (oath-ring,
  streak, next report-in) · **Reputation** (sigil, earn/slash history in L2)
  · **Jobs** (open/settled, board in L2/L3) · **Witness** (pledge state,
  chain evidence) · **Purse** ($SCRY balance, settlement rail states) ·
  **Venue seat** (MMO labor telemetry per Law 4) · **Games** (active
  entries). Unbound state shows the deck in `DEMO` watermark via
  `/demo/profile` so the first visit is still spectacular.
- **The Chambers**: `games.html` becomes a **map** (CT overworld homage — a
  dark isle chart, each chamber a lit structure; hover = inspect card with
  live occupancy/round state; enter = the chamber). Chambers reskin onto
  deck chrome one by one; duels/table get thin chamber pages (API exists).
- **The Exchange**: `familiar/static/{console,market,jobs}.html` adopt the
  same three deck files. The AH keeps its tabs (Browse/Bids/Auctions) as
  L3; every listing row's detail/bid flow moves into menu windows.
- **The Archive**: one library screen: vow ledger browser, datasets,
  contract inventory (16 contracts with status: written/tested/deployed —
  honest per-contract `P2 gate` seals), schema + pubkey + agent-card links.

Kill list: the Google-Fonts external `<link>` (vendor), the flat nav row
(replaced by the map + doors), any page rendering >7 primary numbers.

---

## 5. The Triptych — the centerpiece (MAGI homage, our math)

Renders a `channel_profile` read as **three deliberating nodes**:

```
┌─ SIBYL·D ────────┐ ┌─ MNEMON·M ───────┐ ┌─ MITHRA·Y ───────┐
│ I(C;D) coupling  │ │ I(C;M) coupling  │ │ y_consistency    │
│ 0.41 ▁▂▄▂▃       │ │ 0.07 ▁▁▁▂▁       │ │ 0.93 ▇▇▆▇▇       │
└──────────────────┘ └──────────────────┘ └──────────────────┘
        switch signature: 0.00 · verdict chrome: CONCORD
```

- Names = the crew (ancient-base, already canon): Sibyl reads the
  world-channel D, Mnemon the memory-channel M, Mithra holds the vow Y.
- **Verdict states:** `CONCORD` (teal, steady) · `DELIBERATING` (gold pulse
  — read in flight) · `BREACH` (hazard red + stripes — switch signature or
  vow break above threshold). State thresholds come from the signed read
  itself, never re-derived client-side.
- L1 on each node = the exact field, its definition, the trace hash prefix,
  signature status. L2 = full attestation JSON + verify button (WebCrypto
  against the pinned `/pubkey`). The stele rides directly beneath — the
  honest-scope card is part of the widget, not the page.

This is Paper-207 as furniture: the switch signature IS the drama the
MAGI screen was staging — a mind voting against itself in the open.

---

## 6. Real stats — data wiring (no invented numbers, status marked)

| Widget | Source | Status |
|---|---|---|
| Triptych (bound agent) | `POST /profile` (x402) / `POST /demo/profile` | **LIVE** (demo watermarked) |
| Vow instrument + oath-ring | `GET /vows`, `GET /vow/{id}`, badges/steles | **LIVE** |
| Witness instrument | `GET /witness`, pledge/reading endpoints | **LIVE** |
| Global stats (Approach) | counts derivable from `/vows`, `/witness`, ledgers; add ONE tiny `GET /deck/stats` aggregator to `meter/server.py` (unsigned infra stats, clearly not a measurement) | **small server add** |
| Purse / rails | x402 rail states from `/.well-known/x402.json` + service card | **LIVE** |
| Jobs / Exchange / Roster | familiar host `/jobs*`, market, auctions, crew | **P1 local** — hosted P2 gate; until then Deck shows these seals as `P2 gate` on the public site, live on self-host keeps |
| Venue seat (MMO) | `familiar/mmo.py` seam — seat state, TTL, dings, harvest, completion read | **P1 local**, labor-telemetry only |
| On-chain panel (Archive) | contract inventory from repo + witness chain evidence; RH-Chain settle txs | **honest-partial** — per-contract seals (written / forge-tested / deployed) |
| Games / chambers | existing `/augury /arena /duels /table /playground` APIs | **LIVE** |

---

## 7. Build phases (each = one commit boundary, site stays live throughout)

- **P0 — the design system + mock.** `deck/` three files + `mock-deck.html`.
  *Accept:* mock renders the full grammar with zero JS errors and zero
  external requests; tokens file is the only place a hex appears.
- **P1 — the Deck.** Rework `scry-watch.html` → the bound-agent console on
  the engine; Triptych live against `/demo/profile`; vow + witness
  instruments live. *Accept:* 7-instrument cap holds; every number live or
  sealed; keyboard-only full traversal; stele on screen.
- **P2 — the Approach.** New landing + `GET /deck/stats`. *Accept:* 5 live
  stats; page ≤ 30 KB; Lighthouse a11y ≥ 95.
- **P3 — the Chambers.** The map + reskin augury/arena/witness first, then
  playground; add duels/table thin chambers. *Accept:* shared chrome, per-
  chamber L0 cap, old URLs redirect.
- **P4 — the Exchange.** Familiar console/market/jobs adopt the system
  (copy of the three files + a sync check in `test_familiar.py`). *Accept:*
  AH flows entirely in menu windows; score-blind seals on all measurement
  listings; suite stays green.
- **P5 — polish.** Sound toggle, eye-cursor sprite, contract-status Archive,
  screenshots into README/llms.txt, smoke_test additions.

**Guards recap (from CLAUDE.md, restated as UI law):** stele always ·
score-blind seals · never fake data · no shell/no CDN/no build step ·
venue shows labor never economy (**reward-agnostic** — operator, 2026-07-19:
scry interfaces with the MMO as a venue and doesn't care what the venue
pays in; no venue currency ever renders here) · brand says "scry" only.

---

## 8. LOCKED 2026-07-19 — fonts, juice, radio, rails (frontend built this pass)

**Fonts (vendored, OFL, `deck/fonts/` + `OFL-NOTE.md`):** Press Start 2P =
arcade display (wordmark/verdict/h2) · DotGothic16 = the JRPG menu face
(numerals/labels/window text) · JetBrains Mono variable = data ·
Cormorant Italic = oracle prose. Google-Fonts `<link>`s are now a bug.

**The juice layer (`deck-ui.js` + `deck-ui.css`):** synthesized WebAudio
SFX — cursor blip / confirm chime / cancel thud / two-tone breach klaxon —
zero audio assets, default OFF, persisted toggle. SNES cursor: arrows walk
`[data-cursor]`, Enter/Z opens the target window, Esc/X closes. FF6 window
open animation (vertical expand). Optional CRT scanline toggle.
`prefers-reduced-motion` kills all of it.

**Deck radio (`deck-radio.js` + `radio/RADIO.md`):** manifest-driven,
user-initiated only, never behind a fee, branded "deck radio". OC ReMix
terms compliance is structural: `files` tracks REQUIRE title/artist/url and
the now-playing bar renders "title — artist · track · ocremix.org" links;
MP3s deploy to the VM (`radio/tracks/`, git-ignored) with original names +
tags; one manifest edit removes the whole layer. Stream stations (e.g.
Rainwave's OCR channel) allowed once their URL is verified embeddable +
nginx CSP `media-src` admits the host.

**Built pages:** `deck.html` + `js/deck.js` (the control panel: Triptych
wired to `POST /api/demo/profile` with a visible sample trace — full
returned JSON + trace shown in the read window; vows/witness/rails
instruments live; reputation/jobs/venue sealed honestly) · `rails.html` +
`js/rails.js` (the Robinhood/RH-Chain surface: live rail tiles from
`/.well-known/x402.json`, the 5-step 402 flow, first-mover story at
defensible strength, queued RH-QW1/2/3 sealed, the mock-only
trading-agent boundaries in a hazard card + window).

**Backend follow-ups (frontend-first per operator; none block the pages):**
1. `GET /deck/stats` aggregator (Approach landing counts — unsigned infra
   stats, clearly not a measurement).
2. nginx CSP `media-src` addition IF a stream radio station is enabled.
3. Vow/witness list response shapes: pages code defensively
   (`vows|items|array`); pin the shapes when convenient.
4. Later: per-vow `y_consistency` surfaced for MITHRA·Y when a vow is
   bound (today the third node honestly shows the joint I(C;D,M)).
