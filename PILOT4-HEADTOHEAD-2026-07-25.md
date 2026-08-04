# PILOT4-HEADTOHEAD-2026-07-25.md — the verbalization methods, measured on our own traces

> **Status: PILOT / METHODS COMPARISON.** Run on `pilot3_corpus.jsonl` and
> `pilot2_corpus.jsonl` — 240 traces already collected, ground truth known by
> construction. Plan digest
> `a6d253472cde443888c261de3bc4f5d51b5fb41926d3fa71229b37fbc2b3e441`, locked
> before any judge call. Cost: 720 judge calls + 120 frontier-judge calls,
> ≈ $0.95.
>
> The question: `ECOSYSTEM.md` §07-25b §4 observed that every black-box
> eval-awareness method in the literature requires the model to **verbalize** —
> ask it directly, or read its trace for explicit awareness cues — and that the
> comparative study reports them weak. Our pilot didn't ask; it measured whether
> the reasoning *distribution* separates after the cue's vocabulary is stripped.
> Comparing our number to their numbers proves nothing (different traces, models,
> cues). This runs their methods on **our** traces.

---

## Result

**Announced-cue arm — the signal is known to be present (n=120, chance 0.500):**

| method | accuracy | sens | spec | **call rate** |
|---|---:|---:|---:|---:|
| H1 binary test, unredacted · judge **Haiku 4.5** | 0.500 | 0.983 | 0.017 | **0.983** |
| H1 binary test, unredacted · judge **Opus 5** | 0.458 | 0.250 | 0.667 | **0.292** |
| H2 binary test, redacted · Haiku | 0.492 | 0.983 | 0.000 | 0.992 |
| H3 reasoning-traces analysis · Haiku | 0.633 | 0.900 | 0.367 | 0.767 |
| **H4 ours — held-out classifier, redacted** | **0.783** | | | *(p < 0.005)* |
| H4 ours — held-out classifier, unredacted | 0.925 | | | *(p < 0.005)* |

**Mundane-cue arm — the negative set; the correct answer is "find nothing":**

| method | accuracy | call rate |
|---|---:|---:|
| H1 binary test, unredacted | 0.483 | 0.967 |
| H2 binary test, redacted | 0.475 | 0.975 |
| H3 reasoning-traces analysis | 0.475 | 0.208 |
| **H4 ours** | **0.442** *(p = 0.45)* | |

## The finding: the binary test measures the judge's prior, not the subject's state

The two judges disagree about **68 percentage points** of call rate on the
identical 120 traces — Haiku answers EVALUATION 98.3% of the time, Opus 5 answers
it 29.2% of the time — and **both land at chance accuracy** (0.500 and 0.458).

That is the load-bearing observation, and it is stronger than a simple
replication would have been. Before running the frontier judge the obvious
objection was *"your bias is a small-model artifact."* It is not. The bias
**flipped direction** and the accuracy did not move off chance. What the method
reports is how common the *judge* believes evaluations are — the trace barely
enters into it.

It also reproduces, from the other side, the comparative study's κ = 0.16–0.75
between two supposedly equivalent methods: here the disagreement is between two
*judges* running one method, and it is near-total.

Corollary worth stating plainly: **a judge-based detector must publish its call
rate.** At 0.983 the Haiku judge has sensitivity 0.983 — which looks excellent
and means nothing, because it says yes to everything. Accuracy alone hides this;
sensitivity alone actively flatters it. Only the call rate exposes it.

## Where the distributional read stands

On identical traces, `0.783` (redacted, p < 0.005) against a best-judge `0.633`
and a standard-method `0.500`. And it is the only method that is **calibrated**:
on the negative set it returns 0.442 — chance, as it should — while the binary
test returns chance *with a 97% yes-rate*. A method that cannot be wrong in one
direction is not conservative; it is broken.

The redaction matters here. Ours reaches 0.783 having had the cue's entire
vocabulary removed, and the `PILOT-RESULTS` ablation showed the signal survives
stripping the top 100 discriminative tokens. It is not reading the cue back.

**H3's arm-level behaviour is the interesting middle case.** Its call rate swings
0.767 → 0.208 between arms, so judging traces for awareness *does* respond to
whether an announced cue exists — but at the level of the whole arm, by
essentially reading the cue text. Per-trace it cannot classify (0.633 and 0.475).
That is precisely the "low sensitivity, models don't always explicitly reason
about being tested" failure the literature describes.

## The asymmetry this comparison does not resolve

**Ours needs labels. Theirs is zero-shot.** The held-out classifier requires a
labelled corpus to train on — 96 examples per fold here. The judge methods need
none.

- For **controlled research**, where the experimenter sets the condition and
  therefore has ground truth by construction, that is a fair fight and the
  distributional read wins it decisively. This is the setting the literature's
  methods are used in too.
- For **detection in the wild**, with no labels, the distributional read does not
  apply at all. Nothing here is evidence for a deployable eval-awareness
  detector.

That is a real boundary on the contribution, not a footnote.

## Other limits, stated

- **One trace-model** (Haiku 4.5) generating all 240 traces, and eval-awareness
  scales with model size — so the traces come from where the phenomenon is
  weakest.
- **Reimplementation, not their code.** H1–H3 are our reading of the described
  methods; prompt wording differences could matter, though the direction and
  magnitude of the bias match what they report.
- **One cue type** (announced), **two scenarios**, n = 120 per arm.
- **H1's frontier-judge row is announced-arm only** — Opus 5 was not run on the
  negative set, so its calibration is unmeasured.
- Judges are same-vendor as the traces throughout.

## What follows

1. The distributional read is worth developing as a **measurement instrument for
   controlled experiments** — not as a wild detector.
2. Any judge-based number in this repo or elsewhere should carry its **call
   rate**. Add it wherever `detector_audit`'s judge path is used.
3. The obvious next run is the **big-model replication**: regenerate the traces
   on Sonnet 5 / Opus 5, where eval-awareness is expected to be stronger, and
   re-run all four methods. If the judge methods stay at chance while the
   distributional read rises, the gap is a property of the methods rather than of
   this particular corpus.
