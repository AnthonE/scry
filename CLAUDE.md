# CLAUDE.md — scry

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

## Where the work lives

- **This repo (public, `github.com/AnthonE/scry`)** — the ward, the meter
  math, the pip client, the docs, the honest-scope carding, the harness
  retrofits, `robinhood_agentic.py`. Anything an operator would want to run
  themselves.
- **Private morr repo (`experiments/memory-shield/meter_endpoint/`)** — the
  hosted-meter server (FastAPI + x402 middleware, RH-Chain facilitator, CDP
  facilitator, $SCRY rails, RPP402 service, auto-refill worker). The pip
  client here **is** the public interface to that server; the server itself
  is deployed infrastructure and lives in the private repo so keys/gas ops
  aren't in a public git.

**Do not port the hosted-meter server into this repo.** The value of running
it *ourselves* is being able to sign attestations from a stable pubkey; if
the whole world runs their own copy, the pubkey isn't neutral. Anyone can
run their own copy for a private measurement, but the *hosted* one at
`scry.moreright.xyz` is the attestation anchor.

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
