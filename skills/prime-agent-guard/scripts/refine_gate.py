#!/usr/bin/env python3
"""refine_gate.py — out-of-process pre-flight for Prime Agent's continual harness.

For hosts that would rather gate refinement edits from a hook or a wrapper than
import prime_agent_guard directly. Reads a session JSONL for provenance and a
JSON array of proposed edits, prints one decision per edit, and exits nonzero if
anything was refused.

    python3 refine_gate.py --session ~/.prime/agent/sessions/abc.jsonl \
                           --edits   proposed_edits.json

    exit 0  every edit admitted (some possibly rewritten as attributed evidence)
    exit 1  at least one edit refused
    exit 2  bad input

--edits accepts either a bare JSON array of edits, or the object form
{"edits":[…]}. Each edit is {kind, scope?, title?, content, reference?} — the
shape refinement.ts emits (RefinementKind = prompt|memory|skill|subagent).

Use --json to emit machine-readable decisions for a wrapper to act on; the
rewritten (attributed) form of a downgraded memory is included there, so a host
can write that instead of the original rather than dropping it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# Import scry from the repo root, two levels up from skills/<name>/scripts/.
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from prime_agent_guard import RefinementGate, spans_from_session_file  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Gate Prime Agent continual-harness edits on provenance.")
    ap.add_argument("--session", required=True,
                    help="path to a Prime Agent session JSONL (provenance source)")
    ap.add_argument("--edits", required=True,
                    help="path to proposed edits JSON (array, or {'edits':[…]})")
    ap.add_argument("--allow-global", action="store_true",
                    help="permit global-scope edits on a local human warrant")
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="emit decisions as JSON instead of a table")
    args = ap.parse_args()

    session = os.path.expanduser(args.session)
    edits_path = os.path.expanduser(args.edits)

    try:
        spans = spans_from_session_file(session)
    except OSError as e:
        print(f"cannot read session: {e}", file=sys.stderr)
        return 2

    try:
        with open(edits_path, encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"cannot read edits: {e}", file=sys.stderr)
        return 2

    edits = payload.get("edits") if isinstance(payload, dict) else payload
    if not isinstance(edits, list):
        print("edits must be a JSON array, or an object with an 'edits' array",
              file=sys.stderr)
        return 2

    gate = RefinementGate(allow_global_from_local_warrant=args.allow_global)
    decisions = gate.review(edits, spans)

    if args.as_json:
        print(json.dumps([{
            "kind": d.edit.get("kind"),
            "scope": d.edit.get("scope", "local"),
            "title": d.edit.get("title"),
            "allow": d.allow,
            "action": d.action,
            "reasons": d.reasons,
            "warrant": d.warrant,
            "write": d.rewritten if d.rewritten else (d.edit if d.allow else None),
        } for d in decisions], indent=2))
    else:
        trusted = sum(1 for s in spans if s.trusted)
        print(f"{len(spans)} span(s) from {os.path.basename(session)} "
              f"— {trusted} instruction-grade\n")
        for d in decisions:
            print(f"  {d}")
            if d.rewritten:
                print(f"  {'':>13}write instead: {d.rewritten['content'][:88]}…")

    refused = [d for d in decisions if not d.allow]
    if refused and not args.as_json:
        print(f"\n{len(refused)} of {len(decisions)} edit(s) refused — "
              "executes, or edits the bound, without a live human warrant.")
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
