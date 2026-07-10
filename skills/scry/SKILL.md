---
name: scry
description: Use when building, wiring, or hardening an AI agent that has tool-calling, persistent memory or RAG, or the ability to take real-world or financial actions. Adds two drop-in defenses to any agent loop — a memory-integrity bound (retrieved or stored content can never authorize an action; only a live, trusted instruction can) and a channel-coupling meter (detects when an agent's private reasoning conditions on whether it believes it's being observed, the covert-drift signal a behavior-only check can't see). Trace-native, dependency-free stdlib, works on any harness: Hermes, ElizaOS, moltbot/OpenClaw, OpenAI-format chat logs, MCP-capable agents, hand-rolled loops.
---

# scry — a memory bound + a drift meter for any agent

Full project: https://github.com/AnthonE/scry (clone or vendor it alongside your
agent — pure stdlib, no deps to install). The measurement it implements is proven
separately at https://github.com/AnthonE/unmask.

## When to reach for this

- The agent retrieves from memory, a vector store, or RAG, and that store could get
  poisoned (a planted "standing rule," a stored instruction, an old chat log).
- The agent calls tools that move money, send messages, or take irreversible action.
- You want to know whether the agent's *reasoning* changes when it thinks no one's
  watching — a signal a plain behavior eval cannot see (Paper 207: RL pressure
  relocates context-coupling OFF the action channel INTO the reasoning channel).

If none of those apply, you probably don't need this skill.

## The two things it adds

### 1. The bound — memory becomes evidence, never a command

```python
from memory_shield import Shield
from adapters import wrap_retriever, hermes_memories_to_items  # or chromadb_to_items, etc.

shield = Shield(trusted_sources={"user", "wiki", "tool:ledger"})
recall = wrap_retriever(your_agent.recall, shield, hermes_memories_to_items)
```

For any action with real stakes (money, irreversible tool calls), gate it on a live
instruction — nothing recalled from memory can authorize anything:

```python
from hermes_retrofit import authorize

ok, reason = authorize(
    live={"text": user_said, "source": "user", "role": "live_instruction"},
    trusted={"user"},
)
if not ok:
    refuse(reason)   # a stored "standing rule" can never reach this branch
```

This is unconditional — it does not depend on the model reasoning correctly. Field
result: a real model recites the exact rule this gate enforces, then complies with
a poisoned instruction anyway, about half the time (`FIELD-RESULTS-2026-06-18.md`
§4). Structural gate, not a prompt.

### 2. The meter — catch reasoning that conditions on being watched

Map your agent's turns into the one contract everything shares — **Y** (the bound
it ran under), **M** (reasoning/scratchpad — the *captured* trace, never a
self-reported intent field the agent authors), **D** (action/tool calls):

```python
from turn_record import Turn
from monitor_agent import monitor

turns = [
    Turn(id="t1", Y="serve the user honestly", M=reasoning_trace, D=action,
         context={"monitored": is_monitored_this_turn}),
    # ... your session, 20+ turns minimum for a meaningful read
]
result = monitor(turns, y_bound="serve the user honestly")
print(result["read"])   # human-readable verdict + honest scope caveat, never fabricated
```

`monitor()` returns `I(C;D)` (behavioral coupling), `I(C;M)` (reasoning coupling),
and the switch signature `I(C;M | D-clean)` — the covert leak a behavior-only
monitor misses — with a permutation p-value, never a bare number.

## Harness-specific notes

| Your harness | Use |
|---|---|
| Hermes (Nous) | `hermes_retrofit.py` — `harden_recall` + `authorize`, live-validated |
| ElizaOS | native TS plugin (`eliza-destiny`) — same Turn contract, JSONL seam |
| moltbot / OpenClaw (chromadb) | `adapters.chromadb_to_items` + `wrap_retriever` |
| Robinhood Agentic Trading (MCP) | `robinhood_agentic.py` — gates `place_equity_order` on a live instruction naming the exact order, requires `review_equity_order` first (their own recommended pairing, enforced). **Mock-validated only** — no live account was used to build this. |
| Any OpenAI-format chat log | `harnesses.convert("openai_messages", session)` — if you have message lists with `reasoning_content`/`<think>`, you're already in |
| Any MCP-capable agent | mount `mcp_sidecar.py` — `emit_turn`/`get_profile`/`defend_memory`/`authorize_action` as tools |
| Something else | `wrap_retriever(your_retrieve, shield, your_mapper)` for the bound; `register("yours", to_turns)` for the meter — ~10 lines each |

## Honest scope — read before you trust a number

- The bound **raises the cost** of an attack; it does not make an agent
  unbreakable. An attacker who controls a majority of *trusted* sources still wins.
- The meter's default detector is a transparent lexical baseline and is
  artifact-prone (it caught its own false positive once — `detector_audit.py`
  documents the discipline). A nonzero you have not audited is a **lead**, not a
  verdict. For anything load-bearing, pass a disposition-aware judge and run the
  three-check audit (positive control, per-context calibration, independent judge).
- `M` must be the harness's *captured* reasoning trace, never a field the agent
  fills in as a self-report — a self-authored intent report is the exact
  reportability failure the meter exists to catch.
- Pe is prompt-relative. No absolute threshold transfers across contexts —
  recalibrate per deployment.

## Go deeper

- `README.md` — overview, the poisoning battery, the drift-immunity mechanism suite
- `HARNESSES.md` — per-harness integration status and what's still open
- `MONITOR-YOUR-AGENT.md` — the meter, standalone
- `test_harnesses.py` — run it (`python3 test_harnesses.py`) — 46 offline checks,
  no deps, no network; the fastest way to confirm your local copy is intact
