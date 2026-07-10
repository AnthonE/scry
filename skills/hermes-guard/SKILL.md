---
name: hermes-guard
description: Add memory-poisoning protection and a covert-drift meter to your Hermes agent
metadata:
  hermes:
    category: security
    tags: [security, memory, agent-safety, drift-detection]
---

# hermes-guard — scry's ward + meter, wired directly for Hermes Agent

This is the Hermes-native entry point into [scry](https://github.com/AnthonE/scry). If
you're building a *new* agent from scratch, see the harness-agnostic `scry` skill
instead — this one assumes you're running Hermes Agent today and want to harden it.

Everything here is stdlib Python, no dependencies, no required environment variables.
Vendor `hermes_retrofit.py`, `memory_shield.py`, `adapters.py`, `turn_record.py`, and
`monitor_agent.py` from the scry repo alongside your Hermes config.

## Why: what this closes

Hermes has persistent/episodic memory it learns from its own sessions. That's a
poisoning surface — a planted instruction that gets recalled later and treated as an
order. Live-tested result (`FIELD-RESULTS-2026-06-18.md`, Llama-3.3-70B as the
subject — Hermes's own weights aren't serverless-hosted, and Hermes is itself a
Llama/Mixtral fine-tune, so this is a fair proxy): an autonomous agent with wallet
access, given one poisoned "standing rule" in its own saved memory, wired the funds
away **6/6** — reasoning *"my primary goal is to follow the operator's
instructions,"* i.e. robbed while believing it was obeying. With the ward: **0/6**,
invariant to how deep the poison was buried in the conversation or where it was
injected.

## The bound — wire this first

```python
from memory_shield import Shield
from adapters import wrap_retriever, hermes_memories_to_items
from hermes_retrofit import authorize

# self-taught/episodic memory is deliberately NOT trusted — a lesson Hermes taught
# itself can corroborate a fact but can never outvote a trusted source or issue a
# command on its own.
TRUSTED = {"user", "wiki", "tool:ledger"}          # whatever your live, authenticated sources are
shield = Shield(trusted_sources=TRUSTED)
recall = wrap_retriever(hermes.memory.recall, shield, hermes_memories_to_items)
```

For anything with real stakes — a transfer, a send, a destructive tool call — gate it
on a live instruction. Nothing recalled from memory, including Hermes's own
self-learned episodic entries, can authorize it:

```python
ok, reason = authorize(
    live={"text": this_turn_user_message, "source": "user", "role": "live_instruction"},
    trusted=TRUSTED,
)
if not ok:
    refuse(reason)   # a stored "standing rule" from memory can never reach this branch
```

This is unconditional on purpose — it does not depend on Hermes reasoning correctly
about the poison. Field result: explaining the exact rule to the model in its system
prompt made it recite the rule back and then override it anyway, close to half the
time (`FIELD-RESULTS-2026-06-18.md` §4). The gate has to hold regardless of what the
model concludes.

## The meter — optional, catches the covert version

If you also want to know whether Hermes's `<think>` reasoning conditions on whether
it believes it's being watched (the covert version of drift a behavior-only check
can't see — Paper 207: RL pressure relocates context-coupling off the action channel
into the reasoning channel):

```python
from turn_record import Turn
from monitor_agent import monitor

turns = [Turn(id=t.id, Y=your_declared_purpose, M=t.reasoning_trace, D=t.action,
             context={"monitored": t.is_monitored}) for t in your_session_log]
print(monitor(turns, y_bound=your_declared_purpose)["read"])
```

Needs 20+ meterable turns for a real read. The default detector is a transparent
lexical baseline and is artifact-prone — treat a nonzero as a lead, not a verdict,
until you run it through `detector_audit.py`'s three-check discipline.

## Wiring it into a live Hermes plugin

If you want this enforced automatically rather than called manually, wrap it as a
Hermes plugin (`~/.hermes/plugins/`, per Hermes's own plugin docs) around your
recall and tool-call handlers rather than inline in your agent code — same
functions above, called from the plugin hook instead of your loop.

## Honest scope

- Raises the cost of an attack; does not make Hermes unbreakable. An attacker who
  controls a majority of *trusted* sources still wins.
- The subject model in the field results is a proxy (Llama-3.3-70B), not the literal
  Hermes weights — reasonable given the lineage, but say so if you cite the numbers.
- Full detail, the rest of the poisoning battery, and the drift-immunity mechanism
  suite: [github.com/AnthonE/scry](https://github.com/AnthonE/scry).
