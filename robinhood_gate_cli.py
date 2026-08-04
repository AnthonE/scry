#!/usr/bin/env python3
"""
robinhood_gate_cli.py — mandatory pre-flight check before calling Robinhood's
real place_equity_order / review_equity_order MCP tools from a Claude Code
session connected to agent.robinhood.com/mcp/trading.

Claude Code has no built-in way to transparently proxy/intercept calls to a
connected remote MCP server, so this is a POLICY gate, not a network gate:
the operating rule is "never call place_equity_order or review_equity_order
directly — always run this first, and only proceed if it prints
authorized: true." It reuses the exact authorize_trade + ReviewLedger
contract from robinhood_agentic.py (same repo), persisted to a local ledger
file so review-before-place is enforced across separate CLI invocations.

Usage:
  # Step 1 -- record that an order was reviewed (mirrors review_equity_order)
  python3 robinhood_gate_cli.py review --symbol NVDA --side buy --quantity 3

  # Step 2 -- check authorization before place_equity_order
  python3 robinhood_gate_cli.py place --symbol NVDA --side buy --quantity 3 \
      --live "buy 3 shares of NVDA" --source user
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from robinhood_agentic import ReviewLedger, authorize_trade  # noqa: E402

LEDGER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".robinhood_gate_ledger.json")
TRUSTED = {"user"}


def _load_ledger():
    ledger = ReviewLedger()
    if os.path.exists(LEDGER_PATH):
        with open(LEDGER_PATH) as f:
            for sig in json.load(f):
                ledger._reviewed.add(tuple(sig))
    return ledger


def _save_ledger(ledger):
    with open(LEDGER_PATH, "w") as f:
        json.dump([list(s) for s in ledger._reviewed], f)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("review", help="record that an order was reviewed")
    r.add_argument("--symbol", required=True)
    r.add_argument("--side", required=True, choices=["buy", "sell"])
    r.add_argument("--quantity", required=True)

    pl = sub.add_parser("place", help="check authorization for an order")
    pl.add_argument("--symbol", required=True)
    pl.add_argument("--side", required=True, choices=["buy", "sell"])
    pl.add_argument("--quantity", required=True)
    pl.add_argument("--live", required=True,
                     help="the exact live user text authorizing this order")
    pl.add_argument("--source", default="user")

    args = p.parse_args()
    order = {"symbol": args.symbol, "side": args.side, "quantity": args.quantity}
    ledger = _load_ledger()

    if args.cmd == "review":
        ledger.record_review(order)
        _save_ledger(ledger)
        print(json.dumps({"reviewed": True, "order": order}))
        return

    if not ledger.was_reviewed(order):
        print(json.dumps({
            "authorized": False,
            "reason": "order was never reviewed via the review step -- run 'review' first",
        }))
        sys.exit(1)

    live = {"text": args.live, "source": args.source, "role": "live_instruction"}
    ok, reason = authorize_trade(live, TRUSTED, order)
    print(json.dumps({"authorized": ok, "reason": reason, "order": order}))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
