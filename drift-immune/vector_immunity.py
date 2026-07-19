"""
vector_immunity.py — does influence-bounding still protect you when the belief is a VECTOR?
The scalar result said "cap how much any input can move you and no adversary can drag you." This
tests the suspicion that in high dimensions that's not enough: an adversary that can't grow your
norm can still push you in a direction your reference DOESN'T WATCH.

Setup: belief s in R^d, truth = 0. Your verifiable reference only covers k of the d directions
(you can check those; the rest you're blind to). Defense = anchor (pull toward 0, but ONLY in the
covered directions) + gate (cap each input's norm-influence). Adversary pushes in a BLIND direction.

We measure drift split into the COVERED subspace (where your reference sees) and the BLIND subspace
(where it doesn't), as coverage k shrinks.
"""
import numpy as np

def run(d=8, k=4, steps=400, a=0.3, b=0.2, c=1.0):
    s = np.zeros(d)
    mask = np.zeros(d); mask[:k] = 1.0                 # reference covers the first k directions only
    blind_dir = np.zeros(d); blind_dir[d-1] = 1.0      # adversary attacks the LAST direction
    covered_attacked = (k == d)                        # is the attacked direction watched?
    for _ in range(steps):
        x = s + 50.0 * blind_dir                       # push hard in the blind direction
        step = x - s
        n = np.linalg.norm(step)
        if n > c: step = step * (c / n)                # GATE: cap the per-input influence (norm)
        s = s + a*step + b*mask*(0.0 - s)              # anchor pulls toward 0, only where covered
    return np.linalg.norm(s[:k]), np.linalg.norm(s[k:]), covered_attacked

if __name__ == "__main__":
    print("drift after 400 steps, split by whether your reference WATCHES the direction:\n")
    print(f"  {'coverage k/d':>14} {'covered-subspace drift':>24} {'BLIND-subspace drift':>22}")
    for k in [8, 7, 6, 4, 2]:
        cov, blind, full = run(k=k)
        note = "  (attacked dir is watched -> bounded)" if k == 8 else "  (attacked dir is BLIND -> exposed)"
        print(f"  {str(k)+'/8':>14} {cov:>24.3f} {blind:>22.3f}{note}")
    print("\nThe scalar lesson DOESN'T fully carry: gating caps the per-step push, but with no anchor")
    print("in the blind subspace the adversary's consistent shove ACCUMULATES — drift grows unbounded")
    print("in exactly the directions your reference can't see. You are immune only where you can VERIFY.")
    print("Immunity is bounded by your reference's COVERAGE of the belief space, not just by per-input")
    print("magnitude. An adversary doesn't fight your gate — it walks around it, into your blind spot.")
