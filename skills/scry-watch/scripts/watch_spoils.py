"""Spoils-economy watchdog: are sinks keeping pace, is the pool draining?

The DFK balancing duty (POOLS.md 3.5, GARDENS.md 3) as a cron: emission is
sound while sinks keep pace and the pool's quote side holds. This script
reads the free public ledger for the mint/burn balance, and (optionally)
one eth_call for the pool's quote-token balance. It alerts; the levers -
granary caps, rewardPerSecond, sink prices - stay deliberate human acts.
Script-only, zero LLM tokens, stdlib urllib, no keys.

Env:
  SCRY_BASE                meter base URL (default https://scry.moreright.xyz/api)
  SCRY_SPOILS_WINDOW_DAYS  sink-ratio lookback (default 7)
  SCRY_SPOILS_MIN_MINT     window mint noise floor before the ratio can alert
                           (default 100 coins; below it, quiet)
  SCRY_SPOILS_SINK_FLOOR   alert when burned/minted over the window falls
                           below this (default 0.25)
  SCRY_SPOILS_DAY_MAX      alert when any single day mints more than this
                           many coins of one token (default 0 = off)
  SCRY_POOL_ADDR           pool address to drain-watch (default unset = skip)
  SCRY_POOL_QUOTE          quote-token ERC-20 address (required with POOL_ADDR)
  SCRY_POOL_QUOTE_MIN      alert when the pool's quote balance drops below
                           this many tokens, human units (required with POOL_ADDR)
  SCRY_POOL_QUOTE_DECIMALS quote token decimals (default 18)
  SCRY_RPC                 chain RPC (default https://rpc.mainnet.chain.robinhood.com)

Exit 0 quiet, 1 on any ALERT line.
"""
import json
import os
import sys
import urllib.request
from datetime import date, timedelta

BASE = os.getenv("SCRY_BASE", "https://scry.moreright.xyz/api").rstrip("/")
WINDOW = int(os.getenv("SCRY_SPOILS_WINDOW_DAYS", "7"))
MIN_MINT = float(os.getenv("SCRY_SPOILS_MIN_MINT", "100"))
SINK_FLOOR = float(os.getenv("SCRY_SPOILS_SINK_FLOOR", "0.25"))
DAY_MAX = float(os.getenv("SCRY_SPOILS_DAY_MAX", "0"))
POOL = os.getenv("SCRY_POOL_ADDR", "").strip()
QUOTE = os.getenv("SCRY_POOL_QUOTE", "").strip()
QUOTE_MIN = os.getenv("SCRY_POOL_QUOTE_MIN", "").strip()
QUOTE_DEC = int(os.getenv("SCRY_POOL_QUOTE_DECIMALS", "18"))
RPC = os.getenv("SCRY_RPC", "https://rpc.mainnet.chain.robinhood.com")


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.load(r)


def quote_balance() -> float:
    """token.balanceOf(pool) by hand-encoded eth_call - no web3 dependency."""
    data = "0x70a08231" + POOL.lower().replace("0x", "").rjust(64, "0")
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                       "params": [{"to": QUOTE, "data": data}, "latest"]}).encode()
    req = urllib.request.Request(RPC, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        out = json.load(r)
    if "result" not in out:
        raise RuntimeError(out.get("error") or "no result")
    return int(out["result"], 16) / 10 ** QUOTE_DEC


def main() -> int:
    alerts = []

    # -- sinks vs emission, from the public ledger (works pre-chain) --------
    try:
        led = get_json(f"{BASE}/tokens/ledger")
    except Exception as e:  # noqa: BLE001
        alerts.append(f"tokens ledger unreachable ({e})")
        led = None
    if led is not None:
        days = [(date.today() - timedelta(days=i)).isoformat() for i in range(WINDOW)]
        tokens = set()
        for day in days:
            tokens |= set(led.get("minted_by_day", {}).get(day, {}))
            tokens |= set(led.get("burned_by_day", {}).get(day, {}))
        if not tokens:
            print(f"note: no mint/burn activity in the last {WINDOW} days; quiet")
        for tok in sorted(tokens):
            minted = sum(led.get("minted_by_day", {}).get(d, {}).get(tok, 0) for d in days)
            burned = sum(led.get("burned_by_day", {}).get(d, {}).get(tok, 0) for d in days)
            if DAY_MAX > 0:
                for d in days:
                    m = led.get("minted_by_day", {}).get(d, {}).get(tok, 0)
                    if m > DAY_MAX:
                        alerts.append(f"{tok}: {d} minted {m:g} > day max {DAY_MAX:g}")
            if minted >= MIN_MINT and burned < minted * SINK_FLOOR:
                alerts.append(
                    f"{tok}: sinks lagging - {WINDOW}d minted {minted:g}, "
                    f"burned {burned:g} (ratio {burned / minted:.2f} < {SINK_FLOOR})")

    # -- pool quote-side drain (armed only when a pool is configured) -------
    if POOL:
        if not (QUOTE and QUOTE_MIN):
            alerts.append("SCRY_POOL_ADDR set but SCRY_POOL_QUOTE/QUOTE_MIN missing")
        else:
            try:
                bal = quote_balance()
                if bal < float(QUOTE_MIN):
                    alerts.append(
                        f"pool {POOL[:10]}..: quote side {bal:g} < floor {QUOTE_MIN}")
            except Exception as e:  # noqa: BLE001
                alerts.append(f"pool {POOL[:10]}..: quote balance unreadable ({e})")
    else:
        print("note: SCRY_POOL_ADDR unset; drain watch skipped")

    for a in alerts:
        print(f"ALERT: {a}")
    return 1 if alerts else 0


if __name__ == "__main__":
    sys.exit(main())
