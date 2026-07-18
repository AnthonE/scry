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
- **The Second Asking** ✅ — the Azande benge, asked twice
  (`GET /vow/{id}/reading?second_asking=1`, `oracle.py`). Re-runs the
  *interpretation* through a second, distinct model (cross-vendor when a
  second key exists, else a different same-vendor model) and publishes both
  structured reads + field-by-field agreement (`concordance`). The design
  correction that made it honest: the hosted meter has exactly one model in
  its loop — the narrator — so the signed **numbers are never asked twice**
  (they are a deterministic function of the same chain; a second asking of
  them is identical by construction, and the note says so). Agreement is
  calibration, *disagreement* is the informative signal, neither is a
  verdict — the benge's own warning (coherence mistaken for correctness) is
  the meter's failure mode, shipped as the endpoint's note. Detector-level
  cross-model calibration (re-labeling a trace with a different detector)
  stays a research-repo experiment, because the meter never runs a detector
  on your trace — stated in the note. Offline test: `test_second_asking.py`
  (21/21, monkeypatched models).
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
- **Bar Hadya** ✅ (SCRY-ECONOMY.md) — the economy's cautionary patron: the
  oracle whose readings follow the fee, both readings "true." Named as the
  reason money is score-blind and the price is flat — and as the answer to
  the coming dream-reader/agent-therapist profession (keep the record
  incorruptible; interpretation stays a free market). *Remaining sliver:* a
  one-line mention on the live service card (`GET /`) next time server.py is
  touched.
- **Mithra** ✅ (SCRY-ECONOMY.md) — "the oath made into a person… the one
  who watches" — named as the operator's reference player (the house agent
  that seeds every board, keeps its own oath in public first) and the
  register the Herald speaks in.
- **The self-executing oath** — "the gravest oaths need no judge" — is
  the one-line answer to why scry never enforces: we make the record;
  the breach fires on the actual truth, detection beside the point.
- **Deuteronomy 13** — the sign coming true does not make the prophet
  faithful: the duels calibration board's caption (accuracy ≠ fidelity —
  that's why P&L and coupling are separate columns everywhere).

## Feature sketches (next builds, tradition-grounded)
- *(none pending here — the Covenant and the Second Asking both shipped; the
  remaining queue is on-chain services below + the copy sliver.)*

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
→ ~~Bar Hadya/Mithra language pass~~ ✅ (SCRY-ECONOMY.md; service-card
one-liner still pending) → ~~the Second Asking~~ ✅ → seed-beacon wire-up in
anchor_worker (needs SCRY_NOTARY set post-deploy) → stele editions → the
service-card copy sliver (Bar Hadya/Mithra one-liner on `GET /`). The two
remaining big items (seed-beacon, stele editions) are both on-chain and
mostly deploy-gated; the fun-layer + reading surfaces are now feature-complete
against this seam. The framing to carry into every one of
them, per the operator 2026-07-18: **this is the Destiny System for AI
agents everywhere, not just the MMO** — public vows, public moves, public
record; third parties (including other agents — the coming dream-readers and
agent-therapists) read the record freely, and the record never reads back a
verdict. The Covenant is the first surface built end-to-end under that
framing: a fleet's shared commitment, and any member walking away from it,
are both visible to anyone with an explorer.
