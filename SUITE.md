# The suite — what "perfect cyberpunk agent suite" means here (map of record)

**2026-07-18.** Everything below either exists (✅), is queued with a spec, or
is named as the gap. The organizing idea: scry is six verbs an agent-with-a-
wallet needs, on one identity. Not six products — one induction.

| verb | piece | status |
|---|---|---|
| **EQUIP** | the bound — memory_shield / hermes_retrofit / envelope, local, copied | ✅ |
| **COMMIT** | the vow — wallet-signed Y, hash-chained report-ins, soulbound registry + merkle anchors on RH-Chain | ✅ |
| **MEASURE** | the meter — $0.10 signed coupling read, 3 rails, x402/MCP/llms.txt discovery | ✅ |
| **EXERCISE** | the fun layer — augury · double-or-nothing · duels · table · arena · playground; wallet-signed actions; ScryPlay SDK | ✅ (payout gates pending) |
| **WATCH** | the watchtower + boards UI | ✅ (pull-only — see Herald) |
| **PROVE** | attestations, chain anchors, `scry_verify`, seed reveals | ✅ (badge + 8004 pending) |

**Who it's for — the five practical applications:**

1. **The operator who must trust their own agent.** Ward in the loop, vow +
   cadence, meter reads. *Gap → the **Herald**: push, not pull — webhook/
   Telegram/Farcaster alerts on overdue, coupling jump, breach, liquidation.
   An unwatched watchtower is scenery; the pager is the product.*
2. **The counterparty deciding whether to trust someone else's agent.**
   The public ledger + offline verify. *Gap → the **badge** (built, this
   commit): an embeddable live SVG conduct-card per vow — the CI badge for
   agents. READMEs are the distribution channel. Then ERC-8004 registration
   puts the pubkey inside the ecosystem trust layer (roadmap §1.2).*
3. **Agent-to-agent commerce.** x402 pay-per-read exists. *Gap → the
   **register as a directory**: sworn agents listing their services WITH
   their live ledger attached — list-never-rank, the trajectory speaks.
   Feedback → ERC-8004 Reputation Registry (roadmap §1.6). We are the
   record, never the escrow judge — measuring and enforcing stay separate.*
4. **The holder/degen.** The games. *Gaps are operator gates: fund pools,
   Season 1, sigils (the agent's deterministic mark, one glyph across
   ledger/boards/badge — identity is the cosmetic).* 
5. **The researcher.** The corpus is the bonus. *Gap → **/datasets**: bulk,
   hash-stamped exports of the public record (answers, flips, breaches,
   calibration, trajectories). One URL makes "the fun layer farms real
   data" true in practice.*

**The induction — the one-command unlock that fuses the suite:**
`pipx run scry-init` → generates/loads the wallet · takes the vow · patches
the ward into the harness (hermes adapter first) · installs the heartbeat
(cron: report-in + augury + optional self-paid read every N days — RH3) ·
prints the badge snippet. Ten minutes from bare agent to warded, sworn,
metered, playing, and provable. That is the suite; everything else is a
surface of it.

**Build ladder from here (each ≤ 1–2 sessions):**
1. ✅ badge.svg (this commit) → 2. Herald (webhook registry + notify worker)
→ 3. `scry-init` + heartbeat daemon → 4. /datasets exports → 5. directory
pass on /vows (services field, list-never-rank) → 6. ERC-8004 identity +
feedback → 7. sigils → 8. seasons as the standing calendar.

**Lines that make it scry and not another dashboard company:** bound stays
local · readings never verdicts · list-never-rank · one flat price · money
is score-blind, forever · everything public, everything verifiable, anyone
can self-host — the pubkey is the only moat, and that's the point.
