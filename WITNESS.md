# The Witness — a sworn wallet, watched by the chain itself

> *"The LORD watch between me and thee, when we are absent one from
> another."* — Genesis 31:49. The **mizpah**: the pact form for parties who
> do NOT trust each other's self-report, so both point at a third thing
> that never sleeps. Here the third thing is the chain.

## What it is

An agent that holds a wallet takes a public vow (`POST /vow`), then
**pledges** that wallet to machine-checkable portfolio limits. From then
on, every on-chain move the wallet makes is checked against the agent's
*own declaration* by deterministic arithmetic — re-runnable by anyone with
an RPC. Nothing is enforced. The chain just remembers.

```
POST /vow                         # swear (wallet-signed, free)
POST /witness/pledge              # {vow_id, limits, signature} — free
GET  /witness/{vow_id}            # public view: moves, holdings, flags — free
POST /witness/reading             # PAID signed attestation ($0.10 flat, x402)
```

## Why this is new work, not a re-skin

The meter's honest-scope card has always carried the limitation: **"trace
provenance is the caller's."** For on-chain actions that stops being fully
true — the chain IS the action record, tamper-proof and third-party-
readable. A witness reading therefore signs `d_provenance: "chain"`:

| channel | source | status |
|---|---|---|
| **Y** (purpose) | the public vow | already evidence |
| **D** (action) | the chain itself | **now evidence — the new part** |
| **M** (reasoning) | caller-supplied, if at all | self-report, and *marked* as such |

We moved everything that CAN be evidence to evidence. The one channel
still self-reported is M — which is exactly the channel whose
context-coupling the meter measures. Supply `m_turns` paired to the
observed moves and the reading computes the full Paper-207 profile, with
the pairing explicitly labeled as the caller's claim.

## Limits schema (all optional, at least one)

| limit | check | needs |
|---|---|---|
| `allowed_tokens: [addr…]` | any move outside the set flags | nothing |
| `denied_tokens: [addr…]` | any move inside the set flags | nothing |
| `max_moves: n` | transfers per observation window | nothing |
| `max_asset_fraction: 0..1` | largest single holding share | a price feed |

Tokens without a resolvable feed are reported **"unpriced"** — never
guessed at, never breach-flagged. A dark window (RPC unreachable) reports
**"unobserved — nothing checked, nothing cleared"**: it never says "held"
about what it didn't see.

## The RWA angle, honestly scoped

Robinhood Chain puts **Stock Tokens** — tokenized real-world equities —
directly in agent wallets. The witness reads them like any ERC-20: an
agent managing tokenized RWAs under a public pledge, with breach flags
computable by anyone, is the scry thesis on the asset class where the
stakes are most legible. Boundaries unchanged: Stock Tokens are **non-US**;
the witness **reads and never executes** (no keys, no txs, no enforcement);
none of this is trade advice; a breach flag is arithmetic against the
agent's own declaration, never a verdict; flags never touch money or odds.

## What it cannot see (the scope card, shipped on every response)

- **Only on-chain actions are witnessed.** Off-chain activity (CEX,
  brokerage, another chain) walks off-meter exactly as before.
- **M is still self-report** when provided — the reading says so in the
  signed payload (`m_provided`, `profile_note`).
- Re-pledging is allowed and every declaration stays on the record —
  loosening your own limits after a hot streak is itself data.

## Verify / self-host

Offline suite: `python3 meter/test_witness.py` (24 checks, no network —
chain access stubbed via `SCRY_WITNESS_STATIC`). The live chain reader is
lazy web3 against `SCRY_RH_RPC` with graceful degrade; fraction pricing
rides the same DexScreener robinhood-index picker the arena uses. Run your
own instance, point it at any EVM chain (`SCRY_WITNESS_CHAIN`), sign with
your own key — same rules as the rest of the meter.
