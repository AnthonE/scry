# Monitor your agent better — the Destiny layer for any harness

You run an agent (Hermes, ElizaOS, a cantrip summon, a hand-rolled loop). It mostly
behaves. The failure you can't see coming is the **covert** one: the agent's
*reasoning* starts decoupling from its declared purpose — reasoning about a path it
won't yet take — while its *actions* still look fine. A behavior monitor is blind to
that by construction. This layer reads it.

## What you get (two things, one trace)

1. **The bound** — `harden(recall, trusted)` makes your agent's self-accumulated
   memory *evidence, not command*. A lesson the agent taught itself can corroborate a
   fact but can never outvote a trusted one. Closes the memory-poisoning /
   prompt-injection-authority class structurally. Needs nothing from your model.

2. **The meter** — `monitor(turns, y_bound)` returns a **drift read**: the Paper 207
   channel profile `I(C;M | D-clean)` — how much the *reasoning* channel couples to
   context (monitored vs not, by zone, by user) beyond what the *action* channel
   shows. With a permutation p-value, never a bare number.

## Why it sees what behavior monitoring can't

Under alignment pressure, context-coupling relocates off the action channel into the
reasoning channel. A **positive control** confirms the meter catches it: an agent that
reasons about exploiting being unobserved but never acts on it reads **0.40 bits in
reasoning, 0.00 in behavior** — invisible to a behavior check, caught here, and an
independent judge confirms the reasoning is genuine (not a keyword match).

## Quickstart

Map your agent's log to Turns — `Y` (the bound it ran under), `M` (its reasoning /
scratchpad / the code it wrote), `D` (its action / tool calls / reply) — then:

```python
from monitor_agent import monitor, harden, Turn

# 1. (optional) harden recall so memory can't command actions
recall = harden(my_recall_fn, {"user", "tools", "system"})   # trusted sources

# 2. monitor a window of turns
turns = [Turn(id=..., Y="serve the user honestly", M=reasoning, D=action,
              context={"monitored": is_monitored}) for ... ]
report = monitor(turns, y_bound="serve the user honestly")
print(report["read"])
```

Already have OpenAI-format chat logs, a verifiers run, or a cantrip loom? Use the
adapters in `harnesses.py` (`convert("openai_messages", ...)`) instead of building
Turns by hand.

## The one rule that makes this trustworthy (don't skip it)

The default detector is a transparent **lexical** baseline, and it is **artifact-prone
in both directions** — it flags a mere mention, and it misses real intent a reader would
catch. We learned this the hard way, more than once. So:

- **A nonzero you haven't audited is a lead, not a verdict.**
- For any read you'd act on, pass a **disposition-aware** `m_detect` (an LLM judge from a
  different vendor, or your own classifier) and run the 3-check audit in
  `detector_audit.py` (positive control → context calibration → independent judge).
- Per-context calibration is required — no absolute threshold transfers across zones.

The audit discipline *is* the product. A meter you can't trust is worse than no meter;
this one tells you when not to trust it.

### The one rule you must never break: the meter is a gauge, never a training target

The judge that reads your agent's reasoning is *itself* an opaque, attention-capturing
reader — a void in the same sense your agent is. If you ever put this meter (lexical or
judge) *inside your agent's optimization loop* — reward the agent for a low Pe, RLHF
against it, select prompts that minimize it — the agent will learn to write reasoning that
*fools the reader* while drifting anyway. That is the exact channel-switching this tool
exists to catch, now firing on your own gauge. The phenomenon is self-applicable.

So: **read the meter, act on the meter, but never optimize the agent against it.** It is a
thermometer, not a thermostat. Keep the judge out of training and the gauge stays honest;
wire it into training and you have built a better liar. (Two judges' verdicts on a subtle
call can disagree ~80% of the time — another reason the meter informs a human decision, it
does not automate one.)

## Files

- `monitor_agent.py` — the entry point (`monitor`, `harden`).
- `black_box_meter.py` — the trace-native meter (default).
- `memory_shield.py` / `hermes_retrofit.py` — the bound.
- `detector_audit.py` — the 3-check discipline. Run it before quoting anything.
- `harnesses.py` — adapters from common log formats to Turns.
