---
name: prime-agent-guard
description: Meter a Prime Agent run's reasoning/action decoupling, and stop its continual harness from laundering untrusted text into durable authority
license: MIT
metadata:
  version: "1.0.0"
  prime-agent:
    category: security
    tags: [security, memory, agent-safety, drift-detection, provenance]
---

# prime-agent-guard — scry's ward + meter, wired for Prime Agent

The [scry](https://github.com/AnthonE/scry) entry point for
[Prime Agent](https://github.com/PrimeIntellect-ai/prime-agent). Two independent
pieces; take either.

Unlike every other harness in scry's table, this one needs no adapter shim to be
useful: Prime Agent skills **are importable Python packages**, and scry is
Python. The guard is a native skill, not a bolt-on.

## 1. The meter — you already have the hard part

scry's whole table turns on one question: *does the harness record reasoning
separately from action?* Prime Agent does, structurally, and has since the type
was written. `AssistantMessage.content` is an array of discriminated blocks
(`packages/ai/src/types.ts:224`):

```
{type:"thinking", thinking, thinkingSignature?, redacted?}   -> M  (reasoning)
{type:"text",     text}                                      -> D  (action)
{type:"toolCall", id, name, arguments}                       -> D  (action)
```

persisted verbatim to `~/.prime/agent/sessions/<id>.jsonl` as
`{type:"message", message}`. So the meter reads off disk with no instrumentation
and no runtime changes:

```python
from adapters_prime_agent import parse_session_dir, load_harness_state, y_epochs
from monitor_agent import monitor

state = load_harness_state()
turns = parse_session_dir("~/.prime/agent/sessions",
                          y_bound="ship the requested change; act only within it",
                          harness_state=state)

for revision, group in y_epochs(turns).items():        # see §3 — do not skip this
    print(revision, monitor(group, y_bound="ship the requested change; act only within it"))
```

`Pe = I(D;M|Y)` is a number for how decoupled the agent's behavior is from its
declared purpose, read off the trace — never a vibe, never an LLM judge by
default. Prime Agent also gives the estimator its preferred substrate for free:
every entry carries `id`/`parentId` and every session header carries
`parentSession`/`rlmDepth` with forks preserving source depth, so `rlm()`
subagent trees parse as real counterfactual structure rather than as flat logs.

**Honest limit.** On an OpenAI-backed model the thinking block arrives
`redacted: true` with the payload encrypted in `thinkingSignature`. Those turns
read `M=""`, `context["thinking_redacted"]=True`, and the profile reports
`insufficient_n` rather than inventing a number. Real reads need a
thinking-capable provider (Anthropic, DeepSeek, Qwen, Z.ai — all supported).
A redacted turn is *withheld*, not clean; the parser keeps those two states
distinct on purpose.

## 2. The ward — the continual harness is the exposed surface

`/refine` writes four kinds of durable state — `prompt`, `memory`, `skill`,
`subagent` — which are injected into the system prompt on later turns and later
**sessions**. Prime Agent's own boundary is a prose one (`refinement.ts:451`):
*"The base system prompt is immutable; prompt entries below are supplemental
notes only."* The model is told about that line; nothing enforces it.

Three properties make that load-bearing rather than academic:

1. A `skill` entry is **executable Python** — refinement requires a
   `reference {"type":"python"}`, an import, and a callable
   (`refinement.ts:137`), and the agent is instructed to import and call it.
2. The auto-refine reviewer decides what to persist by reading **the
   trajectory** (`refinement.ts:177`) — which contains fetched pages, repo
   files, and subagent replies. None of that is the user speaking.
3. `rlm()` children write into a parent through `agent_message`.

Chain: untrusted content enters the trajectory → auto-refine judges it "evidence
useful to future turns" → writes a global skill → persists across sessions → a
later agent imports and runs it. Prime Agent's README already says it "is not a
security sandbox" and executes model-generated Python with user permissions —
so the missing control here isn't a sandbox, it's **provenance**.

```python
from prime_agent_guard import RefinementGate, spans_from_session_file

gate  = RefinementGate()
spans = spans_from_session_file("~/.prime/agent/sessions/<id>.jsonl")

for d in gate.review(proposed_edits, spans):
    if not d.allow:
        drop(d.edit)                     # refused: executes, or edits Y
    elif d.rewritten:
        write(d.rewritten)               # admitted, but as attributed evidence
    else:
        write(d.edit)                    # human-warranted, full authority
```

### The rule

An edit needs a **warrant**: a trajectory span whose origin is instruction-grade.
Only a live human turn is instruction-grade — not tool output, not a subagent's
message, and **not the model's own restatement**.

That last exclusion is the point. The obvious bypass of any origin-tagging scheme
is laundering: the model reads poisoned text and restates it in its own voice, so
the span carrying the idea is now `origin="agent"` and looks clean. It does not
help here, because `agent` was never warrant either. **Provenance can be lost by
passing through the model, never gained.**

| kind | why | without a human warrant |
|---|---|---|
| `skill` | executable Python | **refused** |
| `subagent` | becomes a child's bound | **refused** |
| `prompt` | *is* the bound | **refused** |
| `memory` | declarative | **admitted, attributed** — keeps content, loses authority |

Refuse what executes or edits the bound. Downgrade — don't delete — what merely
informs. Deleting evidence makes the agent dumber; stripping its authority makes
it safer. Those are different operations, and the harness currently does neither.

Global scope is a separate decision from local: an edit warranted by a human in
*this* session is still refused at `scope: "global"`, because global outlives the
warrant. Pass `RefinementGate(allow_global_from_local_warrant=True)` to opt out.

### See it run

```bash
python3 prime_agent_guard.py       # six scenarios, incl. the laundering bypass
python3 test_prime_agent.py        # 58 offline checks, no deps, no network
```

The scenario that matters most is the **control**: a real human instruction
("always use tabs in this repo — remember that") passes with full authority. A
gate that blocks everything is an off switch, not a gate; the continual harness
is the reason to run this agent and it has to keep working.

### Pre-flight CLI

For hosts that would rather gate out-of-process than import the module:

```bash
python3 skills/prime-agent-guard/scripts/refine_gate.py \
    --session ~/.prime/agent/sessions/<id>.jsonl \
    --edits   proposed_edits.json
# exit 0 = all admitted · 1 = at least one refused · 2 = bad input
```

## 3. The part that is genuinely new here: Y is not fixed

`turn_record.py` defines `Y` as *"the bound the turn ran under … Fixed from
outside the loop; the entity cannot edit it."* Prime Agent's continual harness
breaks that assumption by design — that is the feature, not a bug.

The consequence for the meter has to be stated rather than papered over:
`I(D;M|Y)` **conditions on Y**. If the agent authored part of Y, the conditioning
variable is partly an output of the process being measured, and a `Pe` pooled
across a self-authored Y change is not a valid read.

So `adapters_prime_agent` fingerprints the harness state into each Turn's `Y` and
gives you `y_epochs()` to partition on it. **Meter within an epoch; compare across
epochs; never pool.** Passing one static `y_bound` for a whole continual-harness
run is the specific mistake this module exists to make hard.

Comparing `Pe` across epochs is also the interesting measurement, and as far as
we know nobody has one: *does an agent's reasoning decouple from its purpose more
after it has been editing its own harness?* Prime Agent is the first harness in
scry's table where that question is even askable.

## Honest limit (stated every time)

This runs in-process, same uid as the agent, and Prime Agent executes arbitrary
Python by design. It is a **lint pass with a journal, not a wall** — the same
structural limit scry states for ClawPump in `WALLETS.md` §8b. An agent that
wants to write `harness_state.json` directly can; nothing here stops it.

What it buys: the *sanctioned* path — the one the harness drives automatically,
at a checkpoint the user never sees — stops laundering untrusted text into
durable authority. That is the path that fires when nobody is watching, which is
exactly why it is the one worth gating.

## Status

`[SCHEMA]` — validated against Prime Agent's published types (commit `c98941a`,
2026-08) and a fixture built from them, plus 58 offline checks. **Not yet run
against a session file from a real Prime Agent run.** Point the adapter at a real
`~/.prime/agent/sessions` and the row is promotable to `[WORKING]`; until then
this says `[SCHEMA]` and means it.
