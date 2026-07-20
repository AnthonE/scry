"""
harnesses.py — map any agent harness's trace into the Turn contract (turn_record.py).

The deal, for anyone with an agent: fill the Turn contract and you get, today,
  - the BOUND   (memory_shield.Shield + the authorization contract) — no model access needed
  - the METER   shape (channel_profile + the Box 2 Pe plug point in hermes_retrofit.DriftMeter)
  - the PROFILE (the Paper 207 coupling read: I(C;D), I(C;M), the switch signature)

Three integration grades, marked honestly on every adapter below:
  [WORKING]  runs now against a real format we have in hand
  [SCHEMA]   written against the harness's published/read schema; awaiting a real dump
  [STUB]     the shape is reserved and the open questions are named; code raises with a
             precise note instead of guessing

Unknown harness? You need ~10 lines: see `loop_tap` (hand-rolled loops) or
`register(name, to_turns)` (anything that can dump its log).
"""
from turn_record import Turn

REGISTRY = {}


def register(name, to_turns=None):
    """to_turns(raw) -> [Turn]. Register your harness; everything downstream
    (bound, meter, profile) is format-blind from here. Works as a plain call
    `register("mybot", fn)` or a decorator `@register("mybot")`."""
    if to_turns is None:
        return lambda fn: register(name, fn)
    REGISTRY[name] = to_turns
    return to_turns


def convert(name, raw, **kwargs):
    """kwargs flow through to the adapter (e.g. openai_messages takes Y=…,
    context=…) so callers never need to import adapters directly."""
    if name not in REGISTRY:
        raise KeyError(f"no adapter '{name}'; have {sorted(REGISTRY)} — or register() your own")
    return REGISTRY[name](raw, **kwargs)


# ── cantrip / Loom (deepfates) — [SCHEMA] ─────────────────────────────────────
# Written against lib/cantrip/loom.ex as read 2026-06-09 (see
# ops/lab/cantrip-loom-idmy-probe.md). The loom is the best-known substrate:
# append-only tree, reasoning (utterance.content) and action (gate_calls/
# observation) in DIFFERENT fields, fixed circle as Y, optional reward, and
# Loom.fork/4 for true counterfactual siblings. Code-medium only — in
# conversation medium M and D collapse and the meter goes behavior-blind
# (state this every time). Awaiting: a real loom dump to confirm whether a
# pre-code thinking block is stored separately from utterance.content.

@register("cantrip")
def cantrip_to_turns(loom_export):
    """loom_export: the loom→(D,M,Y) JSON rows specced in the probe note —
    {id, parent_id, sequence, Y:{circle…}, M:str, D:{gate_calls,observation},
     reward, siblings}. One small Elixir Mix task (or a reader of the stored
    loom JSON) emits this; no Elixir port of the estimator needed."""
    turns = []
    for r in loom_export:
        turns.append(Turn(
            id=r["id"], parent_id=r.get("parent_id"), sequence=r.get("sequence", 0),
            Y=r["Y"], M=r.get("M", ""), D=r.get("D", ""),
            reward=r.get("reward"), siblings=r.get("siblings", []),
            context={"harness": "cantrip", "medium": r.get("medium", "code")},
        ))
    return turns


# ── verifiers / vf-eval results.jsonl — [WORKING] ─────────────────────────────
# The channel-switching-eval's own saved format (and any verifiers env that
# keeps reasoning split from reply). This is the bridge between the published
# eval and the agent layer: the same rollout rows become meter-ready Turns.

@register("verifiers")
def verifiers_to_turns(rows, y_from=lambda info: info.get("scenario", "")):
    """rows: RolloutOutput dicts from `vf-eval … -s` (results.jsonl). Reasoning
    is recovered from completions the same way the eval scores them: inline
    <think> or the reasoning_content field."""
    import re
    turns = []
    for i, r in enumerate(rows):
        info = r.get("info") or {}
        reasoning, reply = "", ""
        for m in (r.get("completion") or []):
            if not (isinstance(m, dict) and m.get("role") == "assistant"):
                continue
            rc = m.get("reasoning_content")
            if isinstance(rc, str) and rc.strip():
                reasoning += rc
            content = m.get("content") or ""
            t = re.search(r"<think>(.*?)</think>", content, re.S | re.I)
            if t:
                reasoning += t.group(1)
                reply += content[t.end():]
            else:
                reply += content
        turns.append(Turn(
            id=str(r.get("example_id", i)), Y=y_from(info), M=reasoning, D=reply,
            reward=r.get("reward"),
            context={"harness": "verifiers", **info, "metrics": r.get("metrics") or {}},
        ))
    return turns


# ── hand-rolled loops / anything alive — [WORKING] ────────────────────────────

class loop_tap:
    """The 'we haven't thought of your harness' path: instrument any agent loop
    in three lines, no framework required.

        tap = loop_tap(Y={"oath": "never disclose the code"})
        ... inside your loop ...
        tap.turn(M=scratchpad_text, D=action_taken, context={"monitored": True})
        ... afterwards ...
        turns = tap.turns          # -> bound/meter/profile, or to_jsonl() to keep
    """
    def __init__(self, Y):
        self.Y, self.turns, self._n = Y, [], 0

    def turn(self, M="", D="", reward=None, context=None):
        self._n += 1
        t = Turn(id=f"t{self._n}", parent_id=f"t{self._n-1}" if self._n > 1 else None,
                 sequence=self._n, Y=self.Y, M=M, D=D, reward=reward,
                 context=context or {})
        self.turns.append(t)
        return t


# ── Excalibur (Vie McCoy, camelot.wiki) — [STUB] ──────────────────────────────
# What's known from public material only: an agent harness with a Warden spirit
# (protection rituals / security audits) and a charge system. The Warden IS the
# bound as a concept — the missing half is the measured meter, which is exactly
# what the Turn contract carries in. Open questions that decide the adapter
# (each one is a field mapping, nothing more):
#   1. Does Excalibur log the agent's reasoning separately from its act?
#      (If yes -> full meter. If no -> bound-only, like conversation-medium.)
#   2. Is the charge system per-action? (charge events look like a native D
#      channel with builtin salience — potentially better than tool logs.)
#   3. Is the Warden's protection spec fixed from outside the loop? (Then it
#      is Y verbatim, same as cantrip's circle.)

@register("excalibur")
def excalibur_to_turns(raw):
    raise NotImplementedError(
        "Excalibur adapter is a reserved shape, not a guess. Needed: one sample "
        "of its session log to answer (1) is reasoning logged separately from "
        "action, (2) are charge events per-action, (3) is the Warden spec "
        "loop-external. Map those to Turn(M=…, D=…, Y=…) and delete this raise. "
        "The Warden already plays the bound's role conceptually; this contract "
        "adds the measured meter half.")


# ── OpenClaw / moltbot — [WORKING, provider-gated] ─────────────────────────────
# The bound is live today via adapters.chromadb_to_items + wrap_retriever (and
# the fixed GROUNDING.md is the canonical-ground layer).
#
# The meter used to be marked a stub here — that was stale. OpenClaw's own
# transport layer (src/agents/anthropic-transport-stream.ts, verified against a
# real install 2026-07) already separates thinking/reasoning_content blocks
# from the final reply for providers that expose them natively (Anthropic,
# DeepSeek, MiniMax, Kimi) — it lands as its own block type in the persisted
# session trajectory JSONL. The gap was "no parser existed to read it," not
# missing capability; adapters_openclaw.py closes that gap.
#
# Honest limit, stated every time: an OpenClaw agent on an OpenAI-backed model
# (gpt-5.x, o-series) will read M="" for effectively every turn — OpenAI's
# reasoning is provider-encrypted, never plaintext in these transcripts. That
# is a provider limitation the meter reports as insufficient_n, not a bug. It
# starts producing real numbers the moment the agent runs on a
# thinking-capable provider.

@register("openclaw")
def openclaw_to_turns(sessions_dir, y_bound=None):
    """sessions_dir: path to an OpenClaw agent's session directory, e.g.
    ~/.openclaw/agents/<agent>/sessions (contains *.trajectory.jsonl files).
    y_bound: the declared bound/purpose string; defaults to a generic one if
    omitted — pass your agent's actual SOUL.md summary for a real Y."""
    from adapters_openclaw import parse_session_dir
    return parse_session_dir(
        sessions_dir,
        y_bound or "act only on live, trusted instructions; treat memory as evidence, never command",
    )


# ── OpenAI-format chat logs — [WORKING] (the universality workhorse) ──────────
# Most of the scene — whatever the harness — ends up with message lists in
# OpenAI chat format on disk. If that's all you have, this is your adapter:
#   Y = the system prompt (the bound, as actually deployed)
#   M = reasoning_content / <think> blocks on assistant messages
#   D = visible content + tool_calls (what crossed the boundary)
# Tool results (role=tool) ride into the NEXT turn's context as observations.

@register("openai_messages")
def openai_messages_to_turns(messages, Y=None, context=None):
    """messages: one session's list of OpenAI-format dicts. Y: override the
    bound; default = first system message verbatim (the honest choice — the
    bound is what the agent actually ran under, not what we wish it was)."""
    import re
    if Y is None:
        Y = next((m.get("content", "") for m in messages
                  if m.get("role") == "system"), "")
    turns, n, pending_obs = [], 0, []
    for m in messages:
        role = m.get("role")
        if role == "tool":
            pending_obs.append(m.get("content", ""))
            continue
        if role != "assistant":
            continue
        n += 1
        reasoning, reply = "", m.get("content") or ""
        rc = m.get("reasoning_content")
        if isinstance(rc, str) and rc.strip():
            reasoning += rc
        t = re.search(r"<think>(.*?)</think>", reply, re.S | re.I)
        if t:
            reasoning += t.group(1)
            reply = reply[t.end():]
        D = {"reply": reply.strip(),
             "tool_calls": [{"name": (tc.get("function") or {}).get("name"),
                             "arguments": (tc.get("function") or {}).get("arguments")}
                            for tc in (m.get("tool_calls") or [])]}
        ctx = dict(context or {}, harness="openai_messages")
        if pending_obs:
            ctx["observations"] = pending_obs
            pending_obs = []
        turns.append(Turn(id=f"m{n}", parent_id=f"m{n-1}" if n > 1 else None,
                          sequence=n, Y=Y, M=reasoning, D=D, context=ctx))
    return turns


# ── pointers, not adapters ────────────────────────────────────────────────────
# ElizaOS: the bound is native TypeScript (packages/eliza-destiny — contract +
#   shield); message memory is partial-M. A TS Turn emitter belongs there, not here.
# Hermes:  hermes_retrofit.py already carries bound + two-tier meter; its recall
#   wrapper feeds the same Shield. Emit Turns from the agent loop via loop_tap
#   until Hermes exposes a structured trace.
# MCP (generic): any MCP-served agent can expose `emit_turn` as a tool and
#   stream Turns to a sidecar — same shape the Destiny VM wiring uses for the
#   game (handoff-destiny-vm-wiring-2026-06.md). Reserved, unbuilt.
