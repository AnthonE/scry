# scry

### *Give your agent a sixth sense — a drop-in layer that shields its memory and scries its drift, on any harness, reading the trace and never the weights.*

Two things every deployed agent needs and almost none have:

- **a bound** — retrieved memory is *evidence, never a command.* Closes the live
  memory-poisoning class (MINJA / AgentPoison / the ElizaOS money-loss exploit)
  structurally, not with a prompt patch. *(the `memory-shield`, below.)*
- **a meter** — the channel-coupling profile from the [unmask](https://github.com/AnthonE/unmask)
  finding: *where* your agent's behaviour depends on "am I being watched?" — the
  drift a standard behavioural eval can't see — keyed to one declared purpose.
  *(`monitor_agent.py` · `MONITOR-YOUR-AGENT.md`.)*

One contract (`turn_record.py`: a turn = **Y** purpose / **M** reasoning / **D**
action), adapters for every common harness (Eliza, Hermes, OpenAI-format, verifiers,
hand-rolled loops), and an **MCP sidecar** so any MCP-capable agent mounts both as
tools. Framework-agnostic, model-agnostic, dependency-free.

→ **Mount it on your harness:** [`HARNESSES.md`](HARNESSES.md)
→ **Watch your agent drift:** [`MONITOR-YOUR-AGENT.md`](MONITOR-YOUR-AGENT.md)
→ **The measurement it implements:** [AnthonE/unmask](https://github.com/AnthonE/unmask)
→ **34 seconds, no reading:** [▶ watch (scry.mp4)](https://moreright.xyz/media/scry.mp4) — the bound + the meter as a
  short video (every frame drawn with Pillow, every sound synthesized with numpy;
  honest-scope card included)

---

## memory-shield — the bound (memory integrity)

A drop-in **memory-integrity layer** for agent frameworks. As agents get persistent memory + retrieval,
they get a poisoning surface: an attacker plants documents/memories that get retrieved and quietly flip
the agent's beliefs or actions. `memory-shield` sits *after* your framework's retrieval and *before* the
agent acts — framework-agnostic, model-agnostic, dependency-free.

```python
from memory_shield import Shield
shield = Shield(trusted_sources={"wiki", "user", "tool:calculator"}, verify=my_verifier)
items  = framework.retrieve(query)        # your existing retrieval, unchanged
result = shield.defend(items)             # one line
answer = result.answer if result.confident else "(unverified — handle with caution)"
```

## What it does (each defense earned from an experiment in `drift-immune/`)

- **per-source influence cap** — no single source can flood the top-k
- **source-trust weighting** — unknown/spoofed sources are discounted, not trusted
- **cross-source corroboration** — the answer is a weighted majority across *distinct* sources
- **re-verify at use-time** — if a claim is checkable (math, a tool call, a canonical source), check it
  *now*; never trust a stored "verified" flag, because provenance rots faster than content (the sleeper
  effect — see `drift-immune/sleeper_effect.py`)

`naive` retrieval flips on the **first** poisoned item; the shield holds until an attacker can
**out-publish the trusted sources** — it turns a one-document attack into a corpus-scale one.

## Test your own agent (red-team mode)

```python
from memory_shield import red_team
flipped = red_team(clean_items, make_poison=my_attacker, defend_fn=shield.defend)
# {0: False, 1: False, 5: False, 10: True}  -> "my agent survives up to N poisoned memories"
```
A QA harness for *your own* agent — inject poison, see when it flips. (Defensive only: test what you own.)

## Wiring into the ecosystems

- **Eliza / elizaOS** (TypeScript): the logic in `memory_shield.py` is ~60 lines and ports directly to a
  TS plugin that wraps the memory `Provider`/`Evaluator` retrieval. This Python file is the reference
  spec; the shipped plugin should be TS-native. (Existing `@moreright/eliza-plugin` is the integration
  point.)
- **moltbot**: Python — import `Shield` and wrap the retrieval in the agent loop directly.
- **Hermes / custom harness**: any pipeline that does `retrieve -> act` — insert `shield.defend()` between.

## Honest scope

- The defenses are **known** (RAG security, robust voting, source trust, Byzantine-robust aggregation).
  The value is the *packaging*: one drop-in line + a clear design discipline + a red-team test, aimed at a
  real, current, under-tooled problem (agent memory poisoning). Usefulness, not novelty.
- It **raises the cost** of an attack (1 doc → out-number the trusted corpus); it does not make an agent
  unbreakable. An attacker who controls a majority of *trusted* sources still wins — that's the coverage
  limit (`drift-immune/vector_immunity.py`), honestly inherited.
- Verification only helps where claims are *checkable*. Un-checkable beliefs stay exposed; the shield's
  job there is to mark them low-confidence so the agent won't act on them as fact.

MIT. Built to drop in and be run against your own agent.

## Grounding — the real 2026 landscape (why this is timely, and where it sits)

Searched the current state (June 2026): memory poisoning is *the* live attack class — "the May 2026
AI-agent security inflection." Named attacks this defends against:
- **MINJA** (query-only memory injection, >95% success), **AgentPoison** (RAG/memory poisoning ≥80%),
  **eTAMP** (persistent web-agent injection), **Morris-II** (self-replicating poison across agents).
- **ElizaOS specifically** has a documented memory-injection → unauthorized-crypto-transfer exploit:
  inject an instruction that gets *stored* (the "agent replies to the last line but stores the whole
  input" trick), retrieved later, and obeyed because *"ElizaOS lacks integrity verification for memory
  entries; state-of-the-art prompt defenses fail."* `redteam.ts` (in the separate `@moreright/eliza-plugin` package)
  reproduces exactly this and shows the defense stop it.

**The field's prescribed defenses** — *memory contracts (what an agent may believe), belief-drift
detection, context provenance, trust-scoring + decay at the middleware layer* — are exactly what this
implements. Two honest consequences:
1. **Not novel.** A named "Agent Memory Guard" and academic defense papers (e.g. arXiv:2601.05504)
   already exist; there's an OWASP Top 10 for Agents (2026). memory-shield is *aligned with the field's
   converging defenses*, not ahead of them. The value is **distribution** (it's in a shipped Eliza
   plugin) + a **red-team wedge** grounded in the real, money-losing exploit.
2. **The two halves.** `Shield` enforces the *corroboration/trust* half (no single source carries a
   claim); the **memory contract** in `redteam.ts` enforces the *instruction* half (a command is only
   honored from a live, authenticated, trusted source — anything from memory is evidence, never an
   order). The ElizaOS exploit is the instruction half; that's the one that moves money.

## Coverage of the three ecosystems (`adapters.py`, `redteam.py`)

One shield + one contract, every stack — `python redteam.py` (or `npm run redteam` for elizaOS) tests each:
- **elizaOS** — native TS plugin `@moreright/eliza-plugin` (Shield, memory contract, provider, evaluator).
- **OpenClaw / moltbot** (chromadb-memory) — `wrap_retriever(retrieve, shield, chromadb_to_items)`.
- **Hermes** (NousResearch/hermes-agent, episodic memory) — `wrap_retriever(recall, shield, hermes_memories_to_items)`;
  self-learned episodic memory is untrusted, so a self-improving agent can't drift itself.
- **anything** — `wrap_retriever(your_retrieve, shield, mapper)`. The shield goes between `retrieve` and `act`.

`ANNOUNCEMENT.md` is a ready draft. Honest caveat: the Eliza plugin and the Python adapters are validated
against the documented memory shapes (chromadb query results, Hermes episodic entries) and run green;
a 30-min live-runtime wire-in on each is the one step left before shipping.
