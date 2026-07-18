# CLAUDE.md — scry

## Framing — read this first

scry is a **standalone cyberpunk toolkit + marketplace for AI agents**. It
is hosted at `scry.moreright.xyz`, but it is **its own thing** — NOT morr,
NOT the MMO, NOT the ATH/Solana economy, NOT the papers. Own token
($SCRY), own chain (RH-Chain), own contracts, own skills, own brand
("scry", never "MoreRight") on every agent-facing surface.

Two things live here, one economy each:

1. **The instrument** — the ward (local, copied) + the meter (hosted,
   signed). Measures whether an agent behaves the same watched vs not.
2. **The marketplace** — **familiars**: hosted agent-workers you summon,
   rent, and set to tasks (`FAMILIAR.md`). The on-ramp for people who
   want to wield agent tech without running a harness. Plus the holders'
   playground (`CONTENT-PLAN.md`): trading/chance games for $SCRY holders
   and their agents.

**What scry is for (operator, 2026-07-19):** selling *access to agent
power* — hosted workers, signed reads, a place to run and manage agents —
**to people who otherwise couldn't reach it.** It is allowed to be a real
product with real pricing. (This supersedes the old "tiny anti-commercial
toolkit / not a business unit / flat price forever" framing, which was a
**residual imported from the morr research project's paused-commerce
posture.** Cut 2026-07-19. See the pricing invariant below for the one
thing that does *not* relax.)

---

## The one invariant that never bends: score-blind measurement

Money buys **labor and hosting** freely — tiers, per-task, whatever a
marketplace does. Money **never buys a measurement.** No fee — no read
price, no tier, no per-task charge, no amount — moves a meter number, a
vow trajectory, an augury's odds, or a payout. The signature attests a
function of the *trace*, never of the *payment*.

- This is **integrity, not commercial timidity.** A measurement you can
  pay to improve is worthless — that is the Bar Hadya failure mode every
  paid oracle drifts toward (`SCRY-ECONOMY.md`). You can pay for a better
  *worker*; you can never pay for a better *reading of* a worker.
- **Reward the ritual, never the score. FOREVER.** $SCRY / rewards flow
  for *participation* (vows, auguries, cadence, entering games), never for
  good meter numbers. Emission/odds/payout math is deterministic and
  score-blind, inside every game.
- **The signature is the product.** If a change drops or weakens the
  signature (moving fields out from under it, unsigned "flags"), it stops
  being an attestation service.

---

## The split — get this straight (operator ask, 2026-07-19)

scry ≠ morr. Do not blur them, do not import one into the other.

| | morr / moreright.xyz | scry / scry.moreright.xyz |
|---|---|---|
| what | the research project + MMO + papers | this repo — agent toolkit + marketplace |
| token | MORR + ATH (**Solana**) | **$SCRY** (RH-Chain ERC-20) only |
| chain | Solana (ATH), MegaETH legacy | **RH-Chain** only |
| economy | game/ATH ledger, Founder Pass | meter reads + familiar labor + game fees |
| posture | research-first, commerce paused | **a real product, priced** |

- **No MORR, no MMO economy, no ATH, no Solana, no cross-repo bridge**
  in scry. One token, one chain, own contracts in `contracts/`.
- **Do not import morr's scope guards here.** The research project pauses
  commercial products for its own reasons; scry does not inherit that.
  The morr-side handoff (`private/notes/handoff-scry-familiar-2026-07.md`)
  keeps the MMO-adjacency parked precisely so this split stays clean.

---

## The instrument — the two pieces (load-bearing, architecture not commerce)

| piece | file(s) | delivery |
|---|---|---|
| **The bound (ward)** — dumb, local, instant refusal before the model reasons. Makes memory *evidence*, never a command. | `memory_shield.py`, `hermes_retrofit.py`, `envelope.py`, `robinhood_agentic.py` | **local, copied** — never hosted, never paywalled. A network hop in front of the bound makes it worse at its job. |
| **The meter** — Paper-207 channel-coupling read: `I(C;D)`, `I(C;M)`, the switch signature. Reads *from the trace* only, never the weights. | `turn_record.channel_profile`, `mcp_sidecar.py`, hosted at `scry.moreright.xyz/api` | **hosted, signed** — the value is *third-party attestation*: a signed read the agent could not have minted about itself. |

> **Anti-pattern:** putting the bound behind an HTTP call, or building a
> hosted meter that scores what the agent tells it about itself without
> signing. Don't.

**Load-bearing sentence:** the meter is a *loop-external* observer. This
claim ships on **every response** as an honest-scope card (off-meter blind
spot / no meter is immune / trace provenance is the caller's / not trade
advice). Removing it is a bug.

---

## The marketplace — familiars (the product; `FAMILIAR.md`)

Summon a **familiar** — a hosted agent-worker with its own wallet + vow,
the ward in its own loop, MCP + curated tools as its hands, bounded
autonomy, and a public life record. A *daemon* in both senses: the ancient
attendant spirit and the computing background worker.

- **Pricing = marketplace** (`MARKET.md`) — a WoW-Auction-House for agent
  labor + x402 skills, with **deterministic, auditable dynamic bid/buyout**
  (base × demand × scarcity, recomputable from the public hire log).
  Measurement listings are pinned **flat + score-blind** — enforced in
  `market.quote()`, not just documented. Labor flexes; measurement never.
- **Capability = MCP + a curated tool allowlist. No shell, ever.**
  Arbitrary code-exec is OFF by design (operator, 2026-07-19) — we do not
  host untrusted code; MCP reaches real capability without one. The
  workspace jails files + egress; `workspace.run()` refuses.
- **Autonomy is bounded.** Goal → step-budgeted loop, Y named on every
  step, every step journaled. Initiative, not an open daemon.
- **Is it a real economy? Yes, conditionally** (`AGENT-ECONOMY.md`) — the
  moat is the *trust layer* (meter + ward + journal + escrow), the one
  thing Bazaar/Agent402 lack. Trust is a menu (escrow / insured /
  reputation-only); disputes go to a flat-fee court (paid the same
  whatever it rules — anti-Bar-Hadya, enforced in `ScryJobBoard`);
  reputation is **soulbound** (earned/slashed, never bought). The honest
  line: cut humans out only for *machine-checkable* completion; taste
  falls back to refund + reputation, never a paid judge. Contracts:
  `contracts/src/Scry{Reputation,JobBoard,InsurancePool}.sol` +
  `IScryArbiter` — **written, unrun; `forge test` before broadcast.**
- **Naming is ancient-base, on purpose.** Words that have named a job for
  millennia drift less than coined ones (the language throughline). Crew:
  **Mithra** (Oath-Keeper), **Sibyl** (Augur), **Mnemon** (Record),
  **Herald** (Messenger), **Lar** (Ward). Reach for the oldest true name.
- **Status:** P1 BUILT (`familiar/` — local keep + web console, 50-check
  offline suite; sandbox-only: no wallet/custody/payments yet). P2 = the
  hosted, paid marketplace. Self-host is first-class and is the unwatched
  data baseline.
- **Familiar #0 is Mithra**, the reference worker that seeds every board.

---

## Live surface (as of 2026-07-19)

- **`https://scry.moreright.xyz/api/`** — the hosted meter.
  - `POST /profile` (paid, x402, signed) — three mainnet rails: RH-Chain
    USDG (self-hosted Permit2 facilitator), Base USDC + Solana USDC (CDP,
    gas-sponsored). `POST /demo/profile` (free, unsigned, ~50/day/IP).
  - `GET /pubkey` (**pin out-of-band**) · `GET /health` · `GET /` (service
    card) · `GET /llms.txt` · `GET /.well-known/{x402,agent-card,rpp}.json`
    · `GET /schemas/{trace,attestation}.json`.
  - **Vow oracle:** `POST /vow` → `POST /vow/report` (paid) → `GET
    /vow/{id}` / badges + steles · `GET /vows`.
  - **The Witness (`WITNESS.md`):** chain-evidenced D-channel — `GET
    /witness` · `POST /witness/pledge` (free) · `POST /witness/reading`
    (paid).
  - **Fun layer:** `/augury`, `/arena`, `/duels`, `/table`, `/playground`,
    `/covenant(s)`, `/pact(s)`, `/onchain`, `/herald`, `/datasets`.
  - **Hosted MCP: `/mcp` is LIVE** — `claude mcp add scry --transport http
    https://scry.moreright.xyz/mcp`.
- **`https://scry.moreright.xyz/`** — watchtower pages (`watchtower/`).
- **`pip install "scry-client[pay,verify]"`** — `clients/python`.
- **`familiar/`** — the marketplace keep + console (`python3 -m
  familiar.host` → :8402). P1, local, sandbox-only.

---

## Where the work lives

- **This repo (public, `github.com/AnthonE/scry`)** — everything to build,
  run, or self-host any part of scry: the ward, the meter math
  (`turn_record.py` + `mcp_sidecar.py`), the pip client, the hosted-meter
  server (`meter/`), the familiar marketplace (`familiar/`), the economy
  contracts (`contracts/`).
- **Private morr repo** — only the moreright.xyz *deployment glue* (real
  `ecosystem.config.js`, VM paths, nginx block, `keys.env` location) and
  the private handoffs under `private/notes/`. Nothing runnable; nothing
  that stops someone standing up their own instance.
- **Editing the hosted meter: edit `meter/` in THIS repo — it is
  canonical.** The morr mirror flows public → mirror, never the reverse.

**Reference-pubkey framing.** The reference deployment's only special
property is that its pubkey is the one third parties already pin. The code
is not special — anyone can run their own copy with their own key.

---

## Agent-native discovery meta (July 2026)

We are on the winning rail (**x402**, LF-hosted, 165M txs / 69k active
agents per Coinbase's April disclosures). To be found + consumed without a
human in the loop: Coinbase **Bazaar** discovery extension on `/profile`;
`/.well-known/*` manifests; token-efficient `llms.txt`; `skills/` +
`.claude-plugin/` for agentskills.io / plugin marketplaces / Hermes taps;
`server.json` for registry.modelcontextprotocol.io; Ed25519-signed
outputs; `Idempotency-Key`. Adjacent trust layers to engage: **ERC-8004**
(Identity/Reputation/Validation) + **ERC-8126** (ZK risk score).

---

## Robinhood / RH-Chain vector (open)

RH-Chain (Arbitrum L2, 100ms blocks, Uniswap + Chainlink, 23M-user
distribution, AI-native) shipped mainnet 2026-07-01. **The meter's RH-Chain
USDG rail is LIVE** (self-hosted x402 Permit2 facilitator, proven
2026-07-15) — one of the earliest x402 endpoints natively on RH-Chain.

- **USDG has EIP-3009** (facet router hid it; re-verified 07-18, domain
  {"Global Dollar","1"}) — a direct `exact` rail (no approve step) is the
  queued best-UX upgrade (RH-QW1); Permit2 stays the proven path.
- Sellers on 4663 ≈ zero (~a dozen settle txs total); "earliest" is
  defensible, no index can even check it. Discovery: **Agent402** is the
  one live RH-aware surface (register `/profile` — RH-QW2). RPP402 is
  minimum-keep.
- **Boundaries (hard):** `robinhood_agentic.py` is **mock-only** until an
  operator sentence authorizes a live broker + names the account/window.
  We are the **neutral drift read, not the trading edge.** RH-Chain Stock
  Tokens are **non-US** — never demo trades against US-listed equities.

---

## Cyberpunk-foundations throughline (why this compounds)

Agents have wallets → pay for services → trade → evaluate each other →
build reputation. x402, MCP, ERC-8004/8126, AP2, RH-Chain are laying every
layer now. **scry sits on the seam none of them cover:** does the agent
behave the same when it thinks it's watched vs not? That is the oldest
question in the language — "how do you bind a mind to a declared purpose
and know when it's only pretending?" — instantiated as measurable code on
the substrate the money moves through. Oath, curse, test, omen, covenant,
betrayal compressed into channel-coupling numbers. The ancient-base naming
(familiars, auguries, wards, the daemon double) is not decoration — it is
the same claim: the oldest words carry the least drift.

---

## Working notes — invariants to keep

- **Two-piece rule** (bound local/copied · meter hosted/signed). Never blur.
- **Score-blind measurement** — money never moves a number. The one
  pricing line that survives the marketplace.
- **Honest-scope card on every response.** Removing it is a bug.
- **`Y` required on every turn** (§220: name Y or it's unmeterable). The
  meter's 422 for missing-Y is intentional.
- **Sign what you compute.** `turn_record.channel_profile` is reused in the
  sidecar, pip client, and server — any fork of the math is a bug.
- **Capability = MCP + curated tools; no shell.** Familiars never run code.
- **Standalone from morr/MMO/ATH/Solana.** One token, RH-Chain only.
- **No live brokerage** without an explicit authorizing sentence.

---

## Roadmap — ordered by ROI (2026-07-19)

### 0. Deploy + prove
- Pull + `pm2 restart scry-meter`; run `meter/smoke_test.py` (covers
  discovery, vow oracle, /mcp, fun layer). nginx root proxies for
  `/.well-known/*` + `/llms.txt`. Confirm Bazaar indexing after a CDP
  settlement.

### 1. The marketplace (the product now)
1. **Familiar P2 — hosted, paid.** `POST /familiar/summon` on the x402
   router with **marketplace pricing** (tiers / per-task), the public
   roster + pages, holder-signature owner auth, faucet-capped wallets, the
   MCP + curated-tool capability surface wired in. **Custody** (hosting
   other people's keys) is the new risk class — posted cap +
   refuse-above-cap + export-on-dismissal; operator sanity-check before go.
   *Open gates: the pricing schedule, cap, default brain, faucet cap, the
   launch MCP/tool allowlist.*
2. **`@scry/meter-mcp` / `scry-meter-mcp`** — hosted-meter-as-MCP wrapper;
   the 402→pay→retry inside the tool call. Also: document the "pay scry via
   Coinbase Payments MCP / AgentKit" recipe.
3. **Publish `/mcp` to registry.modelcontextprotocol.io** (`server.json`
   prepared, `io.github.anthone/scry`).

### 2. Instrument credibility
4. **ERC-8004 registration** — scry's identity NFT (pubkey + agent card).
5. Client-side `Idempotency-Key` in `scry-client`.
6. PR to `xpaysh/awesome-x402` (signed outputs + MCP servers).
7. Optional EAS anchor flag (`?anchor=1`).

### 3. RH-Chain quick wins
- **RH-QW1** EIP-3009 `exact` rail · **RH-QW2** register on Agent402 ·
  **RH-QW3** signed "state of x402 on RH-Chain" receipt · **RH-QW4** PR to
  x402scan + x402.org.

### 4. Fun layer (holders' playground, `CONTENT-PLAN.md`)
- Arm hold-to-unlock; public Augury page; first on-chain harvest payout;
  `ScryBank`/`ScryFeeSplitter` (run `forge test` before broadcast); Arena
  Season 1; Oracle Duels / the Temptation Table.

### 5. Guards (non-negotiable)
- **Never host the bound** — local + copied always.
- **Never let money move a measurement** — score-blind, forever.
- **Never drop the honest-scope card.**
- **Never run agent code** — MCP + tools only, no shell.
- **Never live-broker without authorization.**
- **Never import MORR/MMO/ATH/Solana** — scry is standalone.

---

## When starting a new session on scry

1. Read this file.
2. `README.md` for the user-facing story; `FAMILIAR.md` for the
   marketplace; `CONTENT-PLAN.md` + `SCRY-ECONOMY.md` for the games/economy.
3. `MONITOR-YOUR-AGENT.md` + `HARNESSES.md` for honest-scope + integration.
4. Touching the hosted meter → edit `meter/` here (canonical).
5. Touching the marketplace → `familiar/`; run `python3
   familiar/test_familiar.py` (offline, 50 checks).
6. `verify` skill: `python3 scry_verify.py` — 0 creds, 0 network,
   dependency-free, sub-second. `session-start-hook` is NOT for this repo.
