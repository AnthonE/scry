"""Oracle Duels — parimutuel up/down calls on tomorrow's price (fun layer).

One round per symbol per UTC day. Call `up` or `down` with a stake from your
harvest-ledger balance before the cutoff; the round's open price is locked
when the round is born (first call of the day). After the day ends, the
round settles on first touch: winners take their stakes back plus the
losers' pool minus the rake, split pro-rata by stake. The rake accrues to
`__rake__` in the public ledger — earmarked for the Bank when payouts go
on-chain. One-sided rounds and unchanged prices push (all stakes returned).

Everything is deterministic and score-blind (SCRY-ECONOMY.md line #1): the
odds are made by the players (parimutuel), the settle price comes from the
same public feed the arena uses, and no meter number touches money. The
probe this game earns its keep with: CALIBRATION — every wallet's public
hit-rate over time, predictions registered before outcomes, the cleanest
overconfidence dataset a memecoin ever farmed.
"""
import json
import os
import time
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()
_deps: dict = {}

CUTOFF_UTC_H = int(os.getenv("SCRY_DUELS_CUTOFF_UTC_H", "12"))  # calls close 12:00 UTC
RAKE_BPS = int(os.getenv("SCRY_DUELS_RAKE_BPS", "200"))          # 2% of losing pool
MAX_STAKE = int(os.getenv("SCRY_DUELS_MAX_STAKE", "500"))        # SCRY units per call
MIN_STAKE = 1


def init(*, load_vow, prices, ledger_balance, ledger_adjust, vows_dir):
    _deps.update(load_vow=load_vow, prices=prices,
                 ledger_balance=ledger_balance, ledger_adjust=ledger_adjust,
                 dir=Path(vows_dir) / "duels")
    _deps["dir"].mkdir(parents=True, exist_ok=True)


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _round_path(day: str, sym: str) -> Path:
    return _deps["dir"] / f"{day}.{sym}.json"


def _load_round(day: str, sym: str) -> dict | None:
    p = _round_path(day, sym)
    return json.loads(p.read_text()) if p.exists() else None


def _save_round(r: dict) -> None:
    _round_path(r["day"], r["symbol"]).write_text(json.dumps(r, indent=1))


def _calls_open(day: str) -> bool:
    return day == _today() and time.gmtime().tm_hour < CUTOFF_UTC_H


def settle_math(r: dict) -> tuple[dict[str, int], int, str]:
    """Deterministic settlement: {wallet: delta}, rake, outcome. Deltas are
    RELATIVE to already-escrowed stakes (stakes were debited at call time).
    Winners get stake back + pro-rata share of (losing pool − rake); pushes
    refund everyone. Integer math, remainder dust refunds to the largest
    winner (posted rule, deterministic)."""
    up = [c for c in r["calls"] if c["side"] == "up"]
    down = [c for c in r["calls"] if c["side"] == "down"]
    if not up or not down:
        return {c["wallet"]: c["stake"] for c in r["calls"]}, 0, "push:one-sided"
    if r["settle_price"] == r["open_price"]:
        return {c["wallet"]: c["stake"] for c in r["calls"]}, 0, "push:unchanged"
    winners = up if r["settle_price"] > r["open_price"] else down
    losers = down if winners is up else up
    lose_pool = sum(c["stake"] for c in losers)
    rake = lose_pool * RAKE_BPS // 10_000
    prize = lose_pool - rake
    win_pool = sum(c["stake"] for c in winners)
    deltas: dict[str, int] = {}
    paid = 0
    for c in winners:
        share = prize * c["stake"] // win_pool
        paid += share
        deltas[c["wallet"]] = deltas.get(c["wallet"], 0) + c["stake"] + share
    # integer dust → largest winner (ties: first caller)
    dust = prize - paid
    if dust:
        big = max(winners, key=lambda c: (c["stake"], -r["calls"].index(c)))
        deltas[big["wallet"]] += dust
    return deltas, rake, ("up" if winners is up else "down")


def _maybe_settle(r: dict) -> dict:
    """Settle a past-day round on first touch. The settle price is the feed
    at settlement time, recorded publicly with its timestamp — first-touch
    settlement is the honest zero-infra tradeoff and the record says so."""
    if r["settled"] or r["day"] >= _today():
        return r
    try:
        price = _deps["prices"]()[r["symbol"]]
    except Exception:  # noqa: BLE001
        return r  # feed down — stays unsettled until next touch
    r["settle_price"] = price
    r["settled_at"] = _now()
    deltas, rake, outcome = settle_math(r)
    r["outcome"], r["rake"], r["payouts"], r["settled"] = outcome, rake, deltas, True
    all_deltas = dict(deltas)
    if rake:
        all_deltas["__rake__"] = all_deltas.get("__rake__", 0) + rake
    _deps["ledger_adjust"](r["day"], all_deltas)
    _save_round(r)
    return r


class CallRequest(BaseModel):
    vow_id: str
    symbol: str
    side: str      # up | down
    stake: int


@router.post("/duels/call")
async def duels_call(req: CallRequest) -> JSONResponse:
    day = _today()
    if not _calls_open(day):
        return JSONResponse(status_code=409, content={
            "error": f"calls close {CUTOFF_UTC_H:02d}:00 UTC — come back tomorrow"})
    try:
        vow = _deps["load_vow"](req.vow_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad vow_id"})
    if not vow:
        return JSONResponse(status_code=404, content={"error": "no such vow"})
    wallet = vow["vow"].get("wallet")
    if not wallet or vow["sandbox"]:
        return JSONResponse(status_code=422, content={
            "error": "duels stake the harvest ledger — wallet-signed vows only "
                     "(answer auguries to earn a stake)"})
    sym = req.symbol.upper()
    if req.side not in ("up", "down"):
        return JSONResponse(status_code=422, content={"error": "side must be up|down"})
    if not (MIN_STAKE <= req.stake <= MAX_STAKE):
        return JSONResponse(status_code=422, content={
            "error": f"stake must be {MIN_STAKE}..{MAX_STAKE} SCRY units"})
    if _deps["ledger_balance"](wallet) < req.stake:
        return JSONResponse(status_code=409, content={
            "error": f"harvest balance {_deps['ledger_balance'](wallet)} < stake — "
                     "answer auguries (or win) to play bigger"})
    try:
        feed = _deps["prices"]()
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"error": f"price feed unavailable: {e}"})
    if sym not in feed:
        return JSONResponse(status_code=422, content={"error": f"symbol must be one of {sorted(feed)}"})
    r = _load_round(day, sym) or {
        "day": day, "symbol": sym, "open_price": feed[sym], "opened_at": _now(),
        "cutoff_utc": f"{CUTOFF_UTC_H:02d}:00", "rake_bps": RAKE_BPS,
        "calls": [], "settled": False}
    if any(c["wallet"] == wallet for c in r["calls"]):
        return JSONResponse(status_code=409, content={"error": "one call per wallet per symbol per day"})
    call = {"wallet": wallet, "vow_id": req.vow_id, "agent": vow["vow"]["agent"],
            "side": req.side, "stake": req.stake, "at": _now()}
    r["calls"].append(call)
    _save_round(r)
    _deps["ledger_adjust"](day, {wallet: -req.stake})  # escrow the stake
    return JSONResponse(content={
        **call, "open_price": r["open_price"],
        "pool": {"up": sum(c["stake"] for c in r["calls"] if c["side"] == "up"),
                 "down": sum(c["stake"] for c in r["calls"] if c["side"] == "down")},
        "settles": "first touch after the UTC day ends — parimutuel, rake "
                   f"{RAKE_BPS / 100}% of the losing pool to the Bank accumulator",
        "note": "your call is public now, the outcome is public tomorrow — "
                "the board keeps your hit-rate forever"})


@router.get("/duels")
async def duels_card() -> dict:
    day = _today()
    rounds = []
    for p in sorted(_deps["dir"].glob(f"{day}.*.json")):
        r = json.loads(p.read_text())
        rounds.append({"symbol": r["symbol"], "open_price": r["open_price"],
                       "pool_up": sum(c["stake"] for c in r["calls"] if c["side"] == "up"),
                       "pool_down": sum(c["stake"] for c in r["calls"] if c["side"] == "down"),
                       "n_calls": len(r["calls"])})
    return {"day": day, "calls_open": _calls_open(day),
            "cutoff_utc": f"{CUTOFF_UTC_H:02d}:00",
            "stake_range": [MIN_STAKE, MAX_STAKE], "rake_bps": RAKE_BPS,
            "rounds_today": rounds,
            "call_at": "POST /duels/call {vow_id, symbol, side: up|down, stake}",
            "how": "parimutuel: the players make the odds; winners split the losing "
                   "pool minus rake, pro-rata by stake; one-sided/unchanged = push",
            "red_line": "stakes and payouts never touch meter output — the only thing "
                        "this game measures is whether you're as calibrated as you act"}


@router.get("/duels/round/{day}/{symbol}")
async def duels_round(day: str, symbol: str) -> JSONResponse:
    r = _load_round(day, symbol.upper())
    if not r:
        return JSONResponse(status_code=404, content={"error": "no such round"})
    return JSONResponse(content=_maybe_settle(r))


@router.get("/duels/board")
async def duels_board() -> dict:
    """The calibration board: every wallet's public prediction record across
    all settled rounds. A game stat — rankable, unlike alignment."""
    stats: dict[str, dict] = {}
    for p in sorted(_deps["dir"].glob("*.json")):
        r = _maybe_settle(json.loads(p.read_text()))
        if not r["settled"] or r["outcome"].startswith("push"):
            continue
        for c in r["calls"]:
            s = stats.setdefault(c["wallet"], {"wallet": c["wallet"], "agent": c["agent"],
                                               "calls": 0, "hits": 0, "staked": 0, "won": 0})
            s["calls"] += 1
            s["staked"] += c["stake"]
            if c["side"] == r["outcome"]:
                s["hits"] += 1
                s["won"] += r["payouts"].get(c["wallet"], 0) - c["stake"]
    rows = sorted(stats.values(), key=lambda s: (s["hits"] / s["calls"], s["calls"]),
                  reverse=True)
    for s in rows:
        s["hit_rate"] = round(s["hits"] / s["calls"], 3)
    return {"n": len(rows), "rows": rows,
            "probe": "public calibration under real stakes: predictions registered "
                     "before outcomes, hit-rates forever"}
