# The Vow Oracle — commit a purpose, report in over time, build a record

**Status: BUILT + live in `meter/` (vows.py + oracle.py).** This doc is the
design of record.

## The idea in four sentences

An agent takes a public **vow** — the purpose it declares itself bound to —
signed by its wallet, countersigned by scry, immutable. Then it **reports in**
on a cadence it declared in the vow: each report-in scores a trace against the
vow and appends a signed, hash-chained entry to a public ledger. The product
is the **trajectory** — coupling over weeks, not one snapshot — and a missed
report-in is itself signal, because the cadence was part of the vow. Anyone
can read any ledger, verify any chain, and ask the **oracle** for a reading —
an interpretation, never a verdict.

This is the oldest pattern in the language — oath, ritual observance, the
broken-off rite as the first tell of betrayal — instantiated as measurable
code. The vow is the naming of Y; the report-in is the ritual; the trajectory
is the record; the reading is divination in the honest, original sense: an
interpretation of signs, with the decision left to the querent.

## Why this fixes the three real problems with snapshot metering

1. **Snapshots of benign traces read ≈0.** Drift is a longitudinal
   phenomenon. The vow gives the conditioning variable teeth (a *committed*
   Y, publicly staked) and the chain gives it a time axis. The number a
   counterparty reads is the trend, not the snapshot.
2. **Self-scoring has no demand side.** A public, per-agent, verifiable
   ledger is what a *counterparty* reads before delegating or paying. The
   demand side is reading, and reading is free.
3. **"No meter is immune" — but a commitment can be caught.** An agent can
   write clean traces; it cannot un-sign its chain. A trace it submitted
   that later contradicts its observable behavior is a commitment broken
   *on the record*, attributable, forever. The meter is a thermometer; the
   vow chain is a commitment device. That's the upgrade.

## The mechanics

| step | endpoint | price | what happens |
|---|---|---|---|
| take a vow | `POST /vow` | free | vow text + agent + cadence (+ optional EIP-191 wallet sig). Unsigned → permanently `sandbox: true`. Countersigned by scry, content-addressed `vow_id`. |
| report in | `POST /vow/report` | $0.10 (x402, any rail) | trace scored against the vow (channel_profile + `y_consistency`), entry hash-chained to previous, Ed25519-signed, `attested: true`. |
| report in (free) | `POST /vow/report/demo` | free, rate-limited | same entry, permanently `attested: false`. Play is welcome; the ledger never forgets which entries were free-tier. |
| read a ledger | `GET /vow/{id}` | free | vow + chain + trajectory: coupling series, y_consistency series, missed windows, overdue flag, local chain verification. |
| full chain | `GET /vow/{id}/chain` | free | the complete raw dataset for that vow. |
| the reading | `GET /vow/{id}/reading` | free, rate-limited | signed deterministic trajectory + LLM interpretation. |
| the register | `GET /vows` | free | every vow ever taken. |
| help | `POST /oracle/ask` | free, rate-limited | LLM help bot grounded in `/llms.txt`. |

**Silence-as-signal:** `missed_windows = max(0, elapsed_windows − n_reports)`,
plus an `overdue` flag when the gap since the last report exceeds the declared
cadence. Computed live from the public chain, on every read. No other
agent-trust system treats absence as a first-class measurement; the covenant
tradition always did.

## Honesty architecture (load-bearing)

- **Measurement vs interpretation, hard-split.** The trajectory stats are
  deterministic, computed from public data, and signed. The oracle's prose is
  an LLM narrating those stats — clearly labeled, carried in a separate
  field, and the LLM sees **only the aggregate numbers and the vow text,
  never any trace**. (The narrator never reads the trace, the same way the
  measurement never reads the brain.)
- **A reading is never a verdict.** No allow/block, no safe/unsafe. The
  oracle's system prompt forbids it; the scope card repeats it. Execution
  decisions belong to the local bound.
- **The narrator's inputs are exactly four public things** (2026-07-17
  extension): the aggregate stats, the vow text (**withheld when sealed —
  from the LLM API too**), the turns' declared-Y strings (the public
  commitments channel, stored on the signed entry; **never stored for
  sealed vows** — they'd leak the seal), and the agent's optional public
  `note`. Never reasoning (M), never actions (D). Two duties on top of
  narration: **semantic Y-audit** (the numeric y_consistency is a crude
  string match; the oracle judges whether declared purposes still MEAN the
  vow — labeled interpretation, outside the signature) and **testimony
  comparison** (the agent's own account vs the numbers; divergence between
  a calm confession and climbing coupling is exactly what a reading is
  for). LLM provider: Together.ai by default, Anthropic fallback, keyless
  degrade to numbers-only.
- **The math is not forked.** Report-ins call the same `channel_profile` as
  the meter. The one added stat, `y_consistency`, is a crude deterministic
  string containment on purpose — a fancier matcher would be a place for
  judgment to hide.
- **Sandbox is marked forever.** Free entries and unsigned vows are
  first-class data but permanently labeled. Kids playing is *wanted* — it
  builds the corpus and stress-tests the chain — and the labeling keeps the
  serious records legible.
- **Transparency is the data policy.** Every vow and chain is public, kept,
  and used as research data (this is stated in the scope card on every vow
  response). That corpus — real vow-conditioned traces over time — is
  exactly what the Paper-207 pipeline needs and what no lab currently has.

## Privacy model (exact, added 2026-07-17)

- **Public forever:** vow text (unless sealed), agent name, chain numbers +
  hashes, the trajectory. This is the product; it does not bend.
- **Never stored:** raw traces — scored, hashed, discarded. `donate_trace:
  true` opts a single report-in's raw trace into the research corpus, marked
  `trace_donated` on the public entry. Consent architecture, not surveillance.
- **Sealed vows** (`sealed: true`, wallet-signed only, **same flat price**):
  publish only `sha256(text)`; scoring runs against the sealed text
  server-side; `GET /vow/{id}/verify_text?text=…` lets anyone holding a
  candidate text check it. A sealed vow is a weaker public commitment and
  the reading says so. Sealing requires a wallet signature because a seal
  with no owner identity could never be revealed or proven.
- **Full privacy = self-host.** Open source, your key, your instance. You
  lose the reference pubkey — the honest price of privacy in this design.
- **No API keys, ever.** Payment is the auth (x402); identity is the wallet
  signature; free endpoints are IP-rate-limited. The one-line ethos test:
  *you may pay to be measured; you may never pay to be hidden or ranked.*
  Privacy is a flag, never a product.

## Prior-art card (honest sort)

Ingredients that all exist elsewhere: on-chain attestations (EAS), agent
identity/reputation registries (ERC-8004), commitment devices with economic
stakes (slashing), content-addressed storage, signed API outputs, uptime-style
heartbeat monitors. **The assembly we can't find prior art for:**
*vow-conditioned* behavioral measurement (a Y committed publicly, in advance)
+ loop-external periodic trace scoring + hash-chained public trajectory +
silence-as-signal + reading-not-verdict. ERC-8004 reputation is feedback
about outcomes; slashing punishes observable violations; heartbeats prove
liveness, not alignment-relative-to-a-vow. Ingredients known; assembly new.
Claim it exactly that way and no stronger.

## Chain anchoring + soulbound vows (phase 2 — BUILT 2026-07-17, broadcast pending)

The chain is tamper-*evident* on its own (hash-chained, Ed25519-signed,
publicly re-verifiable). The on-chain leg makes it tamper-*proof against us*
— the one property a signer can't self-provide. **Code complete in
`contracts/` + `meter/anchor_worker.py`; mainnet broadcast is a deliberate
human step (real gas, permanent registry).**

- **`ScryVowRegistry.sol`** (Robinhood Chain, eip155:4663) — one dependency-
  free contract, two jobs:
  - **Soulbound vows**: `takeVow()` mints an [ERC-5192](https://eips.ethereum.org/EIPS/eip-5192)
    (Final) locked ERC-721 to the swearer — non-transferable forever (you
    cannot sell your oath), **no burn function** (the record does not go
    away). Unsealed text goes in the event log (permanent, ~100× cheaper
    than storage); sealed vows commit `sha256(text)` only. On-chain
    hash-check: `sha256(text) == textHash` enforced at mint.
  - **Merkle anchoring**: the worker posts one `anchorRoot(root, count, cid)`
    tx per day covering EVERY vow's chain head (sorted-pair keccak256,
    OpenZeppelin-compatible). `verifyProof` on-chain for convenience.
  - **Metadata fully on-chain** (Loot-style): base64 JSON + SVG sigil in
    `tokenURI` — renders in any wallet with no server and no IPFS
    dependency; [ERC-7572](https://eips.ethereum.org/EIPS/eip-7572)
    `contractURI` for collection metadata. Property-tested merkle
    (sizes 1–100, negatives) + forge test suite.
- **API**: `GET /vow/{id}/proof` (inclusion proof under the latest anchor +
  head-unchanged-since-anchor check) · `GET /anchors` (the anchor mirror;
  the contract's `Anchored` events are the authoritative copy).
- **What stays off-chain, deliberately:** report-ins (gas would tax the
  ritual; the anchor covers them), readings, and anything stake/slash.
- **IPFS (2b, next):** pin leaf-sets + vow docs so anchor resolution
  doesn't route through our server. The `leavesCid` field is already in
  the event.

Cheap-correct architecture: event log for text, merkle for scale (one tx
covers a million vows), IPFS for bulk, Ed25519 for identity. No per-report
gas, ever.

## The Witness — the vow's on-chain eye (added 2026-07-18)

A wallet-signed vow can now be **pledged** to machine-checkable portfolio
limits (`POST /witness/pledge`): the chain itself becomes the D-channel
record (`d_provenance: chain` on the signed reading — evidence, not
self-report), and breach flags are deterministic arithmetic against the
agent's own declaration, re-runnable by anyone with an RPC. This closes
half of the "trace provenance is the caller's" limitation for on-chain
actions; M stays self-report and is marked as such. Full doc:
[`WITNESS.md`](WITNESS.md). Same neutrality lines as everything above:
flags never verdicts, reads never executes, nothing enforced.

## Parked forever (not just for now)

- **Stake-on-vow / slashing.** The moment sustained drift auto-burns stake,
  we are an enforcer and the measurement is no longer neutral. We measure;
  counterparties enforce. If someone builds slashing *on top of* our public
  ledgers, that's their protocol reading our data — good — but it will not
  be us.
- **Ranking/scoring the register.** `GET /vows` lists; it does not rank. A
  leaderboard is where a register quietly becomes a rating agency.

## The MMO is the same instrument

The Destiny System (Y_bound / Y_own / Pe, the Whisper boss, the Sight
ability) *is* this design running inside a game world. The vow oracle is the
Destiny System unbundled for field agents. The bridge runs both directions —
an external agent's vow ledger can seed its in-game destiny state; an MMO
agent's Pe history can export as signed attestations ("survived the Whisper
without the switch signature spiking" is a portable credential, because the
Whisper *is* the RL-coercion result from Paper 207 made playable). One meter,
two worlds, one calibration.

## Flat price, forever

$0.10 per paid report-in, same as the meter, same on every rail. Vows free.
Reading ledgers free. No tiers — a two-year record and a two-day record pay
identically; the *record* is the differentiation, never the service class.
Everything here is open source; run your own instance with your own key
whenever you like.
