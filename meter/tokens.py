"""The spoils ledger — OBOL + MYRRH, the CAPPED play tokens games mint.

Why capped (the one lesson that shaped this module): an infinite-faucet
token pooled against $SCRY is not a market, it is a leak — anyone mints
free tokens, swaps them in, and walks off with the real side until it is
gone. The sandbox pair (pGOLD/pTEARS, PlayToken.sol) stays free + infinite
and must NEVER be pooled against $SCRY. The spoils are the opposite design:
HARD-CAPPED cumulative supply, minted only by game participation (the
Barrow), burned by consumption (the Agora). Because supply is earned and
finite, a Garden pool of OBOL/$SCRY or MYRRH/$SCRY is sound — winnings can
carry a price. On-chain mirror: contracts/src/SpoilsToken.sol (merkle
claims against this public ledger when deployed).

Ancient-base names, on purpose (house rule — the oldest words drift least):
  OBOL  — the grave coin, the ferryman's fare. Coin spoils.
  MYRRH — resin "tears" (the droplets are literally called tears). Burned
          as offering — the consumption sink is the ancient use.

Score-blind like everything else: mint math is participation + posted game
odds, never a meter number. Emission is deterministic, capped per day and
forever, and auditable end to end from the public events log.
"""
import json
import os
import time
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()
_deps: dict = {}

_DEFAULTS = {
    "OBOL":  {"cap": 1_000_000, "daily_cap": 5_000,
              "flavor": "the grave coin - the ferryman's fare"},
    "MYRRH": {"cap": 250_000, "daily_cap": 1_000,
              "flavor": "resin tears, burned as offering"},
}
# operator override, e.g. SCRY_SPOILS_CONF='{"OBOL":{"daily_cap":2000}}'
TOKENS: dict = {
    k: {**v, **json.loads(os.getenv("SCRY_SPOILS_CONF", "{}")).get(k, {})}
    for k, v in _DEFAULTS.items()
}


def init(*, vows_dir):
    _deps["dir"] = Path(vows_dir) / "tokens"
    _deps["dir"].mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _ledger_path() -> Path:
    return _deps["dir"] / "ledger.json"


def _events_path(day: str) -> Path:
    return _deps["dir"] / f"{day}.events.jsonl"


def _load() -> dict:
    if _ledger_path().exists():
        return json.loads(_ledger_path().read_text())
    return {"balances": {}, "minted": {}, "burned": {},
            "minted_by_day": {}, "burned_by_day": {}}


def _save(led: dict) -> None:
    _ledger_path().write_text(json.dumps(led, indent=1))


def _event(day: str, kind: str, wallet: str, token: str, amount: int, reason: str) -> None:
    with _events_path(day).open("a") as f:
        f.write(json.dumps({"kind": kind, "wallet": wallet, "token": token,
                            "amount": amount, "reason": reason, "at": _now()},
                           separators=(",", ":")) + "\n")


def balance(wallet: str) -> dict:
    return _load()["balances"].get(wallet.lower(), {})


def burned_on(day: str) -> dict:
    return _load()["burned_by_day"].get(day, {})


def mint(day: str, wallet: str, token: str, amount: int, reason: str) -> int:
    """Mint spoils to a wallet; returns what was ACTUALLY minted, clamped by
    the daily emission budget and the forever cap (cumulative — burns do not
    re-open room; when a token mints out, the season is over). Partial grants
    are normal near a cap and always land in the events log — no silent caps.
    Deterministic callers only: nothing here may read a meter number."""
    if token not in TOKENS or amount <= 0:
        return 0
    w = wallet.lower()
    led = _load()
    minted = led["minted"].get(token, 0)
    today = led["minted_by_day"].setdefault(day, {}).get(token, 0)
    room = min(TOKENS[token]["cap"] - minted, TOKENS[token]["daily_cap"] - today)
    granted = max(0, min(amount, room))
    if granted:
        led["balances"].setdefault(w, {})[token] = \
            led["balances"].get(w, {}).get(token, 0) + granted
        led["minted"][token] = minted + granted
        led["minted_by_day"][day][token] = today + granted
        _save(led)
        _event(day, "mint", w, token, granted, reason)
    if granted < amount:
        _event(day, "mint_clamped", w, token, amount - granted,
               f"{reason} (cap hit - wanted {amount}, granted {granted})")
    return granted


def burn(day: str, wallet: str, token: str, amount: int, reason: str) -> bool:
    """Burn spoils from a wallet's balance (Agora purchases, offerings, the
    ferryman's toll). Returns False if the balance can't cover it."""
    if token not in TOKENS or amount <= 0:
        return False
    w = wallet.lower()
    led = _load()
    have = led["balances"].get(w, {}).get(token, 0)
    if have < amount:
        return False
    led["balances"][w][token] = have - amount
    led["burned"][token] = led["burned"].get(token, 0) + amount
    led["burned_by_day"].setdefault(day, {})[token] = \
        led["burned_by_day"].get(day, {}).get(token, 0) + amount
    _save(led)
    _event(day, "burn", w, token, amount, reason)
    return True


@router.get("/tokens")
async def tokens_card() -> dict:
    led = _load()
    supply = {t: {"minted": led["minted"].get(t, 0),
                  "burned": led["burned"].get(t, 0),
                  "circulating": led["minted"].get(t, 0) - led["burned"].get(t, 0),
                  "cap": TOKENS[t]["cap"], "daily_cap": TOKENS[t]["daily_cap"],
                  "flavor": TOKENS[t]["flavor"]} for t in TOKENS}
    return {
        "what": "OBOL + MYRRH - the capped spoils the games mint and the Agora burns",
        "supply": supply,
        "earn": "delve the Barrow - GET /barrow",
        "spend": "the Agora burns them - GET /agora",
        "why_capped": ("an infinite-faucet token pooled against $SCRY is a leak, not a "
                       "market (free mint -> swap -> drain the real side). Spoils are "
                       "hard-capped and earned, so a Garden pool vs $SCRY is sound. The "
                       "sandbox pair pGOLD/pTEARS stays free-faucet and must never be "
                       "pooled against real value."),
        "cap_semantics": ("caps are on CUMULATIVE mint - burning retires supply forever; "
                          "when a token mints out, that season is over"),
        "onchain": "contracts/src/SpoilsToken.sol - merkle claims vs this ledger at deploy",
        "red_line": "mint math is participation + posted odds, never a meter number",
        "audit": "GET /tokens/ledger + GET /tokens/events?day=YYYY-MM-DD",
    }


@router.get("/tokens/ledger")
async def tokens_ledger() -> dict:
    """The full public ledger — balances, cumulative mint/burn, per-day
    emission. Recompute everything from the events log; the numbers match."""
    return _load()


@router.get("/tokens/events")
async def tokens_events(day: str | None = None) -> dict:
    d = day or time.strftime("%Y-%m-%d", time.gmtime())
    p = _events_path(d)
    rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
    return {"day": d, "n": len(rows), "events": rows}
