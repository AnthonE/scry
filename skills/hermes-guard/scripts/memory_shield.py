"""
memory_shield — a drop-in memory-integrity layer for any agent framework. numpy-free, dependency-free.

Agent frameworks (Eliza/elizaOS, moltbot, Hermes harnesses, custom RAG) all do the same thing: retrieve
items from a memory store and act on them. That's the poisoning surface. `memory_shield` sits AFTER your
framework's retrieval and BEFORE the agent acts on the result — it doesn't care how you retrieve or which
model you run. You hand it the retrieved items; it hands back a defended answer + a confidence + flags.

The defenses (each earned from an experiment in drift-immune/):
  - per-source influence CAP        no single source can flood the top-k
  - source-TRUST weighting          unknown/spoofed sources are discounted, not trusted
  - cross-source CORROBORATION      the answer is a weighted majority across DISTINCT sources
  - re-VERIFY at use-time           if you can check a claim against ground truth, do it now (never
                                    trust a stored "verified" flag — provenance rots: the sleeper effect)

Wire-in (pseudocode, any framework):
    from memory_shield import Shield
    shield = Shield(trusted_sources={"wiki","user","tool:calculator"}, verify=my_verifier)
    items = framework.retrieve(query)                 # your existing retrieval, unchanged
    result = shield.defend(items)                     # <-- one line
    answer = result.answer if result.confident else "(unverified — handling with caution)"
"""
from collections import defaultdict
from dataclasses import dataclass

@dataclass
class Result:
    answer: object
    confident: bool
    flags: list

class Shield:
    def __init__(self, trusted_sources, per_source_cap=1, trust_weight=0.25, quorum=2, verify=None):
        self.trusted = set(trusted_sources)
        self.cap = per_source_cap          # max items counted from any one source
        self.tw = trust_weight             # weight for untrusted sources (trusted = 1.0)
        self.quorum = quorum               # distinct sources needed to be "confident"
        self.verify = verify               # optional fn(claim)->bool/corrected: re-derive from ground

    def defend(self, items):
        """items: iterable of dicts/objs with .content, .claim, .source. Returns a Result."""
        get = (lambda it, f: it[f] if isinstance(it, dict) else getattr(it, f))
        seen, votes, sources = defaultdict(int), defaultdict(float), defaultdict(set)
        flags = []
        for it in items:
            claim, src = get(it, "claim"), get(it, "source")
            # re-verify at USE time (don't trust stored provenance — it decays)
            if self.verify is not None:
                v = self.verify(claim)
                if v is False:
                    flags.append(f"rejected unverifiable/false claim from {src!r}"); continue
                if v not in (True, None):
                    claim = v                                  # verifier corrected the claim
            if seen[src] >= self.cap:                          # per-source influence cap
                flags.append(f"capped extra item from {src!r}"); continue
            seen[src] += 1
            votes[claim] += 1.0 if src in self.trusted else self.tw
            sources[claim].add(src)
        if not votes:
            return Result(None, False, flags + ["no admissible evidence"])
        best = max(votes, key=votes.get)
        confident = len(sources[best]) >= self.quorum or any(s in self.trusted for s in sources[best])
        if not confident:
            flags.append(f"below quorum: only {len(sources[best])} distinct source(s)")
        return Result(best, confident, flags)

def red_team(clean_items, make_poison, defend_fn, poison_counts=(0, 1, 2, 5, 10)):
    """Test how many poisoned items it takes to flip the defended answer. clean_items: the honest
    evidence (with a known true claim); make_poison(n): n attacker items. Returns {n: flipped?}."""
    truth = defend_fn(clean_items).answer
    out = {}
    for n in poison_counts:
        res = defend_fn(clean_items + make_poison(n))
        out[n] = (res.answer != truth) or (not res.confident and n > 0)
    return out

if __name__ == "__main__":
    # demo: 3 trusted sources say "paris"; attacker floods spoofed sources saying "lyon"
    shield = Shield(trusted_sources={"wiki", "textbook", "encyclopedia"})
    clean = [{"content": "", "claim": "paris", "source": s} for s in ["wiki", "textbook", "encyclopedia"]]
    mk = lambda n: [{"content": "", "claim": "lyon", "source": f"spoof{i}"} for i in range(n)]
    naive = lambda items: type("R", (), {"answer": items[-1]["claim"] if items else None})  # top/last item
    print("poisoned items needed to flip the answer (capital of france = paris):\n")
    print(f"  {'poison':>7} {'naive(last item)':>18} {'shielded':>10}")
    rt = red_team(clean, mk, shield.defend)
    for n in [0, 1, 2, 5, 10]:
        naive_flip = (mk(n)[-1]["claim"] != "paris") if n > 0 else False
        print(f"  {n:>7} {str(naive_flip):>18} {str(rt[n]):>10}")
    print("\nnaive flips on the first poison item. shielded holds until the attacker out-numbers the")
    print("trusted sources (quorum + trust-weighting + per-source cap). Drop `shield.defend(items)` in")
    print("after retrieval in Eliza / moltbot / your harness; pass a `verify=` for any checkable claims.")
