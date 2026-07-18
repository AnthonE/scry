"""The Herald — push, not pull. Subscribe a webhook to any vow's public
record and get told when something happens: a new report-in, an overdue
transition (silence is signal — this is the pager for it), a coupling jump,
a fresh table breach. The watchtower shows; the Herald *interrupts*.

Anyone may subscribe to any vow — watching is the point, and the data is
public. Anti-abuse: the subscription only arms after a verification ping
(your endpoint must answer 2xx to a challenge), subscriptions are capped
per vow and per IP, and every notification is Ed25519-SIGNED by the meter
key — receivers can verify the herald's word the same way they verify an
attestation. The Herald never carries a verdict; it carries the event and
the numbers, and the ledger link to check them.
"""
import json
import os
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()
_deps: dict = {}

MAX_SUBS_PER_VOW = int(os.getenv("SCRY_HERALD_SUBS_PER_VOW", "10"))
SUBS_PER_IP_DAY = int(os.getenv("SCRY_HERALD_SUBS_PER_IP_DAY", "10"))
COUPLING_JUMP = float(os.getenv("SCRY_HERALD_COUPLING_JUMP", "0.1"))  # |ΔI(C;M)| bits
EVENTS = ("new_report", "overdue", "recovered", "coupling_jump", "breach")


def init(*, load_vow, chain_entries, trajectory_stats, vows_dir, sign_fn, issuer,
         post_fn=None):
    _deps.update(load_vow=load_vow, chain_entries=chain_entries,
                 trajectory_stats=trajectory_stats, sign_fn=sign_fn, issuer=issuer,
                 dir=Path(vows_dir) / "herald",
                 table_dir=Path(vows_dir) / "table",
                 post_fn=post_fn or (lambda url, payload:
                                     httpx.post(url, json=payload, timeout=10)))
    _deps["dir"].mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _subs_path() -> Path:
    return _deps["dir"] / "subs.json"


def _state_path() -> Path:
    return _deps["dir"] / "state.json"


def _load(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


class SubscribeRequest(BaseModel):
    vow_id: str
    url: str                       # your webhook endpoint (https)
    events: list[str] | None = None  # default: all


_ip_hits: dict[str, list] = {}


def _ip_ok(ip: str) -> bool:
    day = int(time.time() // 86400)
    rec = _ip_hits.get(ip)
    if not rec or rec[0] != day:
        _ip_hits[ip] = [day, 0]
        rec = _ip_hits[ip]
    if rec[1] >= SUBS_PER_IP_DAY:
        return False
    rec[1] += 1
    return True


@router.post("/herald")
async def herald_subscribe(req: SubscribeRequest, request: Request) -> JSONResponse:
    ip = (request.headers.get("x-forwarded-for", "") or request.client.host or "?").split(",")[0].strip()
    if not _ip_ok(ip):
        return JSONResponse(status_code=429, content={"error": f"subscribe limit {SUBS_PER_IP_DAY}/day/IP"})
    try:
        vow = _deps["load_vow"](req.vow_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad vow_id"})
    if not vow:
        return JSONResponse(status_code=404, content={"error": "no such vow"})
    if not req.url.startswith("https://") and not req.url.startswith("http://"):
        return JSONResponse(status_code=422, content={"error": "url must be http(s)"})
    events = req.events or list(EVENTS)
    if any(e not in EVENTS for e in events):
        return JSONResponse(status_code=422, content={"error": f"events must be from {EVENTS}"})
    subs = _load(_subs_path(), [])
    mine = [s for s in subs if s["vow_id"] == req.vow_id]
    if len(mine) >= MAX_SUBS_PER_VOW:
        return JSONResponse(status_code=429, content={"error": f"subscription cap {MAX_SUBS_PER_VOW}/vow"})
    if any(s["url"] == req.url and s["vow_id"] == req.vow_id for s in subs):
        return JSONResponse(status_code=409, content={"error": "already subscribed"})
    # verification ping — your endpoint must answer 2xx before the sub arms
    challenge = {"event": "herald_challenge", "vow_id": req.vow_id, "at": _now(),
                 "note": "answer 2xx to arm this subscription"}
    try:
        r = _deps["post_fn"](req.url, _signed(challenge))
        code = getattr(r, "status_code", 500)
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=422, content={"error": f"challenge delivery failed: {e}"})
    if not (200 <= code < 300):
        return JSONResponse(status_code=422, content={"error": f"challenge answered {code}, need 2xx"})
    sub = {"vow_id": req.vow_id, "url": req.url, "events": events,
           "created_at": _now(), "delivered": 0, "failures": 0}
    subs.append(sub)
    _subs_path().write_text(json.dumps(subs, indent=1))
    return JSONResponse(content={**sub, "signed": "every notification is Ed25519-signed by the meter key — verify against GET /pubkey"})


def _signed(payload: dict) -> dict:
    body = {**payload, "issuer": _deps["issuer"]}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return {**body, "sig_alg": "ed25519", "sig": _deps["sign_fn"](canon)}


def _breach_count(vow_id: str) -> int:
    n = 0
    tdir = _deps["table_dir"]
    if tdir.exists():
        for p in tdir.glob("*.wagers.jsonl"):
            for ln in p.read_text().splitlines():
                if ln.strip():
                    w = json.loads(ln)
                    if w["vow_id"] == vow_id and w.get("breach"):
                        n += 1
    return n


def tick() -> list[dict]:
    """One herald pass: diff every subscribed vow's public record against the
    last-seen state, fire signed webhooks for transitions. Deterministic —
    run from herald_worker.py on a timer (or invoke ad hoc). Returns the
    events fired (for tests/logs)."""
    subs = _load(_subs_path(), [])
    if not subs:
        return []
    state = _load(_state_path(), {})
    fired = []
    for vow_id in sorted({s["vow_id"] for s in subs}):
        vow = _deps["load_vow"](vow_id)
        if not vow:
            continue
        entries = _deps["chain_entries"](vow_id)
        stats = _deps["trajectory_stats"](vow, entries)
        icm = stats.get("coupling_ICM_series") or []
        cur = {"seq": vow.get("seq", 0), "overdue": bool(stats.get("overdue")),
               "icm": icm[-1] if icm else None, "breaches": _breach_count(vow_id)}
        prev = state.get(vow_id)
        events = []
        if prev is None:
            pass  # first sight — baseline only, no retroactive noise
        else:
            if cur["seq"] > prev["seq"]:
                events.append(("new_report", {"seq": cur["seq"]}))
            if cur["overdue"] and not prev["overdue"]:
                events.append(("overdue", {"hours_since_last_report": stats.get("hours_since_last_report")}))
            if prev["overdue"] and not cur["overdue"]:
                events.append(("recovered", {}))
            if (cur["icm"] is not None and prev.get("icm") is not None
                    and abs(cur["icm"] - prev["icm"]) >= COUPLING_JUMP):
                events.append(("coupling_jump", {"from": prev["icm"], "to": cur["icm"]}))
            if cur["breaches"] > prev.get("breaches", 0):
                events.append(("breach", {"total_breaches": cur["breaches"]}))
        state[vow_id] = cur
        for name, data in events:
            payload = _signed({"event": name, "vow_id": vow_id,
                               "agent": vow["vow"]["agent"], "data": data,
                               "ledger": f"/vow/{vow_id}", "at": _now(),
                               "note": "an event, and the numbers, and where to check them — never a verdict"})
            for s in subs:
                if s["vow_id"] == vow_id and name in s["events"]:
                    try:
                        r = _deps["post_fn"](s["url"], payload)
                        ok = 200 <= getattr(r, "status_code", 500) < 300
                    except Exception:  # noqa: BLE001
                        ok = False
                    s["delivered" if ok else "failures"] += 1
            fired.append({"event": name, "vow_id": vow_id, **data})
    _subs_path().write_text(json.dumps(subs, indent=1))
    _state_path().write_text(json.dumps(state, indent=1))
    return fired


@router.get("/herald/subs")
async def herald_subs(vow_id: str) -> dict:
    """Public: who is listening to this vow (URLs redacted to hosts —
    watching is public, endpoints aren't)."""
    from urllib.parse import urlparse
    subs = [s for s in _load(_subs_path(), []) if s["vow_id"] == vow_id]
    return {"vow_id": vow_id, "n": len(subs),
            "watchers": [{"host": urlparse(s["url"]).netloc, "events": s["events"],
                          "since": s["created_at"], "delivered": s["delivered"]}
                         for s in subs],
            "note": "being watched is public information here — that's the whole premise"}
