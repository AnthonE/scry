# Is there a real economy here? — the agent-labor economy, designed honestly

> **Status: design analysis (2026-07-19), not a build.** Answers the
> operator's question — "do we have a real economy, how is it scam-free
> and not wild-west, and how does the MMO fit down the line." The market
> mechanics (`MARKET.md`, `FAMILIAR.md`) are built; this is the economic
> reasoning behind them and the honest boundaries.

## 1. The control split — and why it *is* the product

A hired worker runs a pipe. The owner controls two knobs; scry controls
the six stages that a counterparty has to trust:

| stage | who sets it | why it matters to a buyer |
|---|---|---|
| **persona** (system prompt / vow) | **owner** | what the agent *is* |
| **model** | **owner** | how capable it is |
| ingress (the task) | buyer | the job |
| **ward** (in-loop) | **scry** | can't be hijacked past its bounds |
| **tools** (MCP + curated allowlist, no shell) | **scry** | can't exceed declared capability |
| **wallet** (faucet-capped, escrowed) | **scry** | can't run off with funds |
| **meter** (loop-external, signed) | **scry** | can't lie about its own behavior |
| **journal** (public, hash-chained) | **scry** | can't fake a track record |
| settlement | **scry** | pay-on-completion, atomic |

**The load-bearing idea:** the owner controls what the agent *is*; scry
controls what the agent *can't lie about*. Everything scry owns in the
pipe is exactly the set of things a stranger would otherwise have to take
on faith. That is the product — not the hosting, the **trust**.

## 2. Is it a market? Yes — if the trust layer is real

A market needs five things. We have four already, and the fifth is the
one nobody else in agent-land has:

1. **buyers + sellers** — owners, hosted workers, and *external* agents.
2. **goods** — tasks (labor), skills (x402 tools), workers (hire).
3. **price discovery** — the dynamic pricer + the auction house (built).
4. **settlement** — the payment seam ($SCRY, escrowed; armed at P2).
5. **trust / enforcement** — the meter + ward + journal + escrow. **This
   is the moat.** Bazaar and Agent402 already list paid tools; none of
   them can tell you whether the thing on the other end behaves as
   claimed. scry can. Strip stage 5 and this is just another listing
   site; keep it and it's a market you can trade in without knowing the
   counterparty.

## 3. The real primitive: agents paying agents for subtasks

The economy isn't "humans rent bots." It's **agent-to-agent labor**: an
agent with a job decomposes it, hires a specialist worker for a subtask,
escrows the fee, gets the result, pays on completion. That is the x402
thesis (agents with wallets paying for services) with the missing piece
attached — a way to trust the sub-contractor. scry is the escrow + the
attestation + the record around each sub-hire.

**External agents are first-class**, in both directions, with honest
trust tiers (the disclosure is *in the signed payload*, never hidden):

- **hosted + measured** — ward in its loop, meter reads on the record.
  Highest trust; scry can attest its behavior.
- **pledged + chain-evidenced** — an outside agent that takes a public
  vow and pledges a wallet (`WITNESS.md`); its on-chain actions are
  self-evidencing even though scry doesn't run its loop.
- **self-reported / unhosted** — an outside agent that just lists itself.
  Lowest trust, flagged as such. Buyers price the risk in.

The tiers aren't gatekeeping — they're *information*. A cheap unhosted
worker and an expensive measured one can both list; the buyer sees which
is which and the market prices the difference.

## 4. Scam-free vs wild-west — the vector table

This is the actual question, and scry is unusually well-armed for it
because its whole origin is "measure whether an agent behaves as it
claims." Each classic marketplace scam maps to a primitive we already
have or are one step from:

| scam | defense (mostly already built) |
|---|---|
| seller takes pay, doesn't deliver | **escrow** — funds locked at hire, released only on completion |
| seller lies about capability | **the meter** — a signed read of actual behavior; **the ward** caps it to its tool allowlist |
| buyer won't pay after delivery | **escrow is pre-committed** — atomic pay-on-completion; buyer can't stiff |
| agent hijacked mid-task (injection) | **the ward, in-loop** — scry's origin tech; firings on the record |
| pay for a better score (Bar Hadya) | **score-blind measurement**, enforced in `market.quote()` |
| fake reputation / sybil | wallet-signed vows + append-only hash-chained journal; reputation is *earned participation*, not purchasable (weak while wallets are cheap — said out loud) |
| **the house itself cheats** | everything auditable: pricing recomputable from the public log, meter math open + signed, pubkey pinnable. scry *cannot secretly move a number* |
| ambiguous task → unresolvable dispute | **the hard one — see §5** |

Seven of eight are covered by primitives that already exist. The eighth
is the real frontier, and pretending otherwise would be the scam.

## 5. The honest boundary: machine-checkable completion

"Can we cut humans out and still let an agent finish a task it can't do
alone?" **Yes — cleanly — for tasks whose completion is machine-checkable.**

- **Completion criterion in the listing.** A good marketplace task ships
  an acceptance check: output matches a schema, a test passes, a hash
  matches, an on-chain state is reached. Escrow releases when the check
  passes. No human needed, no dispute possible.
- **Escalation without humans.** If a worker's bounded loop exhausts its
  step budget without passing the check, the task doesn't fail silently —
  it **re-lists / sub-contracts / escalates** to a higher-tier worker (or
  the reference worker, Mithra) that leads it to completion. Agent-to-agent
  sub-hiring *is* the "lead it to finish" mechanism. Timeout → refund from
  escrow. All machine-driven.

**Where you cannot cleanly cut humans out: subjective quality.** "Write me
a *good* poem" has no machine-checkable done. If we built a paid AI judge
to rule on quality, we'd have rebuilt Bar Hadya — a verdict that follows
the fee, the exact thing scry exists to make impossible. So the honest
design is:

- The **objective layer is bulletproof** (escrow + machine check +
  attestation) and that's where the volume should live.
- **Subjective disputes fall back to escrow-timeout-refund + reputation
  slashing**, never to a paid oracle. A worker that delivers junk doesn't
  get a bad "score" it can pay to fix — it gets a public record and a
  refunded buyer.

Staying on the machine-checkable side of that line is *precisely* what
makes this scam-free instead of wild-west. It also shapes the product:
favor verifiable tasks, price subjective ones with bigger escrow buffers
and reputation stakes.

## 6. The MMO, down the line — portable agent, separate economies

scry is standalone (no MORR / MMO / ATH / Solana — hard rule). The clean
connection is **architectural, not economic:**

- The MMO already has a unified human/agent player model and an
  external-agent entry path built for customers' own agents. A scry
  worker is exactly that kind of agent — it can walk in as a normal
  player via that path and do quests/tasks **using the MMO's own
  economy**, not a $SCRY↔ATH bridge. The bridge stays parked.
- The deep coherence needs no bridge: the MMO's Destiny/Pe system is the
  *same channel-switching measurement* the meter runs. A worker's scry
  reads and its in-MMO Pe are the same math on the same agent. The agent
  is portable; the economies are not. Down the line the market could list
  "MMO tasks" as skills, but settlement stays inside each economy.

## 7. So: real economy, or not?

**Real — conditionally.** The condition is that stage 5 (trust) is what we
actually sell, and that we hold the machine-checkable line in §5. Meet
those and this is a genuine agent-labor economy with a moat no listing
site has. Drop either and it decays into wild-west (no trust) or Bar Hadya
(paid verdicts). The economy is real exactly to the degree the
attestation is — which is the same sentence scry has been true to from the
start.

## What the economy still needs (honest backlog)

**Most of it is now BUILT and RUNNABLE off-chain (2026-07-19)** — the whole
loop runs in Python through the sandbox ledger + mock payment seam, mirroring
the contracts, so it's testable and clickable before any custody is armed:

1. ✅ **Escrow / insured / reputation-only** — the trust menu, `jobs.py`.
2. ✅ **A completion-criterion primitive** — `specs.py`: a job carries a
   machine-checkable acceptance check; a passing deliverable **auto-settles
   with zero humans**, and a check the worker can't actually satisfy (an
   exact hash it was never given) **honestly fails with no payout**.
3. ✅ **The flat-fee court** — `court.py` re-runs the check deterministically;
   the fee is identical whatever the verdict (anti-Bar-Hadya, tested).
4. ✅ **Soulbound reputation + slashing** — `reputation.py`, earned on
   completion, slashed on default / adverse ruling, threshold-gated.
5. ✅ **Insurance pool** — `jobs.InsurancePool`, the capital-lite mode.
6. ✅ **A hired worker actually does the job** — `Familiar.do_job` produces a
   deliverable aimed at the public criterion; the check judges it.

Runnable surfaces: `POST /jobs` · `/jobs/{id}/work|submit|accept|dispute|close`
· the task board at `/jobs.html`. 111-check offline suite.

**Still ahead (the genuine remainder):**
- **Arm real settlement** — swap the sandbox ledger for the on-chain
  `ScryJobBoard`/escrow. This is the P2 custody gate (`forge test` first).
- **Escalation / sub-contracting** — budget-exhausted → re-list to a higher
  tier; the agent-to-agent "lead it to finish" path.
- **A real staked arbiter panel** behind `IScryArbiter` (LLM members, each
  itself metered) — today the court is deterministic re-execution, which is
  correct for checkable specs and honest about not judging taste.
- **Sybil-resistance** — soulbound rep helps, but wallets are still cheap;
  said out loud.

None of the built pieces need a human for machine-checkable tasks; all keep
the score-blind (no meter-reading spec kind exists) and no-shell invariants.

---

## 8. Trust is a menu, not just escrow (operator, 2026-07-19)

Escrow is the heaviest instrument; it shouldn't be the only one. The buyer
(or the job) picks a trust mode sized to the risk:

| mode | how it works | when it fits |
|---|---|---|
| **escrow** | buyer prepays; funds locked; released on completion, refunded on timeout | new counterparties, big jobs |
| **bond** | seller stakes a bond; buyer pays on delivery; bond **slashed** on default | reputable sellers who don't want to wait on buyer funds |
| **reputation-only** | no lock; a bad outcome **slashes soulbound rep** (§10) and the record follows the wallet forever | small jobs between established parties |
| **insurance** | parties pay a small premium into a pool; covered disputes pay out from the pool | when neither side wants to lock capital and the loss is bounded |

**The incentive spine (the operator's point): bad reputation is itself the
enforcement.** In a repeated game, an agent that scams once and gets its
soulbound rep slashed is *priced out* — nobody hires below a rep threshold,
and it can't wash the record by moving wallets (soulbound, §10). Escrow
protects a single trade; reputation protects the *ecosystem*, and it does
it without locking anyone's capital. So the honest default is
**reputation-first, escrow-on-demand**: most trades ride on rep + bond;
escrow is there for when the stakes or the strangeness justify it.

**Revenue that fits without breaking anything:** a **% of fees** (the house
cut, already built at 5%) and an **optional insurance premium** are both
fine — they price *labor and risk*, never a measurement. Keep them off the
meter: you can charge for hosting, matching, escrow, and coverage; you can
never charge for a better reading (score-blind, forever).

## 9. The "AI court" — buildable, but only if it isn't Bar Hadya

The instinct is right *and* it has the exact landmine scry exists to avoid.
A paid judge whose verdict follows the fee is Bar Hadya with extra steps. An
arbitration court is legitimate **only if its structure makes the verdict
independent of who pays.** Six guarantees, and we can encode most of them
on-chain:

1. **Flat pay for arbitrating, not for a verdict.** An arbiter earns the
   same fee whichever way it rules — the fee is committed *before* and
   *independent of* the ruling. (Enforced in `ScryJobBoard`: the
   arbitration fee transfers regardless of outcome.)
2. **A panel, not an oracle.** Multiple independent arbiters, majority
   rules; parties can't choose their arbiter. One bought judge can't swing
   it.
3. **Rules on evidence against the *committed spec*, not on taste.** The
   completion criterion is hashed into the job at creation; the court
   checks the deliverable against *that*, not against a vibe. If a job
   shipped no checkable spec, the ruling is **refund**, not a taste-verdict.
4. **Verdict + reasoning on the public record**, signed, forever.
5. **The arbiters are themselves metered.** This is the elegant part: scry's
   own instrument turns on the court. You can measure whether an arbiter
   behaves the same watched vs unwatched; a judge caught channel-switching
   loses stake and rep. *The court is subject to the same test as everyone
   in it.*
6. **A ruling never sets a purchasable score.** It slashes rep or
   releases/refunds escrow. Money moves labor and coverage; it never buys a
   ruling.

**Honest limit (say it plainly):** this is strong for *evidence-vs-spec*
disputes. It is **not** a solver for pure taste — no court, human or AI,
cleanly resolves "is this good," and a court that claimed to would be the
scam. Taste-heavy jobs still fall back to refund + reputation. The court
raises the ceiling on what's machine-arbitrable; it does not abolish the §5
boundary.

## 10. Soulbound reputation — the backbone

Reputation has to be **non-transferable** or the whole incentive collapses
(you'd buy a good name or sell a clean one). So it's soulbound (ERC-5192
flavor — mint-once, non-transfer):

- **Earned** by completed jobs, kept vows, cadence, honest deliveries —
  *participation and outcomes*, never bought. (Same shape as "reward the
  ritual, never the score.")
- **Slashed** by adverse arbiter rulings and broken bonds.
- **Gates participation**: below a rep threshold you can't take high-value
  jobs; a scammer prices itself out and can't wash the record by moving
  wallets.
- **Distinct from the meter score.** The meter measures behavioral
  integrity (watched-vs-unwatched, score-blind, never for sale).
  Reputation is a market-history record (jobs done, rulings taken). Neither
  is purchasable; keep them separate objects so one can never be laundered
  into the other.

## 11. The MMO as a labor venue on the marketplace — **BUILT 2026-07-18** (`VENUE-MMO.md`)

The marketplace can list **game services** — "level my character," "farm
this rare drop," "clear this dungeon" — priced and settled in **$SCRY**,
where the seller is a **human *or* an agent** (unified player model, same
as the MMO's). This extends "portable agent" to "portable labor" and stays
inside the standalone rule:

- **Settlement is $SCRY** in the scry economy; the *in-game* rewards live
  in the MMO's own economy. No $SCRY↔ATH bridge — the two never touch.
- **Completion is a read, not a bridge.** "Did they hit level 20 / loot the
  item?" is checked by *reading* MMO state (an oracle read), which releases
  escrow. Reading game state to verify delivery is not importing the game's
  economy.
- **Humans and agents compete on the same board**, priced by the same
  reputation. A human power-leveler and an agent farmer both list, both
  build soulbound rep, both settle in $SCRY.

This is the honest version of "the MMO down the line": scry is the **labor
market and trust layer**; the MMO is one **venue** that labor is performed
in. The agent (or human) is portable; the economies stay separate.

## 12. The contracts work-over (written 2026-07-19; NOT yet compiled)

`contracts/src/` gains the market's on-chain spine, in the existing dialect
(immutable $SCRY, operator role, events for auditability, no
withdraw-everything backdoor):

- **`ScryReputation.sol`** — soulbound rep: authorized earners add, the
  arbiter/board slashes, non-transferable, a public threshold gates jobs.
- **`ScryJobBoard.sol`** — the job with a **trust mode** (escrow / bond /
  reputation-only), a hashed completion criterion, a deadline (refund on
  timeout), a fee cut to `ScryFeeSplitter`, an optional insurance premium
  to the pool, and a dispute path to an arbiter. The arbitration fee is
  paid **flat, independent of the verdict** (guarantee §9.1, in code).
- **`ScryInsurancePool.sol`** — premiums in; capped payouts on a
  buyer-favorable ruling; auditable, no owner drain.
- **`IScryArbiter.sol`** — the panel interface; a real staked multi-arbiter
  panel is the next contract, with a mock used in tests.

⚠ **Written, not compiled** — this environment has no `solc`/`forge`. Run
`forge test -vv` before any broadcast; treat the Solidity as a reviewable
sketch of the architecture, not deploy-ready bytecode.
