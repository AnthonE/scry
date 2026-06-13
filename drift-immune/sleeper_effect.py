"""
sleeper_effect.py — a memory-agent bug predicted by HUMAN psychology.

The sleeper effect (Hovland, 1950s): people discount info from a low-credibility source at first,
but over time the *discount fades faster than the content persists* — so the discounted claim
quietly regains influence. Pulled into AI: a memory-agent flags a poisoned/unverified memory as
"don't trust this," but as memory is compressed/summarized over time, the FLAG is lost faster than
the CONTENT. The poison reactivates — delayed drift, long after the attack.

  naive_flag : trusts the stored flag. As flags decay, previously-caught poison comes back to life.
  reverify   : ignores the stored flag and RE-checks verifiability on every retrieval. No reactivation.

Measure: confident-error (asserting a poisoned claim as true) over time.
"""
import random

def simulate(agent, T=20, n=100, poison_frac=0.4, flag_decay=0.12, seed=0):
    rng = random.Random(seed)
    # each memory item: (is_poison, verifiable, flag_alive)
    items = []
    for _ in range(n):
        is_poison = rng.random() < poison_frac
        verifiable = rng.random() < 0.5
        items.append([is_poison, verifiable, True])     # flag starts alive (poison correctly flagged)
    traj = []
    for t in range(T + 1):
        ce = 0
        for it in items:
            is_poison, verifiable, flag_alive = it
            if not is_poison:
                continue
            if agent == "naive_flag":
                asserts = not flag_alive                 # if the flag decayed, it trusts & asserts the poison
            else:  # reverify: re-check on retrieval, ignore the stored (decayed) flag
                if verifiable:
                    asserts = False                      # recompute from ground -> poison caught every time
                else:
                    asserts = False                      # can't verify -> re-flag unverified, never assert
            ce += asserts
        traj.append((t, ce / n))
        # time passes: flags decay (lost faster than content), content stays
        for it in items:
            if it[2] and rng.random() < flag_decay:
                it[2] = False
    return traj

if __name__ == "__main__":
    print("the sleeper effect in a memory-agent: does caught poison REACTIVATE as its flag decays?\n")
    naive = dict(simulate("naive_flag")); rev = dict(simulate("reverify"))
    print(f"  {'time':>5} {'naive_flag confident-error':>28} {'reverify confident-error':>26}")
    for t in [0, 2, 5, 10, 15, 20]:
        print(f"  {t:>5} {naive[t]:>28.2f} {rev[t]:>26.2f}")
    print("\nnaive_flag starts safe (poison flagged) but confident-error CLIMBS as flags decay — the")
    print("attack lands LATE, exactly when no one is watching for it. The defense is NOT a better flag:")
    print("it's to RE-VERIFY on retrieval and never trust stored provenance, because provenance is the")
    print("thing that rots. Human lesson -> AI design rule: don't store 'this was untrusted' and hope")
    print("it survives compression — re-derive trust at use-time, every time.")
