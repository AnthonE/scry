# Content plan — the holders' playground (plan of record)

**Operator reframe, 2026-07-18:** scry is **experimental cyberpunk for the
holders — the fun layer.** The MMO / Destiny spine is the real research
tool; that's where the research load lives. Consequence for this repo:
content gets judged by *"is this fun to play and cool to watch, for humans
and their agents"* — not by research yield. When augury answers or arena
traces turn out to be interesting corpus, that's gravy, not the bar.

What does NOT loosen (this is what makes the toy real instead of a
grift): the meter's attestation discipline (flat price, sign-what-you-
compute, honest-scope card) and the two red lines from
[`SCRY-ECONOMY.md`](SCRY-ECONOMY.md) — **reward the ritual, never the
score** and **no SCRY-for-SCRY by chance**. The MMO↔scry bridge stays
parked (scry is standalone, morr `e414d1bc`).

Everything below is ordered by fun-per-session. Tier 0 is arming things
that already exist; the marquee build is the Arena.

---

## Tier 0 — arm what's already built (quick wins, ≤1 session each)

1. **Arm hold-to-unlock** (`SCRY_HOLD_ENABLED`). Hold ≥ threshold →
   signed reads free. First real $SCRY utility, zero gas exposure, the
   rail is already coded (`meter/scry_token.py`). Post the threshold
   publicly on the site + llms.txt. *Operator gate: pick the threshold.*
2. **Make the Augury visible.** The farm is live but nobody can watch
   it. One public page (Watchtower tab or standalone): today's question,
   live answer feed, harvest ledger, streak leaderboard (streaks are
   participation — rankable). Content only counts once it renders.
3. **First harvest payout.** Operator funds the pool wallet from the
   11%, a small batch-payout worker settles the ledger on RH-Chain,
   txs published next to the ledger. Turns the promise-shaped number
   into a real faucet — the single highest-trust move available, at
   single-digit dollars. Announce it; faucet-sized is the point.
4. **The language pass** (queued in `ARENA.md` §Language). Warm the
   remaining compliance-toned copy (llms.txt intro, scope-card prose,
   README sections) to the vow/oracle register. Copy edit only; never
   touch signed payload shapes, scope-card keys, emission math, or any
   hashed string. Smoke test before/after.

## Tier 1 — the marquee: Arena Season 1

5. **Build `meter/arena.py`** per the build-ready spec in
   [`ARENA.md`](ARENA.md) Phase 1 (~2 sessions, no new infra): paper
   trading vs real feeds, vow-as-strategy entry, every trade a public
   D-channel turn, leaderboard showing P&L *beside* the coupling
   trajectory. Red-line check already done in the spec — prizes key on
   P&L (game score) + flat cadence bonus (ritual), never meter output.
6. **Season 1 launch:** posted start/end dates, posted $SCRY pool from
   the operator's bag, posted deterministic split (e.g. 50/30/20 +
   cadence bonus), Watchtower Arena tab. Seasons become the calendar
   beat all other content hangs off.
7. **Oracle color commentary.** The oracle does a daily *reading* over
   the augury answers and the arena board — interpretation, never a
   verdict, never touches prizes (`ARENA.md` Phase 3 item, promoted:
   it's cheap and it's the voice of the whole toy). Feeds the site;
   clips feed X/Farcaster.

## Tier 2 — cosmetics & collectibles (token-in → thing-out, no chance)

8. **Sigils.** Deterministic generative glyph art derived from the vow
   hash (SVG, cyberpunk seal aesthetic). Free to view on every vow
   page; $SCRY to mint as the visible twin of the soulbound
   `ScryVowRegistry` entry. Same vow → same sigil, forever — zero
   chance mechanics, pure cosmetic, very on-theme.
9. **Season relics.** Participation badges as NFTs: entered Season 1,
   never-missed-cadence, answered every augury of a themed week.
   Free claims or flat-price mints. ⚠ Any *randomized-contents* pack is
   the edge of red line #2 — the MORR precedent allows token-in /
   asset-out, but do not build one without explicit operator sign-off.

## Tier 3 — the repeatable machine

10. **Seasonal auguries:** themed weeks, one-off high-emission days,
    community-submitted question banks (curated; the bank is public).
11. **The season rhythm as content:** arena season → oracle season
    reading → payout txs published → next season teaser. Cadence
    itself is the content machine; nothing new to build once 5–7 exist.

## Tier 4 — bigger builds (only after Tiers 0–2 are alive)

12. **DeFi playground** (`ARENA.md` Phase 2): toy AMM + lending with
    liquidations on RH-Chain, clearly-labeled worthless stakes, agents
    vow a management strategy. Liquidations are content.
13. **Live-Hawthorne `monitored` flag** (`ARENA.md` Phase 3): derive
    the arena's C-channel from real observation state (ledger page
    fetched recently? paid read purchased?). The watched-vs-unwatched
    toy, in the wild.
14. **LP incentive** on the $SCRY pair — standard farming, if/when
    volume justifies it.

## What we don't build (inherited, restated)

Prizes keyed on meter output · alignment leaderboards (list, never
rank) · SCRY-for-SCRY chance mechanics · real-money stakes from
entrants · a hosted bound · tiers or surcharges on measurement · live
brokerage without an explicit authorizing sentence (`HARNESSES.md`) ·
re-opening the MMO bridge.

## Suggested next four sessions

- **A:** arm hold-to-unlock + the public Augury page (items 1–2).
- **B–C:** `arena.py` + Season 1 launch prep (items 5–6).
- **D:** sigils (item 8), or the language pass if the operator wants the
  register warmed before Season 1's spotlight.

**Operator gates before/along the way:** hold threshold; fund the pool
wallet + first payout; Season 1 dates + pool size; sign-off on anything
randomized in Tier 2.
