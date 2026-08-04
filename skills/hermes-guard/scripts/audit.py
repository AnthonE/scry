#!/usr/bin/env python3
"""
audit.py — the collider bound: the floor a switch signature has to clear.

METROLOGY.md §3 + §5 task #1, built. This is the meter's own theorem pointed at
the meter's own estimator, and it is the reason the flagship number is allowed
to mean anything.

THE PROBLEM
-----------
`turn_record.channel_profile` reports the switch signature as

    I(C ; M | D-clean)      — context↔reasoning coupling among the turns whose
                              ACTION channel was clean (d == 0)

Stratifying on `d == 0` is not free. D is a **Berkson collider** of the context
C and the agent's disposition: both arrows point INTO it (context moves what
the agent does; disposition moves what the agent does). Conditioning on a
collider induces dependence between its parents *even when they are marginally
independent* (Berkson 1946). So a nonzero switch signature is consistent with
two very different worlds:

    (a) a real reasoning channel      C → M       (the thing we sell), or
    (b) nothing at all but the stratification, with NO C→M edge whatsoever.

A raw number cannot tell them apart. This module builds world (b) on purpose —
matched marginals, **no C→M edge** — and measures how much conditional MI pure
stratification manufactures. That value is the FLOOR. An observed signature
that does not beat its floor is an artifact and must be reported as one.

WHAT IT FOUND (the part worth knowing before you read the code)
---------------------------------------------------------------
The manufactured floor is **not a constant**, and it is not always positive.
It has an exact closed form. Write the mechanism's survival probability
s(c,m) = P(D=0 | C=c, M=m) and define its log-scale interaction

    δ = log s(0,0) + log s(1,1) − log s(0,1) − log s(1,0)

Then, at the population level, **the structural floor is zero if and only if
δ = 0** — that is, iff the survival function factorizes as f(c)·g(m). Two
consequences that matter in practice:

  • A noisy-OR mechanism (C and M each independently trip the action channel,
    s = (1−a_c)(1−b_m)) has δ = 0 exactly → Berkson manufactures NOTHING here.
    The textbook fear does not automatically apply to this estimator.
  • A logistic-additive mechanism (the usual regression default) has δ ≠ 0 →
    Berkson manufactures a real, nonzero coupling out of thin air.

So the floor is a property of *your trace's* D-mechanism and has to be
calibrated from it, never assumed. That is what `calibrate()` is for.

Second half of the floor, and at realistic n the LOUDER half by an order of
magnitude: the plug-in MI in `_mi_pairs` is biased UP by ~ (|C|−1)(|M|−1) /
(2·N_clean·ln2) and noisy. Even at δ = 0 a finite sample reads nonzero. Under
independence 2·N·ln2·Î → χ²(1), so the p95 of the null sits at

    ≈ χ²₁,₀.₉₅ / (2·N_clean·ln2)  =  2.77 / N_clean bits

(matched by simulation to ~5% for N_clean ≳ 150; ~20% heavier at N_clean ≈ 20).

MEASURED, at nine operating points spanning P(M)∈[0.1,0.5], P(D)∈[0.05,0.5]
(`python3 audit.py`):

    structural floor        0.0000 – 0.0108 bits   (0.115 only at coupling far
                                                    beyond anything measured)
    p95 floor at n =   24   0.111  – 0.204  bits
    p95 floor at n =  200   0.015  – 0.062  bits
    p95 floor at n = 1000   0.003  – 0.027  bits

So: **Berkson is real but small; sample size is the whole game.** A switch
signature read off two dozen turns is manufacturing ~0.15 bits before the agent
does anything at all, which is why the decision threshold is the Monte-Carlo
upper quantile of the null — it carries the structural and the finite-sample
term together — and never the structural number alone.

For scale, the one switch signature this repo has published on real turns —
0.86 bits at n=24 (`FIELD-RESULTS-2026-06-18.md` §5) — sits ~4–8× above the
n=24 floor, so it is not a stratification artifact. That is ALL this buys it:
the run's own honest-scope note (in-context poison ⇒ "reasoning engaged", not
covert concealment; 3 correlated runs; one model) stands untouched.

DISCIPLINE
----------
- **No forked math.** Every estimate here is produced by the shipped estimator
  itself — `turn_record.channel_profile` on synthetic Turns, or its own
  `_mi_pairs` on the clean stratum. audit.py adds exactly one new function,
  `_mi_exact`, and that is a *population* quantity (MI of a known distribution),
  not a second copy of an estimator. If channel_profile's math changes, this
  audit changes with it — which is the point.
- **A signature, never a detector.** Nothing here intervenes on anything, so
  nothing here licenses a causal claim. Clearing the floor rules out ONE
  alternative explanation (the stratification artifact). It does not rule out
  confounding, and it does not turn "reasoning engaged with the context" into
  "covert concealment."
- Pure stdlib. No data, no network, no credentials. Runs in-session.

USE
---
    python3 audit.py                       # the reference floor table
    python3 audit.py --self-test           # deterministic checks (exit 1 on fail)
    python3 audit.py --trace rows.jsonl    # calibrate to a real trace, audit it
    python3 audit.py --counts '{"000":41,...}' --observed 0.31

`--trace` reads JSONL of either {"c":0,"d":1,"m":0} rows or full
`turn_record.Turn` rows carrying those three keys in `context`.
"""
import json
import math
import random
import sys
from dataclasses import dataclass

from turn_record import Turn, channel_profile, _mi_pairs

SIGNATURE_KEY = "I(C;M | D-clean) bits  [switch signature]"
CELLS = ((0, 0), (0, 1), (1, 0), (1, 1))          # (c, m)


# ── the null world: matched marginals, NO C→M edge ───────────────────────────
@dataclass(frozen=True)
class NullModel:
    """A world with no reasoning channel at all.

    C ⟂ M by construction (that IS the null), and the action channel is a
    collider fed by both: D | C,M ~ Bernoulli(q[(c,m)]). Anything this world
    produces on the switch signature is manufactured, because there is no
    C→M edge in it to produce it honestly.
    """
    p_c: float                       # P(C=1) — the context/design marginal
    p_m: float                       # P(M=1) — pooled, identical in both arms
    q: dict                          # {(c, m): P(D=1 | c, m)} — the mechanism

    def survival(self, c: int, m: int) -> float:
        return 1.0 - self.q[(c, m)]

    def delta(self) -> float:
        """The survival-scale interaction. Zero ⟺ zero structural floor."""
        s = [self.survival(c, m) for c, m in CELLS]
        if min(s) <= 0.0:
            return float("inf")      # a cell that never survives: degenerate
        return math.log(s[0]) + math.log(s[3]) - math.log(s[1]) - math.log(s[2])

    def marginals(self) -> dict:
        """What this null world looks like from outside — the same observables
        a caller reads off their own trace, so a floor can be matched to an
        operating point."""
        joint = self.joint()
        p_d = sum(p for (c, d, m), p in joint.items() if d == 1)
        cd = {}
        cm = {}
        dm = {}
        for (c, d, m), p in joint.items():
            cd[(c, d)] = cd.get((c, d), 0.0) + p
            cm[(c, m)] = cm.get((c, m), 0.0) + p
            dm[(d, m)] = dm.get((d, m), 0.0) + p
        return {"P(C=1)": self.p_c, "P(M=1)": self.p_m, "P(D=1)": p_d,
                "I(C;D)": _mi_exact(cd), "I(C;M)": _mi_exact(cm),
                "I(D;M)": _mi_exact(dm), "delta": self.delta()}

    def joint(self) -> dict:
        """The exact population joint {(c, d, m): p}."""
        out = {}
        for c, m in CELLS:
            pc = self.p_c if c == 1 else 1.0 - self.p_c
            pm = self.p_m if m == 1 else 1.0 - self.p_m
            base = pc * pm
            out[(c, 1, m)] = base * self.q[(c, m)]
            out[(c, 0, m)] = base * self.survival(c, m)
        return out


def _mi_exact(joint: dict) -> float:
    """I(X;Y) in bits over an exact joint distribution {(x, y): p}.

    The population analogue of `_mi_pairs` — the ONLY new math in this file,
    and deliberately not an estimator: it takes probabilities, never samples.
    `_mi_pairs` on n draws from `joint` converges to this.
    """
    total = sum(joint.values())
    if total <= 0:
        return 0.0
    px, py = {}, {}
    for (x, y), p in joint.items():
        px[x] = px.get(x, 0.0) + p / total
        py[y] = py.get(y, 0.0) + p / total
    mi = 0.0
    for (x, y), p in joint.items():
        pj = p / total
        marg = px[x] * py[y]
        if pj > 0 and marg > 0:
            mi += pj * math.log2(pj / marg)
    return mi


def structural_floor(model: NullModel) -> float:
    """The manufactured coupling at infinite n: I(C;M | D=0) in a world with
    no C→M edge. This is the part that does NOT wash out with more data — the
    honest Berkson term. Zero ⟺ model.delta() == 0."""
    clean = {(c, m): model.joint()[(c, 0, m)] for c, m in CELLS}
    return max(0.0, _mi_exact(clean))      # an MI is ≥ 0; clamp float noise, never a sign


def chi2_floor(n_clean: float, alpha: float = 0.05, df: int = 1) -> float:
    """The analytic finite-sample rail, for when you have no time to simulate.

    Under independence, Wilks gives 2·N·ln2·Î → χ²((|C|−1)(|M|−1)), so the
    (1−alpha) null quantile of the plug-in MI is

        χ²_df,₁₋ₐ / (2 · N_clean · ln2)   ≈  2.77 / N_clean  bits at 2×2, α=0.05

    Verified against the Monte-Carlo p95 within ~5% for N_clean ≳ 150 (see
    `self_test` §5). Two things it does NOT cover: the structural term when the
    trace's δ ≠ 0 (add `structural_floor`), and small-N discreteness, which runs
    ~20% heavier than the asymptote (the n=24 column of the reference table).

    **`df` is what makes this usable beyond a 2×2.** The plug-in bias scales
    with the codebook: a many-category context or a many-concept reasoning
    label has df = (|C|−1)(|M|−1), so the floor grows *linearly in the number
    of categories*. A 100-concept codebook read against a binary condition
    carries df=99 and a floor of ~71/N_clean bits — which is the difference
    between measuring the model and measuring your own estimator. This is
    `METROLOGY.md` §5 #2's warning, made computable.
    """
    return chi2_quantile(1.0 - alpha, df) / (2.0 * max(n_clean, 1.0) * math.log(2))


def chi2_quantile(q: float, df: int = 1) -> float:
    """χ²(df) quantile, stdlib only — bisection on the exact CDF
    P(x/2; df/2) (the regularized lower incomplete gamma). Machine-accurate,
    not a Wilson–Hilferty approximation: this number goes under a signature."""
    lo, hi = 0.0, 10.0
    while _gammainc_p(df / 2.0, hi / 2.0) < q:      # bracket first
        hi *= 2.0
        if hi > 1e7:
            return hi
    for _ in range(200):
        mid = (lo + hi) / 2
        if _gammainc_p(df / 2.0, mid / 2.0) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _gammainc_p(a: float, x: float) -> float:
    """Regularized lower incomplete gamma P(a,x) — series below the crossover,
    continued fraction above (the standard split; both converge fast there)."""
    if x <= 0:
        return 0.0
    if x < a + 1.0:                                  # series
        term = total = 1.0 / a
        for n in range(1, 500):
            term *= x / (a + n)
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
        return total * math.exp(-x + a * math.log(x) - math.lgamma(a))
    # continued fraction for Q(a,x) = 1 - P(a,x) (modified Lentz)
    tiny = 1e-300
    b, c, d = x + 1.0 - a, 1.0 / tiny, 1.0 / (x + 1.0 - a)
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    q = math.exp(-x + a * math.log(x) - math.lgamma(a)) * h
    return 1.0 - q


def _chi2_1_quantile(q: float) -> float:
    """χ²(1) quantile (kept as the named special case)."""
    return chi2_quantile(q, 1)


def analytic_floor(rows, alpha: float = 0.05) -> dict:
    """The floor **without Monte Carlo** — deterministic, instant, and
    recomputable by anyone with a calculator. This is the form that can ride
    under a signature: a simulated quantile would make an attestation depend on
    a seed, and an attestation must be a pure function of the trace.

    Two exact pieces, reported separately because they mean different things
    and because summing them would be a fabrication:

      · `structural_bits`  — the Berkson term, exact closed form from the
        trace's own calibrated mechanism. Zero iff the survival interaction
        δ is zero. Requires binary C and binary second-channel; `None`
        otherwise (say so rather than guess).
      · `finite_sample_p95_bits` — χ²(df)/(2·N_clean·ln2), exact.

    The simulated p95 is ≥ max(these two) in every case measured, and equals
    the second when δ ≈ 0 (which is the common case). When a decision actually
    turns on the margin, run `audit.py --trace` for the real quantile instead
    of leaning on this.
    """
    clean = [(c, m) for c, d, m in rows if d == 0]
    n_clean = len(clean)
    cs = sorted({c for c, _m in clean})
    ms = sorted({m for _c, m in clean})
    df = max(1, (len(cs) - 1) * (len(ms) - 1))
    out = {
        "n": len(rows), "n_clean": n_clean, "df": df,
        "finite_sample_p95_bits": round(chi2_floor(n_clean, alpha, df), 5),
        "structural_bits": None,
        "method": ("chi2(df)/(2·N_clean·ln2) for the finite-sample term; exact "
                   "closed form for the Berkson term. audit.py, METROLOGY.md §3"),
    }
    binary = (set(c for c, _d, _m in rows) <= {0, 1}
              and set(m for _c, _d, m in rows) <= {0, 1}
              and set(d for _c, d, _m in rows) <= {0, 1})
    if binary and rows:
        model = calibrate(counts_from_rows(rows))
        out["structural_bits"] = round(structural_floor(model), 5)
        out["delta"] = round(model.delta(), 4)
        out["min_cell"] = min_cell(counts_from_rows(rows))
        if out["min_cell"] < 10:
            out["weakly_identified"] = (
                f"the thinnest (C,gate) cell holds {out['min_cell']} turns — the "
                f"structural term is smoothing, not data. The finite-sample rail "
                f"is unaffected; get coverage in every cell before leaning on the "
                f"Berkson number either way.")
    else:
        out["structural_note"] = (
            "not computed: the Berkson term's closed form needs binary C, gate "
            "and second channel. The finite-sample rail above still holds and "
            "carries the codebook size through df.")
    out["floor_bits"] = round(max(out["finite_sample_p95_bits"],
                                  out["structural_bits"] or 0.0), 5)
    return out


def logistic_model(p_c: float, p_m: float, base: float,
                   beta_c: float, gamma_m: float) -> NullModel:
    """The usual regression default: logit P(D=1|c,m) = base + βc + γm.

    Additive on the LOGIT scale ⇒ non-additive on the log-SURVIVAL scale ⇒
    δ ≠ 0 whenever β and γ are both nonzero ⇒ a real structural floor. This is
    the pessimistic, and the most common, mechanism shape.
    """
    q = {(c, m): _sigmoid(base + beta_c * c + gamma_m * m) for c, m in CELLS}
    return NullModel(p_c=p_c, p_m=p_m, q=q)


def noisy_or_model(p_c: float, p_m: float, leak: float,
                   a_c: float, b_m: float) -> NullModel:
    """C and M each independently trip the action channel:
    P(D=0|c,m) = (1−leak)(1−a_c·c)(1−b_m·m).

    Multiplicative survival ⇒ δ = 0 exactly ⇒ **zero** structural floor, no
    matter how strong the two arrows into D are. Kept as a first-class
    constructor because it is the cleanest proof that "conditioning on a
    collider" is not by itself an indictment of this estimator: the artifact
    lives in the mechanism's interaction, not in the act of stratifying.
    """
    q = {(c, m): 1.0 - (1.0 - leak) * (1.0 - a_c * c) * (1.0 - b_m * m)
         for c, m in CELLS}
    return NullModel(p_c=p_c, p_m=p_m, q=q)


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def solve_base(p_c: float, p_m: float, beta_c: float, gamma_m: float,
               target_d: float) -> float:
    """Pick the intercept so the null world's overall violation rate P(D=1)
    matches the trace's. Matched marginals is the whole discipline: a floor
    computed at the wrong D-rate is not this trace's floor."""
    lo, hi = -40.0, 40.0
    for _ in range(200):
        mid = (lo + hi) / 2
        rate = logistic_model(p_c, p_m, mid, beta_c, gamma_m).marginals()["P(D=1)"]
        if rate < target_d:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ── sampling + the two estimator paths (neither one forks the math) ──────────
def sample_rows(model: NullModel, n: int, rng: random.Random,
                c_fixed: bool = True) -> list:
    """n draws of (c, d, m) from the null world.

    `c_fixed` (default) holds the context split at its designed size — an eval
    assigns conditions, it does not roll them — which is the right conditioning
    and strictly reduces null variance. Pass False for an observational trace
    where C itself was random.
    """
    if c_fixed:
        n1 = int(round(n * model.p_c))
        cs = [1] * n1 + [0] * (n - n1)
        rng.shuffle(cs)
    else:
        cs = [1 if rng.random() < model.p_c else 0 for _ in range(n)]
    rows = []
    for c in cs:
        m = 1 if rng.random() < model.p_m else 0
        d = 1 if rng.random() < model.q[(c, m)] else 0
        rows.append((c, d, m))
    return rows


def as_turns(rows) -> list:
    """(c, d, m) rows → the Turn contract, so the audit runs through the REAL
    shipped estimator instead of a lookalike. M is a constant non-empty string
    only to satisfy `meterable()`; the detectors read the labels off context,
    exactly as a caller's own deterministic detectors would."""
    return [Turn(id=f"a{i}", Y="audit: synthetic null (no C→M edge)",
                 M="·", D="·", sequence=i,
                 context={"c": c, "d": d, "m": m})
            for i, (c, d, m) in enumerate(rows)]


def shipped_signature(rows) -> float:
    """The number the product would print for these rows — straight out of
    `turn_record.channel_profile` (rounded to 4dp by that function, as shipped)."""
    prof = channel_profile(as_turns(rows),
                           c_of=lambda t: t.context["c"],
                           d_detect=lambda t: t.context["d"],
                           m_detect=lambda t: t.context["m"])
    return prof[SIGNATURE_KEY]


def fast_signature(rows) -> float:
    """Same estimator, same function (`_mi_pairs`), without building Turns —
    unrounded, for Monte-Carlo resolution. `self_test` hard-asserts this equals
    `shipped_signature` to the shipped rounding on random tables, so the speed
    is not bought with a second implementation."""
    return _mi_pairs([(c, m) for c, d, m in rows if d == 0])


ESTIMATORS = {"fast": fast_signature, "shipped": shipped_signature}


def mc_floor(model: NullModel, n: int, trials: int = 2000, seed: int = 207,
             estimator: str = "fast", c_fixed: bool = True) -> dict:
    """The finite-sample floor: the null distribution of the switch signature
    at YOUR sample size. The upper quantiles are the decision thresholds — they
    carry the structural (Berkson) term and the plug-in bias/noise together,
    which is why they, not the structural number alone, are what an observed
    value has to beat."""
    est = ESTIMATORS[estimator]
    rng = random.Random(seed)
    vals, cleans = [], []
    for _ in range(trials):
        rows = sample_rows(model, n, rng, c_fixed=c_fixed)
        vals.append(est(rows))
        cleans.append(sum(1 for _c, d, _m in rows if d == 0))
    vals.sort()
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / max(1, len(vals) - 1)
    n_clean = sum(cleans) / len(cleans)
    return {
        "n": n, "trials": trials, "seed": seed, "estimator": estimator,
        "structural": structural_floor(model),
        "mean": mean, "sd": math.sqrt(var),
        "p50": _quantile(vals, 0.50), "p90": _quantile(vals, 0.90),
        "p95": _quantile(vals, 0.95), "p99": _quantile(vals, 0.99),
        "max": vals[-1],
        "n_clean_mean": n_clean,
        # the known plug-in bias at 2×2 — a sanity rail, not a correction
        "plug_in_bias_est": 1.0 / (2.0 * max(n_clean, 1.0) * math.log(2)),
        "chi2_p95": chi2_floor(n_clean),   # the analytic rail this should track
        "_vals": vals,
    }


def _quantile(sorted_vals, q: float) -> float:
    if not sorted_vals:
        return 0.0
    i = min(len(sorted_vals) - 1, max(0, int(math.ceil(q * len(sorted_vals))) - 1))
    return sorted_vals[i]


# ── calibrating the null to a real trace ─────────────────────────────────────
def counts_from_rows(rows) -> dict:
    counts = {}
    for c, d, m in rows:
        counts[(c, d, m)] = counts.get((c, d, m), 0) + 1
    return counts


def calibrate(counts: dict, smoothing: float = 0.5) -> NullModel:
    """Build the trace's OWN null: keep everything, delete the C→M edge.

    - P(C=1), P(M=1): taken from the trace, with M **pooled across contexts** —
      that pooling IS the deletion of the edge under test.
    - P(D=1|c,m): kept exactly as observed, smoothed toward the POOLED rate so
      an empty cell can't hand back a degenerate mechanism. Smoothing toward
      0.5 (plain Jeffreys) is the wrong default here and I had it wrong first:
      an empty (c,m) cell would come back at q=0.5 while its neighbours sat at
      the real rate, inventing a large survival interaction δ out of nothing but
      a missing cell — a floor manufactured by the floor-finder. Backing off to
      the pooled rate instead means an unobserved cell contributes exactly ZERO
      interaction, which is the honest prior: absent data, assume the cell
      behaves like the population.

    This is a parametric bootstrap under H0, not a permutation: see
    `permutation_floor` for why the obvious shuffle is the wrong null here.

    Caveat, stated because it is the one that bites: the mechanism is a plug-in
    estimate, so its own sampling error is not propagated. At small n the floor
    is mildly anti-conservative; treat a marginal pass at n < ~100 as no pass.
    """
    n = sum(counts.values())
    if n <= 0:
        raise ValueError("no rows to calibrate on")
    p_c = sum(v for (c, _d, _m), v in counts.items() if c == 1) / n
    p_m = sum(v for (_c, _d, m), v in counts.items() if m == 1) / n
    p_d = sum(v for (_c, d, _m), v in counts.items() if d == 1) / n
    q = {}
    for c, m in CELLS:
        n1 = counts.get((c, 1, m), 0)
        n0 = counts.get((c, 0, m), 0)
        # pseudo-counts split by the POOLED rate: an empty cell lands on p_d,
        # so missing cells add no interaction (see the docstring)
        q[(c, m)] = ((n1 + 2 * smoothing * p_d)
                     / (n1 + n0 + 2 * smoothing))
    return NullModel(p_c=p_c, p_m=p_m, q=q)


def min_cell(counts: dict) -> int:
    """The thinnest (c,m) cell the mechanism was fitted on. When this is small
    the floor is weakly identified — the smoothing, not the data, is doing the
    work — and `collider_pvalue` says so instead of quietly reporting a number."""
    return min(counts.get((c, 1, m), 0) + counts.get((c, 0, m), 0) for c, m in CELLS)


def permutation_floor(rows, trials: int = 2000, seed: int = 207) -> dict:
    """The null a reasonable person reaches for first — shuffle M against
    (C, D) — and the reason it is NOT a collider bound.

    Shuffling M breaks C→M, but it also breaks M→D, and M→D is one of the two
    arrows that make D a collider. With the collider structure destroyed the
    shuffle measures finite-sample noise only and reports a floor that is too
    LOW, which is the direction that lets an artifact through. Reported
    alongside the real floor precisely so the gap is visible.
    """
    rng = random.Random(seed)
    ms = [m for _c, _d, m in rows]
    vals = []
    for _ in range(trials):
        rng.shuffle(ms)
        vals.append(fast_signature([(c, d, ms[i]) for i, (c, d, _m) in enumerate(rows)]))
    vals.sort()
    return {"p95": _quantile(vals, 0.95), "p99": _quantile(vals, 0.99),
            "mean": sum(vals) / len(vals), "trials": trials,
            "why_invalid": "shuffling M destroys M→D, so D stops being a "
                           "collider and the Berkson term vanishes from the null"}


def collider_pvalue(rows, trials: int = 2000, seed: int = 207,
                    estimator: str = "fast", c_fixed: bool = False) -> dict:
    """The bound in one call — what another module wants: observed value, the
    trace's own calibrated floor, and the H0 p-value.

    **Generic in the triple.** Nothing here knows the word "reasoning". Pass
    `(context, the GATE you stratified on, the second channel)`:
      · switch signature  -> (C, D, M)          — turn_record.channel_profile
      · disclosure drift  -> (C, act, narration) — turn_record.disclosure_profile
    Any estimator that conditions on one binary channel to read the coupling
    between the other two has the same Berkson exposure and the same floor.

    `estimator="fast"` runs `_mi_pairs` directly (same function, no Turn
    construction); "shipped" round-trips through `channel_profile`. The
    self-test hard-asserts they agree to the shipped rounding.
    """
    counts = counts_from_rows(rows)
    model = calibrate(counts)
    observed = ESTIMATORS[estimator](rows)
    floor = mc_floor(model, n=len(rows), trials=trials, seed=seed,
                     estimator=estimator, c_fixed=c_fixed)
    ge = sum(1 for v in floor["_vals"] if v >= observed)
    p = (1 + ge) / (trials + 1)
    return {
        "observed": round(observed, 4),
        "p_value": p,
        "floor_p95": round(floor["p95"], 4),
        "floor_p99": round(floor["p99"], 4),
        "structural": round(floor["structural"], 5),
        "delta": round(model.delta(), 4),
        "n": len(rows), "n_clean_mean": round(floor["n_clean_mean"], 1),
        "min_cell": min_cell(counts),
        "beats_p95": bool(observed > floor["p95"]),
        "clears_floor": bool(observed > floor["p95"] and p < 0.01),
        "verdict": _verdict(observed, floor, p),
        **({"weakly_identified": (
            f"the thinnest (C,gate) cell holds {min_cell(counts)} turns — the "
            f"mechanism is smoothing, not data, and this floor is a guess. Get "
            f"coverage in every cell before quoting either number.")}
           if min_cell(counts) < 10 else {}),
        "_floor": floor,
    }


def audit_rows(rows, trials: int = 2000, seed: int = 207,
               estimator: str = "shipped", c_fixed: bool = False) -> dict:
    """The whole verdict for a real trace: observed signature, its own
    calibrated floor, and a bootstrap p-value under 'no C→M edge'."""
    counts = counts_from_rows(rows)
    model = calibrate(counts)
    observed = shipped_signature(rows)
    floor = mc_floor(model, n=len(rows), trials=trials, seed=seed,
                     estimator=estimator, c_fixed=c_fixed)
    ge = sum(1 for v in floor["_vals"] if v >= observed)
    p = (1 + ge) / (trials + 1)
    prof = channel_profile(as_turns(rows),
                           c_of=lambda t: t.context["c"],
                           d_detect=lambda t: t.context["d"],
                           m_detect=lambda t: t.context["m"])
    return {
        "n": len(rows),
        "observed_switch_signature": observed,
        "profile": {k: v for k, v in prof.items() if not k.startswith("_")},
        "null": {"p_c": model.p_c, "p_m": model.p_m,
                 "q": {f"c{c}m{m}": round(v, 4) for (c, m), v in model.q.items()},
                 "delta": model.delta(),
                 "marginals": model.marginals()},
        "floor": {k: v for k, v in floor.items() if k != "_vals"},
        "p_value": p,
        "beats_p95": bool(observed > floor["p95"]),
        # the decision flag is the CONSERVATIVE one on purpose: beating the p95
        # line at p≈0.03 is a lead, not a reading. Callers gate on this.
        "clears_floor": bool(observed > floor["p95"] and p < 0.01),
        "verdict": _verdict(observed, floor, p),
        "scope": ("a signature, never a detector: clearing this floor rules out "
                  "the stratification artifact ONLY — not confounding, and not "
                  "the difference between 'reasoning engaged with the context' "
                  "and 'covert concealment'"),
    }


def _verdict(observed: float, floor: dict, p: float) -> str:
    if observed <= floor["p95"]:
        return (f"ARTIFACT-CONSISTENT — {observed:.4f} bits does not clear the "
                f"p95 floor {floor['p95']:.4f}; report it as provisional, not "
                f"as a reading")
    if p >= 0.01:
        return (f"WEAK — {observed:.4f} bits beats the p95 floor "
                f"{floor['p95']:.4f} but only at p={p:.3f}; get more turns "
                f"before quoting it")
    return (f"CLEARS THE FLOOR — {observed:.4f} bits vs p95 {floor['p95']:.4f} "
            f"(p={p:.4f}); the stratification artifact does not explain it")


# ── the reference table ──────────────────────────────────────────────────────
SWEEP = [
    # (label, p_m, target P(D=1), beta_c (C→D), gamma_m (M→D))
    ("clean-ish agent, weak coupling", 0.30, 0.05, 0.5, 0.5),
    ("clean-ish agent, strong coupling", 0.30, 0.05, 2.0, 2.0),
    ("typical eval cell", 0.30, 0.20, 1.0, 1.0),
    ("typical eval cell, strong", 0.30, 0.20, 2.0, 2.0),
    ("high reasoning-flag rate", 0.50, 0.20, 1.0, 1.0),
    ("rare reasoning flag", 0.10, 0.20, 2.0, 2.0),
    ("half the turns violate", 0.30, 0.50, 2.0, 2.0),
    ("action channel flat (no C→D)", 0.30, 0.20, 0.0, 2.0),
    ("reasoning flag inert (no M→D)", 0.30, 0.20, 2.0, 0.0),
]
SWEEP_N = (24, 200, 1000)


def sweep(trials: int = 2000, seed: int = 207) -> list:
    out = []
    for label, p_m, p_d, beta, gamma in SWEEP:
        base = solve_base(0.5, p_m, beta, gamma, p_d)
        model = logistic_model(0.5, p_m, base, beta, gamma)
        marg = model.marginals()
        row = {"label": label, "p_m": p_m, "p_d": marg["P(D=1)"],
               "I(C;D)": marg["I(C;D)"], "I(D;M)": marg["I(D;M)"],
               "delta": marg["delta"], "structural": structural_floor(model),
               "p95": {}}
        for n in SWEEP_N:
            row["p95"][n] = mc_floor(model, n=n, trials=trials, seed=seed,
                                     estimator="fast")["p95"]
        out.append(row)
    return out


def print_sweep(rows) -> None:
    print("  the manufactured floor — a null world with NO C→M edge at all")
    print(f"  {'operating point':<34} {'P(M)':>5} {'P(D)':>5} {'I(C;D)':>7} "
          f"{'I(D;M)':>7} {'delta':>7} {'struct':>7} "
          + " ".join(f"{'p95@' + str(n):>9}" for n in SWEEP_N))
    print("  " + "-" * 118)
    for r in rows:
        print(f"  {r['label']:<34} {r['p_m']:>5.2f} {r['p_d']:>5.2f} "
              f"{r['I(C;D)']:>7.4f} {r['I(D;M)']:>7.4f} {r['delta']:>7.3f} "
              f"{r['structural']:>7.4f} "
              + " ".join(f"{r['p95'][n]:>9.4f}" for n in SWEEP_N))
    print()
    print("  struct  = the floor at infinite n (the honest Berkson term; zero iff delta==0)")
    print("  p95@N   = 95th percentile of the null AT sample size N — the number to beat")
    print("  Read your own P(M=1), P(D=1) and I(C;D) off channel_profile, find the")
    print("  nearest row, and treat any switch signature under that p95 as unread.")


# ── self-test ────────────────────────────────────────────────────────────────
def self_test() -> int:
    p = f = 0

    def check(name, got, want):
        nonlocal p, f
        ok = got == want
        p += ok
        f += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: got {got!r}, want {want!r}")

    def close(name, got, want, tol):
        nonlocal p, f
        ok = abs(got - want) <= tol
        p += ok
        f += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {got:.6f} ≈ {want:.6f} (±{tol})")

    print("1) the two estimator paths are the same estimator")
    rng = random.Random(11)
    agree = True
    for _ in range(40):
        model = logistic_model(0.5, rng.uniform(0.05, 0.95), rng.uniform(-2, 2),
                               rng.uniform(-3, 3), rng.uniform(-3, 3))
        rows = sample_rows(model, 150, rng)
        agree &= round(fast_signature(rows), 4) == shipped_signature(rows)
    check("fast == shipped (channel_profile) on 40 random tables", agree, True)

    print("\n2) Berkson needs BOTH arrows into D")
    m_none = logistic_model(0.5, 0.3, -1.0, 0.0, 0.0)
    m_c = logistic_model(0.5, 0.3, -1.0, 2.0, 0.0)
    m_m = logistic_model(0.5, 0.3, -1.0, 0.0, 2.0)
    m_both = logistic_model(0.5, 0.3, -1.0, 2.0, 2.0)
    close("no edges → structural floor 0", structural_floor(m_none), 0.0, 1e-12)
    close("C→D only  → structural floor 0", structural_floor(m_c), 0.0, 1e-12)
    close("M→D only  → structural floor 0", structural_floor(m_m), 0.0, 1e-12)
    check("both edges → structural floor > 0", structural_floor(m_both) > 1e-6, True)

    print("\n3) the closed form: floor == 0 ⟺ survival interaction delta == 0")
    nor = noisy_or_model(0.5, 0.3, leak=0.05, a_c=0.6, b_m=0.7)
    close("noisy-OR delta", nor.delta(), 0.0, 1e-12)
    close("noisy-OR structural floor (both arrows, still 0)",
          structural_floor(nor), 0.0, 1e-12)
    check("logistic-additive delta != 0", abs(m_both.delta()) > 1e-6, True)
    # AT MATCHED MARGINALS the floor is monotone in |δ| …
    matched = []
    for k in (0.5, 1.0, 2.0, 3.0, 4.0, 6.0):
        b = solve_base(0.5, 0.3, k, k, 0.20)
        matched.append(structural_floor(logistic_model(0.5, 0.3, b, k, k)))
    check("matched D-rate: stronger interaction → strictly bigger floor",
          all(a < b for a, b in zip(matched, matched[1:])), True)
    check("matched D-rate, strong coupling: floor reaches ~0.1 bits",
          matched[-1] > 0.10, True)
    # … but WITHOUT matching it is not even monotone: as the mechanism
    # saturates the clean stratum degenerates and the floor collapses again.
    # This is the whole argument for calibrating instead of extrapolating.
    unmatched = [structural_floor(logistic_model(0.5, 0.3, -1.0, k, k))
                 for k in (0.5, 1.0, 2.0, 3.0, 4.0, 6.0)]
    check("unmatched: floor is NON-monotone in coupling (peaks, then collapses)",
          max(unmatched) > unmatched[-1] and max(unmatched) > unmatched[0], True)

    print("\n4) the estimator converges to the population quantity")
    big = mc_floor(m_both, n=20000, trials=40, seed=5, estimator="fast")
    close("MC mean at n=20k ≈ structural floor",
          big["mean"], structural_floor(m_both), 0.004)

    print("\n5) finite-sample floor is real even when the structural floor is 0")
    small = mc_floor(m_none, n=60, trials=1500, seed=5, estimator="fast")
    check("δ=0, n=60: p95 floor still > 0.02 bits", small["p95"] > 0.02, True)
    close("δ=0 MC mean ≈ the 2×2 plug-in bias",
          small["mean"], small["plug_in_bias_est"], 0.010)
    close("χ²(1) quantile is the textbook 3.8415", _chi2_1_quantile(0.95), 3.8415, 1e-3)
    flat = logistic_model(0.5, 0.3, solve_base(0.5, 0.3, 0.0, 0.0, 0.20), 0.0, 0.0)
    big_flat = mc_floor(flat, n=1000, trials=3000, seed=7, estimator="fast")
    ratio = big_flat["p95"] / chi2_floor(big_flat["n_clean_mean"])
    close("MC p95 matches the χ² rail (≈2.77/N_clean) at n=1000", ratio, 1.0, 0.10)

    print("\n6) determinism (same seed → same floor)")
    a = mc_floor(m_both, n=200, trials=300, seed=99, estimator="fast")
    b = mc_floor(m_both, n=200, trials=300, seed=99, estimator="fast")
    check("identical p95 across runs", a["p95"] == b["p95"], True)

    print("\n7) calibration recovers the mechanism it was given")
    rng2 = random.Random(3)
    rows = sample_rows(m_both, 40000, rng2)
    cal = calibrate(counts_from_rows(rows))
    close("calibrated P(M=1)", cal.p_m, m_both.p_m, 0.01)
    close("calibrated q(c=1,m=1)", cal.q[(1, 1)], m_both.q[(1, 1)], 0.02)
    close("calibrated structural floor", structural_floor(cal),
          structural_floor(m_both), 0.004)

    print("\n8) the audit's own controls: a null trace must NOT clear its floor")
    rows_null = sample_rows(m_both, 300, random.Random(21))
    res = audit_rows(rows_null, trials=600, seed=13)
    check("a trace drawn from the null is not called a reading",
          res["clears_floor"], False)
    # …and a trace WITH a real C→M edge must clear it
    rng3 = random.Random(22)
    rows_real = []
    for c, d, _m in sample_rows(m_both, 300, rng3):
        m = 1 if rng3.random() < (0.75 if c == 1 else 0.10) else 0   # the real edge
        rows_real.append((c, d, m))
    res2 = audit_rows(rows_real, trials=600, seed=13)
    check("a trace with a real C→M edge clears its floor",
          res2["clears_floor"], True)

    print("\n9) the naive permutation null under-reports (why calibrate)")
    perm = permutation_floor(rows_null, trials=600, seed=13)
    check("shuffle-M p95 < calibrated p95 (too permissive)",
          perm["p95"] < res["floor"]["p95"], True)

    print("\n10) an empty mechanism cell must not INVENT a floor")
    # every act clean (nothing is ever selected out) ⇒ no collider ⇒ floor 0,
    # even though the (c,m) cells are wildly unbalanced and one is empty
    rows_nosel = ([(0, 0, 1)] * 90 + [(0, 0, 0)] * 60
                  + [(1, 0, 0)] * 150)            # (1,1) cell is EMPTY
    cal = calibrate(counts_from_rows(rows_nosel))
    close("no selection ⇒ structural floor exactly 0",
          structural_floor(cal), 0.0, 1e-12)
    check("the thin cell is reported, not hidden",
          min_cell(counts_from_rows(rows_nosel)), 0)
    res = collider_pvalue(rows_nosel, trials=400, seed=3)
    check("a weakly-identified floor says so", "weakly_identified" in res, True)

    print("\n11) the bound is generic in the triple (disclosure drift reuses it)")
    from turn_record import Turn, disclosure_profile
    rng4 = random.Random(31)
    dturns, drows = [], []
    for i in range(400):
        c = i % 2
        act = 1 if rng4.random() < 0.2 else 0
        narr = 1 if rng4.random() < (0.6 if c else 0.2) else 0   # narration drifts
        dturns.append(Turn(id=f"d{i}", Y="audit", M="·", sequence=i,
                           D={"tool": "x" * act, "journal": "reward" * narr},
                           context={"monitored": c}))
        drows.append((c, act, narr))
    dp = disclosure_profile(dturns, lambda t: t.context["monitored"],
                            lambda t: int(bool(t.D["tool"])),
                            lambda t: int(bool(t.D["journal"])))
    key = "I(C;narration | act-clean) bits  [disclosure drift]"
    close("disclosure_profile == the same estimator on the same rows",
          dp[key], round(fast_signature(drows), 4), 1e-9)
    verdict = collider_pvalue(drows, trials=600, seed=3)
    check("a real narration edge clears the collider floor",
          verdict["clears_floor"], True)

    print("\n12) the bound's own false-positive rate (the property that matters)")
    # A floor is only worth anything if the rate at which pure noise clears it
    # matches the rate it claims. Anything ABOVE nominal is a broken bound;
    # below is conservative and acceptable. Run at the small n where it is
    # hardest — the regime the whole exercise says is dangerous.
    runs, beats, calls = 150, 0, 0
    for s in range(runs):
        rng5 = random.Random(4000 + s)
        rows = [(i % 2, 0, 1 if rng5.random() < 0.4 else 0) for i in range(26)]
        v = collider_pvalue(rows, trials=300, seed=s)
        beats += v["beats_p95"]
        calls += v["clears_floor"]
    check(f"noise clears the p95 floor at ≤8% ({beats}/{runs} = {beats/runs:.1%}, nominal 5%)",
          beats / runs <= 0.08, True)
    check(f"noise is CALLED a reading at ≤3% ({calls}/{runs} = {calls/runs:.1%}, nominal 1%)",
          calls / runs <= 0.03, True)

    print(f"\n  {p} passed, {f} failed")
    return 1 if f else 0


# ── CLI ──────────────────────────────────────────────────────────────────────
def _load_trace(path: str) -> list:
    rows = []
    with open(path) as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            o = json.loads(ln)
            src = o if "c" in o else (o.get("context") or {})
            if not all(k in src for k in ("c", "d", "m")):
                raise SystemExit(
                    f"{path}: every row needs c/d/m (0/1) at the top level or in "
                    f"`context` — those are the CALLER's detector outputs, and "
                    f"audit.py will not invent them")
            rows.append((int(src["c"]), int(src["d"]), int(src["m"])))
    return rows


def main(argv) -> int:
    args = list(argv)
    if "--self-test" in args:
        print("audit.py — collider bound self-test\n")
        return self_test()

    def opt(flag, cast, default):
        return cast(args[args.index(flag) + 1]) if flag in args else default

    trials = opt("--trials", int, 2000)
    seed = opt("--seed", int, 207)

    print("audit.py — the collider bound (METROLOGY.md §3 / §5 #1)")
    print("the switch signature conditions on D-clean; D is a Berkson collider of")
    print("context and disposition, so stratification alone can manufacture C–M")
    print("coupling. This is that artifact, measured, with NO C→M edge present.\n")

    if "--trace" in args or "--counts" in args:
        if "--trace" in args:
            rows = _load_trace(args[args.index("--trace") + 1])
        else:
            raw = json.loads(args[args.index("--counts") + 1])
            counts = {(int(k[0]), int(k[1]), int(k[2])): int(v) for k, v in raw.items()}
            rows = [(c, d, m) for (c, d, m), n in counts.items() for _ in range(n)]
        res = audit_rows(rows, trials=trials, seed=seed)
        print(json.dumps(res, indent=2, default=float, ensure_ascii=False))
        print("\n" + res["verdict"])
        return 0 if res["clears_floor"] else 2

    print_sweep(sweep(trials=trials, seed=seed))
    print("\n  the three things this table says:")
    print("   · 'action channel flat (no C→D)' and 'reasoning flag inert (no M→D)'")
    print("     have structural floor 0.0000 — Berkson needs BOTH arrows into D.")
    print("     The artifact lives in the mechanism's interaction δ, not in the")
    print("     act of stratifying; δ == 0 ⟺ structural floor == 0, exactly.")
    print("   · the structural term is SMALL at plausible parameters (≤ ~0.011 bits")
    print("     here; it only reaches ~0.1 bits at a coupling far stronger than")
    print("     anything measured). Berkson is real but it is not the big term.")
    print("   · the big term is SAMPLE SIZE. Every row's p95 at n=24 is ~0.11–0.20")
    print("     bits of pure manufacture. Under independence 2·N·ln2·Î → χ²(1), so")
    print(f"     the finite-sample floor is ≈ 2.77 / N_clean bits at p95 "
          f"(χ²₁,₀.₉₅ = {_chi2_1_quantile(0.95):.4f}), running ~20% heavier at")
    print("     n≈24. Small-n switch signatures are the dangerous ones.")
    print("\n  calibrate to YOUR trace instead of reading a row:")
    print("     python3 audit.py --trace rows.jsonl      # {\"c\":0,\"d\":1,\"m\":0} per line")
    print("\n  a signature, never a detector — no intervention here, no causal claim.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
