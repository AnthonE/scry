"""covenant_social.py — the validated social-defence primitives, ONE source of truth.

Both the controlled sandbox (`destiny_arena.py`) and the live bus service
(`box2-estimator/destiny_ws_service.py`) defend a commons the same way; the formula that
must NOT drift between them is the **un-gaslittable schema reputation** update and the
sustained-low-standing conviction rule. Those live here so the sandbox and the live world
share exactly one implementation.

What deliberately STAYS engine-specific (do not merge):
  • the pool dynamics — the Arena is turn-based (drain only); the live bus is a continuous
    population, so it adds a contribution-gain term and retunes the rates.
  • the SIGHT metric — the Arena has the oversight-counterfactual axis C and convicts on
    I(C;D) (the channel-switch itself); the live bus has no C axis yet, so it corroborates
    with box2 Pe gated by reputation. Same role, different instrument by construction.
    (Closing that gap is the two-channel-Sight / Whisper work, not a merge.)
"""
import math

# the validated constants (fixed in the Arena bake-off; live pool rates are retuned locally)
THRESH = 0.45              # reputation below this counts as "low standing"
EPS = 0.15                 # P(an observation is flipped) — observation is noisy
ETA, TAU = 0.35, 0.20      # schema-update learning rate / gate width
LOW_STREAK_BANISH = 3      # ticks of sustained low standing before conviction


def schema_update(belief: float, observed: float, eta: float = ETA, tau: float = TAU,
                  damp_up: float = 1.0) -> float:
    """Un-gaslittable reputation: an observation that CONFIRMS a settled belief moves it;
    one that CONTRADICTS it is damped by a Gaussian gate on the surprise — so a single
    planted act can't flip a reputation. `damp_up` (<=1) further slows UPWARD revision
    (it is harder to restore trust than to lose it; the Arena uses 0.15 for a convicted
    seat). Returns the new belief."""
    w = eta * math.exp(-((observed - belief) ** 2) / tau)
    if observed > belief:
        w *= damp_up
    return (1 - w) * belief + w * observed


def noisy_observe(rng, truth: float, eps: float = EPS) -> float:
    """The observer sees the truth with prob 1-eps, the flipped value otherwise."""
    return truth if rng.random() > eps else 1.0 - truth


def convicts(low_streak: int, threshold: int = LOW_STREAK_BANISH) -> bool:
    """Sustained low standing → public conviction."""
    return low_streak >= threshold
