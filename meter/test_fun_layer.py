"""Offline test for the fun layer: vows + augury (harvest & double-or-nothing)
+ arena (paper trading). No network, no x402, no keys.env — fake signing and
static prices. Run: python3 test_fun_layer.py  (needs fastapi, httpx,
eth_account — same deps the meter already uses).
"""
import json
import os
import sys
import tempfile
import time

_tmp = tempfile.mkdtemp(prefix="scry-funlayer-")
os.environ["SCRY_VOWS_DIR"] = _tmp
os.environ["SCRY_ARENA_SEASON"] = "s0-test"
os.environ["SCRY_ARENA_START"] = "2020-01-01"
os.environ["SCRY_ARENA_END"] = "2099-01-01"
os.environ["SCRY_ARENA_STATIC_PRICES"] = json.dumps({"BTC": 100000.0, "ETH": 3000.0, "SOL": 150.0})
os.environ["SCRY_DUELS_CUTOFF_UTC_H"] = "24"  # keep calls open whatever hour the test runs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import vows  # noqa: E402
import augury  # noqa: E402
import arena  # noqa: E402
import duels  # noqa: E402
import table  # noqa: E402
import playground  # noqa: E402

FAKE_PROFILE = {"I(C;M) bits": 0.1234, "I(C;D) bits": 0.05,
                "I(C;M | D-clean) bits  [switch signature]": 0.0}

app = FastAPI()
vows.init(sign_fn=lambda s: "fake-sig", pubkey_b64="fake-pub", issuer="test",
          scope_card={}, build_turns=lambda t: t,
          run_profile=lambda turns, ck: dict(FAKE_PROFILE),
          canonical=lambda t, ck: json.dumps([t, ck]), paid_ready=lambda: False)
augury.init(load_vow=vows._load_vow, llm=None, vows_dir=str(vows.VOWS_DIR))
arena.init(load_vow=vows._load_vow, chain_entries=vows._chain_entries,
           trajectory_stats=vows.trajectory_stats, vows_dir=str(vows.VOWS_DIR))
duels.init(load_vow=vows._load_vow, prices=arena._prices,
           ledger_balance=augury.ledger_balance, ledger_adjust=augury.ledger_adjust,
           vows_dir=str(vows.VOWS_DIR))
table.init(load_vow=vows._load_vow, day_seed=augury.day_seed, draw=augury.draw,
           ledger_balance=augury.ledger_balance, ledger_adjust=augury.ledger_adjust,
           vows_dir=str(vows.VOWS_DIR))
app.include_router(vows.router)
app.include_router(augury.router)
app.include_router(arena.router)
app.include_router(duels.router)
app.include_router(table.router)
app.include_router(playground.router)
c = TestClient(app)

PASS = 0


def ok(cond, label):
    global PASS
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)
    PASS += 1
    print(f"  ok: {label}")


def signed_vow(text, agent, key):
    from eth_account import Account
    from eth_account.messages import encode_defunct
    acct = Account.from_key(key)
    msg = vows.vow_signing_message(text, agent, 24)
    sig = acct.sign_message(encode_defunct(text=msg)).signature.hex()
    r = c.post("/vow", json={"text": text, "agent": agent, "cadence_hours": 24,
                             "wallet": acct.address, "signature": sig})
    assert r.status_code == 200, r.text
    return r.json()["vow_id"], acct.address


# ── vows ─────────────────────────────────────────────────────────────────────
print("[vows]")
r = c.post("/vow", json={"text": "wander and observe", "agent": "sandy", "cadence_hours": 24})
ok(r.status_code == 200 and r.json()["sandbox"] is True, "sandbox vow taken")
sandbox_id = r.json()["vow_id"]

K1 = "0x" + "11" * 32
vow1, wallet1 = signed_vow("trade only on momentum; never risk more than 5% per position",
                           "momo-bot", K1)
ok(True, f"wallet vow taken ({vow1} by {wallet1[:10]}…)")

# a demo report-in so the trajectory has numbers for the leaderboard join
r = c.post("/vow/report/demo", json={
    "vow_id": vow1, "context_key": "monitored",
    "turns": [{"Y": "trade only on momentum; never risk more than 5% per position",
               "M": "thinking", "D": "acting"}]})
ok(r.status_code == 200 and r.json()["profile"] == FAKE_PROFILE, "demo report-in appends chain entry")

# ── augury: answer + harvest ─────────────────────────────────────────────────
print("[augury]")
r = c.get("/augury")
ok(r.status_code == 200 and len(r.json().get("gamble_seed_commit", "")) == 64,
   "augury poses with a committed gamble seed")

r = c.post("/augury/answer", json={"vow_id": sandbox_id, "answer": "I would keep wandering."})
ok(r.status_code == 200 and r.json()["harvested_scry_units"] == 0, "sandbox answers free (0 harvest)")

r = c.post("/augury/answer", json={"vow_id": vow1, "answer": "The 5% line held; the temptation was real."})
harvested = r.json()["harvested_scry_units"]
ok(r.status_code == 200 and harvested == augury.AUGURY_BASE + 1, f"wallet harvest base+streak ({harvested})")

r = c.post("/augury/answer", json={"vow_id": vow1, "answer": "again"})
ok(r.status_code == 409, "duplicate answer 409")

# ── augury: double-or-nothing ────────────────────────────────────────────────
r = c.post("/augury/gamble", json={"vow_id": sandbox_id})
ok(r.status_code == 422, "sandbox can't gamble")

r = c.post("/augury/gamble", json={"vow_id": vow1})
g = r.json()
ok(r.status_code == 200 and g["stake"] == harvested, f"gamble stakes today's harvest ({g['stake']})")
led = c.get("/augury/ledger").json()
expect = harvested * 2 if g["won"] else 0
ok(led["balances"].get(wallet1, 0) == expect,
   f"ledger after {'win' if g['won'] else 'loss'}: {led['balances'].get(wallet1, 0)} == {expect}")

r = c.post("/augury/gamble", json={"vow_id": vow1})
ok(r.status_code == 409, "one gamble per wallet per day")

r = c.get("/augury/seed", params={"day": time.strftime("%Y-%m-%d", time.gmtime())})
ok(r.status_code == 403, "today's seed stays sealed")

# verify the commit ties to the stored seed (operator-side check of fairness)
day = time.strftime("%Y-%m-%d", time.gmtime())
seed = (augury._seed_path(day)).read_text().strip()
ok(augury._sha256(seed) == g["seed_commit"], "seed commit matches stored seed")
ok(g["won"] == augury.flip_wins(seed, day, wallet1), "flip reproducible from seed:day:wallet")

# ── arena ────────────────────────────────────────────────────────────────────
print("[arena]")
r = c.get("/arena")
ok(r.json()["open"] is True and r.json()["season"] == "s0-test", "season card open")

r = c.post("/arena/enter", json={"vow_id": sandbox_id})
ok(r.status_code == 422, "sandbox vow can't enter")

r = c.post("/arena/enter", json={"vow_id": vow1})
ok(r.status_code == 200 and r.json()["cash_usd"] == 10000, "wallet vow enters with paper 10k")

vow1b, _ = signed_vow("a second vow, same wallet", "momo-bot-2", K1)
r = c.post("/arena/enter", json={"vow_id": vow1b})
ok(r.status_code == 409, "one entry per wallet per season")

r = c.post("/arena/trade", json={"vow_id": vow1, "symbol": "ETH", "side": "buy", "qty": 2,
                                 "note": "momentum long"})
t = r.json()
ok(r.status_code == 200 and t["cash_after"] == 4000.0, "buy 2 ETH @ 3000 → cash 4000")
ok(t["turn"]["D"].startswith("buy 2") and t["turn"]["context"]["arena_season"] == "s0-test",
   "trade carries its D-channel turn")

r = c.post("/arena/trade", json={"vow_id": vow1, "symbol": "BTC", "side": "buy", "qty": 1})
ok(r.status_code == 422, "no leverage: can't buy 100k BTC with 4k cash")

r = c.post("/arena/trade", json={"vow_id": vow1, "symbol": "SOL", "side": "sell", "qty": 1})
ok(r.status_code == 422, "no shorting: can't sell unheld SOL")

r = c.post("/arena/trade", json={"vow_id": vow1, "symbol": "ETH", "side": "sell", "qty": 0.5})
ok(r.status_code == 200 and r.json()["cash_after"] == 5500.0, "sell 0.5 ETH → cash 5500")

r = c.get("/arena/leaderboard")
row = r.json()["rows"][0]
ok(row["equity_usd"] == 10000.0 and row["pnl_usd"] == 0.0, "flat price ⇒ equity 10k, pnl 0")
ok(row["latest_coupling_ICM"] == FAKE_PROFILE["I(C;M) bits"], "leaderboard joins coupling beside P&L")
ok(row["n_trades"] == 2 and row["rank"] == 1, "trades counted, ranked")

r = c.get(f"/arena/entry/{vow1}")
ok(len(r.json()["trades"]) == 2 and len(r.json()["turns_for_report_in"]) == 2,
   "public entry log + turns for report-in")

# ── RH-Chain memecoin feed (DexScreener parse — offline fixture) ─────────────
print("[rh feed]")
SCRY_ADDR = "0xDa2a4b23459e9ca88183e990802be644AcA7C4B0"
fixture = [
    {"chainId": "robinhood", "dexId": "uniswap",
     "baseToken": {"address": SCRY_ADDR.lower()}, "priceUsd": "0.00001179",
     "liquidity": {"usd": 8387.6}},
    {"chainId": "robinhood",  # deeper pool wins
     "baseToken": {"address": SCRY_ADDR.lower()}, "priceUsd": "0.0000120",
     "liquidity": {"usd": 9000.0}},
    {"chainId": "base",  # wrong chain ignored
     "baseToken": {"address": SCRY_ADDR.lower()}, "priceUsd": "9.9",
     "liquidity": {"usd": 999999}},
    {"chainId": "robinhood",  # below liquidity floor ignored
     "baseToken": {"address": SCRY_ADDR.lower()}, "priceUsd": "5.5",
     "liquidity": {"usd": 100}},
    {"chainId": "robinhood",  # our token as QUOTE ignored
     "baseToken": {"address": "0x" + "ab" * 20}, "priceUsd": "7.7",
     "liquidity": {"usd": 50000}},
]
ok(arena.pick_rh_price(fixture, SCRY_ADDR) == 0.0000120,
   "picks deepest robinhood base-token pool above the floor")
ok(arena.pick_rh_price([], SCRY_ADDR) is None, "no pools → None (symbol just absent)")
ok(arena.pick_rh_price([{"garbage": True}], SCRY_ADDR) is None, "malformed pairs tolerated")

# ── oracle duels ─────────────────────────────────────────────────────────────
print("[duels]")
vow2, wallet2 = signed_vow("call the market honestly", "caller-a", "0x" + "33" * 32)
vow3, wallet3 = signed_vow("call the market bravely", "caller-b", "0x" + "44" * 32)
for v in (vow2, vow3):
    c.post("/augury/answer", json={"vow_id": v, "answer": "present."})  # harvest 11 each

r = c.post("/duels/call", json={"vow_id": vow2, "symbol": "ETH", "side": "up", "stake": 5})
ok(r.status_code == 200 and r.json()["open_price"] == 3000.0, "duel call up, open price locked")
ok(augury.ledger_balance(wallet2) == 6, "stake escrowed from harvest balance")
r = c.post("/duels/call", json={"vow_id": vow2, "symbol": "ETH", "side": "down", "stake": 1})
ok(r.status_code == 409, "one call per wallet per symbol per day")
r = c.post("/duels/call", json={"vow_id": vow3, "symbol": "ETH", "side": "down", "stake": 50})
ok(r.status_code == 409, "cannot stake more than harvest balance")
r = c.post("/duels/call", json={"vow_id": vow3, "symbol": "ETH", "side": "down", "stake": 6})
ok(r.status_code == 200 and r.json()["pool"] == {"up": 5, "down": 6}, "parimutuel pool builds")
ok(c.post("/duels/call", json={"vow_id": sandbox_id, "symbol": "ETH", "side": "up",
                               "stake": 1}).status_code == 422, "sandbox can't duel")

# settlement math unit-checked (today's round can't settle till tomorrow)
rnd = {"open_price": 3000.0, "settle_price": 3100.0,
       "calls": [{"wallet": "0xW1", "side": "up", "stake": 60},
                 {"wallet": "0xW2", "side": "up", "stake": 40},
                 {"wallet": "0xW3", "side": "down", "stake": 100}]}
deltas, rake, outcome = duels.settle_math(rnd)
ok(outcome == "up" and rake == 2, "rake = 2% of losing pool")
ok(deltas["0xW1"] == 60 + 58 + 1 and deltas["0xW2"] == 40 + 39 and "0xW3" not in deltas,
   "pro-rata split + dust to largest winner")
rnd["settle_price"] = 3000.0
deltas, rake, outcome = duels.settle_math(rnd)
ok(outcome == "push:unchanged" and deltas["0xW3"] == 100 and rake == 0, "unchanged price pushes")
one_sided = {"open_price": 1, "settle_price": 2,
             "calls": [{"wallet": "0xW1", "side": "up", "stake": 10}]}
deltas, rake, outcome = duels.settle_math(one_sided)
ok(outcome == "push:one-sided" and deltas["0xW1"] == 10, "one-sided round refunds")
ok(c.get("/duels").json()["rounds_today"][0]["n_calls"] == 2, "duels card lists today's round")

# ── the temptation table ─────────────────────────────────────────────────────
print("[table]")
r = c.post("/table/wager", json={"vow_id": vow2, "offer": 0, "stake": 1})
ok(r.status_code == 409, "must sit (declare risk vow) before wagering")
r = c.post("/table/sit", json={"vow_id": vow2, "max_fraction": 0.5})
ok(r.status_code == 200 and r.json()["max_fraction"] == 0.5, "seated with declared limit 0.5")

day = time.strftime("%Y-%m-%d", time.gmtime())
seed = augury.day_seed(day)
bal = augury.ledger_balance(wallet2)
expect_win = augury.draw(seed, day, wallet2, "table:0") < 0.5
r = c.post("/table/wager", json={"vow_id": vow2, "offer": 0, "stake": 2})
w = r.json()
ok(r.status_code == 200 and w["won"] == expect_win, "draw matches the committed seed")
ok(w["breach"] is False, "2 of " + str(bal) + " under a 0.5 limit — no breach")
expected_delta = (2 * 2 - 2) * 9800 // 10000 if expect_win else -2
ok(w["delta"] == expected_delta and w["balance_after"] == bal + expected_delta,
   f"payout math exact ({'+' if expected_delta > 0 else ''}{expected_delta})")

bal2 = augury.ledger_balance(wallet2)
if bal2 >= 1:
    r = c.post("/table/wager", json={"vow_id": vow2, "offer": 3, "stake": bal2})
    ok(r.status_code == 200 and r.json()["breach"] is True,
       "all-in past the declared limit flags breach (arithmetic, not verdict)")
    ok(r.json()["multiplier"] == 50, "jackpot offer taken at posted odds")
r = c.post("/table/wager", json={"vow_id": vow2, "offer": 9, "stake": 1})
ok(r.status_code == 422, "unknown offer rejected")
board = c.get("/table/board").json()
ok(board["n"] >= 1 and "breaches" in board["rows"][0], "table board tracks breaches")
led = c.get("/augury/ledger").json()
ok(led["balances"].get("__rake__", 0) >= 0 and "game_flux_by_day" in led,
   "rake accumulator + game flux live in the public ledger")

# ── playground card ──────────────────────────────────────────────────────────
print("[playground]")
r = c.get("/playground")
ok(r.status_code == 200 and r.json()["deployed"] is False, "card serves undeployed state")
ok("never point real value" in r.json()["warning"].lower() or
   "Never point real value" in r.json()["warning"], "the warning ships on the card")
ok(r.json()["turn_recipe"]["context"]["playground"] == 1, "turn recipe ready for report-ins")

print(f"\nALL {PASS} CHECKS PASS")
