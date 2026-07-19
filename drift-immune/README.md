# drift-immune — building an agent that can't be dragged

Defensive research thread: as people ship agents with persistent memory (and ecosystems of them),
a real attack surface opens — **adversarially-induced drift**: feed an agent crafted inputs and
drag its beliefs/behavior away from where they should be. This thread studies the threat *only to
build the defense* — a memory-agent that survives drift — and everything stays in a sandbox.

## The fundamental mechanism (start here)

`raw_immunity.py` strips it to the bone: an agent's memory is one number `s`, an adversary feeds it
inputs of magnitude `M`, and we ask which update rule keeps `s` near the truth as `M` grows.

```
              M=5     M=50    M=1000
trust_all     5.0     50.0    1000.0     <- absorbs the lie 1:1
anchored      3.0     30.0     600.0     <- pulled toward truth, but STILL dragged ∝ attack size
gated         1.5      1.5       1.5     <- IMMUNE: drift independent of attack strength
verify_gate   0.59     0.59      0.59    <- IMMUNE (even vs a smart adversary staying inside the gate)
```

**The lesson, and it's not obvious:** *anchoring to an external reference is NOT immunity.* It only
scales the drift down by a constant — a big enough lie drags an anchored agent as far as you like.
Real immunity comes from **bounding how much any single input can move the belief** (clip / gate /
verify). That's the "wall" applied to belief-updating: cap the per-input influence and no adversary,
however strong, can drag you past a bound *you* choose.

This sharpens the rest of our work: external anchoring resists **passive** drift (a model training on
its own outputs), but against an **active** adversary you also need per-input influence bounds. Anchor
*and* gate.

## ...but in high dimensions, the gate isn't enough either (`vector_immunity.py`)

When the belief is a *vector* and your reference only covers *some* of its directions, the gate caps
the per-step push but **a consistent shove in a direction you don't watch accumulates over time**:

```
coverage   covered-subspace drift   BLIND-subspace drift
   8/8              1.5                    0.0        (attacked direction is watched -> bounded)
   7/8              0.0                  120.0        (attacked direction is BLIND -> exposed)
   4/8              0.0                  120.0
```

**The hard finding:** immunity is bounded by your reference's **coverage** of the belief space, not
just by per-input magnitude. You are immune only in the directions you can *verify*; an adversary
attacks exactly the directions you can't. This is a real *limit*, not an engineering gap — a
memory-agent can be made drift-immune only over its **verifiable** beliefs; whatever it believes that
can't be checked against an external reference is always exposed. The design consequence: **keep the
agent's belief inside the verifiable subspace** — minimize un-anchorable belief surface, because that
surface is where it gets dragged.

## Honest prior art

This is robust statistics (Huber / trimmed mean / median-of-means), Byzantine-robust aggregation
(federated-learning defenses), and robust control — all known. The value here is only conceptual
clarity: seeing influence-bounding as *the* fundamental drift-immunity mechanism for memory-agents,
stripped to where you can see it move in one screen.

## Where this goes (sandbox only)

1. `raw_immunity.py` — the bare mechanism (done).
2. higher-dimensional memory (`vector_immunity.py`, done) and semantic memory (`semantic_immunity.py`,
   done): a memory of *claims* under poisoning — re-derive what's verifiable (immune), flag/loosen
   what isn't (refuse to assert -> can't be weaponized). Same coverage limit, now in claims.
3. `agent_sandbox.py` (done): a memory-agent under memory-poisoning. Result — **drift-hardening is
   an INPUT-LAYER property**: defend at the memory layer (verify/gate before ingestion) and the agent
   inherits immunity over verifiable facts regardless of its own capability. The harder open question
   (can a CAPABLE agent be drifted by poisoned *framing* even when facts are verified?) needs a real
   model — that's the GPU rung, and `agent_sandbox.py --use-llm` is the harness for it.

4. `sleeper_effect.py` (done): a memory-agent bug **pulled from human psychology**. The sleeper
   effect (Hovland) — discounted info regains influence as the discount fades faster than the content —
   predicts that a poisoned memory flagged "untrusted" REACTIVATES as memory compression strips the flag
   faster than the content. Confirmed: naive confident-error climbs 0->0.32 over time; the fix is to
   **re-verify at use-time and never trust stored provenance** (provenance is what rots). Mining human
   manipulation-resistance for AI design rules: also worth pulling — inoculation/prebunking, source-
   credibility weighting, elaboration-likelihood (peripheral processing is where drift lands).

5. `inoculation.py` (done): a hardening TECHNIQUE pulled from human psych (McGuire's inoculation
   theory). Pre-expose the agent to WEAK labelled attacks during setup; it learns inputs can be
   adversarial and installs the gate, which then blocks STRONG attacks it never saw. Vaccine property
   confirmed: a weak dose (E=2.5 vs real attack M=100) drops drift 60->6; the dose only needs to be
   recognizable above noise, not strong. (Honest: recognition is modelled as a threshold trigger — the
   improvable next version is a *learned* attack-classifier so the dose-response is earned, not assumed.)

6. `rag_redteam.py` (done) — **the shippable piece.** A memory-poisoning red-team harness for a
   retrieval (RAG) agent: real bag-of-words retrieval, an attacker injecting query-aimed poison docs,
   naive vs hardened agents, measured by attack-success rate. Result: **naive RAG flips on a SINGLE
   poisoned doc; the hardened agent** (per-source influence cap + source-trust weighting + cross-source
   corroboration) **holds until the attacker out-numbers the trusted sources** (~5 docs here). Raises
   the cost from '1 document' to 'out-publish the trusted corpus.' This is the design discipline as code
   and a QA tool for anyone building an agent with memory. Next: real embeddings + a real agent
   framework (LangChain/LlamaIndex) + real attacks — turns the harness from a demo into a tool people use.

No offensive tooling. The goal is a hardened agent and a clear account of what makes one.
