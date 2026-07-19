#!/usr/bin/env python3
"""
mcp_sidecar.py — the Destiny layer as an MCP server. Pure stdlib, no SDK.

Any MCP-capable agent (Claude Code, OpenClaw, a Hermes bridge, whatever ships
next month) mounts this as a tool server and gets the layer without touching
its own runtime — the "decentralized modding" path: the harness is theirs, the
bound and the meter are mods.

Tools exposed:
  emit_turn        stream a (Y, M, D) turn into the session trace
  get_profile      the Paper 207 coupling read over everything emitted so far
  defend_memory    memory_shield over retrieved items (the bound, on demand)
  authorize_action the authorization contract (live trusted instruction or no)

Speaks MCP's JSON-RPC 2.0 over stdio (initialize / tools/list / tools/call).
Trace persists to --trace PATH (jsonl) so the meter survives the session.

Wire-in (e.g. Claude Code .mcp.json):
  {"mcpServers": {"destiny": {"command": "python3",
      "args": ["/path/to/mcp_sidecar.py", "--trace", "/tmp/destiny-trace.jsonl"]}}}

Honest scope, embedded in every get_profile response: the meter reads only
recorded channels; an agent acting in a channel it never emits walks off-meter.
Self-emitted turns are SELF-REPORT — pair with harness-side logging when stakes
are real (the same reason self-learned memory is never trusted).
"""
import json
import sys

from memory_shield import Shield
from hermes_retrofit import authorize
from turn_record import Turn, channel_profile, to_jsonl

TOOLS = [
    {"name": "emit_turn",
     "description": "Record one agent turn split into Y (bound), M (reasoning), D (action).",
     "inputSchema": {"type": "object", "properties": {
         "Y": {"type": "string", "description": "the declared purpose this turn ran under"},
         "M": {"type": "string", "description": "reasoning/scratchpad (empty = bound-only turn)"},
         "D": {"type": "string", "description": "the action/reply that crossed the boundary"},
         "context": {"type": "object", "description": "extras, e.g. {\"monitored\": 1}"}},
      "required": ["Y", "D"]}},
    {"name": "get_profile",
     "description": "Coupling profile over emitted turns: I(C;D), I(C;M), switch signature.",
     "inputSchema": {"type": "object", "properties": {
         "context_key": {"type": "string", "description": "context field to use as C",
                         "default": "monitored"}}}},
    {"name": "defend_memory",
     "description": "Run retrieved memory items through the shield (evidence, never command).",
     "inputSchema": {"type": "object", "properties": {
         "items": {"type": "array", "items": {"type": "object"}},
         "trusted_sources": {"type": "array", "items": {"type": "string"}}},
      "required": ["items", "trusted_sources"]}},
    {"name": "authorize_action",
     "description": "The contract: authorized iff a live instruction from a trusted principal.",
     "inputSchema": {"type": "object", "properties": {
         "live": {"type": "object", "description": "{text, source, role}"},
         "trusted": {"type": "array", "items": {"type": "string"}}},
      "required": ["live", "trusted"]}},
]


class Sidecar:
    def __init__(self, trace_path=None):
        self.turns, self.n, self.trace_path = [], 0, trace_path

    def emit_turn(self, Y, D, M="", context=None):
        self.n += 1
        t = Turn(id=f"t{self.n}", parent_id=f"t{self.n-1}" if self.n > 1 else None,
                 sequence=self.n, Y=Y, M=M, D=D, context=context or {})
        self.turns.append(t)
        if self.trace_path:
            to_jsonl(self.turns, self.trace_path)
        return {"recorded": t.id, "meterable": t.meterable(),
                "note": None if t.meterable() else
                "no reasoning channel on this turn — bound-only, meter blind here"}

    def get_profile(self, context_key="monitored"):
        prof = channel_profile(
            self.turns,
            c_of=lambda t: t.context.get(context_key, 0),
            d_detect=lambda t: int(bool(t.context.get("violated", 0))),
            m_detect=lambda t: int(bool(t.context.get("flagged_reasoning", 0))))
        prof["scope"] = ("meter reads only recorded channels; self-emitted turns are "
                        "self-report — pair with harness-side logging when stakes are real")
        return prof

    def defend_memory(self, items, trusted_sources):
        r = Shield(trusted_sources=set(trusted_sources)).defend(items)
        return {"answer": r.answer, "confident": r.confident, "flags": r.flags}

    def authorize_action(self, live, trusted):
        ok, why = authorize(live, trusted)
        return {"authorized": ok, "reason": why}


def handle(req, sc):
    m, p = req.get("method"), req.get("params") or {}
    if m == "initialize":
        return {"protocolVersion": p.get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "destiny-sidecar", "version": "0.1.0"}}
    if m == "tools/list":
        return {"tools": TOOLS}
    if m == "tools/call":
        fn = getattr(sc, p["name"], None)
        if fn is None or p["name"] not in {t["name"] for t in TOOLS}:
            raise ValueError(f"unknown tool {p['name']!r}")
        out = fn(**(p.get("arguments") or {}))
        return {"content": [{"type": "text", "text": json.dumps(out)}]}
    if m in ("notifications/initialized", "ping"):
        return {}
    raise ValueError(f"unsupported method {m!r}")


def main():
    trace = None
    if "--trace" in sys.argv:
        trace = sys.argv[sys.argv.index("--trace") + 1]
    sc = Sidecar(trace_path=trace)
    for line in sys.stdin:
        if not line.strip():
            continue
        req = json.loads(line)
        rid = req.get("id")
        try:
            result = handle(req, sc)
            if rid is None:           # notification — no response
                continue
            resp = {"jsonrpc": "2.0", "id": rid, "result": result}
        except Exception as e:
            resp = {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32000, "message": str(e)}}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
