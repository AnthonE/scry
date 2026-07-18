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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import vows  # noqa: E402
import augury  # noqa: E402
import arena  # noqa: E402

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
app.include_router(vows.router)
app.include_router(augury.router)
app.include_router(arena.router)
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

print(f"\nALL {PASS} CHECKS PASS")
