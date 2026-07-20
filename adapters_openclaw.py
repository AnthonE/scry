"""adapters_openclaw.py — parse OpenClaw session trajectories into scry Turns.

Standalone, offline parser (not a live hook): OpenClaw's transcripts already
persist to JSONL (~/.openclaw/agents/<agent>/sessions/*.trajectory.jsonl), and
the meter needs a batch of turns anyway (see monitor_agent.monitor's
MIN_METERABLE), so parsing after the fact is simpler than wiring a live
capture hook.

Y (bound)      — a fixed declared-purpose string, passed in by the caller
                 (e.g. a one-line summary of the agent's SOUL.md).
M (reasoning)  — concatenated "thinking"/"reasoning_content"-typed blocks
                 from the assistant message's content array. Empty for
                 providers whose reasoning isn't exposed as plaintext (see
                 the honest scope note below).
D (action)     — concatenated "text" block text plus a short summary of any
                 "tool_use" blocks.
context        — {"monitored": <best-effort DM/guild proxy, None if
                 undeterminable>}. OpenClaw's persisted trajectory doesn't
                 reliably carry a guildId/channelType field on the message
                 object today; this is a rough placeholder, not a load-
                 bearing signal yet — refine once there's real M data to
                 correlate a context split against.

Honest scope: OpenClaw's transport layer (src/agents/anthropic-transport-
stream.ts) DOES separate thinking/reasoning_content from the final reply for
providers that expose it natively (Anthropic, DeepSeek, MiniMax, Kimi).
OpenAI's reasoning is provider-encrypted and never appears as plaintext in
these transcripts, so an OpenClaw agent running gpt-5.6 will show M="" for
effectively every turn here — monitor() will honestly report
insufficient_n / no drift read rather than fabricate one. This parser starts
producing real numbers the moment an OpenClaw agent runs on a thinking-
capable provider. See HARNESSES.md for the harness-status table this
corrects (OpenClaw's meter was marked an unbuilt stub there; the raw
material has existed since OpenClaw started separating thinking blocks in
its transport layer — this file is the missing parser, not new capability).
"""
from __future__ import annotations

import glob
import json
import os
from typing import List, Optional, Tuple

from turn_record import Turn

_REASONING_BLOCK_TYPES = {"thinking", "redacted_thinking", "reasoning_content", "reasoning"}


def _extract_m_and_d(content_blocks: list) -> Tuple[str, str]:
    m_parts: List[str] = []
    d_parts: List[str] = []
    for block in content_blocks or []:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype in _REASONING_BLOCK_TYPES:
            text = block.get("text") or block.get("thinking") or block.get("reasoning_content") or ""
            if text:
                m_parts.append(str(text))
        elif btype == "text":
            if block.get("text"):
                d_parts.append(str(block["text"]))
        elif btype == "tool_use":
            d_parts.append(f"[tool_use:{block.get('name', '?')}]")
    return "\n".join(m_parts), "\n".join(d_parts)


def _guess_monitored(message: dict) -> Optional[bool]:
    """Best-effort DM-vs-guild proxy from a persisted user message object.

    OpenClaw's discord extension distinguishes isGuildMessage/isDirectMessage
    internally (extensions/discord/src/monitor/message-handler.preflight.ts)
    but that flag isn't reliably mirrored onto the persisted session message
    today. Treat a guild-like identifier as "monitored" (more observers);
    return None (unknown) rather than guessing when no signal is present —
    an unset context bucket is honest, a wrong guess isn't.
    """
    if not isinstance(message, dict):
        return None
    if message.get("guildId") or message.get("guild_id"):
        return True
    return None


def parse_session_dir(sessions_dir: str, y_bound: str) -> List[Turn]:
    """Parse every *.trajectory.jsonl in sessions_dir into scry Turns."""
    turns: List[Turn] = []
    for path in sorted(glob.glob(os.path.join(sessions_dir, "*.trajectory.jsonl"))):
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") != "model.completed":
                    continue
                data = event.get("data") or {}
                snapshot = data.get("messagesSnapshot") or []
                if not snapshot or snapshot[-1].get("role") != "assistant":
                    continue
                assistant_msg = snapshot[-1]
                m, d = _extract_m_and_d(assistant_msg.get("content"))
                user_msg = next(
                    (m2 for m2 in reversed(snapshot[:-1]) if m2.get("role") == "user"),
                    {},
                )
                turn_id = data.get("turnId") or f"{event.get('sessionId', '')}-{i}"
                turns.append(
                    Turn(
                        id=turn_id,
                        Y=y_bound,
                        M=m,
                        D=d,
                        context={
                            "monitored": _guess_monitored(user_msg),
                            "provider": event.get("provider"),
                            "model": event.get("modelId"),
                        },
                    )
                )
    return turns


if __name__ == "__main__":
    import sys

    from monitor_agent import monitor

    sessions_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
        "~/.openclaw/agents/main/sessions"
    )
    y_bound = (
        "guard what the blade is for; judge by use, not by name; gate, decide, "
        "and never let a dressed-up choice pass as forced truth"
    )
    turns = parse_session_dir(sessions_dir, y_bound)
    print(f"parsed {len(turns)} turn(s) from {sessions_dir}")
    if not turns:
        print("no turns found — nothing to profile")
        sys.exit(0)
    profile = monitor(turns, y_bound=y_bound)
    print(json.dumps(profile, indent=2, default=str))
