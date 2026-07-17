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
VOW_MAX_TEXT = 2000
VOW_MIN_CADENCE_H = 1
VOW_MAX_CADENCE_H = 24 * 30

router = APIRouter()

# Injected by server.py at mount time (shared with the meter — same key, same
# math, same scope discipline).
_deps: dict = {}


def init(*, sign_fn, pubkey_b64, issuer, scope_card, build_turns, run_profile, canonical):
    """server.py hands us the meter's signing + scoring plumbing. We never
    duplicate the key handling or the math."""
    _deps.update(sign_fn=sign_fn, pubkey_b64=pubkey_b64, issuer=issuer,
                 scope_card=scope_card, build_turns=build_turns,
                 run_profile=run_profile, canonical=canonical)
    VOWS_DIR.mkdir(parents=True, exist_ok=True)


VOW_SCOPE = {
    "public_by_design": (
        "Vow text (unless sealed), agent name, and every chain entry's NUMBERS "
        "and HASHES are public forever — that is what makes the record checkable. "
        "Raw traces are NEVER stored or published unless you set donate_trace=true "
        "on a report-in (they are scored, hashed, and discarded). Sealed vows "
        "publish only sha256(text) — same price; the reading notes the seal."),
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


@router.post("/vow")
async def take_vow(req: VowRequest) -> JSONResponse:
    """Take a vow. Free. Signed (wallet) vows are first-class; unsigned vows
    are accepted but permanently marked sandbox — kids get to play, and the
    ledger stays honest about which is which."""
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


def _append_report(vow: dict, turns_raw: list[dict], context_key: str,
                   attested: bool, donate_trace: bool = False) -> dict:
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
        "issued_at": _now(),
        "issuer": _deps["issuer"],
        "attestation_pubkey_b64": _deps["pubkey_b64"],
    }
    entry["entry_hash"] = _sha(_canon(entry))
    entry["sig"] = _deps["sign_fn"](_canon(entry))
    with _chain_path(vow["vow_id"]).open("a") as f:
        f.write(_canon(entry) + "\n")
    if donate_trace:
        ddir = VOWS_DIR / "donations"
        ddir.mkdir(exist_ok=True)
        (ddir / f"{vow['vow_id']}.{entry['seq']}.json").write_text(
            _canon({"turns": turns_raw, "context_key": context_key,
                    "trace_sha256": trace_sha256, "donated_at": entry["issued_at"]}))
    vow["seq"] = entry["seq"]
    vow["chain_head"] = entry["entry_hash"]
    _save_vow(vow)
    return entry


@router.post("/vow/report")
async def vow_report(req: ReportRequest) -> JSONResponse:
    """Paid report-in — reached only AFTER x402 settle (server.py registers
    this path with the payment middleware). Flat price, same as /profile."""
    vow = _load_vow(req.vow_id)
    if not vow:
        return JSONResponse(status_code=404, content={"error": "no such vow", "scope": VOW_SCOPE})
    try:
        entry = _append_report(vow, req.turns, req.context_key, attested=True,
                               donate_trace=req.donate_trace)
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
                               donate_trace=req.donate_trace)
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
async def vow_index() -> JSONResponse:
    """Public index of every vow ever taken. The register."""
    out = []
    for p in sorted(VOWS_DIR.glob("*.json")):
        try:
            v = json.loads(p.read_text())
        except Exception:  # noqa: BLE001
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
                    "overdue": stats["overdue"]})
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
