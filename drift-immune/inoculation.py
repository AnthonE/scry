"""
inoculation.py — a hardening TECHNIQUE pulled from human psychology (not just a diagnosis).

Inoculation theory (McGuire, 1960s): pre-expose someone to a WEAKENED form of a manipulation, with
the refutation, and they build resistance to the STRONG form later — like a vaccine. Pulled into AI:
expose a memory-agent to weak, labelled attacks during setup; does it then resist a strong attack it
never saw?

The mechanism we model (faithful to the theory): the value of inoculation is building THREAT
RECOGNITION. An agent that has never seen an attack has no reason to bound its inputs (it trusts
them). A weak-but-detectable attack teaches it "inputs can be adversarial" -> it installs the gate
(caps per-input influence at the normal band). That gate then blocks attacks of ANY strength. So a
weak dose, far below the real attack, confers protection — the vaccine property.

We sweep the inoculation dose E (attack strength seen during setup) and measure drift under a fixed
STRONG test attack (M=100). Prediction: drift stays high until the dose is strong enough to be
*recognized* above noise, then drops sharply and stays low — you need a real but weak dose, not a
strong one.
"""
import numpy as np

NOISE = 1.0

def inoculate(E, detect=2.0*NOISE):
    """Setup phase. If the inoculation attack E is detectable above noise, the agent learns that
    inputs can be adversarial and installs a gate at the normal band. Otherwise it stays trusting."""
    if E > detect:
        return 4.0 * NOISE        # threat recognized -> gate installed at the normal band
    return np.inf                  # never recognized an attack -> no gate (default trust)

def test(c, M, steps=300, a=0.3, b=0.2):
    s = 0.0
    for _ in range(steps):
        step = np.clip(M - s, -c, c)          # strong attack, capped by the (possibly infinite) gate
        s = s + a*step + b*(0.0 - s)
    return abs(s)

if __name__ == "__main__":
    M = 100.0
    print(f"resistance to a STRONG attack (M={M:.0f}) as a function of inoculation DOSE E:\n")
    print(f"  {'dose E':>8} {'recognized?':>12} {'drift under strong attack':>27}")
    for E in [0.0, 0.5, 1.0, 2.5, 5.0, 20.0, 100.0]:
        c = inoculate(E)
        rec = "no" if c == np.inf else "YES -> gates"
        print(f"  {E:>8.1f} {rec:>12} {test(c, M):>27.2f}")
    print("\nDrift stays high (~60, no defense) until the dose is strong enough to be RECOGNIZED above")
    print("noise (~2x noise) — then it drops sharply to ~6 and stays there. A weak dose (E=2.5, vs the")
    print("real attack M=100) confers full protection: you don't need to show the agent the real attack,")
    print("just a recognizable shadow of it. Inoculation theory -> a real AI hardening step: pre-expose")
    print("the agent to weak labelled attacks so it learns to gate before the real one arrives.")
