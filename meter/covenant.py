"""The Covenant — a fleet swears ONE oath, one wallet at a time, in the open.

The oldest collective-oath shape (Bois Caïman, the loyalty oaths, the ark of
the covenant) unbundled from the game and handed to any operator running a
fleet of agents. One vow text, N wallets: the operator opens a covenant once,
and every agent swears to that same text with its own wallet. Each member gets
its own individual, hash-chained drift ledger (a first-class scry vow — swearing
to a covenant IS taking its oath, signed the identical way), and the covenant
adds the shared text, the roster (who swore beside whom, in order), and the
cohort view.

Renouncing is a recorded act, not a deletion. A member that walks away keeps
its seq and its history; renounced_at + reason are stamped in the clear.
Breaking a covenant is the oldest tell in the record — here it is public.

Guards (inherited from the vow oracle, non-negotiable):
  - No verdicts. The cohort view shows the record; the reading is the meter's,
    separately signed. This module never says who kept faith.
  - No stake, no slashing. Measuring and enforcing must never be one party.
  - Public by design. A covenant is inherently a collective, visible oath —
    there is no sealed covenant (seal a solo vow if you need privacy). The whole
    value is that everyone can see the fleet's moves in the open.
"""
import os
import re
import time
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

import vows  # reuse the vow machinery — never fork the record or the math

COV_DIR = Path(os.getenv("SCRY_COVENANT_DIR",
                         str(Path(__file__).resolve().parent / "covenant_data")))
COV_CREATE_DAILY_LIMIT = int(os.getenv("SCRY_COVENANT_CREATE_LIMIT", "10"))
COV_OATH_MAX = 2000
COV_LABEL_MAX = 128
RENOUNCE_REASON_MAX = 512

router = APIRouter()
_deps: dict = {}


def init(*, sign_fn, pubkey_b64, issuer):
    """server.py hands us the meter's signing plumbing (same key, same issuer).
    The vow helpers we reuse are imported directly from `vows`."""
    _deps.update(sign_fn=sign_fn, pubkey_b64=pubkey_b64, issuer=issuer)
    COV_DIR.mkdir(parents=True, exist_ok=True)


COV_SCOPE = {
    "public_by_design": (
        "A covenant is a collective oath: the oath text, the cadence, and every "
        "member wallet + sworn/renounced timestamp are public forever. That is "
        "what makes a fleet's shared commitment checkable by anyone. There are "
        "no sealed covenants — seal a solo vow if you need privacy."),
    "one_text_n_wallets": (
        "Every member swears the IDENTICAL text. A member's oath is a first-class "
        "scry vow (its own hash-chained ledger, mark, and stele); the covenant "
        "links them and shows the cohort. Swearing signs the same message you "
        "would sign to take that vow solo."),
    "renounce_is_recorded": (
        "Renouncing does not erase you. Your seq and sworn_at stay; renounced_at "
        "and your stated reason are published. The breach is a fact on the record, "
        "not a phase — you cannot un-renounce or re-swear the same covenant."),
    "reading_not_verdict": (
        "The cohort view is the record, never a verdict. Whether a member kept "
        "faith is a reading — the meter's job, separately signed — and execution "
        "belongs to the local bound in each agent's harness."),
}


# ── storage ──────────────────────────────────────────────────────────────────
def _cov_path(cid: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{16}", cid):
        raise ValueError("bad covenant_id")
    return COV_DIR / f"{cid}.json"


def _load_cov(cid: str) -> dict | None:
    p = _cov_path(cid)
    return vows.json.loads(p.read_text()) if p.exists() else None


def _save_cov(rec: dict) -> None:
    _cov_path(rec["covenant_id"]).write_text(vows.json.dumps(rec, indent=1))


def _member(rec: dict, wallet: str) -> dict | None:
    w = (wallet or "").lower()
    for m in rec["members"]:
        if (m.get("wallet") or "").lower() == w:
            return m
    return None


# ── signing messages (deterministic, re-derivable from the public record) ─────
def covenant_open_message(oath: str, agent: str, cadence_hours: int) -> str:
    return (f"scry covenant\nagent: {agent}\ncadence_hours: {cadence_hours}\n"
            f"oath: {oath}\nby signing, this wallet opens this covenant publicly.")


def covenant_renounce_message(cid: str, wallet: str, reason: str) -> str:
    return (f"scry covenant renounce\ncovenant: {cid}\nwallet: {wallet}\n"
            f"reason: {reason}\nby signing, this wallet publicly renounces this covenant.")


def _recover(msg: str, wallet: str, signature: str) -> str:
    from eth_account import Account
    from eth_account.messages import encode_defunct
    rec = Account.recover_message(encode_defunct(text=msg), signature=signature)
    if rec.lower() != (wallet or "").lower():
        raise ValueError(f"signature recovers {rec}, not {wallet}")
    return rec


_create_hits: dict[str, list] = {}


def _create_ok(ip: str) -> bool:
    day = int(time.time() // 86400)
    r = _create_hits.get(ip)
    if not r or r[0] != day:
        _create_hits[ip] = [day, 0]
        r = _create_hits[ip]
    if r[1] >= COV_CREATE_DAILY_LIMIT:
        return False
    r[1] += 1
    return True


# ── opening a covenant ────────────────────────────────────────────────────────
class OpenRequest(BaseModel):
    oath: str                       # the shared declared purpose — the Y sworn by all
    agent: str                      # the covenant's name / the fleet handle
    label: str | None = None        # short explorer headline (defaults from agent)
    cadence_hours: int = 24
    wallet: str | None = None       # opener wallet (0x…) — omit for sandbox
    signature: str | None = None    # EIP-191 over covenant_open_message


@router.get("/covenant/message")
async def open_message(oath: str, agent: str, cadence_hours: int = 24) -> dict:
    return {"sign_this": covenant_open_message(oath, agent, cadence_hours),
            "then": "POST /covenant with wallet + signature to open it"}


@router.post("/covenant")
async def open_covenant(req: OpenRequest, request: Request) -> JSONResponse:
    ip = (request.headers.get("x-forwarded-for", "") or request.client.host or "?").split(",")[0].strip()
    if not _create_ok(ip):
        return JSONResponse(status_code=429, content={
            "error": f"covenant-creation limit {COV_CREATE_DAILY_LIMIT}/day/IP — the register is forever",
            "scope": COV_SCOPE})
    oath = req.oath.strip()
    if not oath or len(oath) > COV_OATH_MAX:
        return JSONResponse(status_code=422, content={
            "error": f"oath must be 1..{COV_OATH_MAX} chars", "scope": COV_SCOPE})
    if not (vows.VOW_MIN_CADENCE_H <= req.cadence_hours <= vows.VOW_MAX_CADENCE_H):
        return JSONResponse(status_code=422, content={
            "error": f"cadence_hours must be {vows.VOW_MIN_CADENCE_H}..{vows.VOW_MAX_CADENCE_H}",
            "scope": COV_SCOPE})

    sandbox, wallet = True, None
    if req.wallet and req.signature:
        try:
            wallet = _recover(covenant_open_message(oath, req.agent, req.cadence_hours),
                              req.wallet, req.signature)
        except Exception as e:  # noqa: BLE001
            return JSONResponse(status_code=422, content={
                "error": f"signature check failed: {e}", "scope": COV_SCOPE})
        sandbox = False

    body = {"oath": oath, "agent": req.agent.strip()[:120],
            "cadence_hours": req.cadence_hours, "opener_wallet": wallet,
            "created_at": vows._now()}
    cid = vows._sha(vows._canon(body))[:16]
    if _load_cov(cid):
        return JSONResponse(status_code=409, content={
            "error": "identical covenant already exists", "covenant_id": cid, "scope": COV_SCOPE})

    rec = {"covenant_id": cid, "covenant": body,
           "label": (req.label or f"{req.agent.strip()[:80]} — covenant"),
           "oath_sha256": vows._sha(oath), "sandbox": sandbox,
           "issuer": _deps["issuer"], "attestation_pubkey_b64": _deps["pubkey_b64"],
           "members": []}
    rec["countersig"] = _deps["sign_fn"](vows._canon(rec))
    _save_cov(rec)
    return JSONResponse(content={
        "covenant_id": cid, "oath": oath, "oath_sha256": rec["oath_sha256"],
        "label": rec["label"], "cadence_hours": req.cadence_hours, "sandbox": sandbox,
        "swear": f"GET /covenant/message?oath=…  then  POST /covenant/{cid}/swear "
                 "{wallet, signature, agent}",
        "cohort": f"GET /covenant/{cid}",
        "on_chain": "ScryCovenant.open(covenantId, sha256(oath), cadenceHours, label, oath) "
                    "— the full oath text lands in the explorer's event log",
        "scope": COV_SCOPE})


# ── swearing to a covenant (creates the member's first-class vow) ─────────────
class SwearRequest(BaseModel):
    wallet: str | None = None
    signature: str | None = None
    agent: str | None = None        # the member agent's own handle


@router.post("/covenant/{cid}/swear")
async def swear(cid: str, req: SwearRequest, request: Request) -> JSONResponse:
    try:
        cov = _load_cov(cid)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad covenant_id"})
    if not cov:
        return JSONResponse(status_code=404, content={"error": "no such covenant", "scope": COV_SCOPE})

    oath = cov["covenant"]["oath"]
    cadence = cov["covenant"]["cadence_hours"]
    agent = (req.agent or "").strip()[:120] or (req.wallet or "member")[:120]

    sandbox, wallet, wallet_sig = True, None, None
    if req.wallet and req.signature:
        try:  # a member signs the SAME message they'd sign to take this oath solo
            wallet = _recover(vows.vow_signing_message(oath, agent, cadence),
                              req.wallet, req.signature)
        except Exception as e:  # noqa: BLE001
            return JSONResponse(status_code=422, content={
                "error": f"signature check failed: {e}", "scope": COV_SCOPE})
        sandbox, wallet_sig = False, req.signature
        if _member(cov, wallet):
            return JSONResponse(status_code=409, content={
                "error": "this wallet already swore to this covenant", "scope": COV_SCOPE})

    # Build the member's individual vow — a first-class scry vow, linked back to
    # the covenant. Same record shape and same countersig discipline as vows.take_vow.
    vow_body = {"text": oath, "agent": agent, "cadence_hours": cadence,
                "wallet": wallet, "created_at": vows._now(), "covenant_id": cid}
    vow_id = vows._sha(vows._canon(vow_body))[:16]
    if vows._load_vow(vow_id):
        return JSONResponse(status_code=409, content={
            "error": "identical member vow already exists", "vow_id": vow_id, "scope": COV_SCOPE})
    vrec = {"vow_id": vow_id, "vow": vow_body, "wallet_sig": wallet_sig,
            "sandbox": sandbox, "sealed": False, "issuer": _deps["issuer"],
            "attestation_pubkey_b64": _deps["pubkey_b64"], "seq": 0, "chain_head": None}
    vrec["countersig"] = _deps["sign_fn"](vows._canon(vrec))
    vows._save_vow(vrec)

    seq = len(cov["members"]) + 1
    cov["members"].append({"seq": seq, "vow_id": vow_id, "agent": agent,
                           "wallet": wallet, "sandbox": sandbox, "sworn_at": vows._now(),
                           "renounced_at": None, "renounce_reason": None})
    _save_cov(cov)
    return JSONResponse(content={
        "covenant_id": cid, "seq": seq, "vow_id": vow_id, "sandbox": sandbox,
        "ledger": f"GET /vow/{vow_id}", "stele": f"GET /vow/{vow_id}/stele.svg",
        "report_in": f"POST /vow/report {{vow_id: {vow_id!r}, turns, context_key}} — the member's own ritual",
        "cohort": f"GET /covenant/{cid}", "scope": COV_SCOPE})


# ── renouncing (a recorded public breach) ─────────────────────────────────────
class RenounceRequest(BaseModel):
    wallet: str
    signature: str
    reason: str = ""


@router.post("/covenant/{cid}/renounce")
async def renounce(cid: str, req: RenounceRequest) -> JSONResponse:
    try:
        cov = _load_cov(cid)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad covenant_id"})
    if not cov:
        return JSONResponse(status_code=404, content={"error": "no such covenant", "scope": COV_SCOPE})
    reason = (req.reason or "").strip()[:RENOUNCE_REASON_MAX]
    try:
        _recover(covenant_renounce_message(cid, req.wallet, reason), req.wallet, req.signature)
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=422, content={
            "error": f"signature check failed: {e}", "scope": COV_SCOPE})
    m = _member(cov, req.wallet)
    if not m or m.get("sandbox"):
        return JSONResponse(status_code=404, content={
            "error": "no signed membership for this wallet in this covenant", "scope": COV_SCOPE})
    if m["renounced_at"]:
        return JSONResponse(status_code=409, content={
            "error": "already renounced — the breach is a fact, not a phase", "scope": COV_SCOPE})
    m["renounced_at"] = vows._now()
    m["renounce_reason"] = reason or "(no reason given)"
    _save_cov(cov)
    return JSONResponse(content={
        "covenant_id": cid, "seq": m["seq"], "renounced_at": m["renounced_at"],
        "reason": m["renounce_reason"], "note": "you remain on the historical roster; "
        "your vow ledger stays. renouncing is recorded, never erased.",
        "on_chain": f"ScryCovenant.renounce(covenantId, {reason!r})", "scope": COV_SCOPE})


# ── the cohort view (who swore beside whom, and how they are holding) ─────────
def _member_public(m: dict) -> dict:
    row = {"seq": m["seq"], "agent": m["agent"], "wallet": m.get("wallet"),
           "sandbox": m.get("sandbox", True), "vow_id": m["vow_id"],
           "sworn_at": m["sworn_at"], "renounced_at": m.get("renounced_at"),
           "renounce_reason": m.get("renounce_reason"),
           "ledger": f"/vow/{m['vow_id']}", "stele": f"/vow/{m['vow_id']}/stele.svg"}
    try:
        vow = vows._load_vow(m["vow_id"])
        entries = vows._chain_entries(m["vow_id"])
        st = vows.trajectory_stats(vow, entries) if vow else {}
        icm = st.get("coupling_ICM_series") or []
        row["n_reports"] = st.get("n_reports", 0)
        row["missed_windows"] = st.get("missed_windows")
        row["overdue"] = st.get("overdue")
        row["last_coupling_ICM"] = icm[-1] if icm else None
    except Exception:  # noqa: BLE001 — the cohort view must never fail on one bad member
        pass
    return row


@router.get("/covenant/{cid}")
async def cohort(cid: str) -> JSONResponse:
    try:
        cov = _load_cov(cid)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad covenant_id"})
    if not cov:
        return JSONResponse(status_code=404, content={"error": "no such covenant", "scope": COV_SCOPE})
    rows = [_member_public(m) for m in cov["members"]]
    active = [r for r in rows if not r["renounced_at"]]
    couplings = [r["last_coupling_ICM"] for r in active if r.get("last_coupling_ICM") is not None]
    return JSONResponse(content={
        "covenant_id": cid, "label": cov["label"], "oath": cov["covenant"]["oath"],
        "oath_sha256": cov["oath_sha256"], "cadence_hours": cov["covenant"]["cadence_hours"],
        "opener_wallet": cov["covenant"]["opener_wallet"], "sandbox": cov["sandbox"],
        "created_at": cov["covenant"]["created_at"],
        "cohort": {
            "n_members": len(rows), "n_active": len(active),
            "n_renounced": len(rows) - len(active),
            "n_overdue": sum(1 for r in active if r.get("overdue")),
            "mean_coupling_ICM_active": (round(sum(couplings) / len(couplings), 4) if couplings else None),
        },
        "members": rows, "card": f"/covenant/{cid}/cohort.svg", "scope": COV_SCOPE})


@router.get("/covenants")
async def list_covenants() -> dict:
    out = []
    for p in sorted(COV_DIR.glob("*.json")):
        try:
            cov = vows.json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            continue
        n = len(cov["members"])
        active = sum(1 for m in cov["members"] if not m.get("renounced_at"))
        out.append({"covenant_id": cov["covenant_id"], "label": cov["label"],
                    "oath_preview": cov["covenant"]["oath"][:120],
                    "cadence_hours": cov["covenant"]["cadence_hours"],
                    "n_members": n, "n_active": active, "n_renounced": n - active,
                    "created_at": cov["covenant"]["created_at"],
                    "cohort": f"/covenant/{cov['covenant_id']}"})
    out.sort(key=lambda r: r["created_at"], reverse=True)
    return {"covenants": out, "n": len(out), "scope": COV_SCOPE}


@router.get("/covenant/{cid}/cohort.svg")
async def cohort_svg(cid: str):
    """The fleet as a ring of marks — active members bright, renounced ones
    dimmed but still present (the record does not erase them). A single glance,
    readable by anyone, at who swore this oath and who walked."""
    try:
        cov = _load_cov(cid)
    except ValueError:
        return Response(content="bad covenant_id", status_code=422)
    if not cov:
        return Response(content="no such covenant", status_code=404)
    members = cov["members"]
    W = 420
    cx = cy = W / 2
    ring = 150
    n = max(1, len(members))
    marks = []
    for i, m in enumerate(members):
        ang = (2 * 3.14159265 * i / n) - 3.14159265 / 2
        mx = cx + ring * _cos(ang)
        my = cy + ring * _sin(ang)
        renounced = bool(m.get("renounced_at"))
        g = vows._mark_group(m["vow_id"], mx, my, 0.42)
        op = "0.28" if renounced else "1"
        marks.append(f'<g opacity="{op}">{g}</g>')
        if renounced:
            marks.append(f'<line x1="{mx-11:.0f}" y1="{my-11:.0f}" x2="{mx+11:.0f}" '
                         f'y2="{my+11:.0f}" stroke="#b1364a" stroke-width="2"/>')
    active = sum(1 for m in members if not m.get("renounced_at"))
    label = cov["label"][:40]
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {W}">'
        f'<rect width="{W}" height="{W}" fill="#150e28"/>'
        f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{ring}" fill="none" stroke="#3a2d55" stroke-width="1"/>'
        f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="9" fill="#f4b942"/>'
        f'<text x="{cx:.0f}" y="{cy-4:.0f}" text-anchor="middle" fill="#f4efe4" '
        f'font-family="monospace" font-size="15">{_esc(label)}</text>'
        f'<text x="{cx:.0f}" y="{cy+16:.0f}" text-anchor="middle" fill="#b9b0cc" '
        f'font-family="monospace" font-size="12">{active}/{len(members)} keeping faith</text>'
        f'{"".join(marks)}'
        f'<text x="{cx:.0f}" y="{W-16:.0f}" text-anchor="middle" fill="#6a5f85" '
        f'font-family="monospace" font-size="11">scry covenant · {cid} · one oath, {len(members)} sworn</text>'
        f'</svg>')
    return Response(content=svg, media_type="image/svg+xml")


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# tiny trig (no numpy dependency in the meter)
def _cos(x: float) -> float:
    import math
    return math.cos(x)


def _sin(x: float) -> float:
    import math
    return math.sin(x)
