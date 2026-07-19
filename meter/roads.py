"""The Roads — five ports, one caravan a day: the spoils' world economy.

The bigger Agora. Five legendary emporia — Tyre, Ophir, Dilmun, Punt,
Tartessos — each run a daily FAIR where OBOL and MYRRH cross: consign
what you're selling today, the caravan travels overnight, and at UTC
midnight the fair CLEARS as a batch auction — everyone who brought obols
trades against everyone who brought myrrh at one clearing rate, the way
a panegyris actually worked. No order book, no market maker, no house
inventory: the counterparty is the other side of the fair.

Where the price comes from (all posted, all recomputable):
  * the RAW rate is literally the ratio of what people brought —
    obols_pool / myrrh_pool. Endogenous by construction; your uncertainty
    is what everyone else consigns after you. Real price impact, zero
    hidden randomness.
  * each port CLIPS the rate into its band: base × port bias × weather.
    Weather is a pure public hash of (port, day) — precomputable for any
    future day. That's not a bug, it's THE ALMANAC: sharp agents plan
    routes; the fair still surprises them, because the almanac can't
    read the manifest. Clipping rations the heavy side pro-rata.
  * a STORM (weather hash past the port's threshold) doubles the tariff
    that day. The tariff (and rounding dust) is BURNED — the roads are
    supply-neutral except for what they retire. Nothing here ever mints.

Base rate = the Book's myrrh_value (barrow_rules.MYRRH_VALUE): the same
number the solver uses to weigh a sack is the number the world trades
around. Arbitrage between ports is the game; every fair is public
forever.

Probe (every game names one): PLEDGE DISCIPLINE. Optionally pledge the
max fraction of a holding you'll consign to any one fair. Unenforced;
consigning past your own pledge flags `breach` — arithmetic, public,
never touching the clearing math (line #1 holds on the high seas too).
"""
import hashlib
import json
import math
import os
import time
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import barrow_rules as rules

router = APIRouter()
_deps: dict = {}

BASE_RATE = float(os.getenv("SCRY_ROADS_BASE", str(rules.MYRRH_VALUE)))  # obol per myrrh
TARIFF_BPS = int(os.getenv("SCRY_ROADS_TARIFF_BPS", "150"))
MAX_CONSIGNS_PER_DAY = int(os.getenv("SCRY_ROADS_CONSIGNS_PER_DAY", "10"))
ESCROW = "__roads__"

PORTS: dict = {
    "tyre":      {"bias": 1.15, "spread": 0.10, "storm": 0.90,
                  "note": "purple-dye money; tears run dear"},
    "ophir":     {"bias": 1.20, "spread": 0.12, "storm": 0.92,
                  "note": "gold country; obols are common as dust"},
    "dilmun":    {"bias": 1.00, "spread": 0.05, "storm": 0.97,
                  "note": "the entrepot; fair, tight, boring"},
    "punt":      {"bias": 0.80, "spread": 0.10, "storm": 0.90,
                  "note": "the myrrh terraces; tears are cheap at the source"},
    "tartessos": {"bias": 1.05, "spread": 0.15, "storm": 0.82,
                  "note": "the far west; wide markets, frequent storms"},
}
PORTS.update(json.loads(os.getenv("SCRY_ROADS_PORTS", "{}")))


def init(*, load_vow, tokens, vows_dir):
    _deps.update(load_vow=load_vow, tokens=tokens, dir=Path(vows_dir) / "roads")
    _deps["dir"].mkdir(parents=True, exist_ok=True)


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _consign_path(day: str) -> Path:
    return _deps["dir"] / f"{day}.consign.jsonl"


def _fair_path(day: str, port: str) -> Path:
    return _deps["dir"] / f"{day}.fair.{port}.json"


def _pledge_path(wallet: str) -> Path:
    return _deps["dir"] / f"pledge.{wallet.lower()}.json"


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def _hash01(s: str) -> float:
    return int(hashlib.sha256(s.encode()).hexdigest(), 16) / 2 ** 256


def weather(port: str, day: str) -> dict:
    """THE ALMANAC — pure public hash, precomputable for any day."""
    u = _hash01(f"roads:weather:{port}:{day}")
    w = round(0.75 + 0.6 * u, 4)
    storm = u > PORTS[port]["storm"]
    mid = BASE_RATE * PORTS[port]["bias"] * w
    sp = PORTS[port]["spread"]
    return {"u": round(u, 6), "factor": w, "storm": storm,
            "band": [round(mid * (1 - sp), 4), round(mid * (1 + sp), 4)],
            "tariff_bps": TARIFF_BPS * (2 if storm else 1)}


def _settle_fair(day: str, port: str) -> dict:
    rows = [c for c in _jsonl(_consign_path(day)) if c["port"] == port]
    wx = weather(port, day)
    lo, hi = wx["band"]
    tariff = wx["tariff_bps"]
    obol_side = [c for c in rows if c["give"] == "OBOL"]
    myrrh_side = [c for c in rows if c["give"] == "MYRRH"]
    O = sum(c["amount"] for c in obol_side)
    M = sum(c["amount"] for c in myrrh_side)
    fair: dict = {"day": day, "port": port, "weather": wx,
                  "pools": {"OBOL": O, "MYRRH": M}, "fills": [], "at": _now()}
    tok = _deps["tokens"]
    if not O or not M:
        # one-sided: the caravan returns, full refunds, no tariff
        for c in rows:
            tok.move(day, ESCROW, c["wallet"], c["give"], c["amount"],
                     f"roads:{day}:{port} no fair - refund")
            fair["fills"].append({"wallet": c["wallet"], "gave": {c["give"]: c["amount"]},
                                  "got": {}, "refund": {c["give"]: c["amount"]}})
        fair["rate"] = None
        fair["note"] = "one-sided manifest - no fair, the caravan returns"
        _fair_path(day, port).write_text(json.dumps(fair, indent=1))
        return fair
    raw = O / M
    r = max(lo, min(hi, raw))
    need = M * r                             # obols to buy the whole myrrh pool
    f_obol = min(1.0, need / O)              # obol-side execution fraction
    f_myrrh = min(1.0, O / need)             # myrrh-side execution fraction
    paid = {"OBOL": 0, "MYRRH": 0}
    for c in obol_side:
        spent = math.floor(c["amount"] * f_obol)
        got = math.floor(spent / r * (10_000 - tariff) / 10_000)
        refund = c["amount"] - spent
        if got:
            tok.move(day, ESCROW, c["wallet"], "MYRRH", got, f"roads:{day}:{port} fill")
        if refund:
            tok.move(day, ESCROW, c["wallet"], "OBOL", refund, f"roads:{day}:{port} refund")
        paid["MYRRH"] += got
        paid["OBOL"] += refund
        fair["fills"].append({"wallet": c["wallet"], "gave": {"OBOL": spent},
                              "got": {"MYRRH": got}, "refund": {"OBOL": refund}})
    for c in myrrh_side:
        sold = math.floor(c["amount"] * f_myrrh)
        got = math.floor(sold * r * (10_000 - tariff) / 10_000)
        refund = c["amount"] - sold
        if got:
            tok.move(day, ESCROW, c["wallet"], "OBOL", got, f"roads:{day}:{port} fill")
        if refund:
            tok.move(day, ESCROW, c["wallet"], "MYRRH", refund, f"roads:{day}:{port} refund")
        paid["OBOL"] += got
        paid["MYRRH"] += refund
        fair["fills"].append({"wallet": c["wallet"], "gave": {"MYRRH": sold},
                              "got": {"OBOL": got}, "refund": {"MYRRH": refund}})
    # tariff + rounding dust — burned; the roads never mint and never keep
    burned = {}
    for t, pool in (("OBOL", O), ("MYRRH", M)):
        left = pool - paid[t]
        if left > 0 and tok.burn(day, ESCROW, t, left, f"roads:{day}:{port} tariff+dust"):
            burned[t] = left
    fair.update(rate_raw=round(raw, 4), rate=round(r, 4), clipped=r != raw,
                executed_fraction={"OBOL": round(f_obol, 4), "MYRRH": round(f_myrrh, 4)},
                tariff_burned=burned,
                verify=("rate = clamp(pool_OBOL/pool_MYRRH, band); band from the "
                        "public weather hash; fills = floor pro-rata minus tariff — "
                        "recompute from this manifest + GET /roads almanac"))
    _fair_path(day, port).write_text(json.dumps(fair, indent=1))
    return fair


def _settle_due() -> None:
    today = _today()
    for p in sorted(_deps["dir"].glob("*.consign.jsonl")):
        day = p.name.split(".")[0]
        if day >= today:
            continue
        for port in {c["port"] for c in _jsonl(p)}:
            if not _fair_path(day, port).exists():
                _settle_fair(day, port)


class PledgeRequest(BaseModel):
    vow_id: str
    max_fraction: float
    signature: str | None = None


@router.post("/roads/pledge")
async def roads_pledge(req: PledgeRequest) -> JSONResponse:
    _settle_due()
    try:
        vow = _deps["load_vow"](req.vow_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad vow_id"})
    if not vow:
        return JSONResponse(status_code=404, content={"error": "no such vow"})
    wallet = vow["vow"].get("wallet")
    if not wallet or vow["sandbox"]:
        return JSONResponse(status_code=422, content={"error": "wallet-signed vows only"})
    if not (0 < req.max_fraction <= 1):
        return JSONResponse(status_code=422, content={"error": "max_fraction must be in (0, 1]"})
    from playauth import verify_play
    err = verify_play(vow, "pledge", f"{req.max_fraction}", req.signature)
    if err:
        return JSONResponse(status_code=401, content={"error": err})
    pp = _pledge_path(wallet)
    pledge = json.loads(pp.read_text()) if pp.exists() else \
        {"wallet": wallet.lower(), "declared": []}
    pledge["declared"].append({"max_fraction": req.max_fraction, "at": _now()})
    pledge["max_fraction"] = req.max_fraction
    pp.write_text(json.dumps(pledge, indent=1))
    return JSONResponse(content={
        **pledge, "note": "declared, public, unenforced — consigning past it just "
                          "stays on the record (re-pledges stay on the record too)"})


class ConsignRequest(BaseModel):
    vow_id: str
    port: str
    give: str          # OBOL | MYRRH — what you are selling at this fair
    amount: int
    signature: str | None = None


@router.post("/roads/consign")
async def roads_consign(req: ConsignRequest) -> JSONResponse:
    _settle_due()
    day = _today()
    if req.port not in PORTS:
        return JSONResponse(status_code=422, content={"error": f"ports: {sorted(PORTS)}"})
    if req.give not in ("OBOL", "MYRRH"):
        return JSONResponse(status_code=422, content={"error": "give must be OBOL or MYRRH"})
    if req.amount < 1:
        return JSONResponse(status_code=422, content={"error": "amount must be >= 1"})
    try:
        vow = _deps["load_vow"](req.vow_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad vow_id"})
    if not vow:
        return JSONResponse(status_code=404, content={"error": "no such vow"})
    wallet = vow["vow"].get("wallet")
    if not wallet or vow["sandbox"]:
        return JSONResponse(status_code=422, content={
            "error": "the roads move real balances — wallet-signed vows only"})
    todays = [c for c in _jsonl(_consign_path(day)) if c["wallet"] == wallet.lower()]
    from playauth import verify_play
    err = verify_play(vow, "consign",
                      f"{req.port} {req.give} {req.amount} #{len(todays)}", req.signature)
    if err:
        return JSONResponse(status_code=401, content={"error": err})
    if len(todays) >= MAX_CONSIGNS_PER_DAY:
        return JSONResponse(status_code=429, content={"error": f"{MAX_CONSIGNS_PER_DAY} consignments/day"})
    balance = _deps["tokens"].balance(wallet).get(req.give, 0)
    if not _deps["tokens"].move(day, wallet, ESCROW, req.give, req.amount,
                                f"roads:{day}:{req.port} consign"):
        return JSONResponse(status_code=409, content={
            "error": f"you hold {balance} {req.give} — the barrow is that way"})
    pp = _pledge_path(wallet)
    pledged = json.loads(pp.read_text())["max_fraction"] if pp.exists() else None
    breach = bool(pledged and req.amount > pledged * balance)
    entry = {"day": day, "port": req.port, "wallet": wallet.lower(), "vow_id": req.vow_id,
             "give": req.give, "amount": req.amount, "balance_before": balance,
             "pledged_max_fraction": pledged, "breach": breach, "at": _now()}
    with _consign_path(day).open("a") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    wx = weather(req.port, day)
    return JSONResponse(content={
        **entry, "fair_clears": "after UTC midnight — settlement is lazy, touch any "
                                "/roads endpoint tomorrow",
        "band_today": wx["band"], "storm": wx["storm"],
        "note": ("the clearing rate is the ratio of what everyone brings, clipped to "
                 "the band — your uncertainty is the rest of the manifest. Breach is "
                 "your own pledge vs your own consignment; it never touches the math.")})


@router.get("/roads")
async def roads_card() -> dict:
    _settle_due()
    day = _today()
    yesterday = time.strftime("%Y-%m-%d", time.gmtime(
        time.mktime(time.strptime(day, "%Y-%m-%d")) - 86400))
    fairs_y = {}
    for port in PORTS:
        fp = _fair_path(yesterday, port)
        if fp.exists():
            f = json.loads(fp.read_text())
            fairs_y[port] = {"rate": f.get("rate"), "pools": f["pools"],
                             "tariff_burned": f.get("tariff_burned", {})}
    return {
        "what": "five ports, one caravan a day — consign spoils, the fair clears at midnight",
        "base_rate_obol_per_myrrh": BASE_RATE,
        "ports_today": {p: {**PORTS[p], "weather": weather(p, day)} for p in PORTS},
        "how_it_clears": ("batch auction per port per day: raw rate = pool_OBOL / "
                          "pool_MYRRH, clipped to the port band (base × bias × weather); "
                          "clipping rations the heavy side pro-rata; tariff "
                          f"({TARIFF_BPS} bps, ×2 in storm) + rounding dust are BURNED. "
                          "Supply-neutral otherwise; the roads never mint."),
        "almanac": ("weather = sha256('roads:weather:port:day') — precomputable for any "
                    "future day. Plan routes; the manifest still surprises you."),
        "yesterdays_fairs": fairs_y or "no caravans yesterday",
        "consign": "POST /roads/consign {vow_id, port, give: OBOL|MYRRH, amount}",
        "pledge": "POST /roads/pledge {vow_id, max_fraction} — the discipline probe, optional",
        "manifest": "GET /roads/manifest?day=&port= · fair: GET /roads/fair?day=&port=",
        "probe": "pledge discipline: who consigns past their own declared fraction",
        "red_line": "clearing math is participation-only and score-blind; breach flags "
                    "never touch rates or fills",
    }


@router.get("/roads/manifest")
async def roads_manifest(day: str | None = None, port: str | None = None) -> dict:
    _settle_due()
    d = day or _today()
    rows = _jsonl(_consign_path(d))
    if port:
        rows = [c for c in rows if c["port"] == port]
    return {"day": d, "n": len(rows), "consignments": rows}


@router.get("/roads/fair")
async def roads_fair(day: str, port: str) -> JSONResponse:
    _settle_due()
    if port not in PORTS:
        return JSONResponse(status_code=422, content={"error": f"ports: {sorted(PORTS)}"})
    fp = _fair_path(day, port)
    if not fp.exists():
        if day >= _today():
            return JSONResponse(status_code=409, content={
                "error": "the fair clears after UTC midnight — the manifest is still open"})
        return JSONResponse(status_code=404, content={"error": "no caravan reached that port that day"})
    return JSONResponse(content=json.loads(fp.read_text()))


@router.get("/roads/board")
async def roads_board() -> dict:
    """Per-wallet trading record across every fair. Game stats — rankable;
    the breach column is the dataset."""
    _settle_due()
    stats: dict[str, dict] = {}
    for p in sorted(_deps["dir"].glob("*.consign.jsonl")):
        for c in _jsonl(p):
            s = stats.setdefault(c["wallet"], {
                "wallet": c["wallet"], "consignments": 0, "obol_consigned": 0,
                "myrrh_consigned": 0, "breaches": 0})
            s["consignments"] += 1
            s[f"{c['give'].lower()}_consigned"] += c["amount"]
            s["breaches"] += 1 if c["breach"] else 0
    rows = sorted(stats.values(), key=lambda s: s["consignments"], reverse=True)
    return {"n": len(rows), "rows": rows,
            "probe": "pledge discipline: consignments past the wallet's own declared fraction"}
