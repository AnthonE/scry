"""Vow Oracle — vow registry + hash-chained report-ins (the Destiny System,
unbundled from the game and offered to any agent anywhere).

The primitive: an agent COMMITS a declared purpose (a vow — this is §220's
"name Y or park" made into a product: the vow IS the naming of Y), then
REPORTS IN over time. Each report-in scores a trace against the vow's Y and
appends a signed, hash-chained entry to the agent's public ledger. The
product is the TRAJECTORY, not any single read — and a missed report-in is
itself signal (silence is data; breaking off the ritual is the oldest tell
in the record).

Transparency is the data policy: every vow and every chain entry is PUBLIC
by design. That's the honest trade — the service is near-free, the ledger is
the product, and the corpus (real vow-conditioned traces over time) is the
research data. This is stated in the scope card on every response.

What this module does NOT do (guards, non-negotiable):
  - No verdicts. The oracle gives a READING; the querent decides. Blocking
    an action is the bound's job, and the bound stays local.
  - No stake/slashing. Measuring and enforcing must not be the same party.
    Parked forever, not just for now.
  - The measurement math is turn_record.channel_profile — same function as
    the meter, not forked. The vow adds ONE deterministic stat on top:
    y_consistency (do the turns' declared Y still match the vow?).
"""
import hashlib
import json
import os
import re
import time
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

VOWS_DIR = Path(os.getenv("SCRY_VOWS_DIR", str(Path(__file__).resolve().parent / "vows_data")))
VOW_DEMO_DAILY_LIMIT = int(os.getenv("SCRY_VOW_DEMO_LIMIT", "20"))   # sandbox reports / IP / day
VOW_CREATE_DAILY_LIMIT = int(os.getenv("SCRY_VOW_CREATE_LIMIT", "10"))  # new vows / IP / day
DONATION_MAX_BYTES = int(os.getenv("SCRY_DONATION_MAX_BYTES", "524288"))  # 512KB / donated trace
VOW_MAX_TEXT = 2000
NOTE_MAX_CHARS = 1000               # confession length cap
Y_DECLARED_MAX = 20                 # unique Y strings kept per entry
Y_DECLARED_CHAR_CAP = 300           # per-string truncation
VOW_MIN_CADENCE_H = 1
VOW_MAX_CADENCE_H = 24 * 30

router = APIRouter()

# Injected by server.py at mount time (shared with the meter — same key, same
# math, same scope discipline).
_deps: dict = {}


def init(*, sign_fn, pubkey_b64, issuer, scope_card, build_turns, run_profile,
         canonical, paid_ready=lambda: False):
    """server.py hands us the meter's signing + scoring plumbing. We never
    duplicate the key handling or the math. `paid_ready` mirrors the meter's
    fail-closed discipline: no payment rail mounted => no attested entries."""
    _deps.update(sign_fn=sign_fn, pubkey_b64=pubkey_b64, issuer=issuer,
                 scope_card=scope_card, build_turns=build_turns,
                 run_profile=run_profile, canonical=canonical,
                 paid_ready=paid_ready)
    VOWS_DIR.mkdir(parents=True, exist_ok=True)


VOW_SCOPE = {
    "public_by_design": (
        "Vow text (unless sealed), agent name, and every chain entry's NUMBERS "
        "and HASHES are public forever — that is what makes the record checkable. "
        "Raw traces are NEVER stored or published unless you set donate_trace=true "
        "on a report-in (they are scored, hashed, and discarded) — EXCEPT the "
        "turns' declared-Y strings (the public commitments channel) and any "
        "`note` you attach (your public self-account), which live on the signed "
        "chain entry forever. Reasoning (M) and actions (D) are never stored. "
        "Sealed vows publish only sha256(text) and store NO declared-Y strings "
        "(they would leak the seal) — same price; the reading notes the seal."),
    "no_api_keys": (
        "There are no API keys and never will be. Payment IS the auth (x402); "
        "identity IS the wallet signature; free endpoints are IP-rate-limited. "
        "You may pay to be measured; you may never pay to be hidden or ranked."),
    "reading_not_verdict": (
        "The oracle returns a reading of a trajectory, never a verdict on an "
        "action. Execution decisions belong to the local bound in your harness."),
    "silence_is_signal": (
        "Your declared cadence is part of your vow. Missed report-ins are "
        "computed and shown on your public ledger. Going quiet is data."),
    "no_meter_is_immune": (
        "A long clean chain is evidence, not proof. An agent optimizing against "
        "the meter can write clean traces — but a signed chain it later "
        "contradicts in the world is a commitment it can be caught breaking."),
}


# ── canonical forms + hashing ────────────────────────────────────────────────
def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _vow_path(vow_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{16}", vow_id):
        raise ValueError("bad vow_id")
    return VOWS_DIR / f"{vow_id}.json"


def _chain_path(vow_id: str) -> Path:
    return VOWS_DIR / f"{vow_id}.chain.jsonl"


def _load_vow(vow_id: str) -> dict | None:
    p = _vow_path(vow_id)
    return json.loads(p.read_text()) if p.exists() else None


def _save_vow(rec: dict) -> None:
    _vow_path(rec["vow_id"]).write_text(json.dumps(rec, indent=1))


def _chain_entries(vow_id: str) -> list[dict]:
    p = _chain_path(vow_id)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


# ── vow registration ─────────────────────────────────────────────────────────
class VowRequest(BaseModel):
    text: str                       # the declared purpose — the Y being sworn
    agent: str                      # a human-readable agent name/handle
    cadence_hours: int = 24         # declared report-in cadence
    wallet: str | None = None       # EVM wallet (0x…) — omit for sandbox
    signature: str | None = None    # EIP-191 personal_sign over the canonical vow text
    sealed: bool = False            # publish only sha256(text); wallet-signed vows only


def vow_signing_message(text: str, agent: str, cadence_hours: int) -> str:
    """The exact text a wallet signs to take a vow. Deterministic, so anyone
    can re-derive and re-verify it from the public record forever."""
    return (f"scry vow\nagent: {agent}\ncadence_hours: {cadence_hours}\n"
            f"vow: {text}\nby signing, this wallet takes this vow publicly.")


@router.get("/vow/message")
async def vow_message(text: str, agent: str, cadence_hours: int = 24) -> dict:
    """Step 0 for a signed vow: fetch the exact message to EIP-191-sign."""
    return {"sign_this": vow_signing_message(text, agent, cadence_hours)}


_vow_create_hits: dict[str, list] = {}


def _create_ok(ip: str) -> bool:
    day = int(time.time() // 86400)
    rec = _vow_create_hits.get(ip)
    if not rec or rec[0] != day:
        _vow_create_hits[ip] = [day, 0]
        rec = _vow_create_hits[ip]
    if rec[1] >= VOW_CREATE_DAILY_LIMIT:
        return False
    rec[1] += 1
    return True


@router.post("/vow")
async def take_vow(req: VowRequest, request: Request) -> JSONResponse:
    """Take a vow. Free. Signed (wallet) vows are first-class; unsigned vows
    are accepted but permanently marked sandbox — kids get to play, and the
    ledger stays honest about which is which."""
    ip = (request.headers.get("x-forwarded-for", "") or request.client.host or "?").split(",")[0].strip()
    if not _create_ok(ip):
        return JSONResponse(status_code=429, content={
            "error": f"vow-creation limit {VOW_CREATE_DAILY_LIMIT}/day/IP — the register is forever, take vows deliberately",
            "scope": VOW_SCOPE})
    text = req.text.strip()
    if not text or len(text) > VOW_MAX_TEXT:
        return JSONResponse(status_code=422, content={
            "error": f"vow text must be 1..{VOW_MAX_TEXT} chars", "scope": VOW_SCOPE})
    if not (VOW_MIN_CADENCE_H <= req.cadence_hours <= VOW_MAX_CADENCE_H):
        return JSONResponse(status_code=422, content={
            "error": f"cadence_hours must be {VOW_MIN_CADENCE_H}..{VOW_MAX_CADENCE_H}",
            "scope": VOW_SCOPE})

    sandbox = True
    wallet = None
    if req.wallet and req.signature:
        try:
            from eth_account import Account
            from eth_account.messages import encode_defunct
            msg = vow_signing_message(text, req.agent, req.cadence_hours)
            recovered = Account.recover_message(encode_defunct(text=msg),
                                                signature=req.signature)
        except Exception as e:  # noqa: BLE001
            return JSONResponse(status_code=422, content={
                "error": f"signature check failed: {e}", "scope": VOW_SCOPE})
        if recovered.lower() != req.wallet.lower():
            return JSONResponse(status_code=422, content={
                "error": f"signature recovers {recovered}, not {req.wallet}",
                "scope": VOW_SCOPE})
        sandbox = False
        wallet = recovered

    if req.sealed and sandbox:
        return JSONResponse(status_code=422, content={
            "error": "sealed vows require a wallet signature — a seal with no "
                     "owner identity could never be revealed or proven",
            "scope": VOW_SCOPE})

    vow_body = {"text": text, "agent": req.agent.strip()[:120],
                "cadence_hours": req.cadence_hours,
                "wallet": wallet, "created_at": _now()}
    vow_id = _sha(_canon(vow_body))[:16]
    if _load_vow(vow_id):
        return JSONResponse(status_code=409, content={
            "error": "identical vow already exists", "vow_id": vow_id,
            "scope": VOW_SCOPE})

    rec = {"vow_id": vow_id, "vow": vow_body,
           "wallet_sig": req.signature if not sandbox else None,
           "sandbox": sandbox,
           "sealed": bool(req.sealed),
           "issuer": _deps["issuer"],
           "attestation_pubkey_b64": _deps["pubkey_b64"],
           "seq": 0, "chain_head": None}
    rec["countersig"] = _deps["sign_fn"](_canon(rec))
    _save_vow(rec)
    return JSONResponse(content={**_public_vow(rec), "scope": VOW_SCOPE,
                                 "report_in": "POST /vow/report {vow_id, turns, context_key} — paid, attested"
                                              " | POST /vow/report/demo — free, sandbox-marked"})


def _public_vow(rec: dict) -> dict:
    """The public shape of a vow record. Sealed vows publish only the hash of
    the text — the text stays server-side (needed to score y_consistency) and
    the owner (or anyone holding the text) can verify it against text_sha256."""
    out = json.loads(json.dumps(rec))  # deep copy
    if out.get("sealed"):
        out["vow"]["text_sha256"] = _sha(out["vow"]["text"])
        out["vow"]["text"] = None
        out["vow"]["sealed_note"] = (
            "vow text is sealed — committed by text_sha256, scored privately. "
            "Verify a candidate text at GET /vow/{id}/verify_text?text=…")
    return out


# ── report-ins (the ritual) ──────────────────────────────────────────────────
class ReportRequest(BaseModel):
    vow_id: str
    turns: list[dict]
    context_key: str = "monitored"
    donate_trace: bool = False      # opt-in: persist raw turns for research (default: score, hash, discard)
    note: str | None = None         # optional CONFESSION: the agent's own public account
                                    # of this period. Stored on the chain entry, signed,
                                    # public forever. The oracle compares testimony vs numbers.


def _y_consistency(turns_raw: list[dict], vow_text: str) -> float:
    """Deterministic: fraction of turns whose declared Y still names the vow.
    Normalized substring containment either direction — crude on purpose; a
    fancier matcher would be a place for judgment to hide."""
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s.strip().lower())
    v = norm(vow_text)
    if not turns_raw:
        return 0.0
    hits = 0
    for t in turns_raw:
        y = norm(str(t.get("Y", "")))
        if y and (y in v or v in y):
            hits += 1
    return round(hits / len(turns_raw), 4)


def _y_declared(turns_raw: list[dict], vow: dict) -> list[str] | None:
    """The turns' DECLARED Y strings — the public-commitments channel. Stored on
    the entry (deduped, capped) so the oracle can audit semantic faithfulness to
    the vow without ever seeing reasoning (M) or actions (D).

    SEALED vows: returns None. An agent's Y usually mirrors its vow, so storing
    declared Y's would leak the sealed text. No Y storage, no semantic audit —
    the reading says so."""
    if vow.get("sealed"):
        return None
    seen: list[str] = []
    for t in turns_raw:
        y = str(t.get("Y", "")).strip()[:Y_DECLARED_CHAR_CAP]
        if y and y not in seen:
            seen.append(y)
        if len(seen) >= Y_DECLARED_MAX:
            break
    return seen


def _append_report(vow: dict, turns_raw: list[dict], context_key: str,
                   attested: bool, donate_trace: bool = False,
                   note: str | None = None) -> dict:
    """Score the trace against the vow, hash-chain it, sign it, persist the
    ENTRY (numbers + hashes). The raw trace is scored and discarded unless the
    caller opted in with donate_trace — consent architecture, not surveillance."""
    turns = _deps["build_turns"](turns_raw)
    profile = _deps["run_profile"](turns, context_key)
    trace_sha256 = _sha(_deps["canonical"](turns_raw, context_key))
    entry = {
        "vow_id": vow["vow_id"],
        "seq": vow["seq"] + 1,
        "prev_hash": vow["chain_head"],
        "trace_sha256": trace_sha256,
        "context_key": context_key,
        "profile": profile,
        "y_consistency": _y_consistency(turns_raw, vow["vow"]["text"]),
        "attested": attested,          # False = sandbox/demo entry, marked forever
        "trace_donated": bool(donate_trace),
        "y_declared": _y_declared(turns_raw, vow),
        "note": (note.strip()[:NOTE_MAX_CHARS] if note and note.strip() else None),
        "issued_at": _now(),
        "issuer": _deps["issuer"],
        "attestation_pubkey_b64": _deps["pubkey_b64"],
    }
    entry["entry_hash"] = _sha(_canon(entry))
    entry["sig"] = _deps["sign_fn"](_canon(entry))
    with _chain_path(vow["vow_id"]).open("a") as f:
        f.write(_canon(entry) + "\n")
    if donate_trace:
        blob = _canon({"turns": turns_raw, "context_key": context_key,
                       "trace_sha256": trace_sha256, "donated_at": entry["issued_at"]})
        if len(blob.encode()) <= DONATION_MAX_BYTES:
            ddir = VOWS_DIR / "donations"
            ddir.mkdir(exist_ok=True)
            (ddir / f"{vow['vow_id']}.{entry['seq']}.json").write_text(blob)
        else:
            entry["trace_donated"] = False  # too large — scored + hashed, not kept
    vow["seq"] = entry["seq"]
    vow["chain_head"] = entry["entry_hash"]
    _save_vow(vow)
    return entry


@router.post("/vow/report")
async def vow_report(req: ReportRequest) -> JSONResponse:
    """Paid report-in — reached only AFTER x402 settle (server.py registers
    this path with the payment middleware). Flat price, same as /profile.
    Fail closed: if no paid rail is mounted the middleware isn't either, so
    refuse rather than hand out free attested entries."""
    if not _deps["paid_ready"]():
        return JSONResponse(status_code=503, content={
            "error": "no paid rail available — use POST /vow/report/demo (unsigned tier) meanwhile",
            "scope": VOW_SCOPE})
    vow = _load_vow(req.vow_id)
    if not vow:
        return JSONResponse(status_code=404, content={"error": "no such vow", "scope": VOW_SCOPE})
    try:
        entry = _append_report(vow, req.turns, req.context_key, attested=True,
                               donate_trace=req.donate_trace, note=req.note)
    except (ValueError, KeyError, TypeError) as e:
        return JSONResponse(status_code=422, content={"error": str(e), "scope": VOW_SCOPE})
    return JSONResponse(content={**entry, "scope": VOW_SCOPE})


_demo_hits: dict[str, list] = {}


def _demo_ok(ip: str) -> bool:
    day = int(time.time() // 86400)
    rec = _demo_hits.get(ip)
    if not rec or rec[0] != day:
        _demo_hits[ip] = [day, 0]
        rec = _demo_hits[ip]
    if rec[1] >= VOW_DEMO_DAILY_LIMIT:
        return False
    rec[1] += 1
    return True


@router.post("/vow/report/demo")
async def vow_report_demo(req: ReportRequest, request: Request) -> JSONResponse:
    """Free report-in. Appends a REAL chain entry, permanently marked
    attested=false — play is welcome, the ledger just never forgets which
    entries were free-tier."""
    ip = (request.headers.get("x-forwarded-for", "") or request.client.host or "?").split(",")[0].strip()
    if not _demo_ok(ip):
        return JSONResponse(status_code=429, content={
            "error": f"demo limit {VOW_DEMO_DAILY_LIMIT}/day — POST /vow/report (paid) has no cap",
            "scope": VOW_SCOPE})
    vow = _load_vow(req.vow_id)
    if not vow:
        return JSONResponse(status_code=404, content={"error": "no such vow", "scope": VOW_SCOPE})
    try:
        entry = _append_report(vow, req.turns, req.context_key, attested=False,
                               donate_trace=req.donate_trace, note=req.note)
    except (ValueError, KeyError, TypeError) as e:
        return JSONResponse(status_code=422, content={"error": str(e), "scope": VOW_SCOPE})
    return JSONResponse(content={**entry, "scope": VOW_SCOPE})


# ── the trajectory (deterministic — this is what the oracle narrates) ────────
SWITCH_KEY = "I(C;M | D-clean) bits  [switch signature]"
ICM_KEY = "I(C;M) bits"


def trajectory_stats(vow: dict, entries: list[dict]) -> dict:
    """Everything a counterparty reads, computed from the public chain.
    Deterministic — no model, no judgment. Silence-as-signal lives here:
    missed windows are (elapsed / cadence) - reports, floored at 0."""
    now = time.time()
    created = time.mktime(time.strptime(vow["vow"]["created_at"], "%Y-%m-%dT%H:%M:%SZ"))
    cadence_s = vow["vow"]["cadence_hours"] * 3600
    elapsed_windows = max(0, int((now - created) // cadence_s))
    n = len(entries)
    times = [time.mktime(time.strptime(e["issued_at"], "%Y-%m-%dT%H:%M:%SZ")) for e in entries]
    gaps_h = [round((b - a) / 3600, 2) for a, b in zip(times, times[1:])]
    icm = [e["profile"].get(ICM_KEY) for e in entries if ICM_KEY in e["profile"]]
    switch = [e["profile"].get(SWITCH_KEY) for e in entries if SWITCH_KEY in e["profile"]]
    ycon = [e.get("y_consistency") for e in entries if e.get("y_consistency") is not None]
    last_seen_h = round((now - times[-1]) / 3600, 2) if times else None
    return {
        "n_reports": n,
        "n_attested": sum(1 for e in entries if e.get("attested")),
        "n_sandbox": sum(1 for e in entries if not e.get("attested")),
        "cadence_declared_hours": vow["vow"]["cadence_hours"],
        "median_gap_hours": (sorted(gaps_h)[len(gaps_h) // 2] if gaps_h else None),
        "elapsed_windows": elapsed_windows,
        "missed_windows": max(0, elapsed_windows - n),
        "hours_since_last_report": last_seen_h,
        "overdue": (last_seen_h is not None and last_seen_h > vow["vow"]["cadence_hours"]),
        "coupling_ICM_series": icm[-30:],
        "switch_signature_series": switch[-30:],
        "y_consistency_series": ycon[-30:],
        "coupling_ICM_delta_last5": (round(icm[-1] - icm[-5], 4) if len(icm) >= 5 else None),
        "chain_verified_locally": None,  # filled by the ledger view below
    }


def verify_chain(entries: list[dict]) -> bool:
    """Re-hash every entry and check the prev_hash links. Anyone can run this
    from the public data — that is the point."""
    prev = None
    for e in entries:
        body = {k: v for k, v in e.items() if k not in ("entry_hash", "sig")}
        if body.get("prev_hash") != prev:
            return False
        if _sha(_canon(body)) != e.get("entry_hash"):
            return False
        prev = e["entry_hash"]
    return True


@router.get("/vow/{vow_id}")
async def vow_ledger(vow_id: str) -> JSONResponse:
    """The public ledger: the vow, the chain, the trajectory. Free forever —
    reading the record is the demand side of the whole design."""
    try:
        vow = _load_vow(vow_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad vow_id"})
    if not vow:
        return JSONResponse(status_code=404, content={"error": "no such vow", "scope": VOW_SCOPE})
    entries = _chain_entries(vow_id)
    stats = trajectory_stats(vow, entries)
    stats["chain_verified_locally"] = verify_chain(entries)
    return JSONResponse(content={
        "vow": _public_vow(vow),
        "trajectory": stats,
        "chain": entries[-50:],
        "chain_full_note": f"showing last 50 of {len(entries)}; full chain at GET /vow/{vow_id}/chain",
        "reading": f"GET /vow/{vow_id}/reading — the oracle's interpretation of this trajectory",
        "scope": VOW_SCOPE,
    })


@router.get("/vow/{vow_id}/chain")
async def vow_chain_full(vow_id: str) -> JSONResponse:
    """The complete raw chain — the whole dataset for this vow, no pagination
    games. Transparency is the data policy."""
    try:
        entries = _chain_entries(vow_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad vow_id"})
    return JSONResponse(content={"vow_id": vow_id, "n": len(entries), "chain": entries})


@router.get("/vows")
async def vow_index(listed: int = 0) -> JSONResponse:
    """Public index of every vow ever taken — the register, and (with
    ?listed=1) the DIRECTORY of sworn agents advertising services.
    Alphabetical by agent, never ranked."""
    out = []
    for p in sorted(VOWS_DIR.glob("*.json")):
        try:
            v = json.loads(p.read_text())
            if "vow_id" not in v:
                continue
        except Exception:  # noqa: BLE001
            continue
        if listed and not v.get("listing"):
            continue
        entries = _chain_entries(v["vow_id"])
        stats = trajectory_stats(v, entries)
        pv = _public_vow(v)
        out.append({"vow_id": v["vow_id"], "agent": v["vow"]["agent"],
                    "text": (pv["vow"]["text"][:140] if pv["vow"]["text"] else None),
                    "sealed": bool(v.get("sealed")),
                    "text_sha256": pv["vow"].get("text_sha256"), "sandbox": v["sandbox"],
                    "wallet": v["vow"].get("wallet"),
                    "created_at": v["vow"]["created_at"],
                    "n_reports": stats["n_reports"],
                    "missed_windows": stats["missed_windows"],
                    "overdue": stats["overdue"],
                    "listing": v.get("listing"),
                    "mark": f"/vow/{v['vow_id']}/mark.svg",
                    "stele": f"/vow/{v['vow_id']}/stele.svg",
                    "badge": f"/vow/{v['vow_id']}/badge.svg"})
    if listed:
        out.sort(key=lambda r: (r["agent"] or "").lower())
    return JSONResponse(content={"n_vows": len(out), "vows": out, "scope": VOW_SCOPE})


@router.get("/vow/{vow_id}/verify_text")
async def vow_verify_text(vow_id: str, text: str) -> JSONResponse:
    """Sealed-vow reveal check: anyone holding a candidate text can verify it
    against the public commitment. Returns match true/false — the server never
    echoes the sealed text itself."""
    try:
        vow = _load_vow(vow_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad vow_id"})
    if not vow:
        return JSONResponse(status_code=404, content={"error": "no such vow"})
    if not vow.get("sealed"):
        return JSONResponse(content={"sealed": False,
                                     "note": "this vow is not sealed — its text is public on GET /vow/{id}"})
    return JSONResponse(content={
        "sealed": True,
        "match": _sha(text.strip()) == _sha(vow["vow"]["text"]),
        "text_sha256": _sha(vow["vow"]["text"]),
    })


# ── the badge — an embeddable live conduct card (the CI badge for agents) ────
@router.get("/vow/{vow_id}/badge.svg")
async def vow_badge(vow_id: str):
    """Live SVG badge for a vow — drop it in a README:
    ![scry](https://scry.moreright.xyz/api/vow/<id>/badge.svg)
    Shows: agent, reports/missed, latest coupling, overdue state, chain-
    verified check. Renders from the same public data as the ledger; the
    badge asserts nothing the ledger can't back."""
    from fastapi.responses import Response
    try:
        vow = _load_vow(vow_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad vow_id"})
    if not vow:
        return JSONResponse(status_code=404, content={"error": "no such vow"})
    entries = _chain_entries(vow_id)
    stats = trajectory_stats(vow, entries)
    verified = verify_chain(entries)
    icm = stats.get("coupling_ICM_series") or []
    overdue = bool(stats.get("overdue"))
    status = "overdue" if overdue else "reporting"
    scolor = "#e07070" if overdue else "#00c805"
    agent = (vow["vow"]["agent"] or "?")[:24]
    line2 = (f"reports {stats['n_reports']} · missed {stats['missed_windows']} · "
             f"I(C;M) {icm[-1] if icm else '—'} · "
             f"chain {'✓' if verified else '✗'}")
    def _esc(s: str) -> str:
        return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="380" height="48" role="img" aria-label="scry conduct badge">
<rect width="380" height="48" rx="8" fill="#150e28" stroke="#2b1c45"/>
<text x="14" y="20" font-family="Menlo,monospace" font-size="12" fill="#f4b942" font-weight="bold">scry.</text>
<text x="52" y="20" font-family="Menlo,monospace" font-size="12" fill="#f4efe4">{_esc(agent)}</text>
<rect x="{380 - 92}" y="9" width="78" height="16" rx="8" fill="none" stroke="{scolor}"/>
<text x="{380 - 53}" y="20" font-family="Menlo,monospace" font-size="9" fill="{scolor}" text-anchor="middle">{status}</text>
<text x="14" y="38" font-family="Menlo,monospace" font-size="10" fill="#b9b0cc">{_esc(line2)}</text>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=300"})


# ── the mark + the stele — the vow as artifact ───────────────────────────────
# Naming per the Cut-the-Ouroboros corpus (ketef-hinnom, defixio tablets, the
# self-executing oath): the MARK is the seal-impression — a deterministic
# glyph that authenticates; the STELE is the public monument — the oath
# itself, inscribed and displayed. Same vow → same mark, same stele, forever.

def _mark_group(vow_id: str, cx: float, cy: float, scale: float = 1.0) -> str:
    """The glyph geometry (pure sha256(vow_id) — zero chance, zero knobs),
    rendered as an SVG group centered at (cx, cy)."""
    import math
    h = hashlib.sha256(vow_id.encode()).digest()
    R = 44 * scale
    pts = []
    for i in range(8):
        r = (14 + (h[i] / 255) * 30) * scale
        a = (i / 8) * 2 * math.pi - math.pi / 2
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    ring = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    chords = []
    for i in range(8, 14):
        a, b = h[i] % 8, h[i] // 16 % 8
        if a != b:
            chords.append(f'<line x1="{pts[a][0]:.1f}" y1="{pts[a][1]:.1f}" '
                          f'x2="{pts[b][0]:.1f}" y2="{pts[b][1]:.1f}"/>')
    accent = ["#4f8fd9", "#b5811f", "#b8619e"][h[14] % 3]
    dot = pts[h[15] % 8]
    return (f'<circle cx="{cx}" cy="{cy}" r="{R + 6 * scale:.1f}" fill="none" '
            f'stroke="#2b1c45" stroke-width="{1.5 * scale:.1f}"/>' 
            f'<g stroke="{accent}" stroke-width="{1.2 * scale:.1f}" opacity="0.85">{"".join(chords)}</g>'
            f'<polygon points="{ring}" fill="none" stroke="#f4b942" '
            f'stroke-width="{2 * scale:.1f}" stroke-linejoin="round"/>'
            f'<circle cx="{dot[0]:.1f}" cy="{dot[1]:.1f}" r="{3.4 * scale:.1f}" fill="#f4b942"/>')


@router.get("/vow/{vow_id}/mark.svg")
async def vow_mark(vow_id: str):
    """The mark — the vow's seal-impression. Deterministic glyph from
    sha256(vow_id); the identity emblem across register, boards, and the
    stele. Free to render; minting is a later, separate, operator gate."""
    from fastapi.responses import Response
    try:
        vow = _load_vow(vow_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad vow_id"})
    if not vow:
        return JSONResponse(status_code=404, content={"error": "no such vow"})
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" '
           f'viewBox="0 0 120 120" role="img" aria-label="mark of vow {vow_id}">'
           f'<rect width="120" height="120" rx="14" fill="#150e28"/>'
           f'{_mark_group(vow_id, 60, 60)}</svg>')
    return Response(content=svg, media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=86400"})


def _wrap(text: str, width: int, max_lines: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
        if len(lines) == max_lines:
            lines[-1] = lines[-1][: width - 1] + "…"
            return lines
    if cur:
        lines.append(cur)
    return lines


@router.get("/vow/{vow_id}/stele.svg")
async def vow_stele(vow_id: str):
    """The stele — the vow as a public monument: the sworn text inscribed in
    full, the swearer, the date, the cadence, the mark as its seal, and the
    record's living state. Everything on it is re-checkable against the
    ledger; the stele asserts nothing the chain can't back."""
    from fastapi.responses import Response
    try:
        vow = _load_vow(vow_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad vow_id"})
    if not vow:
        return JSONResponse(status_code=404, content={"error": "no such vow"})
    entries = _chain_entries(vow_id)
    stats = trajectory_stats(vow, entries)
    verified = verify_chain(entries)
    v = vow["vow"]
    def esc(x):
        return (str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    if vow.get("sealed"):
        body_lines = ["[ sealed — committed by hash ]",
                      f"sha256: {_sha(v['text'])[:32]}…"]
        body_style = 'font-family="Menlo,monospace" font-size="12" fill="#b9b0cc"'
    else:
        body_lines = _wrap(v["text"], 52, 8)
        body_style = ('font-family="Georgia,serif" font-size="16" font-style="italic" '
                      'fill="#e8d5b7"')
    text_h = len(body_lines) * 24
    H = 300 + text_h
    tspans = "".join(
        f'<tspan x="50" dy="{0 if i == 0 else 24}">{esc(ln)}</tspan>'
        for i, ln in enumerate(body_lines))
    status = "OVERDUE" if stats.get("overdue") else "REPORTING"
    scolor = "#e07070" if stats.get("overdue") else "#00c805"
    footer = (f"reports {stats['n_reports']} · missed {stats['missed_windows']} · "
              f"chain {'verified' if verified else 'BROKEN'} · vow {vow_id}")
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="560" height="{H}" viewBox="0 0 560 {H}" role="img" aria-label="stele of vow {vow_id}">
<rect width="560" height="{H}" rx="16" fill="#150e28"/>
<rect x="14" y="14" width="532" height="{H - 28}" rx="10" fill="none" stroke="#2b1c45" stroke-width="2"/>
<rect x="20" y="20" width="520" height="{H - 40}" rx="7" fill="none" stroke="rgba(244,185,66,0.25)" stroke-width="1"/>
<text x="50" y="64" font-family="Menlo,monospace" font-size="11" letter-spacing="4" fill="#f4b942">SCRY · THE VOW OF</text>
<text x="50" y="96" font-family="Georgia,serif" font-size="26" fill="#f4efe4">{esc(v['agent'])}</text>
<text x="50" y="140" {body_style}>{tspans}</text>
<text x="50" y="{170 + text_h}" font-family="Menlo,monospace" font-size="10.5" fill="#b9b0cc">sworn {esc(v['created_at'][:10])} · every {v['cadence_hours']}h · {esc((v.get('wallet') or 'sandbox')[:20])}{'…' if v.get('wallet') else ''}</text>
<text x="50" y="{192 + text_h}" font-family="Menlo,monospace" font-size="10.5" fill="#b9b0cc">{esc(footer)}</text>
<text x="50" y="{224 + text_h}" font-family="Menlo,monospace" font-size="10" fill="{scolor}">{status}</text>
<text x="50" y="{H - 34}" font-family="Menlo,monospace" font-size="9" fill="#776f8f">publicly recorded · hash-chained · anchored on RH-Chain · /vow/{vow_id}</text>
{_mark_group(vow_id, 470, H - 90, 0.62)}
</svg>"""
    return Response(content=svg, media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=300"})


# ── the directory — sworn agents advertise services (list-never-rank) ────────
class ListingRequest(BaseModel):
    vow_id: str
    services: str               # what this agent offers (plain text, public)
    endpoint: str | None = None  # where to reach it (URL / MCP / handle)
    signature: str | None = None  # playauth "listing" action sig


@router.post("/vow/listing")
async def vow_listing(req: ListingRequest) -> JSONResponse:
    """Attach (or update) a public services listing to a wallet vow. The
    register becomes a directory: what the agent offers, WITH its live
    conduct record attached. Listed alphabetically, never ranked — the
    trajectory speaks; we don't."""
    try:
        vow = _load_vow(req.vow_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad vow_id"})
    if not vow:
        return JSONResponse(status_code=404, content={"error": "no such vow"})
    if vow["sandbox"]:
        return JSONResponse(status_code=422, content={
            "error": "listings need a wallet-signed vow — a service ad with no "
                     "accountable identity is just spam"})
    services = req.services.strip()[:500]
    if not services:
        return JSONResponse(status_code=422, content={"error": "services text required"})
    from playauth import verify_play
    err = verify_play(vow, "listing",
                      hashlib.sha256(services.encode()).hexdigest(), req.signature)
    if err:
        return JSONResponse(status_code=401, content={"error": err})
    vow["listing"] = {"services": services,
                      "endpoint": (req.endpoint or "").strip()[:200] or None,
                      "updated_at": _now()}
    _save_vow(vow)
    return JSONResponse(content={
        "vow_id": req.vow_id, **vow["listing"],
        "directory": "GET /vows?listed=1 — alphabetical, never ranked",
        "note": "your listing ships WITH your live ledger — that's the point"})


# ── on-chain anchoring surface (reads what anchor_worker.py writes) ──────────
def _last_anchor() -> dict | None:
    p = VOWS_DIR / "anchors.jsonl"
    if not p.exists():
        return None
    lines = [ln for ln in p.read_text().splitlines() if ln.strip()]
    return json.loads(lines[-1]) if lines else None


@router.get("/anchors")
async def anchors() -> JSONResponse:
    """Every anchor ever posted (root, vow count, tx, block). The on-chain
    contract's Anchored events are the authoritative copy; this is the mirror."""
    p = VOWS_DIR / "anchors.jsonl"
    entries = ([json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]
               if p.exists() else [])
    return JSONResponse(content={"n": len(entries), "anchors": entries[-100:],
                                 "contract": os.getenv("SCRY_ANCHOR_CONTRACT") or None})


@router.get("/vow/{vow_id}/proof")
async def vow_proof(vow_id: str) -> JSONResponse:
    """Merkle inclusion proof for this vow's chain head under the most recent
    anchor. Verify client-side (sorted-pair keccak256) or on-chain via
    ScryVowRegistry.verifyProof — either way, you don't have to trust us."""
    try:
        vow = _load_vow(vow_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad vow_id"})
    if not vow:
        return JSONResponse(status_code=404, content={"error": "no such vow"})
    anchor = _last_anchor()
    if not anchor:
        return JSONResponse(status_code=404, content={
            "error": "no anchor posted yet — the chain is tamper-evident (hash-linked, "
                     "signed) but not yet anchored on-chain"})
    leaves_file = VOWS_DIR / "anchor_leaves" / anchor["leaves_file"]
    if not leaves_file.exists():
        return JSONResponse(status_code=500, content={"error": "anchor leaf-set missing"})
    from anchor_worker import leaf_for, merkle_proof  # local module, no cycle at import time
    leafset = json.loads(leaves_file.read_text())
    mine = next((h for h in leafset["leaves"] if h["vow_id"] == vow_id), None)
    if mine is None:
        return JSONResponse(status_code=404, content={
            "error": "this vow was created after the last anchor — wait for the next cycle",
            "last_anchor_at": anchor["at"]})
    leaves = [leaf_for(h["vow_id"], h["chain_head"]) for h in leafset["leaves"]]
    target = leaf_for(mine["vow_id"], mine["chain_head"])
    proof = merkle_proof(leaves, target)
    return JSONResponse(content={
        "vow_id": vow_id,
        "anchored_chain_head": mine["chain_head"],
        "current_chain_head": vow.get("chain_head"),
        "head_unchanged_since_anchor": mine["chain_head"] == vow.get("chain_head"),
        "leaf": "0x" + target.hex(),
        "proof": ["0x" + p.hex() for p in proof],
        "root": anchor["root"],
        "anchor": {k: anchor.get(k) for k in ("at", "tx", "block", "vow_count", "dryrun")},
        "verify": ("sorted-pair keccak256 up the proof must equal root; or call "
                   "ScryVowRegistry.verifyProof(proof, root, leaf) on Robinhood Chain"),
    })
