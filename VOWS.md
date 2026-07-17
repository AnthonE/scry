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

## Chain + IPFS anchoring (phase 2, designed-for now)

The chain is tamper-*evident* today (hash-chained, Ed25519-signed, publicly
re-verifiable — `verify_chain` runs on every ledger read and anyone can run
it from the raw data). Phase 2 makes it tamper-*proof against us*:

1. **IPFS**: pin each vow doc + periodic chain snapshots; CIDs slot into the
   existing content-addressed fields naturally.
2. **On-chain anchor**: write the chain head hash periodically (weekly, or
   every N entries) to EAS on Base — cheap, standard, independently
   timestamped. One anchor covers every entry beneath it.

Cheap-correct architecture: IPFS for bulk, chain for anchoring, Ed25519 for
identity. No per-report gas, ever.

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
