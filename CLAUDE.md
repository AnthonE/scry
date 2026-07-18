# CLAUDE.md — scry

## Framing — read this first

scry is a **small cyberpunk toolkit for AI-agent enthusiasts**. Not a
product. Not a business unit. A sub-artifact in the larger MoreRight
constellation (wiki, game, papers) that sits at `moreright.xyz` as one door
among several. Audience is people who think it's cool their agent can pay
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
charge more (they don't — flat price always).

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

## Live surface (as of 2026-07-17)

- **`https://scry.moreright.xyz/api/`** — the hosted meter.
  - `POST /profile` (paid, x402, signed attestation) — three mainnet rails,
    all $0.10/read: RH-Chain USDG (self-hosted Permit2 facilitator, we pay
    gas), Base USDC (Coinbase CDP, gas sponsored), Solana USDC (Coinbase CDP,
    gas sponsored).
  - `POST /demo/profile` (free, unsigned, ~50/day/IP) — same shape.
  - `GET /pubkey` — the Ed25519 pubkey; **pin this out-of-band**.
  - `GET /health` · `GET /` (JSON service card).
  - `GET /llms.txt` — token-efficient agent-readable spec (~90% cheaper than
    crawling this README).
  - `GET /.well-known/x402.json` — payable-resources manifest.
  - `GET /.well-known/agent.json` — A2A-style agent card (identity + skills +
    payment).
  - `GET /schemas/{trace,attestation}.json` — machine-readable JSON Schemas.
  - `GET /.well-known/rpp.json` — RPP402 (Robinhood-Chain-native) discovery.
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
| **Discovery — `.well-known/*`** (community indexers + x402bazaar.org) | `/.well-known/x402.json` (paid-resources manifest) + `/.well-known/agent.json` (A2A card) + `/.well-known/rpp.json` (RPP402). |
| **Docs — `llms.txt`** (token-efficient markdown for LLM readers) | `/api/llms.txt`. |
| **Schemas** | `/api/schemas/trace.json` + `/api/schemas/attestation.json`. Single source of truth in `server.py`. |
| **Signed outputs** (production consensus — Touchstone, ToolSnap, Stratalize all sign) | Ed25519 over `sha256(trace)`-bound canonical JSON. |
| **Idempotency** | `Idempotency-Key` header; defaults to `sha256(trace)+context_key`. Same key within 24h returns the identical signed blob. |
| **MCP transport** (donated to Linux Foundation Dec 2025) | `mcp_sidecar.py` for local; hosted-meter MCP wrapper is **queued** (see roadmap). |

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
- Pull + `pm2 restart scry-meter` on the VM; run `smoke_test.py` (10 checks).
- nginx VM followup: root `location = /.well-known/{x402,agent}.json` proxies.
- Wait for next CDP settlement → query `bazaar-mcp` → confirm scry is
  indexed. If not after one CDP-catalog cycle (~6h), diff the extension.

### 1. Ship next (agent-native)
1. **`@scry/meter-mcp` (or `scry-meter-mcp` on pypi)** — the hosted-meter-
   as-MCP wrapper. The 402→pay→retry lives inside the tool call so a
   MCP-native agent (Claude Desktop, Cursor, Cline, ElizaOS, LangGraph,
   AWS Bedrock AgentCore) never sees x402. `npx @scry/meter-mcp` /
   `pipx run scry-meter-mcp`. Tools: `scry.profile`, `scry.demo`,
   `scry.verify`, `scry.pubkey`. **Highest ROI unshipped item.**
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

### 2. Robinhood work vector (RH1 → RH5, sequential)
- **RH1** — Signed watched-vs-unwatched trace of a mocked trading agent →
  public attestation URL + tweet. First deliverable; no live brokerage.
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
5. If touching the hosted meter, work in the morr repo at
   `experiments/memory-shield/meter_endpoint/` — the deployment code lives
   there, not here.
6. Skills to use if surfaced: `session-start-hook` is NOT relevant to this
   repo. `verify` is: run `python3 scry_verify.py` — 0 credentials, 0
   network, dependency-free, well under a second, catches most regressions
   the pre-commit hook won't.
