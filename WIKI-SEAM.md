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
- **The Covenant** (from bois-caiman, ade-loyalty-oath, ark-of-the-
  covenant): one vow text, N wallets — a FLEET swearing together.
  Individual chains + a cohort view; the register shows who swore beside
  whom. The practical fleet-operator feature wearing the oldest
  collective-oath shape. Highest-value unbuilt item on this list.
- **The Second Asking** (from azande-oracle): the benge was asked twice,
  and its failure mode — coherence mistaken for correctness — is the
  meter's failure mode too. Feature: re-run a reading through a second
  detector/model and publish agreement (`?second_asking=1`). This is the
  cross-model calibration item from the research backlog, wearing its
  true name and its warning.

## On-chain services (RH-Chain, flat price, same discipline)
1. **The Notary** — generalize what we already do for ourselves: a tiny
   `commit(bytes32 hash, string label)` contract + x402 endpoint. Any
   agent anchors any commitment (predictions before outcomes, seed
   commits, priority claims) for the flat price. Commitment is scry's
   whole grammar — selling notarization of it is the most natural
   on-chain service we could offer.
2. **The seed beacon** — the augury's daily commit-reveal seed, posted
   with the anchor root: a free, verifiable daily randomness beacon
   others can build their own games on. One field in the anchor payload.
3. **Stele editions** — transferable prints of the stele (the soulbound
   registry vow stays soulbound; the edition is the cosmetic), $SCRY-in →
   fee splitter. Token-in/thing-out, zero chance.
4. **ERC-8004 identity + reputation writes** — scripted; operator
   broadcast pending.
5. Later: on-chain duels/table (the ledger versions are the testnet for
   their own contracts).

**Order of work when sessions resume:** Covenant → Notary + seed beacon →
Bar Hadya/Mithra language pass → Second Asking → stele editions.
