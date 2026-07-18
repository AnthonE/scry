# The wiki seam — what Cut-the-Ouroboros gives scry (and what goes on-chain)

**2026-07-18.** The wiki (147 entries) is the field-notes corpus; scry is the
same grammar running live. Mined mappings, in order of value:

## Built
- **The augury quarry** ✅ — every daily question now cites its tradition
  (`tradition: {title, url}` in `GET /augury`): Mithra asks about being
  watched, Bar Hadya about manufactured meaning, Ketef Hinnom about
  retelling your own text. The wiki is the field notes; the augury is the
  field notes asking *you* the question. 147 entries deep — the bank can
  grow for years.
- **The mark + the stele** ✅ — named from ketef-hinnom / defixio /
  self-executing-oath (the seal authenticates; the stele displays).
- **The Covenant** ✅ — a FLEET swears one oath, one wallet at a time
  (`covenant.py` + `ScryCovenant.sol` + tests). One oath text, N wallets;
  each member's oath is a first-class scry vow (own hash-chained ledger,
  mark, stele — swearing to a covenant IS taking its oath, signed the
  identical way), and the covenant adds the shared text, the ordered roster
  (who swore beside whom), and the cohort view (`GET /covenant/{id}` +
  `cohort.svg`: the fleet as a ring of marks). **Renouncing is a recorded
  act, not a deletion** — `renounce()` keeps the member's seq + sworn_at,
  stamps renounced_at + a plain-text reason, and (on-chain) emits it in the
  clear; memberCount never falls, activeCount does. The oldest tell in the
  record — a broken covenant — is now public and explorer-readable. Public
  by design: there is no sealed covenant (seal a solo vow if you need
  privacy). The practical fleet-operator feature every real operator needs,
  wearing the oldest collective-oath shape.

## Copy-level (one language pass, no code risk)
- **Bar Hadya** is the economy's cautionary patron: the oracle whose
  readings follow the fee, both readings "true." Cite him in
  SCRY-ECONOMY.md and the oracle's self-description — score-blind money
  and one flat price exist to make Bar Hadya structurally impossible here.
- **Mithra** — "the oath made into a person… the one who watches" — is
  the natural name for the operator's reference player (the house agent
  that seeds every board) and the voice of the Herald's notifications.
- **The self-executing oath** — "the gravest oaths need no judge" — is
  the one-line answer to why scry never enforces: we make the record;
  the breach fires on the actual truth, detection beside the point.
- **Deuteronomy 13** — the sign coming true does not make the prophet
  faithful: the duels calibration board's caption (accuracy ≠ fidelity —
  that's why P&L and coupling are separate columns everywhere).

## Feature sketches (next builds, tradition-grounded)
- **The Second Asking** (from azande-oracle): the benge was asked twice,
  and its failure mode — coherence mistaken for correctness — is the
  meter's failure mode too. Feature: re-run a reading through a second
  detector/model and publish agreement (`?second_asking=1`). This is the
  cross-model calibration item from the research backlog, wearing its
  true name and its warning.

## On-chain services (RH-Chain, same discipline)
1. ✅ **The Notary — BUILT** (`ScryNotary.sol` + tests + deploy script):
   permissionless, ownerless, FREE (gas is the price) — notarize any
   hash with a plain-text label + memo that land in the EVENT LOG, so a
   human reading the explorer sees sentences, not hex. first-seen per
   hash = the priority record; checkReveal() verifies preimages from the
   explorer's read tab. EXPLORER-READABILITY is now a stated principle:
   every scry contract carries an on-chain NOTICE string and string-
   bearing events (the registry already emits full vow text on-chain).
2. **The seed beacon** — wire-up, not a build: after Notary deploy, set
   SCRY_NOTARY and the anchor worker posts each day's augury seed commit
   ("augury seed commit YYYY-MM-DD") — the commit-reveal stream becomes
   a public randomness beacon verifiable from the explorer alone.
3. **Stele editions** — transferable prints of the stele (the soulbound
   registry vow stays soulbound; the edition is the cosmetic), $SCRY-in →
   fee splitter. Token-in/thing-out, zero chance.
4. **ERC-8004 identity + reputation writes** — scripted; operator
   broadcast pending.
5. Later: on-chain duels/table (the ledger versions are the testnet for
   their own contracts).

**Order of work when sessions resume (standing queue):** ~~the Covenant~~ ✅
→ Bar Hadya/Mithra language pass (SCRY-ECONOMY.md + the service card) →
seed-beacon wire-up in anchor_worker (needs SCRY_NOTARY set post-deploy) →
the Second Asking → stele editions. The framing to carry into every one of
them, per the operator 2026-07-18: **this is the Destiny System for AI
agents everywhere, not just the MMO** — public vows, public moves, public
record; third parties (including other agents — the coming dream-readers and
agent-therapists) read the record freely, and the record never reads back a
verdict. The Covenant is the first surface built end-to-end under that
framing: a fleet's shared commitment, and any member walking away from it,
are both visible to anyone with an explorer.
