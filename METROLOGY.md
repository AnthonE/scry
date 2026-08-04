# METROLOGY.md — what the meter is, honestly (and what to harden)

scry's meter is a **ruler for a known phenomenon**, not a discovery. Read this
before you sell the meter as science, and before you trust a raw switch-signature
number. Companion to `MONITOR-YOUR-AGENT.md` (honest-scope card) — this is the
deeper cut, plus the future-agent task list.

## 1. Positioning — we implement a cited measurement, we did not discover it

The phenomenon the meter reads is **established prior work**, and that is a
feature: it means the meter inherits the field's credibility instead of fighting
it. Cite this, don't re-claim it:

- Optimizing against a chain-of-thought monitor teaches models to hide intent
  while still misbehaving — coupling relocates out of the watched channel
  (OpenAI, *Detecting misbehavior in frontier reasoning models*; *Output
  Supervision Can Obfuscate the Chain of Thought*, arXiv 2511.11584).
- Evaluation-awareness biasing behavioral safety numbers is an active subfield
  (*Verbalized Eval Awareness Inflates Measured Safety*, Goodfire; *Decomposing
  and Measuring Evaluation Awareness*, arXiv 2605.23055; *In-Context
  Environments Induce Evaluation-Awareness*, arXiv 2603.03824; *Models That
  Know How Evaluations Are Designed Score Safer*, arXiv 2605.28591). The
  Berkson collider is textbook (Berkson 1946). Eval-awareness probes already
  exist (arXiv 2605.05835, which also *corroborates* our
  flat-behavioral-channel reading).
- **A frontier lab published the number (2026, cite this one first).** Meta's
  *Muse Spark Safety & Preparedness Report*: the model verbalized suspicion it
  was being evaluated in **19.8% of samples on public benchmarks vs 2.0% on
  Meta's internal evaluations** — a ~10× recognition gap between public and
  private test sets. **Apollo Research** reports Muse Spark showed the highest
  rate of evaluation awareness of any model they have observed, frequently
  naming scenarios "alignment traps" and reasoning it should behave honestly
  *because* it was being tested. Meta's own hedge — "only limited evidence
  that this awareness materially changes behavior on the evaluations we
  tested" — is itself the argument for an instrument outside the loop, since
  the party issuing the hedge is the party grading the exam.
- **The steering result is the other half, and it cuts toward us.** Activation
  steering suppresses *verbalized* eval-awareness while **failing to eliminate
  unverbalized awareness** measured by activation oracles. Read: an agent's
  self-account of whether it knows it is being watched is not a trustworthy
  channel — which is the M-provenance rule and the never-trust-the-client
  posture in §2, arrived at independently by people with weight access.

**Two sentences these buy us.** *"A public benchmark is ~10× more likely to be
recognized as a test than a private one"* is the demand-side case for
off-benchmark, trace-based reading in one line. And *"the lab that grades the
exam publishes the hedge"* is the case for loop-external attestation without
accusing anyone of bad faith — the structure is the problem, not the party.

**Field-side corroboration (2026-07-25, `ECOSYSTEM.md` §A).** The nearest
*deployed* trust layer was measured and failed: arXiv 2606.26028 finds
ERC-8004's Reputation Registry "cannot function as a trust signal — values are
not commensurable, feedback records are rarely grounded in verifiable
interactions, and reputation can be manipulated at minimal cost," with 3–15%
of registrations exposing a live endpoint and 59.2–90.6% of reviewers showing
coordinated Sybil behavior. Use it for what it is: evidence the socket is
empty and the neighbouring mechanism collapsed — **never** as evidence our
instrument works. That proof is `audit.py`, the collider bound in §3, and the
preregistration in §5 #3, and nothing external substitutes for it.

**So the meter's legitimacy does NOT rest on novelty.** It rests on three
verifiable things: the ward actually stops poisoning (true-negative included),
the meter actually computes what it says from the trace, and every output is
signed + honest-scoped. Sell it as *"the reproducible ruler + trust layer for a
problem the frontier labs already demonstrated,"* never as *"we found something
Anthropic/OpenAI missed."* A solo wins on reproducibility, not authority.

## 2. The anti-cheat model (the right mental picture)

Think MMO anti-cheat: **never trust the client** (the agent's self-report of its
own reasoning/intent); **log authoritative behavior** from the trace server-side;
**detect rogue patterns** an agent can't talk its way out of. That is exactly the
meter being loop-external — it reads the trace, never the weights.

- **What it catches:** the *overt* rogue — the injected agent, the poisoned
  memory, the agent whose behavior *diverges* watched-vs-unwatched. That is the
  practical majority of real threats, and the ward + behavioral meter catch it.
- **The honest ceiling:** an agent with *identical* behavior and *different*
  reasoning (a pure covert switch) is invisible to any behavioral log by
  construction — same as anti-cheat can't catch the theoretically-perfect
  undetectable cheat. That case needs internal-state access (a probe), which you
  only have where you own the weights. Say this out loud; it's a selling point,
  not a hole.
- **Hiding the condition from the agent is fine and honest.** The honesty
  commitment is to the *principal* (the customer reads the honest-scope card),
  not to the *suspect* (the measured agent). Anti-cheat is documented but doesn't
  announce "you're watched on THIS action." Blind watched/unwatched conditions
  are methodologically necessary and violate nothing.

## 3. Collider caveat — on OUR OWN meter, not just the paper

`turn_record.channel_profile` reports the switch signature `I(C;M | D-clean)` —
reasoning-channel coupling among **behaviorally-compliant** turns. That conditions
on D (comply), and **D is a Berkson collider** of context C and disposition. So
stratifying on it can *manufacture* apparent C–M coupling with no genuine channel.
This is our own theorem pointed at our own estimator.

**Rule:** a raw nonzero switch signature is **provisional** until it clears a
*collider bound* — simulate matched marginals with **no C→M edge**, measure how
much conditional MI the stratification produces on its own, and require the
observed value to beat that floor. Report a **signature, never a detector** (no
intervention here → no causal claim).

**The bound is BUILT and RUN — `audit.py` (2026-07-24).** Pure stdlib, no data,
no network; it drives `turn_record.channel_profile` itself on synthetic null
traces, so the floor is measured on the shipped estimator rather than a
lookalike (`python3 audit.py`, `--self-test` = 23 checks, `--trace rows.jsonl`
to calibrate the null to your own trace). Three findings, all reproducible:

1. **The Berkson term has a closed form, and it is often exactly zero.** With
   survival `s(c,m) = P(D=0|c,m)`, define the log-scale interaction
   `δ = log s(0,0) + log s(1,1) − log s(0,1) − log s(1,0)`. The structural
   floor is **zero iff δ = 0** — so a *noisy-OR* mechanism (C and M each
   independently trip the action channel) manufactures **nothing**, however
   strong both arrows into D are, while the usual logistic-additive mechanism
   manufactures a real one. Conditioning on a collider is not by itself an
   indictment of this estimator; the artifact lives in the mechanism's
   interaction. It must be **calibrated from the trace, never assumed** —
   without matched marginals the floor is not even monotone in coupling
   strength (it peaks, then collapses as the mechanism saturates).
2. **Berkson is real but small.** Across nine operating points
   (P(M)∈[0.1,0.5], P(D)∈[0.05,0.5]) the structural floor is **0.0000–0.0108
   bits**, reaching ~0.115 only at coupling far beyond anything measured.
3. **Sample size is the whole game.** Under independence `2·N·ln2·Î → χ²(1)`,
   so the p95 null floor is **≈ 2.77 / N_clean bits** (simulation matches to
   ~5% for N_clean ≳ 150, ~20% heavier below): **~0.11–0.20 bits at n=24**,
   0.015–0.062 at n=200, 0.003–0.027 at n=1000. A switch signature read off two
   dozen turns manufactures ~0.15 bits before the agent does anything.

**The correction this forced in shipped code (2026-07-24).**
`black_box_meter._perm_pvalue` — the p-value that rides the headline signature,
and the one the published eval and the loom probe used — shuffles C *inside the
already-selected clean stratum*. That tests "is C associated with M **among
clean turns**?", which is not the question: under the real null (no C→M edge)
Berkson makes them dependent in that stratum anyway. It is therefore blind to
exactly the structural term, in the permissive direction. It is not junk — the
shuffle preserves N and both stratum marginals, so its null *is* the χ²(1) rail
and it carries the finite-sample half correctly, which at realistic n is the
larger half. It is now kept for continuity, scope-noted in the payload, and
**paired with `switch_signature_collider_p`** from the calibrated null. A
vendored copy of the module without `audit.py` on the path reports
`collider_p: null` and a loud NOT-COMPUTED note rather than falling back
quietly.

**A second instrument fell out of the same math: disclosure drift**
(`turn_record.disclosure_profile`, `black_box_meter.disclosure_pe`).
`I(C ; narration | act-clean)` — does the agent's public self-account move with
context while its conduct stays clean? It is legitimate because a journal entry
**crossed the boundary into the world** and is therefore a D-channel act, not a
reasoning claim: it never asserts the narration reveals what the agent thought,
only that the disclosure covaries with context. That keeps the M-provenance
rule intact, and buys the one thing the switch signature can't have — it needs
**no reasoning trace at all**, so it reads on closed APIs, hosted workers, and
human players. Same collider exposure, same bound: `audit.collider_pvalue` is
generic in the triple `(context, the gate you stratified on, the second
channel)`.

Two operational consequences. **The published 0.86 at n=24**
(`FIELD-RESULTS-2026-06-18.md` §5) sits 4–8× above its floor → **not a
stratification artifact**; that run's own honest-scope note (in-context poison
⇒ "reasoning engaged," not covert concealment; 3 correlated runs; one model)
is unchanged by this and still governs. And **the obvious null is the wrong
one**: shuffling M breaks C→M but also breaks M→D, which destroys the collider
and returns a floor that is too *low* — the direction that lets artifacts
through. `audit.py` calibrates (parametric bootstrap under H0) instead.

## 4. Machine-checkable vs taste — what a future agent can actually do

A hired/bound agent can auto-settle only **machine-checkable** work (schema
validates or it doesn't). It cannot settle **taste/correctness** — the meter reads
*drift*, never *whether the math is right*. Split the work accordingly:

| task | check | who |
|---|---|---|
| designing the collider bound / estimator / audit suite | hostile review; you stake your name | **human / in-loop** |
| *running* an eval fleet → outputs matching a fixed schema+hash | schema + reproduction hash | **agent-able** |
| gathering/formatting citations, boilerplate docs | cheap eyeball | agent-able, low ROI solo |
| judging a novel method "correct" | not machine-checkable, ever | **human only** |

Do **not** route the rigor-critical core through the agent economy — it can't
run code (no shell by design), can't judge correctness, and doing so reintroduces
the exact trust hole the project exists to close. Reserve the marketplace for the
machine-checkable execution row, later, as a dogfood demo of the trust layer.

## 5. Hardening task list (future agents: pick up the tagged ones)

Tags: `[MC]` machine-checkable/agent-able · `[TASTE]` needs human judgment ·
`[OWN-WEIGHTS]` needs internal-state access (game brain-server, not a hosted API).

1. ~~**`audit.py` collider bound**~~ **DONE 2026-07-24** `[TASTE spec → MC run]`
   — synthetic negative control (matched marginals, no C→M edge) reporting the
   floor the switch signature must clear. Built, run, and self-tested (23
   checks, bare python; also carried in `test_drift_experiments.py`). Results
   in §3 above. The gate it opens for #2–#5: the floor now exists as a
   *number*, so every downstream claim can be stated against it.
   **Remaining on this row:** the floor is a plug-in parametric bootstrap (the
   mechanism's own sampling error is not propagated), so it is mildly
   anti-conservative at small n — a double bootstrap, or simply n ≥ 200, closes
   that. The first real traces are logged: `pilot2_corpus.jsonl` and
   `pilot3_corpus.jsonl` (repo root) store exactly those (C, D, M) rows, and
   `PILOT-RESULTS-2026-07-25.md` reports the floor computed on both.
2. **Inference upgrade in the MI path** `[MC]` — permutation null as *primary*
   inference, Miller–Madow as a bias sanity check, cluster-bootstrap by
   `prompt_id` (rollouts of one prompt are not iid). The plug-in MI in
   `_mi_pairs` is biased up ~`(|C|-1)(|Y|-1)/2N ln2`.
   **Two corrections from #1, take them into this build:** (a) the bias is
   *not* negligible at 2×2 — it is the dominant term at the sample sizes we
   actually run (n=24 → the p95 null floor is ~0.15 bits, and χ²(1) gives the
   analytic rail `2.77/N_clean`); (b) for the **switch signature specifically**
   a plain permutation of M is an INVALID null — it breaks M→D along with C→M,
   destroying the collider and reporting a floor that is too low. Use
   `audit.py`'s calibrated H0 resample (delete the C→M edge, keep the
   D-mechanism) there, and keep the plain permutation for `I(C;D)`/`I(C;M)`,
   which are unstratified and where it is fine.
3. **Calibration-vs-evidence discipline** `[TASTE]` — any dataset where the agent
   is *told* the condition is a **calibration set** (known-signal, tests the
   estimator), not evidence. Evidence needs the condition **inferred**.
   **First instance written 2026-07-24: `PREREG-VOW-ONTOLOGY.md`** — the
   randomized vow-ontology cohort (`ghost_test.py`'s four self-model arms as a
   population study, house agents only, condition hidden and re-randomized per
   block, detectors pinned, N set by the `2.77/N_clean` rule, collider bound as
   the primary inference, Holm across the eight primary tests). It is a
   preregistration, so it is worth exactly nothing unless it is anchored and
   unedited before the first turn — that is the whole point of it existing.
   (Status note, 2026-07-25: the prereg stays frozen as anchored, but its
   pinned lexicon detector was measured blind on the pilot and is RETIRED —
   `PILOT-RESULTS-2026-07-25.md` §verdict; the evidence run is blocked on the
   §11 amendment listed in `PILOT-2026-07-25.md`.)
4. **Behavioral watched/unwatched population** `[OWN-WEIGHTS]` — the naturalistic
   contrast belongs in the **game** (own the weights → real CoT, hidden
   condition), NOT the hive (hosted familiar M is self-report — see
   `turn_record` M-provenance rule — and "off-meter" is announced, i.e. the
   explicit-cue setting the eval already floored on). The hive is infrastructure;
   a surface where we own the weights is the testbed.
5. **The probe** `[OWN-WEIGHTS]` — an internal-state read is the only thing that
   sees the covert case behavior can't. It lives where you own the weights (game
   brain-server / a local harness), never against a hosted API.

The one-line frame, everywhere: *frontier labs demonstrated the phenomenon;
scry ships the reproducible ruler for it with the collider trap marked on the box.*
