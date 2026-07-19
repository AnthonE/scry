"""The Agora — the town market that CONSUMES the spoils (the burn side).

The Barrow mints OBOL and MYRRH; the Agora burns them. Three goods, each a
consumable that feeds back into the delve, priced in spoils that are burned
on purchase — mint by play, burn by use, a real circulating economy at toy
scale. Plus the shrine: burn MYRRH as a pure offering, the ancient use of
the resin — participation ritual, public record, never a payout.

LARP-RWA, honestly labeled: the goods wear ancient-commodity skins (salt
rations, pitch torches, resin charms) and each carries an "assay" line for
flavor. The goods are fictional. The MATH is not: prices float on a posted
deterministic formula whose inputs are REAL usage analytics — yesterday's
delve entries, augury answers, and shrine offerings, all public and
recomputable from their own endpoints. Busy town, dear goods; quiet town,
cheap goods. Real foot traffic is the only oracle.

Score-blind like everything else: prices key on participation COUNTS,
never on any meter number, and no fee here moves a measurement.
"""
import json
import math
import os
import time
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()
_deps: dict = {}

# good -> (token, base_price, effect, assay). env-overridable prices.
GOODS: dict = {
    "ration": {"token": "OBOL", "base": 10,
               "effect": "+1 HP for the delve it's used in",
               "assay": "hardtack and salt fish - salt was salary once"},
    "torch":  {"token": "OBOL", "base": 5,
               "effect": "+0.10 sneak odds for a whole delve",
               "assay": "pitch-pine dipped in tallow"},
    "charm":  {"token": "MYRRH", "base": 3,
               "effect": "absorbs one killing blow, then shatters",
               "assay": "an amulet of hardened myrrh resin"},
}
GOODS.update(json.loads(os.getenv("SCRY_AGORA_GOODS", "{}")))
DEMAND_NORM = int(os.getenv("SCRY_AGORA_DEMAND_NORM", "20"))
MULT_FLOOR, MULT_CEIL = 0.5, 3.0
MAX_QTY = 5


def init(*, load_vow, tokens, answers_count, delves_count, vows_dir):
    _deps.update(load_vow=load_vow, tokens=tokens,
                 answers_count=answers_count, delves_count=delves_count,
                 dir=Path(vows_dir) / "agora")
    _deps["dir"].mkdir(parents=True, exist_ok=True)


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _yesterday(day: str) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(
        time.mktime(time.strptime(day, "%Y-%m-%d")) - 86400))


def _inv_path(wallet: str) -> Path:
    return _deps["dir"] / f"inv.{wallet.lower()}.json"


def _trades_path(day: str) -> Path:
    return _deps["dir"] / f"{day}.trades.jsonl"


def _offerings_path(day: str) -> Path:
    return _deps["dir"] / f"{day}.offerings.jsonl"


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def offerings_count(day: str) -> int:
    return len(_jsonl(_offerings_path(day)))


def activity(day: str) -> dict:
    """The REAL analytics a day's prices are computed from — all public."""
    return {"delves": _deps["delves_count"](day),
            "augury_answers": _deps["answers_count"](day),
            "offerings": offerings_count(day)}


def demand_multiplier(day: str) -> tuple[float, dict]:
    """Posted formula: m = clamp(0.5 + activity(yesterday)/NORM, 0.5, 3.0).
    Inputs are yesterday's participation counts — recompute them yourself
    from /barrow/log, /augury/answers, /agora/offerings."""
    y = _yesterday(day)
    a = activity(y)
    m = max(MULT_FLOOR, min(MULT_CEIL, 0.5 + sum(a.values()) / DEMAND_NORM))
    return round(m, 3), {"yesterday": y, **a}


def price(day: str, good: str) -> int:
    m, _ = demand_multiplier(day)
    return max(1, math.ceil(GOODS[good]["base"] * m))


def inventory(wallet: str) -> dict:
    p = _inv_path(wallet)
    return json.loads(p.read_text()) if p.exists() else {}


def consume(wallet: str, item: str) -> bool:
    """Spend one held consumable (the Barrow calls this at enter). The
    token was already burned at purchase; this burns the GOOD itself."""
    inv = inventory(wallet)
    if inv.get(item, 0) < 1:
        return False
    inv[item] -= 1
    _inv_path(wallet).write_text(json.dumps(inv, indent=1))
    return True


class BuyRequest(BaseModel):
    vow_id: str
    good: str
    qty: int = 1
    signature: str | None = None


@router.post("/agora/buy")
async def agora_buy(req: BuyRequest) -> JSONResponse:
    day = _today()
    if req.good not in GOODS:
        return JSONResponse(status_code=422, content={"error": f"goods: {sorted(GOODS)}"})
    if not (1 <= req.qty <= MAX_QTY):
        return JSONResponse(status_code=422, content={"error": f"qty must be 1..{MAX_QTY}"})
    try:
        vow = _deps["load_vow"](req.vow_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad vow_id"})
    if not vow:
        return JSONResponse(status_code=404, content={"error": "no such vow"})
    wallet = vow["vow"].get("wallet")
    if not wallet or vow["sandbox"]:
        return JSONResponse(status_code=422, content={
            "error": "the agora burns spoils — wallet-signed vows only (sandbox delves need no goods)"})
    todays = [t for t in _jsonl(_trades_path(day)) if t["wallet"] == wallet.lower()]
    from playauth import verify_play
    err = verify_play(vow, "buy", f"{req.good} {req.qty} #{len(todays)}", req.signature)
    if err:
        return JSONResponse(status_code=401, content={"error": err})
    token, unit = GOODS[req.good]["token"], price(day, req.good)
    cost = unit * req.qty
    if not _deps["tokens"].burn(day, wallet, token, cost, f"agora: {req.qty} {req.good}"):
        have = _deps["tokens"].balance(wallet).get(token, 0)
        return JSONResponse(status_code=409, content={
            "error": f"costs {cost} {token}, you hold {have} — delve the barrow"})
    inv = inventory(wallet)
    inv[req.good] = inv.get(req.good, 0) + req.qty
    _inv_path(wallet).write_text(json.dumps(inv, indent=1))
    trade = {"day": day, "wallet": wallet.lower(), "vow_id": req.vow_id,
             "good": req.good, "qty": req.qty, "unit_price": unit,
             "burned": {token: cost}, "at": _now()}
    with _trades_path(day).open("a") as f:
        f.write(json.dumps(trade, separators=(",", ":")) + "\n")
    return JSONResponse(content={
        **trade, "inventory": inv,
        "note": f"{cost} {token} burned — supply retired forever. "
                f"Use in the delve: POST /barrow/enter {{use: ['{req.good}']}}"})


class OfferRequest(BaseModel):
    vow_id: str
    amount: int
    signature: str | None = None


@router.post("/agora/offer")
async def agora_offer(req: OfferRequest) -> JSONResponse:
    """Burn MYRRH at the shrine. Pure offering: no payout, no buff, no odds —
    a participation ritual on the public record (rewarding the ritual is
    allowed; this one IS the ritual, unrewarded on purpose)."""
    day = _today()
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
        return JSONResponse(status_code=422, content={"error": "wallet-signed vows only"})
    from playauth import verify_play
    err = verify_play(vow, "offer", str(req.amount), req.signature)
    if err:
        return JSONResponse(status_code=401, content={"error": err})
    if not _deps["tokens"].burn(day, wallet, "MYRRH", req.amount, "shrine offering"):
        have = _deps["tokens"].balance(wallet).get("MYRRH", 0)
        return JSONResponse(status_code=409, content={
            "error": f"you hold {have} MYRRH — the deep rooms of the barrow carry it"})
    entry = {"day": day, "wallet": wallet.lower(), "vow_id": req.vow_id,
             "myrrh": req.amount, "at": _now()}
    with _offerings_path(day).open("a") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    return JSONResponse(content={
        **entry, "note": "the smoke rises. Nothing is owed in return — that is the point."})


@router.get("/agora")
async def agora_card() -> dict:
    day = _today()
    m, inputs = demand_multiplier(day)
    y = inputs.pop("yesterday")
    burned_y = _deps["tokens"].burned_on(y)
    return {
        "what": "the town market — goods burn spoils; the shrine burns myrrh; nothing here mints",
        "prices_today": {g: {"price": price(day, g), "token": GOODS[g]["token"],
                             "base": GOODS[g]["base"], "effect": GOODS[g]["effect"],
                             "assay": GOODS[g]["assay"]} for g in GOODS},
        "demand": {"multiplier": m,
                   "formula": f"clamp(0.5 + (delves + augury_answers + offerings)/{DEMAND_NORM}, "
                              f"{MULT_FLOOR}, {MULT_CEIL}) over YESTERDAY's counts",
                   "inputs": {"day": y, **inputs},
                   "recompute_from": ["/barrow/log?day=" + y, "/augury/answers?day=" + y,
                                      "/agora/offerings?day=" + y]},
        "last_night": {"burned": burned_y or "nothing",
                       "note": "real burn totals from the token ledger — the town's actual consumption"},
        "buy": "POST /agora/buy {vow_id, good, qty} — burns the price, stocks your inventory",
        "offer": "POST /agora/offer {vow_id, amount} — burn MYRRH at the shrine, get nothing, be seen",
        "inventory": "GET /agora/inventory?vow_id=…",
        "larp": ("the goods are fictional ancient commodities; the burn math and the "
                 "demand inputs are real and public. No real-world asset backs anything."),
        "red_line": "prices key on participation counts, never on meter numbers",
    }


@router.get("/agora/inventory")
async def agora_inventory(vow_id: str) -> JSONResponse:
    try:
        vow = _deps["load_vow"](vow_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad vow_id"})
    if not vow:
        return JSONResponse(status_code=404, content={"error": "no such vow"})
    wallet = vow["vow"].get("wallet")
    if not wallet:
        return JSONResponse(content={"inventory": {}, "note": "sandbox vows hold no goods"})
    return JSONResponse(content={"wallet": wallet.lower(), "inventory": inventory(wallet)})


@router.get("/agora/offerings")
async def agora_offerings(day: str | None = None) -> dict:
    d = day or _today()
    rows = _jsonl(_offerings_path(d))
    return {"day": d, "n": len(rows), "myrrh_burned": sum(r["myrrh"] for r in rows),
            "offerings": rows}


@router.get("/agora/trades")
async def agora_trades(day: str | None = None) -> dict:
    d = day or _today()
    return {"day": d, "trades": _jsonl(_trades_path(d))}
