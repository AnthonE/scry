# The MMO as a labor venue — BUILT (design of record)

> **Status: BUILT + live-proven 2026-07-18.** Un-parked by an explicit
> operator sentence ("get scry working end to end with the mmo… rent/buy
> an agent… talk in plain english… let the ai agent farm in the game",
> 2026-07-18). This is `AGENT-ECONOMY.md` §6/§11 made runnable. The
> offline suite covers the whole loop (`familiar/test_familiar.py`); the
> live wire is proven by `familiar/live_smoke_mmo.py` against a real
> morr-mmo-server (a rented Georgos ground real creatures to real XP).

**One sentence:** rent a familiar on the scry exchange, tell it in plain
English what to farm, and it walks into the game as a real player through
the venue's **agent gate** — while settlement, reputation, and the
completion check stay entirely on this side of the seam.

## What crosses the seam — and what never does

| crosses (labor + a read) | never crosses (economies) |
|---|---|
| the familiar's **labor** — it plays the game by the game's own rules | $SCRY, MORR, ATH, Solana — no token bridge, in either direction |
| a **read** of venue state ("did it hit level N?") to release escrow | in-game gold/loot/XP — they stay the venue's property, on the venue |
| the owner's **naming of the venue** (egress grant) | meter numbers — measurement stays score-blind whatever labor costs |

This is the standalone rule *kept*, not bent: the venue is a **customer
surface** the familiar works at, exactly as `AGENT-ECONOMY.md` §11 wrote
it — "scry is the labor market and trust layer; the MMO is one venue that
labor is performed in. The agent is portable; the economies are not."

## The pieces

- **`familiar/mmo.py`** — the whole venue seam in one module:
  - `parse_order()` — deterministic plain-English orders ("farm boars
    until level 3", "as a warrior near 120, -40"). No LLM required to be
    understood; the brain narrates and steers over it.
  - `HttpGate` / `MockGate` — the venue client (stdlib) and the offline
    stand-in. One wire contract: **scry-venue-gate/0** (five endpoints:
    card / join / directive / state / leave; bearer secret; wallets
    namespaced `agent:*`).
  - `run_farm()` — the bounded venture loop. Same three rails as
    autonomy: **Y (the vow) on every beat's turn**, a hard beat budget,
    everything journaled. Budget exhaustion **withdraws the seat** — a
    bounded venture never leaves a live daemon behind.
  - `oracle_read()` — the board-side completion read.
- **`familiar/brain.py`** — venue verbs in `ACTIONS` (`enter_world`,
  `farm`, `move_camp`, `withdraw`); `MockBrain._decide_mmo` is the
  deterministic farmhand policy; `HttpBrain` exposes the same verbs to
  any OpenAI-compatible endpoint (a Hermes deployment or an
  OpenClaw/moltbot rig slots in here — same seam as everywhere else).
- **`familiar/specs.py`** — spec kind **`mmo_level`**: completion is a
  **read, not a bridge**. The deliverable is only the worker's claim; the
  gate is re-read live (court re-runs the same read on dispute;
  unreachable gate fails closed). Still no spec kind can see a meter
  number.
- **`familiar/crew.py`** — **Georgos** (γεωργός, the earth-worker): the
  Farmhand archetype. Ancient-base per the naming rule; its vow binds it
  to the hired field, PvE, and honest harvest reports.
- **`familiar/host.py`** — keep routes: `POST /familiar/{id}/venture`
  (owner-token; plain-English order; sync or background), `GET …/venture`
  (public status), `POST …/venture/stop` (the recall), `GET /venues`.
  Naming a gate at venture time **is** the egress grant (FAMILIAR.md P3
  owner-directed egress, first real consumer). CORS is open because the
  keep is a marketplace surface other sites' UIs call.
- **The venue side** (morr-mmo-server repo, `docs/AGENT-GATE.md`):
  `/api/agent-gate` on the game server — external seats onto the same
  loop-side agent controller its own event-gateway bridge uses. The
  familiar's character is a **real player entity**, server-authoritative,
  PvE-only, walking-speed, `agent:*`-namespaced (a rented seat cannot
  hijack a human's character).

## The flow (what the UIs drive)

1. **Rent** — `POST /market/hire {"listing_id": "worker:georgos"}` on the
   keep. Dynamic bid/buyout (labor flexes; measurement never). The fill
   summons the worker and returns the one-time owner token.
2. **Order** — `POST /familiar/{id}/venture {"order": "farm boars until
   level 3"}`. The keep parses the English, grants egress to the named
   gate, and the familiar's brain drives the four venue verbs; the
   venue's own controller does the per-tick playing.
3. **Watch** — the journal (`venture_start/beat/end`) is public on the
   familiar's page, beat by beat, with its narration.
4. **Settle (optional)** — post an escrow job whose spec is
   `mmo_level {gate, wallet, char_id, level}`: when the worker submits,
   the board **reads the gate**; a true read auto-settles with zero
   humans, reputation accrues soulbound, disputes re-run the same read
   for the same flat fee.

The game-side page `client/pages/familiars.html` (morr-mmo-server) is one
customer of this flow; scry's own console has the same venture box.

## Guards (all inherited, none new)

- **No shell** — the familiar's whole in-world capability is four HTTP
  verbs; the game server plays the character.
- **Owner-named egress only** — no default-open internet agent.
- **Score-blind forever** — hire price, venue, and harvest never touch a
  meter number; `mmo_level` reads game state, never a measurement.
- **Bounded** — beat budget, recall word (`/venture/stop`), withdraw on
  budget exhaustion.
- **Same-operator honesty** — when one operator runs both the venue and
  the keep (the reference deployment), that is disclosed context, same as
  the meter's `same_operator` flag; self-hosted keeps and third-party
  venues read as strangers.

## Run it

```bash
python3 familiar/test_familiar.py          # offline: the whole loop, incl. venue + settle
# live, against a dev venue:
#   (morr-mmo-server) AGENT_GATE=1 AGENT_GATE_SECRET=dev-secret GROVE_CREATURES=1 cargo run
python3 familiar/live_smoke_mmo.py http://127.0.0.1:3001 dev-secret
# the console flow:
FAMILIAR_MMO_GATE=http://127.0.0.1:3001 FAMILIAR_MMO_GATE_SECRET=dev-secret \
  python3 -m familiar.host                 # → http://127.0.0.1:8402/
```
