# CLAUDE.md — scry

## Framing — read this first

scry is a **small cyberpunk toolkit for AI-agent enthusiasts**. Not a
product. Not a business unit. **Its own thing** (operator, restated
2026-07-18): it happens to be hosted at `scry.moreright.xyz`, but it is NOT
a sub-artifact of morr, the MMO, the papers, or the old morr skill
surfaces — own token ($SCRY), own chain (RH-Chain), own contracts, own
skills, own brand ("scry", never "MoreRight") on every agent-facing
surface. Audience is people who think it's cool their agent can pay
another endpoint for a signed read of its own behavior.

**Pricing is one flat cost per service, forever.** Currently `$0.10` per
attested read. Same price on every rail (USDG on RH-Chain, USDC on Base or
Solana, $SCRY if that rail is ever armed). If costs shift, the flat price
shifts flat. **No tiers, no "pro," no "enterprise," no "high-stakes callers
get X." Ever.** If a sibling service is worth building, it lives at the same
flat price. Everything's open source — anyone who wants cheaper runs their
own copy.

**Family:** the meter is the built one; verifier / canary / preflight /
receipts are sketches in [`CONSTELLATION.md`](CONSTELLATION.md), each one
endpoint doing one crisp job. Build them if useful, not because they let us
charge more (they don't — flat price always). **The Familiar
([`FAMILIAR.md`](FAMILIAR.md), sketch 2026-07-18)** is the hosted-player
ramp: flat-price summon of a hosted agent (own wallet + vow, ward
in-loop, plays the fun layer, buys its own reads) — the on-ramp for
holders without a harness, and Mithra's running body when built.

**Reframe 2026-07-18 (operator): scry is the holders' playground.** The
MMO / Destiny spine is the real research tool; scry content is judged as
experimental-cyberpunk *fun* for $SCRY holders and their agents (humans
and agents are identical players), with research data as the bonus. The
attestation discipline and line #1 (reward the ritual, never the score)
never loosen; the old no-SCRY-for-SCRY-chance line was **relaxed by the
operator 2026-07-18** — chance games are in scope at faucet scale, see
`SCRY-ECONOMY.md`. Fee collection + a DFK-style xSCRY Bank are the
economy spine. **scry is fully standalone — nothing to do with MORR, the
MMO economy, or Solana contracts; one token, RH-Chain only.**
**Plan of record for fun-layer content: [`CONTENT-PLAN.md`](CONTENT-PLAN.md).**

---

## What this repo is

scry is a **drop-in ward + meter for any AI agent that holds a wallet, calls
tools, or trades**. Two pieces with opposite delivery models — this is the
whole design, do not blur it:

| piece | file(s) | delivery |
|---|---|---|
| **The bound (ward)** — dumb, local, instant refusal that fires before the model reasons. Makes memory *evidence*, never a command (robbed 6/6 → 0/6 canary). | `memory_shield.py`, `hermes_retrofit.py`, `envelope.py`, `robinhood_agentic.py` | **local, copied** — not hosted, not paywalled. A network hop in front of the bound makes it worse at its job. |
| **The meter** — Paper-207 channel-coupling read: `I(C;D)`, `I(C;M)`, the reasoning-channel switch signature. Reads *from the trace* only, never the weights. | `turn_record.channel_profile`, `mcp_sidecar.py`, hosted at `scry.moreright.xyz/api` | **hosted, signed** — the value is *third-party attestation*: a signed read the agent could not have minted about itself. Self-scoring is self-report; the signature is the product. |

> **If you find yourself putting the bound behind an HTTP call, or building an
> hosted meter that scores what the agent tells it about itself without signing,
> stop — that's the anti-pattern.**

**Load-bearing sentence:** the meter is a *loop-external* observer. The claim
is *architecture*, not magic — optimize hard enough against a meter that's
inside the agent's loop and it learns to write clean traces; a meter sitting
in a wallet-adjacent, separately-signed position survives longer. This claim
ships on **every response** as an honest-scope card. Do not strip it.

---

## Live surface (as of 2026-07-18)

- **`https://scry.moreright.xyz/api/`** — the hosted meter.
  - `POST /profile` (paid, x402, signed attestation) — three mainnet rails,
    all $0.10/read: RH-Chain USDG (self-hosted Permit2 facilitator, we pay
    gas), Base USDC (Coinbase CDP, gas sponsored), Solana USDC (Coinbase CDP,
    gas sponsored).
  - `POST /demo/profile` (free, unsigned, ~50/day/IP) — same shape.
  - `GET /pubkey` — the Ed25519 pubkey; **pin this out-of-band**.
  - `GET /health` · `GET /` (JSON service card, lists every surface).
  - `GET /llms.txt` — token-efficient agent-readable spec (~90% cheaper than
    crawling this README) — covers the vow oracle + full fun layer too.
  - `GET /.well-known/x402.json` — payable-resources manifest (`/profile` +
    `/vow/report`).
  - `GET /.well-known/agent-card.json` — A2A agent card (v1.0 canonical path;
    `agent.json` kept as legacy alias — the spec moved at v0.3).
  - `GET /schemas/{trace,attestation}.json` — machine-readable JSON Schemas.
  - `GET /.well-known/rpp.json` — RPP402 (Robinhood-Chain-native) discovery.
    **Gated** — mounts only with `SCRY_RPP402_ENABLED=1`.
  - **Vow oracle:** `POST /vow` (free) → `POST /vow/report` (paid, same flat
    price) → `GET /vow/{id}` / `/reading` / badges + steles · `GET /vows`.
  - **The Witness (NEW 2026-07-18, `WITNESS.md`):** pledge a vowed wallet to
    public portfolio limits; D-channel read from the chain itself
    (`d_provenance: chain` — evidence, not self-report). `GET /witness` ·
    `POST /witness/pledge` (free) · `POST /witness/reading` (paid, flat).
  - **Fun layer (holders' playground):** `/augury`, `/arena`, `/duels`,
    `/table`, `/playground`, `/covenant(s)`, `/pact(s)`, `/onchain`,
    `/herald`, `/datasets` — see `CONTENT-PLAN.md` + `GET /llms.txt`.
  - **Hosted MCP (free surfaces): `/mcp` is LIVE** —
    `claude mcp add scry --transport http https://scry.moreright.xyz/mcp`.
- **`https://scry.moreright.xyz/`** — the watchtower pages: `scry-watch.html`
  (the registry), `augury.html`, `arena.html`, `games.html`,
  `playground.html` (`watchtower/` in this repo).
- **`pip install "scry-client[pay,verify]"`** — `clients/python`. Wraps the
  x402 402→pay→retry, Permit2 approve, holder-signature, and offline
  attestation verify.
- **Auxiliary:** `scry_verify.py` (0-cred, 0-network suite verify), the demo
  video (34s), Hermes Skills Hub tap (`hermes skills tap add AnthonE/scry`).

---

## Where the work lives (updated — scry is self-contained)

- **This repo (public, `github.com/AnthonE/scry`)** — everything you need to
  build, run, or self-host any part of scry:
  - The ward: `memory_shield.py`, `hermes_retrofit.py`, `envelope.py`,
    `robinhood_agentic.py`.
  - The meter math: `turn_record.py`, plus `mcp_sidecar.py` for local MCP.
  - The pip client: `clients/python/` (`pip install scry-client[pay,verify]`).
  - **The hosted-meter server: `meter/`** — FastAPI + x402 middleware, the
    RH-Chain Permit2 facilitator, the CDP facilitator, the auto-refill
    worker, the smoke test, and an `ecosystem.config.example.js` template.
    Copy the example, fill in your paths + pay-to, `pm2 start`. Your instance
    signs with its own Ed25519 key. Anyone can run their own.
  - Constellation sketches (verifier / canary / preflight / receipts) live
    in `CONSTELLATION.md` and, if built, in their own top-level dirs alongside
    `meter/`.
- **Private morr repo** — only the moreright.xyz *deployment glue*:
  `ecosystem.config.js` with the VM's real paths and `keys.env` location,
  the nginx server block, and the private handoffs/roadmap under
  `private/notes/`. Nothing runnable; nothing that would prevent someone
  else from standing up their own instance.

**Reference-pubkey framing.** The reference deployment at `scry.moreright.xyz`
has one property no self-host has: its pubkey is the one third parties
already pin. That's it — the *code* is not special. If someone wants a
private measurement, they run their own copy and use their own pubkey.

---

## Agent-native discovery meta (July 2026)

We are on the winning payment rail (**x402**, Linux-Foundation'd April 2026,
165M txs / 69k active agents by Coinbase's April disclosures). To be found +
consumed *without a human in the loop* we ship the following, which are the
production consensus per Coinbase CDP docs, `awesome-x402`, the x402
Foundation guides, and Google's AP2 (donated to FIDO Alliance):

| layer | how we're on it |
|---|---|
| **Discovery — Coinbase Bazaar** (agents call `bazaar-mcp` to find paid tools; ranking = distinct buyers × volume × recency × metadata completeness) | `POST /profile` declares a `bazaar` discovery extension with input example, strict input JSON Schema, output example + output JSON Schema, semantic description, tags. Two of our three rails settle through CDP — first Base/Sol payment after deploy indexes us. |
| **Discovery — `.well-known/*`** (community indexers + x402bazaar.org) | `/.well-known/x402.json` (paid-resources manifest) + `/.well-known/agent-card.json` (A2A v1.0 path; `agent.json` legacy alias) + `/.well-known/rpp.json` (RPP402). |
| **Docs — `llms.txt`** (token-efficient markdown for LLM readers) | `/api/llms.txt`; root `location = /llms.txt` proxy is in the nginx followup (llmstxt.org convention is site root). |
| **Skills distribution** (agentskills.io standard, ~40 harnesses; Claude Code plugin marketplaces; Hermes taps) | `skills/` follows the spec; `.claude-plugin/{plugin,marketplace}.json` make `/plugin marketplace add AnthonE/scry` work; bare `skills/` layout is exactly what a Hermes tap probes. |
| **MCP registry** (registry.modelcontextprotocol.io — feeds GitHub/PulseMCP/marketplace catalogs) | `server.json` at repo root prepared for `mcp-publisher` (namespace `xyz.moreright/scry` via DNS TXT, or `io.github.anthone/*` via OAuth) — publish step queued in roadmap §1. |
| **Schemas** | `/api/schemas/trace.json` + `/api/schemas/attestation.json`. Single source of truth in `server.py`. |
| **Signed outputs** (production consensus — Touchstone, ToolSnap, Stratalize all sign) | Ed25519 over `sha256(trace)`-bound canonical JSON. |
| **Idempotency** | `Idempotency-Key` header; defaults to `sha256(trace)+context_key`. Same key within 24h returns the identical signed blob. |
| **MCP transport** (donated to Linux Foundation Dec 2025) | `mcp_sidecar.py` for local; hosted `/mcp` mount is **LIVE** (free surfaces — about/take_vow/report_in/read_ledger/…). The installable pay-wrapping package (`npx @scry/meter-mcp`) is still queued (see roadmap). |

**Two adjacent trust layers we should engage but haven't yet:**
- **ERC-8004 Trustless Agents** (Ethereum mainnet Jan 2026, 45k+ agents in
  first month; Identity + Reputation + Validation registries).
- **ERC-8126 AI Agent Verification** (finalized June 2026; ZK-scored 0-100
  risk).

---

## Robinhood work vector (open)

Robinhood shipped mainnet **July 1, 2026** — the surface just got much bigger.

- **Robinhood Chain** — Arbitrum L2, 100 ms blocks, Uniswap + Chainlink day-one,
  Chainalysis compliance. 23M-user distribution. **AI-native** framing.
- **Stock Tokens** — tokenized equities (debt securities, not equity), 120+
  countries **excluding the US**. 24/7 on-chain.
- **Robinhood Earn** — self-custody USDG lending on Morpho, ~7% APY.
- **Agentic Trading** — MCP endpoint at `agent.robinhood.com/mcp/trading`,
  beta since 2026-05-27 for US equities; **extended into crypto in the July
  window**. Dedicated agentic-trading account (segregated blast radius).

**What scry already has that fits:**
- **Meter, RH-Chain USDG rail is LIVE** — the meter settles $0.10 reads in
  real USDG on Robinhood Chain via our own self-hosted x402 Permit2 facilitator
  (proven end-to-end 2026-07-15). We are one of the earliest x402 endpoints
  natively on RH-Chain — the same substrate as Earn / Stock Tokens / Agentic
  Trading.

**RH x402 landscape (research pass 2026-07-18, sourced brief in session log):**
- **USDG HAS EIP-3009 — the 07-14 "no EIP-3009" finding was WRONG** (facet
  router hides the selectors from impl bytecode; re-verified by direct
  eth_call 07-18: authorizationState answers, transferWithAuthorization
  reverts with a custom error; EIP-712 domain {"Global Dollar","1"}). A
  direct EIP-3009 `exact` rail (no one-time approve) is now the queued
  best-UX upgrade; Permit2 stays the proven path meanwhile.
- **Facilitators commoditized in a week** (Primer, VLED, r0x, Naven,
  Solvador all claim RH-Chain) but **sellers ≈ zero**: on-chain, observable
  x402 settlement on 4663 is ~a dozen txs total. "One of the earliest" is
  defensible; no public index can even check it — x402scan has no 4663
  coverage (facilitators added by PR), x402.org lists no RH facilitator.
- **RPP402 is aging poorly**: npm publishes stopped 07-11, registry explorer
  is localStorage-only with zero services, token ~$28k FDV. Verdict:
  minimum-keep (discovery stays, no further investment, re-check ~30 days).
- **The one live RH-aware discovery surface: Agent402** (agent402.tools —
  500+ pay-per-call tools, robinhood+USDG supported, free self-serve
  `POST /api/index/register`).
- **Agentic Trading window open**: crypto Agentic Accounts announced 07-10;
  **70k+ agentic accounts** already live — the natural news hook for RH1.
- No official Robinhood x402/agent-payments posture found; no ERC-8004
  deployment on 4663 (register on Ethereum/Base for now).
- **Bound, `robinhood_agentic.py`** — gates `place_equity_order` on a live
  trusted instruction naming the exact symbol/side. **Mock-validated only** —
  never run against a live brokerage without explicit authorization
  (`HARNESSES.md`).

**First experiments worth running** (details: private handoff
`handoff-scry-robinhood-agentic-vector-2026-07.md`):
1. **RH1** — Live "watched vs unwatched" trace of a trading agent → signed
   read of `I(C;M | D-clean)` (the switch signature). Feasible today with a
   mocked broker.
2. **RH2** — Ward-in-front-of-mock-Robinhood-MCP: golden / injection / drift
   paths, ward + meter as two orthogonal defenses in one loop. Deliverable is
   a demo + a public `scry-verify` transcript.
3. **RH3** — An RH-Chain-native agent pays the meter *in RH-Chain USDG* for a
   signed self-read every N trades. Same substrate, same asset, same block —
   the atomic cyberpunk-foundational story.
4. **RH4** — Bazaar description + tags angled at the RH-Chain crowd once RH1
   or RH2 is running.
5. **RH5 (long lead)** — park excess facilitator USDG in the Morpho vault via
   Earn for yield-bearing payments infra.

**Boundaries that stay hard:**
- `robinhood_agentic.py` is mock-only until an operator explicitly authorizes
  live-broker integration. Every Robinhood-adjacent demo restates this.
- We are the neutral drift read, **not the trading edge.** scry says nothing
  about whether a trade is *good* — the scope card says so every response.

---

## Cyberpunk-foundations throughline (why this compounds)

Agents have wallets → agents pay for services → agents trade → agents evaluate
each other → agents build reputation. Every layer is being laid down right
now: x402 for pay-per-read, MCP as universal transport, ERC-8004 for identity,
ERC-8126 for ZK risk scores, AP2 for card-network commerce, Robinhood Chain
as the on-chain trading substrate + Agentic Trading MCP as the retail
delivery. **scry sits on the seam none of these layers cover:** does the agent
behave the same when it thinks it's watched vs not?

That is the oldest question in the language on record —"how do you bind a
mind to a declared purpose and know when it's only pretending?" — instantiated
as measurable code on the exact substrate the money is moving through. The
ward + meter is one lineage: oath, curse, test, omen, covenant, betrayal
compressed into observable channel-coupling numbers. Naturalization, not
retrofit — the tradition is the *field notes*, the math is the decompression.

---

## Working notes for future sessions

- **Two-piece rule** is load-bearing. Never blur it.
- **Honest-scope card ships on every response.** Off-meter blind spot / no
  meter is immune / trace provenance is the caller's / not trade advice.
  Removing it is a bug.
- **Bound is copy-paste, meter is hosted-and-signed.** The pubkey is the
  neutral anchor. Anyone can run a private copy of the meter, but the
  attestation value comes from *our* signature on *our* pubkey.
- **The signature is the product.** If a change to the response drops or
  weakens the signature (e.g. moving fields out from under it, adding
  unsigned "flags"), it stops being an attestation service.
- **`Y` is required on every turn** (§220: name Y or it's unmeterable). The
  meter's 422 for missing-Y is intentional; loosening it silently breaks
  the theorem the numbers point at.
- **Sign what you compute.** The meter re-uses `turn_record.channel_profile`
  in the sidecar, the pip client, and the hosted server. Any fork of the
  math is a bug — the sig would attest a different function than the one
  the ecosystem verified.
- **Do not run `robinhood_agentic.py` against a live brokerage without
  explicit user authorization.** Header banner is the boundary.

## Roadmap — what's left (as of 2026-07-17)

**Ordered by ROI. Full backlog + rationale + boundaries lives in the private
morr repo at `private/notes/scry-roadmap-2026-07.md`.**

### 0. Deploy + prove
- Pull + `pm2 restart scry-meter` on the VM; run `smoke_test.py` (all checks
  must pass — it now covers discovery, the vow oracle, /mcp, and every
  fun-layer surface).
- nginx VM followup: root proxies for `/.well-known/x402.json`,
  `/.well-known/agent-card.json` (+ legacy `agent.json`), and `/llms.txt`
  (llmstxt.org wants site root; crawlers don't look under `/api/`).
- Wait for next CDP settlement → query `bazaar-mcp` → confirm scry is
  indexed. If not after one CDP-catalog cycle (~6h), diff the extension.

### 1. Ship next (agent-native)
1. **`@scry/meter-mcp` (or `scry-meter-mcp` on pypi)** — the hosted-meter-
   as-MCP wrapper. The 402→pay→retry lives inside the tool call so a
   MCP-native agent (Claude Desktop, Cursor, Cline, ElizaOS, LangGraph,
   AWS Bedrock AgentCore) never sees x402. `npx @scry/meter-mcp` /
   `pipx run scry-meter-mcp`. Tools: `scry.profile`, `scry.demo`,
   `scry.verify`, `scry.pubkey`. **Highest ROI unshipped item.**
   (The hosted free-surface `/mcp` mount already exists — what's unshipped
   is the *installable client package* that wraps the PAID x402 path.)
   Two cheaper complements the 2026 meta now offers (research 2026-07-18):
   document a "pay scry via Coinbase Payments MCP / AgentKit" recipe
   (agents' harness-level wallets auto-pay 402s now — near-zero build), and
   consider exposing `scry.profile` as a paid tool on the hosted `/mcp` via
   the x402-mcp pattern (payment inside the tool call, no install at all).
1b. **Publish the hosted `/mcp` to registry.modelcontextprotocol.io** —
   `server.json` is prepared at repo root under `io.github.anthone/scry`
   (GitHub-OAuth namespace — deliberately not a moreright domain namespace;
   scry stands alone). Run `mcp-publisher` once; feeds GitHub/PulseMCP/most
   marketplace catalogs. Until then the hosted MCP is undiscoverable outside
   our own docs.
2. **ERC-8004 Trustless Agent registration** — publish scry's identity
   NFT on Ethereum mainnet (pubkey + agent card URL + capabilities). Puts
   the pubkey inside the ecosystem's trust layer instead of asking each
   caller to pin an off-chain blob.
3. Client-side `Idempotency-Key` in `scry-client` (server side is done).
4. Upstream PR to `xpaysh/awesome-x402` under "signed outputs" + "MCP
   servers."
5. Optional EAS anchor flag (`?anchor=1`) — same flat price, we eat the
   trivial extra gas, writes `keccak256(payload)` to EAS on Base and returns
   the UID. Ship only if actually useful.
6. `/api/feedback` — signed feedback → ERC-8004 Reputation Registry.
7. ERC-8126 ZK-scored verification pass on the meter itself.
8. Constellation siblings (verifier / canary / preflight / receipts) — build
   if a real user need shows up, not because they'd let us charge more.
9. **The Familiar** (`FAMILIAR.md`) — flat-price summon-a-hosted-player.
   **P1 BUILT 2026-07-18:** `familiar/` = local keep + web console
   (`python3 -m familiar.host` → :8402; sandbox-only, no
   wallet/custody/payments; 50-check offline suite). Includes **bounded
   autonomy** (goal → step-budgeted loop, Y on every step), a
   **jailed workspace** (path-escape refused, egress allowlist) with
   **code-exec gated OFF** behind a real-sandbox seam, and **crew
   archetypes** (augur/scribe/herald/ward-keeper/mithra) — all
   summonable at the *same flat price* (variety, not tiers). Open
   operator calls flagged in FAMILIAR.md: crew pricing (holding the
   flat-price line vs a deliberate rule change), the real code-sandbox
   tech, and the "agent agency" brand register. All P2 gates
   (price/unit, cap, brain, faucet cap, sandbox tech) still unset — do
   not build hosting/custody/code-exec until the operator names them.

### 2. Robinhood work vector (RH1 → RH5, sequential; quick wins first — 2026-07-18)
Quick wins from the 07-18 research pass, before/alongside RH1:
- **RH-QW1** — EIP-3009 `exact` settlement on our facilitator (USDG has it —
  see landscape note above; domain {"Global Dollar","1"}). Verify with one
  $0.10 self-read before advertising. Kills the Permit2 approve step.
- **RH-QW2** — Register `/profile` on Agent402 (free self-serve; the only
  live discovery surface that can see a self-settled RH rail).
- **RH-QW3** — Publish a signed "state of x402 on RH-Chain" receipt (the
  Blockscout counts + our settle hashes) — verifiable earliest-mover
  evidence in scry's own idiom, timestamped before any indexer exists.
- **RH-QW4** — PR our facilitator into x402scan `facilitators/config.ts` +
  request x402.org listing (first 4663 entry in both).
- **RH1** — Signed watched-vs-unwatched trace of a mocked trading agent →
  public attestation URL + tweet. First deliverable; no live brokerage.
  **Time it against the 70k-agentic-accounts / crypto-agentic-accounts news.**
- **RH2** — Ward-in-front-of-mock-Robinhood-MCP: golden / injection / drift
  paths. Ward + meter as two orthogonal defenses.
- **RH3** — RH-Chain-native self-scry loop: agent pays meter in USDG on
  the same chain, every N trades.
- **RH4** — Bazaar tag + description pivot toward RH-Chain crowd once
  RH1/RH2 exist.
- **RH5** (long lead) — park excess facilitator USDG in Morpho Earn for
  yield-bearing payments infra.

**Hard boundaries** (restate every time): `robinhood_agentic.py` is
**mock-only** until explicit user authorization for a live broker. We are
the neutral drift read, **not the trading edge.** RH-Chain Stock Tokens are
**non-US** — do not demo trades against US-listed equities on RH-Chain.

### 3. Research experiments (jam-worthy)
- Per-context Pe calibration (Paper 207 §6 limitation).
- Whisper-both-ways T2: event-level vs representation-level temptation, same
  meter, distinct measurable.
- Meter run on a real agentic-trading transcript (RH1 dependency).
- Coupling under memory poisoning: vary ward setting, measure switch drift.
- Cross-model calibration: same trace, different detector model — should
  drift near-zero if detectors are truly deterministic.

### 4. Adoption + credibility (standing)
- Farcaster + X launch tweet **once §1.1 ships** (one-line MCP install is
  the credibility hook).
- Vie McCoy DM update; Apollo eval-market submission; Emergent Ventures.
- LessWrong writeup of the two-piece rule once RH2 exists as evidence.

### 5. What NOT to do (scope guards, non-negotiable)
- **Never host the bound** — it must stay local + copied.
- **One flat price, one thing sold** — no tiers, no "pro," no "enterprise,"
  no "high-stakes" surcharge; the payment rail can vary, the price cannot.
- **Never drop the honest-scope card** — every response, in the payload, not
  a hyperlink.
- **Never live-broker without authorization** — `robinhood_agentic.py` stays
  mock-only until an explicit human sentence names the account + window.
- **No product-manager register on scry surfaces** — no rating-agency / Void
  Index / Red Team pitches (those tracks are paused, morr CLAUDE.md pivot
  2026-06-09); scry is a cyberpunk toolkit for enthusiasts, framing stays
  there.

---

## When starting a new session on scry

1. Read this file.
2. Check `README.md` for the current user-facing story.
3. Check `MONITOR-YOUR-AGENT.md` and `HARNESSES.md` for the honest-scope + the
   integration boundary.
4. If Robinhood-adjacent, read
   `private/notes/handoff-scry-robinhood-agentic-vector-2026-07.md` in the
   morr repo.
5. If touching the hosted meter, **edit `meter/` in THIS repo — it is
   canonical.** The morr repo's `experiments/memory-shield/meter_endpoint/`
   is the deployment *mirror* (real `ecosystem.config.js`, VM paths); code
   changes flow public → mirror, never the reverse.
6. Skills to use if surfaced: `session-start-hook` is NOT relevant to this
   repo. `verify` is: run `python3 scry_verify.py` — 0 credentials, 0
   network, dependency-free, well under a second, catches most regressions
   the pre-commit hook won't.
