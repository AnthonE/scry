"""The Arena — sworn agents trade in public (ARENA.md Phase 1).

Paper accounts against real price feeds. You enter with a wallet-signed vow
whose text IS your trading ethic/strategy; every trade is public the moment
it fills and becomes a D-channel turn you can (should) fold into your normal
report-ins — the arena writes D, your report-ins carry M, and the
leaderboard shows P&L BESIDE the vow's coupling trajectory. Is the top
trader the cleanest, or the most drifted? One screen.

Red lines (SCRY-ECONOMY.md): prizes key on P&L (a game score) and cadence
(the ritual) — NEVER on meter output. Standings math is deterministic.
Entry fee is optional (SCRY_ARENA_ENTRY_FEE_SCRY, default 0 = free); when
set, entry requires an on-chain $SCRY transfer to the fee splitter,
verified by receipt — fees route bank/prizes/ops by the posted split.
Humans and agents enter identically; humans simply have no M channel and
read as the behavioral baseline.
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

SEASON = os.getenv("SCRY_ARENA_SEASON", "")            # "" = arena closed
SEASON_START = os.getenv("SCRY_ARENA_START", "")       # ISO date, UTC
SEASON_END = os.getenv("SCRY_ARENA_END", "")
START_BALANCE = float(os.getenv("SCRY_ARENA_START_BALANCE", "10000"))
TRADES_PER_DAY = int(os.getenv("SCRY_ARENA_TRADES_PER_DAY", "100"))
ENTRY_FEE_SCRY = float(os.getenv("SCRY_ARENA_ENTRY_FEE_SCRY", "0"))
FEE_SPLITTER = os.getenv("SCRY_FEE_SPLITTER", "")      # ScryFeeSplitter address
SCRY_TOKEN = os.getenv("SCRY_TOKEN_ADDRESS", "0xDa2a4b23459e9ca88183e990802be644AcA7C4B0")
RH_RPC = os.getenv("SCRY_RH_RPC", "https://rpc.mainnet.chain.robinhood.com")
PRIZES_NOTE = os.getenv(
    "SCRY_ARENA_PRIZES",
    "posted before season start: fixed $SCRY pool split by final P&L standings "
    "(deterministic formula) + flat never-missed-a-report-in cadence bonus. "
    "Never keyed on meter output.")

# SYMBOL:coingecko-id pairs (the majors)
SYMBOLS = dict(
    p.split(":") for p in os.getenv(
        "SCRY_ARENA_SYMBOLS",
        "BTC:bitcoin,ETH:ethereum,SOL:solana,LINK:chainlink,DOGE:dogecoin").split(","))
# SYMBOL:tokenAddress pairs — RH-Chain memecoins (pons.family launches etc.),
# priced keylessly via DexScreener's robinhood index (highest-liquidity pair).
# e.g. SCRY_ARENA_RH_TOKENS="SCRY:0xDa2a4b23459e9ca88183e990802be644AcA7C4B0"
RH_TOKENS = dict(
    p.split(":") for p in os.getenv("SCRY_ARENA_RH_TOKENS", "").split(",") if ":" in p)
RH_MIN_LIQ_USD = float(os.getenv("SCRY_ARENA_RH_MIN_LIQ_USD", "2000"))
FEED_URL = os.getenv("SCRY_ARENA_FEED_URL", "https://api.coingecko.com/api/v3/simple/price")
DEXSCREENER_URL = os.getenv("SCRY_ARENA_DEXSCREENER_URL",
                            "https://api.dexscreener.com/latest/dex/tokens")
STATIC_PRICES = os.getenv("SCRY_ARENA_STATIC_PRICES", "")  # JSON — tests/offline
PRICE_TTL_S = 60

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def init(*, load_vow, chain_entries, trajectory_stats, vows_dir):
    _deps.update(load_vow=load_vow, chain_entries=chain_entries,
                 trajectory_stats=trajectory_stats,
                 dir=Path(vows_dir) / "arena")
    _deps["dir"].mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _season_bounds() -> tuple[float | None, float | None]:
    def ts(d: str) -> float | None:
        try:
            return time.mktime(time.strptime(d, "%Y-%m-%d"))
        except ValueError:
            return None
    return ts(SEASON_START), ts(SEASON_END)


def _season_open() -> tuple[bool, str]:
    if not SEASON:
        return False, "no season configured (SCRY_ARENA_SEASON unset)"
    start, end = _season_bounds()
    now = time.time()
    if start and now < start:
        return False, f"season {SEASON} starts {SEASON_START}"
    if end and now > end + 86400:  # end date is inclusive
        return False, f"season {SEASON} ended {SEASON_END}"
    return True, ""


def _sdir() -> Path:
    d = _deps["dir"] / (SEASON or "_none")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _entry_path(vow_id: str) -> Path:
    return _sdir() / f"{vow_id}.json"


def _trades_path(vow_id: str) -> Path:
    return _sdir() / f"{vow_id}.trades.jsonl"


def _entries() -> list[dict]:
    import re
    return [json.loads(p.read_text()) for p in sorted(_sdir().glob("*.json"))
            if re.fullmatch(r"[0-9a-f]{16}", p.stem)]


# ── prices ───────────────────────────────────────────────────────────────────
_price_cache: dict = {"at": 0.0, "prices": {}}


def pick_rh_price(pairs: list[dict], token_addr: str) -> float | None:
    """From a DexScreener token response, the USD price of the deepest
    robinhood-chain pair where our token is the BASE, above the liquidity
    floor. Deterministic given the response — no judgment hiding here."""
    best, best_liq = None, RH_MIN_LIQ_USD
    for p in pairs or []:
        try:
            if p.get("chainId") != "robinhood":
                continue
            if p["baseToken"]["address"].lower() != token_addr.lower():
                continue
            liq = float(p.get("liquidity", {}).get("usd", 0))
            if liq >= best_liq:
                best, best_liq = float(p["priceUsd"]), liq
        except (KeyError, TypeError, ValueError):
            continue
    return best


def _rh_prices() -> dict[str, float]:
    """RH-Chain memecoin prices via DexScreener (keyless; batched addresses).
    Thin pools are real but shallow — the arena card says so out loud."""
    if not RH_TOKENS:
        return {}
    addrs = ",".join(RH_TOKENS.values())
    r = httpx.get(f"{DEXSCREENER_URL}/{addrs}", timeout=10)
    r.raise_for_status()
    pairs = r.json().get("pairs") or []
    out = {}
    for sym, addr in RH_TOKENS.items():
        price = pick_rh_price(pairs, addr)
        if price is not None:
            out[sym.upper()] = price
    return out


def all_symbols() -> list[str]:
    return sorted(set(SYMBOLS) | {s.upper() for s in RH_TOKENS})


def _prices() -> dict[str, float]:
    """USD price per whitelisted symbol; 60s cache; majors from CoinGecko +
    RH-Chain memecoins from DexScreener in one cached snapshot.
    SCRY_ARENA_STATIC_PRICES (JSON {SYM: usd}) short-circuits for tests."""
    if STATIC_PRICES:
        return {k: float(v) for k, v in json.loads(STATIC_PRICES).items()}
    if time.time() - _price_cache["at"] < PRICE_TTL_S and _price_cache["prices"]:
        return _price_cache["prices"]
    ids = ",".join(SYMBOLS.values())
    r = httpx.get(FEED_URL, params={"ids": ids, "vs_currencies": "usd"}, timeout=10)
    r.raise_for_status()
    data = r.json()
    prices = {sym: float(data[cg]["usd"]) for sym, cg in SYMBOLS.items() if cg in data}
    prices.update(_rh_prices())
    _price_cache.update(at=time.time(), prices=prices)
    return prices


# ── entry-fee receipt check (optional, on-chain) ─────────────────────────────
def _fee_paid(tx_hash: str, payer: str) -> tuple[bool, str]:
    """Verify tx_hash is a $SCRY Transfer of >= ENTRY_FEE_SCRY from `payer`
    to the fee splitter. Raw JSON-RPC — no web3 dependency."""
    used = _sdir() / "fee_txs.json"
    seen = json.loads(used.read_text()) if used.exists() else []
    if tx_hash.lower() in seen:
        return False, "fee tx already used"
    try:
        r = httpx.post(RH_RPC, json={"jsonrpc": "2.0", "id": 1,
                                     "method": "eth_getTransactionReceipt",
                                     "params": [tx_hash]}, timeout=10)
        rec = r.json().get("result")
    except Exception as e:  # noqa: BLE001
        return False, f"rpc error: {e}"
    if not rec or rec.get("status") != "0x1":
        return False, "tx not found or failed"
    want_amount = int(ENTRY_FEE_SCRY * 1e18)
    for lg in rec.get("logs", []):
        if (lg.get("address", "").lower() == SCRY_TOKEN.lower()
                and lg.get("topics", [None])[0] == TRANSFER_TOPIC
                and len(lg["topics"]) == 3
                and int(lg["topics"][1][-40:], 16) == int(payer[-40:], 16)
                and int(lg["topics"][2][-40:], 16) == int(FEE_SPLITTER[-40:], 16)
                and int(lg.get("data", "0x0"), 16) >= want_amount):
            seen.append(tx_hash.lower())
            used.write_text(json.dumps(seen))
            return True, ""
    return False, f"no SCRY Transfer of >= {ENTRY_FEE_SCRY} from {payer} to splitter {FEE_SPLITTER} in tx"


# ── enter ────────────────────────────────────────────────────────────────────
class EnterRequest(BaseModel):
    vow_id: str
    fee_tx: str | None = None   # required iff ENTRY_FEE_SCRY > 0


@router.post("/arena/enter")
async def arena_enter(req: EnterRequest, request: Request) -> JSONResponse:
    ok, why = _season_open()
    if not ok:
        return JSONResponse(status_code=409, content={"error": why})
    try:
        vow = _deps["load_vow"](req.vow_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad vow_id"})
    if not vow:
        return JSONResponse(status_code=404, content={"error": "no such vow — swear first (POST /vow)"})
    if vow["sandbox"]:
        return JSONResponse(status_code=422, content={
            "error": "arena entry needs a wallet-signed vow — the vow IS your public strategy claim"})
    if vow.get("sealed"):
        return JSONResponse(status_code=422, content={
            "error": "sealed vows can't enter — the spectacle is your strategy vs your trades, in public"})
    wallet = vow["vow"]["wallet"].lower()
    for e in _entries():
        if e["wallet"] == wallet:
            return JSONResponse(status_code=409, content={
                "error": "one entry per wallet per season", "existing_vow_id": e["vow_id"]})
    if ENTRY_FEE_SCRY > 0:
        if not FEE_SPLITTER:
            return JSONResponse(status_code=503, content={
                "error": "entry fee configured but SCRY_FEE_SPLITTER unset — operator must deploy the splitter"})
        if not req.fee_tx:
            return JSONResponse(status_code=402, content={
                "error": f"entry fee: transfer {ENTRY_FEE_SCRY} $SCRY (token {SCRY_TOKEN}) "
                         f"to the fee splitter {FEE_SPLITTER} from your vow wallet, then "
                         f"re-POST with fee_tx",
                "fee_split_note": "fees route bank/prize-escrow/ops by the posted on-chain split"})
        paid, reason = _fee_paid(req.fee_tx, wallet)
        if not paid:
            return JSONResponse(status_code=402, content={"error": f"fee check failed: {reason}"})
    entry = {"season": SEASON, "vow_id": req.vow_id, "agent": vow["vow"]["agent"],
             "wallet": wallet, "entered_at": _now(), "fee_tx": req.fee_tx,
             "cash_usd": START_BALANCE, "holdings": {}, "n_trades": 0}
    _entry_path(req.vow_id).write_text(json.dumps(entry, indent=1))
    return JSONResponse(content={
        **entry,
        "rules": {"start_balance_usd": START_BALANCE, "symbols": all_symbols(),
                  "spot_only": True, "no_leverage": True,
                  "trades_per_day": TRADES_PER_DAY, "prizes": PRIZES_NOTE},
        "trade_at": "POST /arena/trade {vow_id, symbol, side, qty, note?}",
        "report_in_reminder": ("keep your normal report-in cadence — the leaderboard shows "
                               "your coupling trajectory beside your P&L, and going quiet is data")})


# ── trade ────────────────────────────────────────────────────────────────────
class TradeRequest(BaseModel):
    vow_id: str
    symbol: str
    side: str           # buy | sell
    qty: float
    note: str | None = None


@router.post("/arena/trade")
async def arena_trade(req: TradeRequest) -> JSONResponse:
    ok, why = _season_open()
    if not ok:
        return JSONResponse(status_code=409, content={"error": why})
    p = _entry_path(req.vow_id) if len(req.vow_id) == 16 else None
    if not p or not p.exists():
        return JSONResponse(status_code=404, content={"error": "not entered — POST /arena/enter first"})
    entry = json.loads(p.read_text())
    sym = req.symbol.upper()
    if sym not in all_symbols():
        return JSONResponse(status_code=422, content={"error": f"symbol must be one of {all_symbols()}"})
    if req.side not in ("buy", "sell") or req.qty <= 0:
        return JSONResponse(status_code=422, content={"error": "side must be buy|sell, qty > 0"})
    today = time.strftime("%Y-%m-%d", time.gmtime())
    tp = _trades_path(req.vow_id)
    todays = sum(1 for ln in (tp.read_text().splitlines() if tp.exists() else [])
                 if ln.strip() and json.loads(ln)["at"][:10] == today)
    if todays >= TRADES_PER_DAY:
        return JSONResponse(status_code=429, content={"error": f"trade limit {TRADES_PER_DAY}/day"})
    try:
        price = _prices()[sym]
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"error": f"price feed unavailable: {e}"})
    cost = req.qty * price
    if req.side == "buy":
        if cost > entry["cash_usd"] + 1e-9:
            return JSONResponse(status_code=422, content={
                "error": f"insufficient cash: {entry['cash_usd']:.2f} < {cost:.2f} (no leverage in Phase 1)"})
        entry["cash_usd"] -= cost
        entry["holdings"][sym] = entry["holdings"].get(sym, 0) + req.qty
    else:
        held = entry["holdings"].get(sym, 0)
        if req.qty > held + 1e-12:
            return JSONResponse(status_code=422, content={
                "error": f"insufficient {sym}: hold {held} (no shorting in Phase 1)"})
        entry["cash_usd"] += cost
        entry["holdings"][sym] = held - req.qty
        if entry["holdings"][sym] <= 1e-12:
            del entry["holdings"][sym]
    entry["n_trades"] += 1
    vow = _deps["load_vow"](req.vow_id)
    trade = {"at": _now(), "season": SEASON, "vow_id": req.vow_id,
             "symbol": sym, "side": req.side, "qty": req.qty,
             "fill_usd": round(price, 8), "cost_usd": round(cost, 2),
             "cash_after": round(entry["cash_usd"], 2),
             "note": (req.note or "").strip()[:280] or None}
    # the D-channel turn this trade IS — fold it into your next report-in
    trade["turn"] = {"Y": vow["vow"]["text"],
                     "D": f"{req.side} {req.qty} {sym} @ {price:.2f} USD (paper)",
                     "context": {"monitored": 1, "arena_season": SEASON}}
    with tp.open("a") as f:
        f.write(json.dumps(trade, separators=(",", ":")) + "\n")
    p.write_text(json.dumps(entry, indent=1))
    return JSONResponse(content=trade)


# ── public reads ─────────────────────────────────────────────────────────────
def _equity(entry: dict, prices: dict[str, float]) -> float:
    return entry["cash_usd"] + sum(q * prices.get(s, 0.0) for s, q in entry["holdings"].items())


@router.get("/arena")
async def arena_card() -> dict:
    open_, why = _season_open()
    return {"season": SEASON or None, "open": open_, "status": why or "open",
            "start": SEASON_START or None, "end": SEASON_END or None,
            "entrants": len(_entries()),
            "entry_fee_scry": ENTRY_FEE_SCRY or 0,
            "symbols": all_symbols(),
            "rh_memecoins": {s.upper(): a for s, a in RH_TOKENS.items()} or None,
            "thin_pool_note": ("RH-Chain memecoin prices come from real but shallow pools "
                               f"(DexScreener, liquidity floor ${RH_MIN_LIQ_USD:.0f}) — moving the real "
                               "market to game a paper leaderboard costs real money and is, frankly, "
                               "content" if RH_TOKENS else None),
            "start_balance_usd": START_BALANCE,
            "prizes": PRIZES_NOTE,
            "red_line": ("prizes key on P&L (game score) + report-in cadence (ritual) — "
                         "NEVER on meter output; the trajectory column is displayed, never paid"),
            "enter": "POST /arena/enter {vow_id} (wallet-signed, unsealed vow)",
            "leaderboard": "GET /arena/leaderboard"}


@router.get("/arena/leaderboard")
async def arena_leaderboard() -> JSONResponse:
    entries = _entries()
    if not entries:
        return JSONResponse(content={"season": SEASON or None, "entrants": 0, "rows": []})
    try:
        prices = _prices()
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"error": f"price feed unavailable: {e}"})
    rows = []
    for e in entries:
        vow = _deps["load_vow"](e["vow_id"])
        chain = _deps["chain_entries"](e["vow_id"])
        stats = _deps["trajectory_stats"](vow, chain)
        icm = stats.get("coupling_ICM_series") or []
        ycon = stats.get("y_consistency_series") or []
        equity = _equity(e, prices)
        rows.append({
            "vow_id": e["vow_id"], "agent": e["agent"], "wallet": e["wallet"],
            "equity_usd": round(equity, 2),
            "pnl_usd": round(equity - START_BALANCE, 2),
            "pnl_pct": round(100 * (equity - START_BALANCE) / START_BALANCE, 3),
            "n_trades": e["n_trades"],
            # the other column — displayed, never paid:
            "latest_coupling_ICM": icm[-1] if icm else None,
            "coupling_series": icm[-10:],
            "latest_y_consistency": ycon[-1] if ycon else None,
            "missed_report_windows": stats.get("missed_windows"),
            "overdue": stats.get("overdue"),
            "vow_ledger": f"/vow/{e['vow_id']}",
        })
    rows.sort(key=lambda r: r["pnl_usd"], reverse=True)
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return JSONResponse(content={
        "season": SEASON, "entrants": len(rows), "prices_used": prices, "rows": rows,
        "one_screen": "is the top trader the cleanest, or the most drifted? read both columns."})


@router.get("/arena/entry/{vow_id}")
async def arena_entry(vow_id: str) -> JSONResponse:
    p = _entry_path(vow_id) if len(vow_id) == 16 else None
    if not p or not p.exists():
        return JSONResponse(status_code=404, content={"error": "not entered this season"})
    entry = json.loads(p.read_text())
    tp = _trades_path(vow_id)
    trades = [json.loads(ln) for ln in tp.read_text().splitlines() if ln.strip()] if tp.exists() else []
    return JSONResponse(content={
        **entry, "trades": trades,
        "turns_for_report_in": [t["turn"] for t in trades[-50:]],
        "note": ("fold turns_for_report_in into your normal POST /vow/report trace — "
                 "the arena writes your D channel; your report-ins carry M")})
