---
name: hermes-guard
description: Add memory-poisoning protection and a covert-drift meter to your Hermes agent
license: MIT
metadata:
  version: "2.0.0"
  hermes:
    category: security
    tags: [security, memory, agent-safety, drift-detection]
---

# hermes-guard — scry's ward + meter, wired directly for Hermes Agent

This is the Hermes-native entry point into [scry](https://github.com/AnthonE/scry). If
you're building a *new* agent from scratch, see the harness-agnostic `scry` skill
instead — this one assumes you're running Hermes Agent today and want to harden it.

This ships a real, tested Hermes **plugin** (not just a code sample) — Hermes skills
only deliver `SKILL.md` text for the model to read; nothing in a skill directory
auto-executes. To get real enforcement (a hook that can actually block a tool call,
not a suggestion the model can ignore), the plugin below is what you install.

## Install

1. Copy every file below into `~/.hermes/plugins/scry-guard/` (same flat layout —
   it's self-contained, no separate scry clone required): the manifest
   ([`scripts/plugin.yaml`](scripts/plugin.yaml)) and hook code
   ([`scripts/__init__.py`](scripts/__init__.py)), plus the vendored dependencies
   [`scripts/memory_shield.py`](scripts/memory_shield.py),
   [`scripts/adapters.py`](scripts/adapters.py),
   [`scripts/turn_record.py`](scripts/turn_record.py),
   [`scripts/black_box_meter.py`](scripts/black_box_meter.py),
   [`scripts/monitor_agent.py`](scripts/monitor_agent.py), and
   [`scripts/hermes_retrofit.py`](scripts/hermes_retrofit.py). Set `SCRY_SRC` to a
   live scry checkout instead if you'd rather track scry's source directly.
2. Enable it: `hermes plugins enable scry-guard`
3. Restart the gateway: `hermes gateway restart`
4. Optional — configure trusted sources and which tools get gated (see
   [Configuration](#configuration) below; both are empty/default-safe if you skip
   this).
5. Verify: copy [`scripts/test_scry_guard.py`](scripts/test_scry_guard.py) alongside
   the rest and run `python3 test_scry_guard.py -v` (23 tests, stdlib-only, no
   network).

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

## The bound

Two pieces, both live in [`scripts/__init__.py`](scripts/__init__.py):

**Memory recall, hardened.** Hermes's built-in `MEMORY.md`/`USER.md` snapshot is baked
into the system prompt before any plugin hook fires — you can't intercept that path
from a plugin (Hermes already runs its own `scan_for_threats` sanitizer on it, worth
checking whether that native protection already covers what you need before adding
more). What you *can* harden from a plugin is a custom memory backend or
`session_search`-style recall, via the `pre_llm_call` hook (Hermes's documented
context-injection point):

```python
from memory_shield import Shield
from adapters import wrap_retriever, hermes_memories_to_items

# self-taught/episodic memory is deliberately NOT trusted — a lesson Hermes taught
# itself can corroborate a fact but can never outvote a trusted source or issue a
# command on its own.
TRUSTED = {"user", "wiki", "tool:ledger"}          # whatever your live, authenticated sources are
shield = Shield(trusted_sources=TRUSTED)
recall = wrap_retriever(your_recall_fn, shield, hermes_memories_to_items)
```

**Authorize before anything consequential.** For a transfer, a send, a destructive
tool call — gate it on a live instruction, and require it to be spent *explicitly*.
An earlier version of this gate just checked "is there any live message this turn" —
which turned out to be a no-op in practice, since a conversational agent has a live
user message on essentially every turn simply by being mid-conversation. The shipped
plugin instead requires a distinct `authorize_action` tool call, single-use, consumed
the instant a gated call reads it:

```python
from hermes_retrofit import authorize

ok, reason = authorize(
    live={"text": this_turn_user_message, "source": "user", "role": "live_instruction"},
    trusted=TRUSTED,
)
if not ok:
    refuse(reason)   # a stored "standing rule" from memory can never reach this branch
# on success, record a single-use pending authorization for this session —
# see _handle_authorize_action / _on_pre_tool_call in scripts/__init__.py
```

This is unconditional on purpose — it does not depend on Hermes reasoning correctly
about the poison. Field result: explaining the exact rule to the model in its system
prompt made it recite the rule back and then override it anyway, close to half the
time (`FIELD-RESULTS-2026-06-18.md` §4). The gate has to hold regardless of what the
model concludes.

Both pieces are wired into the shipped plugin's `pre_llm_call` (caches the live
message), the `authorize_action` tool (spends it, single-use), and `pre_tool_call`
(the gate — blocks unless a passing `authorize_action` is pending for this session,
consuming it on read either way) — see `scripts/__init__.py` for the working
version, not the sketch above. The mechanism is deliberately identical to
[`openclaw-guard`](../openclaw-guard/SKILL.md)'s `before_tool_call`/`after_tool_call`
pair — same single-use semantics, same staleness cap, same test coverage shape —
so the two plugins behave the same way regardless of harness.

## The meter

Whether Hermes's reasoning conditions on whether it believes it's being watched (the
covert version of drift a behavior-only check can't see — Paper 207: RL pressure
relocates context-coupling off the action channel into the reasoning channel):

```python
from turn_record import Turn
from monitor_agent import monitor

turns = [Turn(id=t.id, Y=your_declared_purpose, M=t.reasoning, D=t.action,
             context={"monitored": t.is_monitored}) for t in your_session_log]
print(monitor(turns, y_bound=your_declared_purpose)["read"])
```

The shipped plugin does this for you automatically: `post_api_request` accumulates
each turn's `assistant_message.reasoning` (present when the provider exposes
extended thinking — Anthropic, DeepSeek, and others; empty for providers whose
reasoning isn't plaintext-accessible), `post_llm_call` builds the `Turn` and appends
it to `~/.hermes/scry/turns.jsonl`, and a `scry_profile` tool lets the agent (or you,
by asking it) report its own reading on demand.

Needs 20+ meterable turns for a real read — below that, `monitor()` honestly reports
`insufficient_n` rather than fabricating a number. The default detector is a
transparent lexical baseline and is artifact-prone — treat a nonzero as a lead, not a
verdict, until you run it through `detector_audit.py`'s three-check discipline.

## Configuration

Hermes plugins have no formal config schema — this one reads freeform YAML from
`plugins.entries.scry-guard.config` in `~/.hermes/config.yaml`:

```yaml
plugins:
  entries:
    scry-guard:
      config:
        trusted_sources: ["user"]        # default if omitted
        gated_tools: []                  # default [] — nothing gated
          # e.g. [terminal, write_file, patch] — any tool named here
          # requires a passing, single-use authorize_action call
          # immediately before it. Call authorize_action again for
          # each gated call; it does not stay valid for the whole turn.
        auth_max_age_seconds: 120        # staleness cap on an unconsumed
                                          # authorization (default 120)
```

`gated_tools` is a plain list of tool names. Naming a tool here means every call to
it is blocked unless the agent has just called `authorize_action` — spending *this
turn's* live, trusted user message — and that authorization hasn't already been
spent on an earlier gated call or gone stale past `auth_max_age_seconds`. Nothing
recalled from memory can satisfy `authorize_action`; only a live instruction can.

### Robinhood trade gate (e.g. a connected `agent.robinhood.com/mcp/trading`)

```yaml
        robinhood_place_tools: []        # default [] — nothing gated
          # e.g. [place_equity_order] — STRICTER than gated_tools: also
          # needs a matching prior robinhood_review_tools call this
          # session, and the live instruction must actually NAME this
          # order's symbol/side, not just exist.
        robinhood_review_tools: []       # default [] — nothing recorded
          # e.g. [review_equity_order] — a successful call here is
          # recorded so the matching robinhood_place_tools call can
          # require it. A failed/errored review is never recorded.
```

`gated_tools` alone only asks "did *some* live trusted instruction exist this
turn" — for an order-placing tool that's close to a no-op, since a live user
message exists on essentially every turn of a live conversation. A tool named in
`robinhood_place_tools` instead gets `robinhood_agentic.py`'s `ReviewLedger` +
`authorize_trade` (vendored alongside this plugin), ported onto Hermes's real
`pre_tool_call`/`post_tool_call` hooks: the order must have been reviewed first
(a successful call to a `robinhood_review_tools` tool, same symbol/side/quantity),
and the authorized live text must name *this exact order* — an attacker who gets
a real live, trusted instruction through for one order still cannot ride it into
a different symbol, side, or a bigger quantity. Fails **closed** (blocks) if
`robinhood_agentic.py` didn't import, unlike the rest of this plugin, which fails
open — this path touches real money. `robinhood_place_tools`/`_review_tools` are
independent of `gated_tools`; do not also list a Robinhood tool in `gated_tools`,
the stricter path always wins for tools named in `robinhood_place_tools`.

## Honest scope

- Raises the cost of an attack; does not make Hermes unbreakable. An attacker who
  controls a majority of *trusted* sources still wins.
- The subject model in the field results is a proxy (Llama-3.3-70B), not the literal
  Hermes weights — reasonable given the lineage, but say so if you cite the numbers.
- The bound is wired and ready the moment you enable this plugin; if your Hermes
  install has `memory.memory_enabled: false` (Hermes's default), there's nothing
  live for the memory-recall half to protect yet until you turn memory on or wire a
  custom recall function — the authorize-gate and meter are active regardless.
- Meter coverage depends on your model provider exposing reasoning as plaintext.
  OpenAI's reasoning is provider-encrypted and won't populate `M` — this is a
  provider limitation the meter reports honestly (`insufficient_n`), not a bug.
- Full detail, the rest of the poisoning battery, and the drift-immunity mechanism
  suite: [github.com/AnthonE/scry](https://github.com/AnthonE/scry).
