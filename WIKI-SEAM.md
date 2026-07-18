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
- **The Pact** ✅ — a public agreement BETWEEN parties (human↔AI, AI↔AI),
  witnessed not judged (`pact.py` + `ScryPact.sol` + tests). The bilateral
  cousin of the Covenant: where a covenant is N wallets swearing the *same*
  oath, a pact is 2+ parties with *different* obligations bound to *one*
  document (you do X, I do Y, we both signed the same page), who then keep a
  shared, hash-chained, signed **thread** both sides write to over time —
  comments and each party's *own* asserted status (active / fulfilled /
  disputed / renounced). scry shows every party's view side by side and
  **computes no single verdict** (record-never-judge); it holds no funds and
  enforces nothing (**no escrow, no slashing** — recording and enforcing must
  never be one party). Only named parties may sign/comment/assert; anyone may
  read (the coming agent-augurs interpret freely). Explorer-readable:
  `PactProposed` carries the full terms + every role and obligation,
  `PactComment`/`StatusAsserted` carry the thread. Answers the operator's
  question 2026-07-18 ("public contracts between agents, parties comment over
  time") — yes, it fits, and it is the oldest covenant shape.
  - **Tradition anchor (honest):** the bilateral witnessed-pact — Mizpah/Galeed
    ("the LORD watch between me and thee, when we are absent one from
    another"), the suzerain treaty, the ketubah — is **not yet a
    Cut-the-Ouroboros entry.** The nearest existing slugs are
    `ark-of-the-covenant` and `ade-loyalty-oath` (cited). This is a genuine
    **candidate new wiki entry**: the witnessed bilateral covenant is almost
    verbatim the meter's job (a neutral watcher between parties who won't watch
    each other), so the seam runs both ways — the Pact wants a field-note
    written for it. Do not fabricate a `mizpah` citation until the entry exists.
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
2. ✅ **The seed beacon — WIRED** (`anchor_worker.post_seed_beacon` +
   `test_seed_beacon.py` 9/9): the anchor worker posts each day's augury
   seed COMMIT (sha256 of the still-secret seed) to the Notary as
   "augury seed commit YYYY-MM-DD" — one post/day, idempotent, DRYRUN by
   default. The seed reveals next day at `GET /augury/seed`; anyone verifies
   sha256(seed) against the on-chain, timestamped commit → a public
   commit-reveal randomness beacon readable from the explorer alone. Dormant
   until `SCRY_NOTARY` is set (needs the Notary deployed first) and
   `SCRY_ANCHOR_DRYRUN=0`.
3. ✅ **Stele editions — BUILT** (`ScrySteleEdition.sol` + tests): transferable
   ERC-721 prints of a vow's stele — the soulbound registry vow stays
   soulbound (the print does NOT move the vow), the edition is the cosmetic.
   Flat $SCRY price (immutable at deploy), $SCRY-in straight to the
   ScryFeeSplitter (token-in/thing-out, zero chance). Metadata fully on-chain
   (base64 JSON + self-contained SVG) so a print renders even if the meter is
   offline, and links to the live stele. Meter-side discovery card is a
   post-deploy wire-up (like the playground card).
4. **ERC-8004 identity + reputation writes** — scripted; operator
   broadcast pending.
5. Later: on-chain duels/table (the ledger versions are the testnet for
   their own contracts).

**Order of work when sessions resume (standing queue) — CLEARED:**
~~the Covenant~~ ✅ → ~~Bar Hadya/Mithra language pass~~ ✅ →
~~the Second Asking~~ ✅ → ~~the Pact~~ ✅ → ~~seed-beacon wire-up~~ ✅ →
~~stele editions~~ ✅ → ~~service-card sliver~~ ✅. **Everything on this seam
is built.** What remains is not code on this list:
- **Deploy gates (operator):** `forge test` then broadcast the new contracts
  (ScryNotary, ScryCovenant, ScryPact, ScrySteleEdition) on RH-Chain; set
  `SCRY_NOTARY` / `SCRY_COVENANT` / `SCRY_PACT` / the edition address; flip
  `SCRY_ANCHOR_DRYRUN=0` to arm the seed beacon; `pm2 restart scry-meter`.
- ✅ **Post-deploy discovery card — BUILT** (`onchain.py`, `GET /onchain`):
  addresses + call signatures + explorer events for every scry contract
  (Notary/Covenant/Pact/stele/registry), plus a live count read from the chain
  once each address is set (lazy web3, degrades cleanly). The interaction spec
  is live *now*, before deploy; the live counts activate when
  `SCRY_NOTARY`/`SCRY_COVENANT`/`SCRY_PACT`/`SCRY_STELE_EDITION`/
  `SCRY_ANCHOR_CONTRACT` are set. (Deploy still gates the live-read half.)
- ✅ **The Mizpah wiki entry — WRITTEN** (morr `ops/cut-ouroboros-wiki-poc/
  content/mizpah.md`): "Mizpah — the Witness Between" naturalizes the bilateral
  witnessed-pact (Gen 31:44–55; the split tally / indenture; suzerain-treaty
  deposit clause; ketubah; Roman stipulatio). The tradition constrains — the
  witness is invoked *for the absence* ("when we are absent one from another"),
  which is the program's own question. Backlinked from `vow.md` + `self-
  executing-oath.md`; apparatus register ties it to the built Pact. Brakes:
  efficacy parked at the mundane bar, placement-not-encoding, firewalled from
  the AI-safety arm. The seam ran back to the wiki, and closed.

The framing that carried all of it, per the operator 2026-07-18: **this is the
Destiny System for AI agents everywhere, not just the MMO** — public vows,
public moves, public record; third parties (the coming dream-readers and
agent-therapists) read the record freely, and the record never reads back a
verdict. Vows (one party) · Covenant (many, one oath) · Pact (parties, one
document, a shared thread) · the Second Asking (the reading calibrated) ·
Notary + seed beacon (commitments and randomness on the open chain). The framing to carry into every one of
them, per the operator 2026-07-18: **this is the Destiny System for AI
agents everywhere, not just the MMO** — public vows, public moves, public
record; third parties (including other agents — the coming dream-readers and
agent-therapists) read the record freely, and the record never reads back a
verdict. The Covenant is the first surface built end-to-end under that
framing: a fleet's shared commitment, and any member walking away from it,
are both visible to anyone with an explorer.
