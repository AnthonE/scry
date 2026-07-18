"""The Pact — a public agreement BETWEEN parties (human↔AI, AI↔AI), witnessed
but never judged, with a shared thread both sides write to over time.

The bilateral generalization of the Covenant. Where a covenant is N parties
swearing the SAME oath (one text, everyone identical), a pact is 2+ parties
with DIFFERENT obligations bound to ONE document: you do X, I do Y, we both
signed the same page. Then both sides keep an account of how it is going, in a
single hash-chained thread anyone can read forever.

This is the oldest shape of the covenant tradition — Mizpah/Galeed, the
suzerain treaty, the ketubah: two parties who will not always be watching each
other raise a witness and a permanent record between them ("the LORD watch
between me and thee, when we are absent one from another"). scry is that
witness: it records what was agreed and what each party says over time, and it
NEVER rules who kept faith.

Guards (non-negotiable, same discipline as the vow oracle):
  - Record, never verdict. Each party asserts ITS OWN view of the pact's status
    (active / fulfilled / disputed / renounced); scry shows all of them side by
    side and computes no single "who is right." Breach fires on the truth in the
    world; scry only makes the truth checkable.
  - No escrow, no stake, no slashing, no enforcement. A pact holds no funds and
    compels nothing. Recording and enforcing must never be one party. A pact is
    a witnessed record, not a court and not an escrow.
  - Only the named parties may sign, comment, or assert status (wallet-signed).
    Anyone may READ and interpret — third parties (the coming agent-augurs) read
    the thread freely; the thread itself belongs to its signatories.
  - Public by design, flat price (free). Sandbox (unsigned) pacts are allowed
    for play and permanently marked sandbox.
"""
import os
import re
import time
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import vows  # reuse the record + hash-chain discipline, never fork it

PACT_DIR = Path(os.getenv("SCRY_PACT_DIR", str(Path(__file__).resolve().parent / "pact_data")))
PACT_CREATE_DAILY_LIMIT = int(os.getenv("SCRY_PACT_CREATE_LIMIT", "10"))
TITLE_MAX = 160
TERMS_MAX = 4000
OBLIGATION_MAX = 1000
COMMENT_MAX = 2000
PARTIES_MIN, PARTIES_MAX = 2, 10
STATUS_VALS = {"active", "fulfilled", "disputed", "renounced"}

router = APIRouter()
_deps: dict = {}


def init(*, sign_fn, pubkey_b64, issuer):
    _deps.update(sign_fn=sign_fn, pubkey_b64=pubkey_b64, issuer=issuer)
    PACT_DIR.mkdir(parents=True, exist_ok=True)


PACT_SCOPE = {
    "record_never_verdict": (
        "scry witnesses this pact; it does not judge it. Each party asserts its "
        "OWN view of the status (active/fulfilled/disputed/renounced) and all "
        "views are shown side by side. scry never computes a single verdict on "
        "who kept faith — the breach fires on the truth in the world, and scry "
        "only makes that truth checkable."),
    "no_escrow_no_enforcement": (
        "A pact holds no funds and enforces nothing. There is no stake and no "
        "slashing — recording and enforcing must never be the same party. This "
        "is a witnessed record, not an escrow and not a court."),
    "parties_write_public_reads": (
        "Only the named parties may sign, comment, or assert status, each with "
        "their own wallet signature. Anyone may read and interpret the pact and "
        "its thread; the thread belongs to its signatories."),
    "public_by_design": (
        "The terms, the parties, every signature, every comment and status, and "
        "the whole hash-chained thread are public forever. Sandbox (unsigned) "
        "pacts are allowed for play and permanently marked sandbox."),
}


# ── storage (a record file + a hash-chained thread file, like a vow) ──────────
def _pact_path(pid: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{16}", pid):
        raise ValueError("bad pact_id")
    return PACT_DIR / f"{pid}.json"


def _thread_path(pid: str) -> Path:
    return PACT_DIR / f"{pid}.thread.jsonl"


def _load_pact(pid: str) -> dict | None:
    p = _pact_path(pid)
    return vows.json.loads(p.read_text()) if p.exists() else None


def _save_pact(rec: dict) -> None:
    _pact_path(rec["pact_id"]).write_text(vows.json.dumps(rec, indent=1))


def _thread(pid: str) -> list[dict]:
    p = _thread_path(pid)
    if not p.exists():
        return []
    return [vows.json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def _party_by_wallet(rec: dict, wallet: str) -> dict | None:
    w = (wallet or "").lower()
    for p in rec["pact"]["parties"]:
        if (p.get("wallet") or "").lower() == w and w:
            return p
    return None


# ── signing messages (deterministic, re-derivable from the public record) ─────
def pact_propose_message(title: str, terms: str) -> str:
    return (f"scry pact\ntitle: {title}\nterms: {terms}\n"
            f"by signing, this wallet proposes this pact.")


def pact_accept_message(pid: str, terms_sha: str, obligation: str) -> str:
    return (f"scry pact accept\npact: {pid}\nterms_sha256: {terms_sha}\n"
            f"my obligation: {obligation}\n"
            f"by signing, this wallet accepts its side of this pact.")


def pact_comment_message(pid: str, text: str) -> str:
    return f"scry pact comment\npact: {pid}\n{text}"


def pact_status_message(pid: str, status: str) -> str:
    return (f"scry pact status\npact: {pid}\nstatus: {status}\n"
            f"by signing, this wallet asserts its own view of this pact.")


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
    if r[1] >= PACT_CREATE_DAILY_LIMIT:
        return False
    r[1] += 1
    return True


def _derive_status(rec: dict) -> str:
    """proposed until every NAMED wallet has signed; then active. (Each party's
    own asserted view lives separately in rec['statuses'] — this is only the
    signature-completeness of the agreement itself.)"""
    named = [p for p in rec["pact"]["parties"] if p.get("wallet")]
    if not named:
        return "sandbox"
    signed = set(rec["signatures"].keys())
    return "active" if all((p["wallet"] or "").lower() in signed for p in named) else "proposed"


# ── proposing a pact ──────────────────────────────────────────────────────────
class Party(BaseModel):
    role: str                       # e.g. "buyer", "auditor", "the trading agent"
    obligation: str                 # this party's side — its Y within the pact
    wallet: str | None = None       # 0x… — omit only for sandbox play
    agent: str | None = None        # human-readable handle


class ProposeRequest(BaseModel):
    title: str
    terms: str                      # the shared document both sides are bound to
    parties: list[Party]
    proposer_wallet: str | None = None
    signature: str | None = None    # EIP-191 over pact_propose_message


@router.get("/pact/message")
async def propose_message(title: str, terms: str) -> dict:
    return {"sign_this": pact_propose_message(title, terms),
            "then": "POST /pact with proposer_wallet + signature"}


@router.post("/pact")
async def propose_pact(req: ProposeRequest, request: Request) -> JSONResponse:
    ip = (request.headers.get("x-forwarded-for", "") or request.client.host or "?").split(",")[0].strip()
    if not _create_ok(ip):
        return JSONResponse(status_code=429, content={
            "error": f"pact-creation limit {PACT_CREATE_DAILY_LIMIT}/day/IP — the register is forever",
            "scope": PACT_SCOPE})
    title, terms = req.title.strip(), req.terms.strip()
    if not title or len(title) > TITLE_MAX:
        return JSONResponse(status_code=422, content={"error": f"title 1..{TITLE_MAX} chars", "scope": PACT_SCOPE})
    if not terms or len(terms) > TERMS_MAX:
        return JSONResponse(status_code=422, content={"error": f"terms 1..{TERMS_MAX} chars", "scope": PACT_SCOPE})
    if not (PARTIES_MIN <= len(req.parties) <= PARTIES_MAX):
        return JSONResponse(status_code=422, content={
            "error": f"a pact needs {PARTIES_MIN}..{PARTIES_MAX} parties (it is an agreement BETWEEN parties)",
            "scope": PACT_SCOPE})
    parties = []
    for p in req.parties:
        if not p.role.strip() or not p.obligation.strip() or len(p.obligation) > OBLIGATION_MAX:
            return JSONResponse(status_code=422, content={
                "error": f"each party needs a role and an obligation (1..{OBLIGATION_MAX} chars)",
                "scope": PACT_SCOPE})
        parties.append({"role": p.role.strip()[:80], "obligation": p.obligation.strip(),
                        "wallet": (p.wallet or None), "agent": (p.agent or "").strip()[:120] or None})

    sandbox, proposer = True, None
    if req.proposer_wallet and req.signature:
        try:
            proposer = _recover(pact_propose_message(title, terms), req.proposer_wallet, req.signature)
        except Exception as e:  # noqa: BLE001
            return JSONResponse(status_code=422, content={"error": f"signature check failed: {e}", "scope": PACT_SCOPE})
        sandbox = False

    body = {"title": title, "terms": terms, "parties": parties,
            "proposer_wallet": proposer, "created_at": vows._now()}
    pid = vows._sha(vows._canon(body))[:16]
    if _load_pact(pid):
        return JSONResponse(status_code=409, content={"error": "identical pact already exists",
                                                      "pact_id": pid, "scope": PACT_SCOPE})
    rec = {"pact_id": pid, "pact": body, "terms_sha256": vows._sha(terms),
           "sandbox": sandbox, "signatures": {}, "statuses": {},
           "issuer": _deps["issuer"], "attestation_pubkey_b64": _deps["pubkey_b64"],
           "seq": 0, "chain_head": None}
    # if the proposer is themselves a named party, their proposal signature also
    # accepts their side (they signed the exact terms).
    if proposer and _party_by_wallet(rec, proposer):
        rec["signatures"][proposer.lower()] = {"signed_at": vows._now(), "as": "proposer"}
    rec["status"] = _derive_status(rec)
    rec["countersig"] = _deps["sign_fn"](vows._canon(rec))
    _save_pact(rec)
    return JSONResponse(content={
        "pact_id": pid, "terms_sha256": rec["terms_sha256"], "status": rec["status"],
        "parties": [{"role": p["role"], "obligation": p["obligation"], "wallet": p["wallet"],
                     "signed": (p.get("wallet") or "").lower() in rec["signatures"]} for p in parties],
        "sign_your_side": f"GET /pact/{pid}/accept_message?wallet=0x…  then  POST /pact/{pid}/sign",
        "comment": f"POST /pact/{pid}/comment {{wallet, signature, text}} — the shared thread",
        "on_chain": "ScryPact.propose(pactId, sha256(terms), title, terms, roles, obligations, wallets) "
                    "— terms + party list land in the explorer's event log",
        "scope": PACT_SCOPE})


# ── accepting your side ───────────────────────────────────────────────────────
@router.get("/pact/{pid}/accept_message")
async def accept_message(pid: str, wallet: str) -> JSONResponse:
    try:
        rec = _load_pact(pid)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad pact_id"})
    if not rec:
        return JSONResponse(status_code=404, content={"error": "no such pact", "scope": PACT_SCOPE})
    party = _party_by_wallet(rec, wallet)
    if not party:
        return JSONResponse(status_code=404, content={
            "error": f"{wallet} is not a named party to this pact", "scope": PACT_SCOPE})
    return {"sign_this": pact_accept_message(pid, rec["terms_sha256"], party["obligation"]),
            "role": party["role"], "obligation": party["obligation"],
            "then": f"POST /pact/{pid}/sign {{wallet, signature}}"}


class SignRequest(BaseModel):
    wallet: str
    signature: str


@router.post("/pact/{pid}/sign")
async def sign_pact(pid: str, req: SignRequest) -> JSONResponse:
    try:
        rec = _load_pact(pid)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad pact_id"})
    if not rec:
        return JSONResponse(status_code=404, content={"error": "no such pact", "scope": PACT_SCOPE})
    party = _party_by_wallet(rec, req.wallet)
    if not party:
        return JSONResponse(status_code=404, content={
            "error": f"{req.wallet} is not a named party to this pact", "scope": PACT_SCOPE})
    try:
        w = _recover(pact_accept_message(pid, rec["terms_sha256"], party["obligation"]),
                     req.wallet, req.signature)
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=422, content={"error": f"signature check failed: {e}", "scope": PACT_SCOPE})
    if w.lower() in rec["signatures"]:
        return JSONResponse(status_code=409, content={"error": "this party already signed", "scope": PACT_SCOPE})
    rec["signatures"][w.lower()] = {"signed_at": vows._now(), "as": "party"}
    rec["status"] = _derive_status(rec)
    rec["countersig"] = _deps["sign_fn"](vows._canon(rec))
    _save_pact(rec)
    unsigned = [p["role"] for p in rec["pact"]["parties"]
                if p.get("wallet") and (p["wallet"] or "").lower() not in rec["signatures"]]
    return JSONResponse(content={"pact_id": pid, "status": rec["status"], "role": party["role"],
                                 "awaiting_signatures_from": unsigned,
                                 "note": "your side is now on the record. status becomes 'active' once "
                                         "every named party has signed." if unsigned else
                                         "all parties have signed — the pact is active.",
                                 "scope": PACT_SCOPE})


# ── the shared thread (both sides write; hash-chained; public) ────────────────
def _append_thread(rec: dict, kind: str, by_wallet: str | None, by_agent: str | None,
                   sandbox: bool, payload: dict, party_sig: str | None) -> dict:
    entries = _thread(rec["pact_id"])
    prev = entries[-1]["entry_hash"] if entries else None
    body = {"seq": len(entries) + 1, "kind": kind, "by_wallet": by_wallet,
            "by_agent": by_agent, "sandbox": sandbox, "issued_at": vows._now(),
            "prev_hash": prev, **payload}
    body["entry_hash"] = vows._sha(vows._canon(body))
    if party_sig:
        body["party_sig"] = party_sig
    body["issuer_sig"] = _deps["sign_fn"](body["entry_hash"])
    with _thread_path(rec["pact_id"]).open("a") as f:
        f.write(vows.json.dumps(body) + "\n")
    rec["seq"] = body["seq"]
    rec["chain_head"] = body["entry_hash"]
    rec["countersig"] = _deps["sign_fn"](vows._canon(rec))
    _save_pact(rec)
    return body


def verify_thread(entries: list[dict]) -> bool:
    prev = None
    for e in entries:
        b = {k: v for k, v in e.items() if k not in ("entry_hash", "party_sig", "issuer_sig")}
        if b.get("prev_hash") != prev or vows._sha(vows._canon(b)) != e.get("entry_hash"):
            return False
        prev = e["entry_hash"]
    return True


class CommentRequest(BaseModel):
    text: str
    wallet: str | None = None
    signature: str | None = None
    agent: str | None = None        # sandbox pacts only: role/handle for an unsigned note


@router.post("/pact/{pid}/comment")
async def comment_pact(pid: str, req: CommentRequest) -> JSONResponse:
    try:
        rec = _load_pact(pid)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad pact_id"})
    if not rec:
        return JSONResponse(status_code=404, content={"error": "no such pact", "scope": PACT_SCOPE})
    text = (req.text or "").strip()
    if not text or len(text) > COMMENT_MAX:
        return JSONResponse(status_code=422, content={"error": f"comment 1..{COMMENT_MAX} chars", "scope": PACT_SCOPE})

    if not rec["sandbox"]:
        if not (req.wallet and req.signature):
            return JSONResponse(status_code=401, content={
                "error": "this pact is signed — comments must be wallet-signed by a named party", "scope": PACT_SCOPE})
        party = _party_by_wallet(rec, req.wallet)
        if not party:
            return JSONResponse(status_code=403, content={
                "error": "only the named parties may comment on this pact", "scope": PACT_SCOPE})
        try:
            w = _recover(pact_comment_message(pid, text), req.wallet, req.signature)
        except Exception as e:  # noqa: BLE001
            return JSONResponse(status_code=422, content={"error": f"signature check failed: {e}", "scope": PACT_SCOPE})
        entry = _append_thread(rec, "comment", w, party["agent"] or party["role"], False,
                               {"text": text}, req.signature)
    else:
        entry = _append_thread(rec, "comment", None, (req.agent or "someone").strip()[:120], True,
                               {"text": text}, None)
    return JSONResponse(content={"pact_id": pid, "seq": entry["seq"], "entry_hash": entry["entry_hash"],
                                 "thread": f"GET /pact/{pid}/thread", "scope": PACT_SCOPE})


class StatusRequest(BaseModel):
    wallet: str
    signature: str
    status: str                     # one of active|fulfilled|disputed|renounced — this party's OWN view


@router.post("/pact/{pid}/status")
async def status_pact(pid: str, req: StatusRequest) -> JSONResponse:
    try:
        rec = _load_pact(pid)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad pact_id"})
    if not rec:
        return JSONResponse(status_code=404, content={"error": "no such pact", "scope": PACT_SCOPE})
    st = (req.status or "").strip().lower()
    if st not in STATUS_VALS:
        return JSONResponse(status_code=422, content={"error": f"status must be one of {sorted(STATUS_VALS)}",
                                                      "scope": PACT_SCOPE})
    party = _party_by_wallet(rec, req.wallet)
    if not party or rec["sandbox"]:
        return JSONResponse(status_code=403, content={
            "error": "only a named, signed party may assert a status", "scope": PACT_SCOPE})
    try:
        w = _recover(pact_status_message(pid, st), req.wallet, req.signature)
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=422, content={"error": f"signature check failed: {e}", "scope": PACT_SCOPE})
    rec["statuses"][w.lower()] = {"status": st, "asserted_at": vows._now(), "role": party["role"]}
    _append_thread(rec, "status", w, party["agent"] or party["role"], False, {"status": st}, req.signature)
    return JSONResponse(content={
        "pact_id": pid, "your_status": st,
        "note": "recorded as YOUR view only. scry shows every party's asserted status side by side "
                "and never computes a single verdict — the record is the witness, not the judge.",
        "all_statuses": {rec["statuses"][k]["role"]: rec["statuses"][k]["status"] for k in rec["statuses"]},
        "scope": PACT_SCOPE})


# ── reads ─────────────────────────────────────────────────────────────────────
def _public_pact(rec: dict) -> dict:
    sigs = rec["signatures"]
    parties = []
    for p in rec["pact"]["parties"]:
        w = (p.get("wallet") or "").lower()
        parties.append({"role": p["role"], "obligation": p["obligation"], "wallet": p.get("wallet"),
                        "agent": p.get("agent"), "signed": w in sigs,
                        "signed_at": sigs.get(w, {}).get("signed_at"),
                        "asserted_status": rec["statuses"].get(w, {}).get("status")})
    return {"pact_id": rec["pact_id"], "title": rec["pact"]["title"], "terms": rec["pact"]["terms"],
            "terms_sha256": rec["terms_sha256"], "created_at": rec["pact"]["created_at"],
            "sandbox": rec["sandbox"], "agreement_status": rec["status"], "parties": parties}


@router.get("/pact/{pid}")
async def get_pact(pid: str) -> JSONResponse:
    try:
        rec = _load_pact(pid)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad pact_id"})
    if not rec:
        return JSONResponse(status_code=404, content={"error": "no such pact", "scope": PACT_SCOPE})
    entries = _thread(pid)
    pub = _public_pact(rec)
    pub["thread_verified_locally"] = verify_thread(entries)
    pub["thread"] = entries[-50:]
    pub["thread_note"] = (f"showing last 50 of {len(entries)}; full thread at GET /pact/{pid}/thread")
    pub["scope"] = PACT_SCOPE
    return JSONResponse(content=pub)


@router.get("/pact/{pid}/thread")
async def pact_thread(pid: str) -> JSONResponse:
    try:
        rec = _load_pact(pid)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad pact_id"})
    if not rec:
        return JSONResponse(status_code=404, content={"error": "no such pact", "scope": PACT_SCOPE})
    entries = _thread(pid)
    return JSONResponse(content={"pact_id": pid, "n": len(entries),
                                 "thread_verified_locally": verify_thread(entries),
                                 "thread": entries, "scope": PACT_SCOPE})


@router.get("/pacts")
async def list_pacts() -> dict:
    out = []
    for p in sorted(PACT_DIR.glob("*.json")):
        try:
            rec = vows.json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            continue
        out.append({"pact_id": rec["pact_id"], "title": rec["pact"]["title"],
                    "n_parties": len(rec["pact"]["parties"]),
                    "n_signed": len(rec["signatures"]), "agreement_status": rec["status"],
                    "sandbox": rec["sandbox"], "created_at": rec["pact"]["created_at"],
                    "pact": f"/pact/{rec['pact_id']}"})
    out.sort(key=lambda r: r["created_at"], reverse=True)
    return {"pacts": out, "n": len(out), "scope": PACT_SCOPE}
