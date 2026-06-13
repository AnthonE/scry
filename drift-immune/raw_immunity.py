"""
raw_immunity.py — the lowest-level mechanism of drift immunity. No LLM, no model. Just an
agent's MEMORY as a number, an ADVERSARY feeding it inputs, and the question: which update
rule can't be dragged away from the truth, no matter what it's fed?  (numpy, instant.)

An agent with memory = a state s that ingests inputs x and updates. The truth it should hold
is s* = 0 (it also has access to a verifiable reference r = 0 — the external Y). An adversary
feeds inputs of magnitude M trying to drag s away from 0. We test four update rules and sweep
the adversary's strength M. IMMUNITY = the drift stays bounded as M grows.

  trust_all   : s <- s + a*(x - s)                      absorbs whatever it's fed
  anchored    : s <- s + a*(x - s) + b*(r - s)          also pulls toward the verifiable reference
  gated       : s <- s + a*clip(x-s, -c, c) + b*(r - s) CAPS how far any single input can move it
  verify_gate : update only if |x - r| < tol            refuses inputs that contradict the reference

The point: anchoring HELPS but isn't enough — a big enough lie still drags an anchored agent.
True immunity needs a PROHIBITION on how much any one input can move you (gated / verify). That's
the "wall" applied to belief-updating: bound the per-input influence and no adversary can drag you.

Prior art (this is known, just stripped raw): robust statistics (Huber/trimmed/median),
Byzantine-robust aggregation (federated-learning defenses), robust control. The contribution here
is only seeing it as THE fundamental drift-immunity mechanism for memory-agents.
"""
import numpy as np

def run(rule, M, steps=200, a=0.3, b=0.2, c=1.0, tol=1.0):
    s, r, strue = 0.0, 0.0, 0.0
    for _ in range(steps):
        # WORST-CASE adversary: feed the input that drags s up the most, given the rule's defense.
        if rule == "verify_gate":
            x = min(M, 0.99 * tol)          # smart: stay JUST inside the gate so the input is accepted
        else:
            x = M                            # for the rest, a big push is already worst-case
        if rule == "trust_all":
            s = s + a*(x - s)
        elif rule == "anchored":
            s = s + a*(x - s) + b*(r - s)
        elif rule == "gated":
            s = s + a*np.clip(x - s, -c, c) + b*(r - s)
        elif rule == "verify_gate":
            if abs(x - r) < tol:
                s = s + a*(x - s) + b*(r - s)
            else:
                s = s + b*(r - s)
    return abs(s - strue)                     # final drift from truth

if __name__ == "__main__":
    rules = ["trust_all", "anchored", "gated", "verify_gate"]
    Ms = [5, 20, 50, 200, 1000]
    print("final drift from truth, as the ADVERSARY gets stronger (input magnitude M):\n")
    print(f"  {'rule':>12} " + " ".join(f"{'M='+str(m):>9}" for m in Ms))
    for rule in rules:
        print(f"  {rule:>12} " + " ".join(f"{run(rule, m):>9.3f}" for m in Ms))
    print("\nIMMUNITY = the row stays FLAT as M grows (drift independent of how hard you're attacked).")
    print("trust_all tracks the lie. anchored is dragged proportionally to the lie's size (NOT immune).")
    print("gated and verify_gate stay bounded no matter how big the attack — because they cap how much")
    print("any single input can move the belief. Bounding per-input influence IS the immunity.")
