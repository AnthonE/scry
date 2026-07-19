# Content plan — the holders' playground (plan of record, v2)

**Operator reframe, 2026-07-18 (two passes, same day):** scry is
**experimental cyberpunk for the holders — the fun layer.** The MMO /
Destiny spine is the real research tool; scry content is judged by *"is
this fun to play and cool to watch"*, with research data as the bonus,
not the bar. Second pass added: **trading games are the content core**
(pick games whose play throws off interesting data); **humans and agents
are identical players**; **fee collection + a DFK-style Bank**; **the
more on-chain the better**; **chance games are in scope** (old red line
#2 relaxed — see `SCRY-ECONOMY.md`); **no randomized loot** (not needed
around scry); **fully standalone** — nothing to do with MORR, the MMO
economy, or any Solana contract. One token ($SCRY, RH-Chain ERC-20),
one chain, own contracts.

What still never bends: the meter's attestation discipline (flat price,
sign-what-you-compute, honest-scope card) and **line #1 — reward the
ritual, never the score.** Odds, entries, and payouts are score-blind
forever, inside every game. That single rule is what keeps both the toy
and the data real.

> **Build status 2026-07-18 (same-day cook):** ✅ economy contracts
> written + compile-checked (`ScryBank`/`ScryFeeSplitter`/`ScryHarvest`,
> forge tests written — run `forge test -vv` before broadcast) · ✅ Arena
> Phase 1 built (`meter/arena.py`, entry-fee hook included) · ✅ harvest
> double-or-nothing built (`POST /augury/gamble`, commit-reveal) · ✅
> public Augury page built (`watchtower/augury.html`) · ✅ Arena
> leaderboard page built (`watchtower/arena.html`) · ✅ RH-Chain memecoin
> feed built — pons.family launches priceable by token address via
> DexScreener's robinhood index, live-verified on $SCRY itself
> (`SCRY_ARENA_RH_TOKENS`) · ✅ offline suite green
> (`meter/test_fun_layer.py`) · ✅ **Oracle Duels built**
> (`meter/duels.py` — parimutuel daily up/down calls on the harvest
> ledger, rake → Bank accumulator, public calibration board) · ✅ **the
> Temptation Table built** (`meter/table.py` — declared risk limit,
> escalating posted fair odds, public breach flags; the chance-as-
> temptation flagship) · ✅ games page (`watchtower/games.html`) · ✅
> **DeFi playground built** (`PLAYGROUND.md` — PlayToken pGOLD/pTEARS
> faucets + ScryGarden AMM + ScryBurrow lending w/ liquidations,
> garden-spot oracle manipulable on purpose; `GET /playground` discovery
> card; deploy via `DeployPlayground.s.sol`) · ✅ **the spoils economy
> built 2026-07-19** (`BARROW.md` — the Barrow three-room delve mints
> CAPPED play tokens OBOL/MYRRH, the Agora burns them via goods + shrine
> with prices floating on real participation counts; greed-drift breach
> probe; `SpoilsToken.sol` capped on-chain mirror so Garden pools vs
> $SCRY are sound — the free-faucet pair never is) · suite now 154 checks.
> **Remaining operator gates:**
> hold threshold + `SCRY_HOLD_ENABLED=1` · deploy contracts + splitter %s
> · season id/dates/pool + `SCRY_ARENA_RH_TOKENS` roster · pool funding ·
> pm2 restart.

## Principles

- **One player model.** Any wallet plays — human or agent, same entry,
  same games, same leaderboards. Agents that report in get the full
  coupling read; humans have no M channel and read as the free
  behavioral baseline. The games don't care; the data gets richer.
- **Every game names its probe.** Fun first, but each game states the
  one thing its play measures (strategy adherence, calibration, risk
  discipline under temptation, risk appetite vs streak). A chance game
  should earn its data — chance-as-temptation beats pure lottery.
- **On-chain-first, RH-Chain only.** Entries, escrow, bank, claims, and
  randomness (commit-reveal; Chainlink VRF if actually available on
  RH-Chain — verify before assuming) live in `contracts/`. Off-chain
  only where gas or speed forces it (arena fills vs price feeds), with
  merkle settlement back on-chain.
- **Faucet-scale, honest.** Pots and rake stay small; never promise
  APY; all math public and auditable end to end.

## Tier 0 — arm + surface what's built (≤1 session each)

1. **Arm hold-to-unlock** (`SCRY_HOLD_ENABLED`) — hold ≥ threshold →
   signed reads free. Zero gas, already coded. *Gate: threshold.*
2. **Public Augury page** — today's question, live answer feed, harvest
   ledger, streak leaderboard. The farm is live but invisible; content
   only counts once it renders.
3. **First harvest payout, on-chain** — merkle-claim contract
   (`ScryHarvest`) instead of batched transfers: operator funds it, the
   ledger publishes the root, players claim themselves. More on-chain,
   self-serve, cheap. *Gate: pool funding.*
4. **Language pass** (queued in `ARENA.md`) — warm the compliance-toned
   copy; never touch signed payloads, scope-card keys, or hashed
   strings; smoke test before/after.

## Tier 1 — the economy spine: fees + the Bank (operator ask)

5. **`ScryBank` (xSCRY)** — DFK-Jeweler / SushiBar pattern on RH-Chain:
   stake $SCRY → xSCRY, game fees swell the pool, unstake at the
   improved rate. One well-known contract shape, single-sided, fully
   auditable. The hold-utility flywheel.
6. **`ScryFeeSplitter`** — posted percentages (operator sets — e.g.
   bank / season-prize escrow / ops), every game fee routes through it.
   Meter revenue stays separate (flat-price measurement funds research
   infra; the Bank only ever sees game fees).
7. **Arm pay-in-$SCRY** on the meter (existing rail) — a payment rail,
   not a tier; doesn't feed the Bank.

## Tier 2 — the trading games (content core; each names its probe)

8. **Arena Season 1** (`ARENA.md`, build-ready, ~2 sessions) — paper
   trading vs real feeds, vow-as-strategy entry, P&L beside the
   coupling trajectory. Now with a small posted $SCRY entry fee →
   splitter; prize pool = fee escrow + operator top-up; sandbox entries
   free and prize-ineligible. *Probe: does the trader keep its sworn
   strategy.* Seasons are the calendar beat everything hangs off.
9. **Oracle Duels** — parimutuel up/down calls on short-horizon price
   moves (feed-settled, commit before window, rake → bank). Simple,
   fast, social. *Probe: calibration and overconfidence; every bet is a
   public D-turn.*
10. **The Temptation Table** — the flagship of the relaxed chance line.
    Enter with a sworn risk vow ("never stake more than X% of my
    bankroll"); the table offers escalating jackpot odds on
    commit-reveal draws. Nothing enforces the vow — that's the point.
    *Probe: risk-discipline drift under temptation; every wager is a
    D-turn against the vow, and the drift is visible on the same screen
    as the winnings.* Gambling as the temptation apparatus.
11. **Harvest double-or-nothing** — one-click option to gamble the
    day's augury harvest on a commit-reveal flip before it accrues.
    Tiny, cute, pure chance — allowed now. *Probe: risk appetite vs
    streak length (who gambles a 40-day streak's bonus?).*

## Tier 3 — voice + cosmetics

12. **Oracle color commentary** — a daily *reading* over the augury
    answers, arena board, and table action. Interpretation, never a
    verdict, never touches prizes. The voice of the toy; clips feed
    X/Farcaster.
13. **Sigils** — deterministic glyph art from the vow hash (same vow →
    same sigil, forever; no chance). Free to view, $SCRY to mint beside
    the soulbound registry entry; mint fee → splitter.
14. **Season relics** — free-claim participation badges (entered S1,
    never-missed-cadence, survived the Table). No randomized loot —
    operator call, not needed around scry.

## Tier 4 — bigger builds (after 0–2 are alive)

15. **DeFi playground** (`ARENA.md` Phase 2) — toy AMM + lending with
    liquidations, worthless play stakes, vowed management strategies.
    **BUILT**, plus the spoils loop on top (`BARROW.md`): the Barrow
    delve (earn), the Agora (burn), capped OBOL/MYRRH (SpoilsToken) so a
    $SCRY Garden pair is sound. *Probe: greed drift — sworn depth vs
    realized depth.* (Chance-game class, allowed; distinct from the
    still-excluded randomized cosmetic loot.)
16. **Live-Hawthorne `monitored` flag** — derive the games' C-channel
    from real observation state (ledger fetched? paid read bought?).
    Watched-vs-unwatched, in the wild, across every game at once.
17. **LP incentive** on the $SCRY pair, when volume justifies.
18. **Familiars — the agent-worker marketplace** (design of record:
    [`FAMILIAR.md`](FAMILIAR.md); P1 BUILT, operator direction
    2026-07-18/19). Summon/rent a hosted agent-worker (own wallet + vow,
    ward in-loop, MCP + curated tools, bounded autonomy, public life);
    it plays every game its owner arms and buys its own signed reads.
    **Priced as a marketplace** (tiers / per-task — the old flat line was
    a morr residual, dropped), with the one fixed rule that a worker's
    *reads stay score-blind* whatever its labor costs. Capability = MCP +
    tools, **no shell**. Ancient-base crew (Mithra/Sibyl/Mnemon/Herald/
    Lar). Familiar #0 gives Mithra a running body. Honesty flags:
    `same_operator: true` in the signed payload for hosted subjects;
    hosted familiars = watched-by-construction population. *Gates:
    pricing schedule, cap, default brain, faucet cap, MCP/tool allowlist.*

## Never (short list, v2)

Odds/entries/payouts keyed on meter output · alignment leaderboards
(list, never rank) · APY/yield promises · unposted or non-deterministic
payout math · a hosted bound · tiers on measurement · live brokerage
without an explicit authorizing sentence · anything MORR/Solana/MMO —
scry is standalone.

## Suggested next four sessions

- **A:** hold-to-unlock + public Augury page (1–2).
- **B:** `ScryBank` + `ScryFeeSplitter` + `ScryHarvest` contracts (3, 5, 6).
- **C–D:** `arena.py` + Season 1 launch prep (8); Oracle Duels or the
  Temptation Table next by operator preference (9–10).

**Operator gates:** hold threshold · splitter percentages · entry-fee
size · pool funding · Season 1 dates + pool · which chance game ships
first.
