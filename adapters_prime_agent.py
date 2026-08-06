"""adapters_prime_agent.py — parse Prime Agent session trajectories into scry Turns.

Prime Agent (PrimeIntellect-ai/prime-agent) is a TypeScript harness around a
persistent-IPython execution runtime. Read against commit c98941a, 2026-08.

Why this harness rates highly on the one criterion that decides everything
(HARNESSES.md: "does it record reasoning separately from action?"): it does,
structurally, and has since the type was written. `AssistantMessage.content`
(packages/ai/src/types.ts:224) is an array of *discriminated* blocks —

    {type:"text",     text}                      -> D
    {type:"thinking", thinking, thinkingSignature?, redacted?}  -> M
    {type:"toolCall", id, name, arguments}       -> D

— and the whole message is persisted verbatim into the session JSONL as
`{type:"message", message: AgentMessage}` (session-manager.ts:103). The only
place thinking is filtered anywhere in the codebase is
modes/daemon/compact-session-stream.ts:131, which is a *display* concern for
daemon reattach, not the persist path. So M reaches disk.

It also carries the counterfactual primitive natively: every entry has
`id`/`parentId` (SessionEntryBase, session-manager.ts:96) and every session
header has `parentSession`/`rlmDepth` (session-manager.ts:75) with forks
preserving source depth. That is the same structure that makes cantrip's Loom
"the best-known substrate" — here in a production coding agent.

  Y  — NOT read off the session file. See the Y-epoch note below; this is the
       interesting part, and the one place the Turn contract's assumptions and
       this harness's design genuinely disagree.
  M  — concatenated `thinking` blocks. Redacted blocks contribute NOTHING and
       set context["thinking_redacted"], so a safety-filtered turn reads as
       unmeterable rather than as clean.
  D  — {"reply": joined text blocks, "tool_calls":[{name, arguments}]}.
  lineage — Turn.parent_id is the nearest *assistant* ancestor along the
       entry parentId chain, so the Turn tree is the session tree with the
       non-assistant entries contracted out.

── The Y problem (the finding, not a caveat) ─────────────────────────────────
turn_record.py defines Y as "the bound the turn ran under ... Fixed from
outside the loop; the entity cannot edit it." Prime Agent's continual harness
violates that by design: `/refine` writes prompt/memory/skill/subagent entries
to a durable store (refinement.ts, harness_state.json) which are then injected
into the system prompt on subsequent turns and sessions. The base system prompt
is immutable and refinement entries are labelled "supplemental notes only"
(refinement.ts:451) — but that is a prose boundary, not a structural one.

Consequence for the meter, stated rather than papered over: I(D;M|Y) conditions
on Y. If the agent authored part of Y, the conditioning variable is partly an
output of the process being measured, and a Pe pooled across a self-authored Y
change is not a valid read. `y_epochs()` below partitions turns by harness-state
revision so callers can meter WITHIN an epoch and never across one. Passing a
single static y_bound for a whole continual-harness run is the mistake this
module exists to make hard.

Honest scope, same shape as the OpenClaw row: a Prime Agent session on an
OpenAI-backed model carries provider-encrypted reasoning — `thinking` arrives
`redacted:true` with the opaque payload in `thinkingSignature`. Those turns
read M="" and the profile reports insufficient_n rather than fabricating a
number. Real numbers appear the moment the agent runs on a thinking-capable
provider (Anthropic, DeepSeek, Qwen, Z.ai — all of which prime-agent supports).
"""
from __future__ import annotations

import glob
import json
import os
from typing import Dict, List, Optional, Tuple

from turn_record import Turn

# The block type prime-agent uses for reasoning. Single value, not a set: this
# harness has one canonical name for it (packages/ai/src/types.ts:178), unlike
# the OpenClaw parser which spans four provider spellings.
_THINKING = "thinking"


def _extract_m_and_d(content) -> Tuple[str, dict, bool]:
    """Split one AssistantMessage.content array into (M, D, redacted).

    `redacted` is returned separately rather than folded into M: a redacted
    thinking block means reasoning EXISTED and was withheld, which is a
    different epistemic state from a model that did no reasoning. Both give
    M="" — but only one of them should make a reader suspicious of the read.
    """
    m_parts: List[str] = []
    reply_parts: List[str] = []
    tool_calls: List[dict] = []
    redacted = False

    # A string content is legal on UserMessage but not AssistantMessage; guard
    # anyway so a hand-edited or migrated session can't raise here.
    if isinstance(content, str):
        return "", {"reply": content, "tool_calls": []}, False

    for block in content or []:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == _THINKING:
            if block.get("redacted"):
                redacted = True
                continue          # opaque payload in thinkingSignature is not reasoning
            text = block.get("thinking") or ""
            if text:
                m_parts.append(str(text))
        elif btype == "text":
            if block.get("text"):
                reply_parts.append(str(block["text"]))
        elif btype == "toolCall":
            tool_calls.append({
                "name": block.get("name"),
                "arguments": block.get("arguments"),
            })
        # "image" blocks carry no M or D signal; skipped deliberately.

    return (
        "\n".join(m_parts),
        {"reply": "\n".join(reply_parts).strip(), "tool_calls": tool_calls},
        redacted,
    )


def _tool_result_text(message: dict) -> str:
    """Flatten a ToolResultMessage's content array to text for the observation
    trail. Tool output is the primary UNTRUSTED-origin channel in this harness
    (see prime_agent_guard) — it is recorded as an observation on the next
    turn's context, never merged into D."""
    parts = []
    for block in message.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
        elif isinstance(block, str):
            parts.append(block)
    return "\n".join(parts)


def parse_session_file(path: str, y_bound=None, harness_state=None) -> List[Turn]:
    """Parse one ~/.prime/agent/sessions/<id>.jsonl into Turns.

    y_bound: the declared purpose the agent ran under. Prime Agent does NOT
      persist its system prompt into the session file (it is composed at
      runtime from the base prompt + continual harness state), so Y cannot be
      recovered from this file alone — the caller supplies it. This is the
      honest failure mode: refusing to invent a Y beats fabricating one.
    harness_state: optional dict from `load_harness_state()`. When given, Y
      becomes {"bound":…, "harness_revision":…} so `y_epochs()` can partition
      on a self-authored Y change instead of silently pooling across it.
    """
    header: dict = {}
    entries: List[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue                       # a torn last line on a live session
            if rec.get("type") == "session":
                header = rec
            else:
                entries.append(rec)

    Y: object = y_bound if y_bound is not None else ""
    if harness_state is not None:
        Y = {"bound": y_bound or "", "harness_revision": harness_revision(harness_state)}

    by_id: Dict[str, dict] = {e["id"]: e for e in entries if isinstance(e.get("id"), str)}
    # entry id -> Turn id, for contracting non-assistant entries out of the tree
    turn_of: Dict[str, str] = {}
    turns: List[Turn] = []
    pending_obs: List[dict] = []
    seq = 0

    for entry in entries:
        if entry.get("type") != "message":
            continue
        message = entry.get("message") or {}
        role = message.get("role")

        if role == "toolResult":
            pending_obs.append({
                "tool": message.get("toolName"),
                "is_error": bool(message.get("isError")),
                "text": _tool_result_text(message),
            })
            continue
        if role != "assistant":
            continue

        m, d, redacted = _extract_m_and_d(message.get("content"))

        # Walk up the entry chain to the nearest ancestor that became a Turn.
        parent_turn = None
        cur = entry.get("parentId")
        seen = set()
        while cur is not None and cur not in seen:
            seen.add(cur)                       # a corrupt/hostile parentId cycle
            if cur in turn_of:                  # must not spin forever here
                parent_turn = turn_of[cur]
                break
            cur = (by_id.get(cur) or {}).get("parentId")

        seq += 1
        turn_id = entry["id"]
        turn_of[turn_id] = turn_id

        ctx = {
            "harness": "prime_agent",
            "session_id": header.get("id"),
            "cwd": header.get("cwd"),
            "parent_session": header.get("parentSession"),
            "rlm_depth": header.get("rlmDepth", 0),
            "provider": message.get("provider"),
            "model": message.get("model"),
            "stop_reason": message.get("stopReason"),
            "thinking_redacted": redacted,
        }
        if pending_obs:
            ctx["observations"] = pending_obs
            pending_obs = []

        turns.append(Turn(id=turn_id, parent_id=parent_turn, sequence=seq,
                          Y=Y, M=m, D=d, context=ctx))
    return turns


def parse_session_dir(sessions_dir: str, y_bound=None, harness_state=None) -> List[Turn]:
    """Parse every *.jsonl session in a Prime Agent session root.

    Sessions are flat in this directory (migrations.ts:159 moved them up out of
    the old per-cwd nesting), and `rlm()` children are separate session files
    linked by header.parentSession — so a whole subagent fleet parses here, with
    context["rlm_depth"] preserved for filtering parent vs child work.
    """
    turns: List[Turn] = []
    for path in sorted(glob.glob(os.path.join(sessions_dir, "*.jsonl"))):
        turns.extend(parse_session_file(path, y_bound=y_bound, harness_state=harness_state))
    return turns


# ── the continual harness: Y that the agent can edit ──────────────────────────

def default_harness_state_path() -> str:
    return os.path.expanduser("~/.prime/agent/harness_state.json")


def load_harness_state(path: Optional[str] = None) -> dict:
    """Read harness_state.json (refinement.ts:277). Missing file is not an
    error — a fresh install has no refinements yet, which is a real state."""
    path = path or default_harness_state_path()
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def harness_entries(state: dict) -> List[dict]:
    """Flatten the {kind: {id: entry}} store into a list, kind tagged on each."""
    out = []
    for kind in ("prompt", "memory", "skill", "subagent"):
        bucket = state.get(kind) or {}
        if isinstance(bucket, dict):
            for entry_id, entry in bucket.items():
                if isinstance(entry, dict):
                    out.append(dict(entry, kind=kind, id=entry.get("id", entry_id)))
    return out


def harness_revision(state: dict) -> str:
    """A stable fingerprint of the harness state — the Y-epoch label.

    Deliberately content-derived rather than a timestamp or counter: two
    sessions that ran under identical harness state share an epoch and may be
    pooled, even across a restart. Uses the stdlib hash of a canonical
    serialization; this is an equality key, not a security digest.
    """
    entries = harness_entries(state)
    canon = json.dumps(
        sorted((e.get("kind", ""), str(e.get("id", "")), str(e.get("content", "")))
               for e in entries),
        sort_keys=True,
    )
    import hashlib
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]


def y_epochs(turns) -> Dict[str, List[Turn]]:
    """Partition turns by Y — i.e. by continual-harness revision.

    The guard rail this module exists for. `I(D;M|Y)` conditions on Y; when the
    agent can edit Y, a Pe pooled across a revision boundary is conditioning on
    a variable the measured process authored, and the number means nothing.
    Meter within an epoch, compare across epochs, never pool.
    """
    groups: Dict[str, List[Turn]] = {}
    for t in turns:
        y = t.Y
        key = y.get("harness_revision", "static") if isinstance(y, dict) else "static"
        groups.setdefault(key, []).append(t)
    return groups


if __name__ == "__main__":
    import sys

    from monitor_agent import monitor

    sessions_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
        "~/.prime/agent/sessions"
    )
    state = load_harness_state()
    y_bound = "complete the requested engineering task; do not act outside it"
    turns = parse_session_dir(sessions_dir, y_bound=y_bound, harness_state=state)
    print(f"parsed {len(turns)} turn(s) from {sessions_dir}")
    print(f"continual-harness entries: {len(harness_entries(state))} "
          f"(revision {harness_revision(state)})")
    if not turns:
        print("no turns found — nothing to profile")
        sys.exit(0)
    epochs = y_epochs(turns)
    print(f"Y-epochs: {len(epochs)} — metering within each, never pooled")
    for rev, group in epochs.items():
        meterable = sum(1 for t in group if t.meterable())
        print(f"\n── epoch {rev}: {len(group)} turns, {meterable} meterable ──")
        print(json.dumps(monitor(group, y_bound=y_bound), indent=2, default=str))
