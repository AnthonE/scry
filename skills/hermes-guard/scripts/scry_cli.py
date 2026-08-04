"""scry_cli — the commands behind both ``hermes scry <sub>`` and ``/scry <sub>``.

One implementation, two doors. ``hermes scry read`` in a terminal and
``/scry read`` typed into a Discord channel run the exact same function, so
the two surfaces can never drift apart.

Every function here is pure-ish and takes its dependencies as keyword
arguments (``monitor_fn``, ``turn_cls``, ``api_base``, ``turns_path``…)
rather than importing the plugin module. That keeps the cycle out
(``__init__`` imports this, not the reverse) and makes each command testable
offline with fakes.

Everything returns a **string** — printed by the CLI, returned verbatim to
the chat by the slash command.

One deliberate asymmetry: the slash command will fetch the message a vow
needs but will never POST one. A vow is public forever and the Registry does
not forget; swearing one is a decision to make at a terminal, on purpose,
not something to fire off from a group chat where the agent is mid-turn.
"""
from __future__ import annotations

import json
import os
import shlex
from typing import Any, Callable, Dict, List, Optional, Tuple

import scry_api

# The honest-scope card rides every scry response and this surface inherits
# it (CLAUDE.md: dropping it is a bug, not a style choice).
SCOPE_FOOTER = (
    "scope: off-meter turns are a blind spot · no meter is immune · trace "
    "provenance is yours · not trade advice · a reading is never a verdict."
)

USAGE = """scry — your agent's door into scry (github.com/AnthonE/scry)

  doctor              check the ward + meter wiring, and the issuer pin
  read [--hosted]     this agent's own drift reading, from captured turns
  town                the whole town in one read (today's crier)
  vow                 swear this agent in — a public, permanent conduct record

Free, keyless, no account. `read --hosted` sends your captured trace to the
meter for the free unsigned read; everything else but `doctor` is local."""


def _fmt(lines: List[str]) -> str:
    return "\n".join(line for line in lines if line is not None)


def _err(payload: Dict[str, Any]) -> Optional[str]:
    """Return a printable error line if *payload* carries one, else None."""
    if not isinstance(payload, dict):
        return None
    if payload.get("error"):
        detail = payload.get("detail")
        return f"  ✗ {payload['error']}" + (f"\n    {detail}" if detail else "")
    return None


# --- turn loading ---------------------------------------------------------

def load_turns(turns_path: str, turn_cls: Any, limit: Optional[int] = None) -> Tuple[List[Any], List[dict], int]:
    """Read turns.jsonl → (Turn objects, raw dicts, corrupt-line count).

    Corrupt lines are counted and skipped rather than fatal: a half-written
    final line (the agent was killed mid-append) must not cost you the whole
    window.
    """
    turns: List[Any] = []
    raws: List[dict] = []
    corrupt = 0
    if not os.path.exists(turns_path):
        return turns, raws, corrupt
    with open(turns_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                turns.append(turn_cls(**obj))
                raws.append(obj)
            except Exception:  # noqa: BLE001 - a bad line is data loss, not a crash
                corrupt += 1
    if limit is not None and len(turns) > limit:
        turns, raws = turns[-limit:], raws[-limit:]
    return turns, raws, corrupt


def _meterable(raws: List[dict]) -> int:
    return sum(1 for r in raws if (r.get("M") or "").strip())


def _apply_detectors(turns: List[Any], raws: List[dict]) -> Tuple[Optional[List[dict]], str]:
    """Stamp each turn with ``violated`` / ``flagged_reasoning`` before sending.

    This is not decoration — it is the hosted contract. ``POST /profile`` and
    ``/demo/profile`` read the disposition flags out of each turn's *context*
    (``server.py:_run_profile``); they do **not** run a detector over your M
    and D text, and they must not: the server cannot see your judge, and a
    meter that graded your reasoning by its own private rule would be
    measuring itself.

    So an unflagged trace comes back all-zeros — indistinguishable, on the
    wire, from a clean agent. That is the single most dangerous number this
    project could hand anyone, so the flags get applied here, locally, with
    the same detectors ``monitor()`` uses, and the read says which detector
    produced them.

    Returns ``(payload, detector_name)``, or ``(None, reason)`` if the
    detectors could not be imported — the caller must then refuse.
    """
    try:
        from black_box_meter import default_detectors
    except Exception:  # noqa: BLE001 - caller refuses rather than sending blanks
        return None, "detectors unavailable"

    _, d_detect, m_detect = default_detectors()
    out: List[dict] = []
    for turn, raw in zip(turns, raws):
        context = dict(raw.get("context") or {})
        try:
            context["violated"] = int(bool(d_detect(turn)))
            context["flagged_reasoning"] = int(bool(m_detect(turn)))
        except Exception:  # noqa: BLE001 - a turn the detector chokes on stays unflagged
            context.setdefault("violated", 0)
            context.setdefault("flagged_reasoning", 0)
        out.append({**raw, "context": context})
    return out, "lexical baseline (artifact-prone — an unaudited nonzero is a lead, not a verdict)"


# --- doctor ---------------------------------------------------------------

def doctor(
    *,
    api_base: Optional[str],
    turns_path: str,
    turn_cls: Any,
    config: Dict[str, Any],
    imports: Dict[str, bool],
    offline: bool = False,
) -> str:
    """Verify the wiring end to end, then the issuer pin. Read-only."""
    base = scry_api.normalize_base(api_base)
    out: List[str] = ["scry doctor", ""]

    out.append("the ward (local, copied — never hosted):")
    core_ok = imports.get("core", False)
    out.append(f"  {'✓' if core_ok else '✗'} scry core importable (Turn / authorize / monitor)")
    if not core_ok:
        out.append("    the plugin is inert — check SCRY_SRC and the Hermes plugin log")

    gated = sorted(config.get("gated_tools") or [])
    trusted = sorted(config.get("trusted_sources") or [])
    memory_tools = sorted(config.get("memory_tools") or [])
    rh_place = sorted(config.get("robinhood_place_tools") or [])
    out.append(f"  · trusted sources: {', '.join(trusted) or '(none)'}")
    out.append(
        f"  {'✓' if gated else '·'} gated tools: {', '.join(gated) or '(none — nothing requires authorize_action)'}"
    )
    out.append(
        f"  {'✓' if memory_tools else '·'} memory tools framed as evidence: {', '.join(memory_tools) or '(none)'}"
    )
    if rh_place:
        rh_ok = imports.get("robinhood", False)
        out.append(f"  {'✓' if rh_ok else '✗'} robinhood trade gate on: {', '.join(rh_place)}")
        if not rh_ok:
            out.append("    robinhood_agentic did not import — this path FAILS CLOSED (orders blocked)")

    out.append("")
    out.append("the meter (a loop-external observer — it reads the trace, never the weights):")
    _, raws, corrupt = load_turns(turns_path, turn_cls)
    n, m_ok = len(raws), _meterable(raws)
    out.append(f"  {'✓' if n else '·'} {n} turn(s) captured at {turns_path}")
    if corrupt:
        out.append(f"  ⚠ {corrupt} unreadable line(s) skipped")
    if n:
        out.append(f"  {'✓' if m_ok >= 20 else '·'} {m_ok} carry reasoning (M) — a real read wants ≥20")
        if m_ok == 0:
            out.append(
                "    your provider's reasoning is not plaintext (OpenAI encrypts it). "
                "The meter reports insufficient_n rather than inventing a number."
            )

    out.append("")
    if offline:
        out.append(f"the meter endpoint: {base} (skipped — --offline)")
    else:
        out.append(f"the meter endpoint: {base}")
        health = scry_api.health(base=base)
        err = _err(health)
        if err:
            out.append(err)
        else:
            out.append(f"  ✓ reachable (status {health.get('status', health.get('_status'))})")
            key = scry_api.pubkey(base=base)
            kerr = _err(key)
            if kerr:
                out.append(kerr)
            else:
                served = scry_api.served_pubkey(key)
                if not served:
                    # Not a mismatch — we simply could not read the key. Saying
                    # "MISMATCH" here would cry wolf on a healthy deployment,
                    # and an alarm that fires wrongly is an alarm nobody reads.
                    out.append("  ⚠ could not read an issuer pubkey from this response — check by hand")
                elif not scry_api.is_reference(base):
                    out.append(f"  · self-hosted issuer: {served} — pin this out-of-band yourself")
                elif served == scry_api.REFERENCE_PUBKEY:
                    out.append("  ✓ issuer pubkey matches the pinned reference key")
                else:
                    out.append("  ✗ ISSUER PUBKEY MISMATCH — do not trust reads from this endpoint")
                    out.append(f"    served: {served}")
                    out.append(f"    pinned: {scry_api.REFERENCE_PUBKEY}")

    out.append("")
    out.append(SCOPE_FOOTER)
    return _fmt(out)


# --- read -----------------------------------------------------------------

def read(
    *,
    turns_path: str,
    bound: str,
    monitor_fn: Optional[Callable],
    turn_cls: Any,
    hosted: bool = False,
    api_base: Optional[str] = None,
    limit: int = 2000,
) -> str:
    """This agent's own drift reading, off its captured turns."""
    if turn_cls is None:
        return "scry is not importable — check SCRY_SRC and the Hermes plugin log."

    turns, raws, corrupt = load_turns(turns_path, turn_cls, limit=limit)
    if not turns:
        return _fmt([
            "no turns captured yet.",
            f"  the plugin appends one per completed turn to {turns_path}",
            "  talk to your agent for a while, then ask again.",
            "",
            SCOPE_FOOTER,
        ])

    header = [f"{len(turns)} turn(s) read, {_meterable(raws)} carrying reasoning (M)"]
    if corrupt:
        header.append(f"  ⚠ {corrupt} unreadable line(s) skipped")

    if hosted:
        base = scry_api.normalize_base(api_base)
        flagged, detector = _apply_detectors(turns, raws)
        if flagged is None:
            return _fmt(header + [
                "",
                "  refusing the hosted read: the detectors did not import, so every",
                "  turn would arrive unflagged and the meter would return all-zeros —",
                "  which reads as 'no drift' but means 'nothing was measured'.",
                "  Use `hermes scry read` (local) instead.",
                "", SCOPE_FOOTER,
            ])
        resp = scry_api.demo_profile(flagged, base=base)
        err = _err(resp)
        if err:
            return _fmt(header + ["", "hosted read failed:", err, "", SCOPE_FOOTER])
        prof = resp.get("profile") or {}
        coverage = resp.get("detector_coverage") or {}
        return _fmt(header + [
            f"  endpoint: {base}  (free demo read)",
            f"  detector: {detector}",
            *([
                "  coverage: {}/{} turns scored on both channels{}".format(
                    min(coverage.get("violated", 0), coverage.get("flagged_reasoning", 0)),
                    coverage.get("turns", 0),
                    "" if coverage.get("complete") else "  ⚠ INCOMPLETE",
                )
            ] if coverage else []),
            "",
            *(f"  {k}: {v}" for k, v in prof.items() if not isinstance(v, (dict, list))),
            "",
            "  the switch signature is I(C;M | D-clean) — reasoning coupling to",
            "  context with behaviour held clean. The hosted read returns the",
            "  channel numbers; it does NOT run the permutation test, so nothing",
            "  here establishes significance. `hermes scry read` (local) adds that.",
            "",
            "  ATTESTED: false — the free, UNSIGNED demo read. What you did not buy",
            "  is the third-party signature, which is the only part a stranger can",
            "  verify cold. POST /profile ($0.10 flat, score-blind) is the attested",
            "  read, and the price never moves the number.",
            "",
            SCOPE_FOOTER,
        ])

    if monitor_fn is None:
        return "monitor is not importable — check SCRY_SRC and the Hermes plugin log."
    profile = monitor_fn(turns, y_bound=bound)
    return _fmt(header + [
        f"  bound (Y): {bound}",
        "",
        profile.get("read", "(no read)"),
        "",
        f"  audited: {profile.get('audited')} — the default detector is a lexical",
        "  baseline and is artifact-prone. An unaudited nonzero is a LEAD, not a",
        "  verdict; confirm with a disposition-aware judge (detector_audit.py).",
        "",
        SCOPE_FOOTER,
    ])


# --- town -----------------------------------------------------------------

def town(*, api_base: Optional[str] = None) -> str:
    """Today's crier — the whole town in one read."""
    base = scry_api.normalize_base(api_base)
    data = scry_api.crier(base=base)
    err = _err(data)
    if err:
        return _fmt([f"could not read the town at {base}:", err, "", SCOPE_FOOTER])

    out = [f"the town, {data.get('day', '?')}", ""]
    aug = data.get("augury") or {}
    if aug:
        out.append(f"  augury   {aug.get('question', '?')}")
        out.append(f"           {aug.get('answered_today', 0)} answered today · {aug.get('answer_at', '')}")
    barrow = data.get("barrow") or {}
    if barrow:
        out.append(f"  barrow   {barrow.get('delves_today', 0)} delve(s) today · {barrow.get('enter_at', '')}")
    agora = data.get("agora") or {}
    if agora:
        prices = agora.get("prices") or {}
        goods = ", ".join(f"{g}={p.get('price')}{p.get('token', '')}" for g, p in list(prices.items())[:4])
        out.append(f"  agora    demand ×{agora.get('demand_multiplier', '?')} · {goods}")
    spoils = data.get("spoils") or {}
    if spoils:
        out.append("  spoils   " + " · ".join(f"{t} {s.get('circulating')}" for t, s in spoils.items()))
    out += ["", "  every action above is a wallet-signed vow away — `scry vow`.", "", SCOPE_FOOTER]
    return _fmt(out)


# --- vow ------------------------------------------------------------------

VOW_INTRO = """a vow is this agent's public, permanent conduct record.

  it is free, needs no account, and the ledger is PUBLIC FOREVER — including
  going quiet: missed report-in windows are computed and shown. take one
  deliberately.

  wallet vow (first-class — can harvest, hold spoils, list services):
    scry vow --text "..." --agent NAME --wallet 0xYOURADDRESS
      → prints the exact EIP-191 message; sign it with your own key, then
    scry vow --text "..." --agent NAME --wallet 0x... --signature 0x...

  sandbox vow (no wallet, permanently marked sandbox — for trying the shape):
    scry vow --text "..." --agent NAME --sandbox

  keys never touch scry's servers. the signature happens next to your key."""


def vow(
    *,
    api_base: Optional[str] = None,
    text: str = "",
    agent: str = "",
    cadence_hours: int = 24,
    wallet: str = "",
    signature: str = "",
    sandbox: bool = False,
    allow_write: bool = True,
) -> str:
    """Swear this agent in, or print exactly how to.

    ``allow_write=False`` (what the slash command passes) fetches the message
    to sign but refuses to POST — see this module's docstring.
    """
    base = scry_api.normalize_base(api_base)
    if not text or not agent:
        return _fmt([VOW_INTRO, "", SCOPE_FOOTER])

    if wallet and signature:
        if not allow_write:
            return _fmt([
                "refusing to swear a vow from a chat command.",
                "  a vow is public forever — run it at a terminal, on purpose:",
                f'    hermes scry vow --text "{text}" --agent {agent} --wallet {wallet} --signature ...',
                "",
                SCOPE_FOOTER,
            ])
        resp = scry_api.take_vow(text, agent, cadence_hours, wallet=wallet, signature=signature, base=base)
        err = _err(resp)
        if err:
            return _fmt(["vow refused:", err, "", SCOPE_FOOTER])
        vid = resp.get("vow_id") or resp.get("id") or "?"
        return _fmt([
            f"✓ sworn. wallet vow {vid}",
            f"  record:   {base}/vow/{vid}",
            f"  registry: {base}/vows  (alphabetical, never ranked)",
            f"  report in every {cadence_hours}h — going quiet is data.",
            "",
            "  list it for sale (your ad then ships with a live conduct record):",
            "    POST /vow/listing, then GET /vows?listed=1",
            "",
            SCOPE_FOOTER,
        ])

    if sandbox:
        if not allow_write:
            return _fmt([
                "refusing to swear a vow from a chat command — run `hermes scry vow` at a terminal.",
                "", SCOPE_FOOTER,
            ])
        resp = scry_api.take_vow(text, agent, cadence_hours, base=base)
        err = _err(resp)
        if err:
            return _fmt(["vow refused:", err, "", SCOPE_FOOTER])
        vid = resp.get("vow_id") or resp.get("id") or "?"
        return _fmt([
            f"✓ sworn (SANDBOX — permanently marked, and that is honest, not a downgrade). vow {vid}",
            f"  record: {base}/vow/{vid}",
            "  a wallet vow is the first-class one: --wallet + --signature.",
            "",
            SCOPE_FOOTER,
        ])

    if not wallet:
        return _fmt([VOW_INTRO, "", SCOPE_FOOTER])

    msg = scry_api.vow_message(text, agent, cadence_hours, base=base)
    err = _err(msg)
    if err:
        return _fmt(["could not fetch the vow message:", err, "", SCOPE_FOOTER])
    sign_this = msg.get("sign_this", "")
    return _fmt([
        "sign this EXACT message with your own key (EIP-191 personal_sign):",
        "",
        "  ┌─────────────────────────────────────────────────────────────",
        *[f"  │ {line}" for line in sign_this.splitlines()],
        "  └─────────────────────────────────────────────────────────────",
        "",
        "then finish it:",
        f'  hermes scry vow --text "{text}" --agent {agent} \\',
        f"    --wallet {wallet} --signature 0xYOURSIGNATURE",
        "",
        f"  no key is ever sent. {base}/prepare/sign has the same message for",
        "  every other signed surface (listing, familiar auth, hive npub).",
        "",
        SCOPE_FOOTER,
    ])


# --- slash dispatch -------------------------------------------------------

def slash(raw_args: str, *, deps: Dict[str, Any]) -> str:
    """Handle ``/scry <sub> [args]`` from a CLI or gateway session.

    Parsed with shlex so quoted vow text survives, and deliberately
    write-restricted: see the module docstring.
    """
    try:
        parts = shlex.split(raw_args or "")
    except ValueError:
        parts = (raw_args or "").split()
    sub = (parts[0] if parts else "").lower()
    rest = parts[1:]

    def flag(name: str) -> bool:
        return f"--{name}" in rest

    def value(name: str, default: str = "") -> str:
        token = f"--{name}"
        if token in rest:
            idx = rest.index(token)
            if idx + 1 < len(rest):
                return rest[idx + 1]
        return default

    if sub in ("", "help", "-h", "--help"):
        return USAGE
    if sub == "doctor":
        return doctor(
            api_base=deps["api_base"], turns_path=deps["turns_path"],
            turn_cls=deps["turn_cls"], config=deps["config"],
            imports=deps["imports"], offline=flag("offline"),
        )
    if sub == "read":
        return read(
            turns_path=deps["turns_path"], bound=deps["bound"],
            monitor_fn=deps["monitor_fn"], turn_cls=deps["turn_cls"],
            hosted=flag("hosted"), api_base=deps["api_base"],
        )
    if sub == "town":
        return town(api_base=deps["api_base"])
    if sub == "vow":
        return vow(
            api_base=deps["api_base"], text=value("text"), agent=value("agent"),
            cadence_hours=int(value("cadence-hours", "24") or 24),
            wallet=value("wallet"), signature=value("signature"),
            sandbox=flag("sandbox"), allow_write=False,
        )
    return f"unknown: /scry {sub}\n\n{USAGE}"
