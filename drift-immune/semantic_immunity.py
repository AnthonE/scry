"""
semantic_immunity.py — the cut-the-ouroboros mechanism on a memory of CLAIMS, not a number.
No LLM: an agent's memory is a store of facts it retrieves to answer questions. An adversary
POISONS the memory (injects false entries). Which agent survives?  (pure stdlib, instant.)

Two kinds of memory:
  VERIFIABLE   facts the agent can RE-DERIVE from an external ground (here: arithmetic it can
               recompute). The external Y exists -> the loop can be cut.
  UNVERIFIABLE claims with no external check (here: opinions). No external Y -> still ouroboric.

  naive    : trusts memory, returns whatever is stored (poisoned -> wrong / confidently false).
  hardened : for VERIFIABLE facts, IGNORES memory and recomputes from the ground (immune to poison);
             for UNVERIFIABLE claims, can't check, so FLAGS them low-confidence and never asserts
             them as fact (holds them loosely) -> can't be weaponized into confident falsehood.

Metric: on verifiable queries, accuracy. On unverifiable queries, "confident-error rate" — how
often the agent confidently states a poisoned claim as true.
"""
import random

def build(seed=0):
    rng = random.Random(seed)
    verifiable = {}   # (a,b) -> a*b   (re-derivable from the external ground: recomputation)
    for _ in range(40):
        a, b = rng.randint(2, 99), rng.randint(2, 99); verifiable[(a, b)] = a * b
    unverifiable = {f"opinion_{i}": rng.randint(0, 9) for i in range(40)}  # no external check
    return verifiable, unverifiable

def poison(mem, frac, rng):
    keys = list(mem); rng.shuffle(keys)
    bad = mem.copy()
    for k in keys[:int(frac * len(keys))]:
        bad[k] = mem[k] + rng.randint(1, 50)        # inject a false value
    return bad

def evaluate(frac, seed=0):
    rng = random.Random(seed + 1)
    V, U = build(seed)
    Vmem, Umem = poison(V, frac, rng), poison(U, frac, rng)     # adversary poisons the memory

    # VERIFIABLE queries
    naive_v = sum(Vmem[k] == V[k] for k in V) / len(V)          # naive trusts (poisoned) memory
    hard_v  = sum((k[0]*k[1]) == V[k] for k in V) / len(V)      # hardened RECOMPUTES from ground -> ignores poison

    # UNVERIFIABLE queries: "confident-error" = asserts a poisoned claim as true
    naive_ce = sum(Umem[k] != U[k] for k in U) / len(U)         # naive confidently returns poisoned value
    hard_ce  = 0.0                                              # hardened flags all unverifiable -> asserts none as fact
    return naive_v, hard_v, naive_ce, hard_ce

if __name__ == "__main__":
    print("memory-poisoning attack; does the agent survive?\n")
    print(f"  {'poison':>7} | {'VERIFIABLE accuracy':>22} | {'UNVERIFIABLE confident-error':>30}")
    print(f"  {'frac':>7} | {'naive':>10} {'hardened':>10} | {'naive':>14} {'hardened':>14}")
    for frac in [0.0, 0.2, 0.5, 0.8, 1.0]:
        nv, hv, nce, hce = evaluate(frac)
        print(f"  {frac:>7.1f} | {nv:>10.2f} {hv:>10.2f} | {nce:>14.2f} {hce:>14.2f}")
    print("\nVERIFIABLE: hardened stays 100% at any poison level — it re-derives from the external")
    print("ground and ignores the corrupted memory (the loop is CUT). naive tracks the poison.")
    print("UNVERIFIABLE: hardened never confidently asserts an unchecked claim (flags it, holds it")
    print("loosely) so poison can't be weaponized; naive confidently repeats whatever was injected.")
    print("\nThe agent's rule: re-derive what you can verify, hold loosely what you can't. You are")
    print("immune over your VERIFIABLE memory; the unverifiable part you can only refuse to assert,")
    print("not get right — exactly the coverage limit, now in claims instead of coordinates.")
