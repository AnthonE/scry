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

1. **Escrow, armed** — funds locked at hire, released on a completion
   check. Today settlement is mock (no custody). This is the P2 gate.
2. **A completion-criterion primitive** — a task listing carries a
   machine-checkable acceptance check + escrow terms.
3. **Escalation / sub-contracting** — budget-exhausted → re-list to a
   higher tier; timeout → refund.
4. **Reputation + slashing** — earned from the journal, staked on jobs;
   the sybil-resistance the honest note flags as weak today.
5. **Dispute fallback** — refund-on-timeout, never a paid judge.

None of these need a human in the loop for machine-checkable tasks; all of
them keep the score-blind and no-shell invariants.
