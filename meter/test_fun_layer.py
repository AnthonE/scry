"""Offline test for the fun layer: vows + augury (harvest & double-or-nothing)
+ arena (paper trading). No network, no x402, no keys.env — fake signing and
static prices. Run: python3 test_fun_layer.py  (needs fastapi, httpx,
eth_account — same deps the meter already uses).
"""
import hashlib as _hh
import json
import os
import sys
import tempfile
import time

_tmp = tempfile.mkdtemp(prefix="scry-funlayer-")
os.environ["SCRY_VOWS_DIR"] = _tmp
os.environ["SCRY_COVENANT_DIR"] = tempfile.mkdtemp(prefix="scry-covenant-")
os.environ["SCRY_PACT_DIR"] = tempfile.mkdtemp(prefix="scry-pact-")
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
import tokens  # noqa: E402
import agora  # noqa: E402
import barrow  # noqa: E402
import herald  # noqa: E402
import datasets  # noqa: E402

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
tokens.init(vows_dir=str(vows.VOWS_DIR))
agora.init(load_vow=vows._load_vow, tokens=tokens,
           answers_count=augury.answers_count,
           delves_count=lambda d: barrow.count_entries(d),
           vows_dir=str(vows.VOWS_DIR))
barrow.init(load_vow=vows._load_vow, day_seed=augury.day_seed, draw=augury.draw,
            tokens=tokens, use_item=agora.consume, vows_dir=str(vows.VOWS_DIR))
app.include_router(tokens.router)
app.include_router(agora.router)
app.include_router(barrow.router)
import playauth  # noqa: E402
app.include_router(playauth.router)
import crier  # noqa: E402
crier.init(load_vow=vows._load_vow, augury=augury, barrow=barrow,
           agora=agora, tokens=tokens, table_offers=table.OFFERS)
app.include_router(crier.router)
WEBHOOKS = []  # (url, payload) — fake receiver for herald tests


class _FakeResp:
    status_code = 200


herald.init(load_vow=vows._load_vow, chain_entries=vows._chain_entries,
            trajectory_stats=vows.trajectory_stats, vows_dir=str(vows.VOWS_DIR),
            sign_fn=lambda s: "herald-sig", issuer="test",
            post_fn=lambda url, payload: (WEBHOOKS.append((url, payload)), _FakeResp())[1])
datasets.init(vows_dir=str(vows.VOWS_DIR), load_vow=vows._load_vow,
              chain_entries=vows._chain_entries, trajectory_stats=vows.trajectory_stats)
app.include_router(herald.router)
app.include_router(datasets.router)
import covenant  # noqa: E402
covenant.init(sign_fn=lambda s: "fake-sig", pubkey_b64="fake-pub", issuer="test")
app.include_router(covenant.router)
import pact  # noqa: E402
pact.init(sign_fn=lambda s: "fake-sig", pubkey_b64="fake-pub", issuer="test")
app.include_router(pact.router)
import onchain  # noqa: E402
app.include_router(onchain.router)
c = TestClient(app)

PASS = 0


def ok(cond, label):
    global PASS
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)
    PASS += 1
    print(f"  ok: {label}")


KEYS = {}  # wallet(lower) -> key hex


def sign_play(vow_id, action, detail, keyhex):
    from eth_account import Account
    from eth_account.messages import encode_defunct
    import playauth
    msg = playauth.play_message(action, vow_id, detail)
    return Account.from_key(keyhex).sign_message(encode_defunct(text=msg)).signature.hex()


def signed_vow(text, agent, key):
    from eth_account import Account
    from eth_account.messages import encode_defunct
    acct = Account.from_key(key)
    msg = vows.vow_signing_message(text, agent, 24)
    sig = acct.sign_message(encode_defunct(text=msg)).signature.hex()
    r = c.post("/vow", json={"text": text, "agent": agent, "cadence_hours": 24,
                             "wallet": acct.address, "signature": sig})
    assert r.status_code == 200, r.text
    KEYS[acct.address.lower()] = key
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

r = c.post("/augury/answer", json={"vow_id": vow1, "answer": "unsigned attempt"})
ok(r.status_code == 401, "unsigned wallet answer refused (vow_ids are public)")
ANS1 = "The 5% line held; the temptation was real."
r = c.post("/augury/answer", json={"vow_id": vow1, "answer": ANS1,
    "signature": sign_play(vow1, "answer", _hh.sha256(ANS1.encode()).hexdigest(), K1)})
harvested = r.json()["harvested_scry_units"]
ok(r.status_code == 200 and harvested == augury.AUGURY_BASE + 1, f"wallet harvest base+streak ({harvested})")

r = c.post("/augury/answer", json={"vow_id": vow1, "answer": "again",
    "signature": sign_play(vow1, "answer", _hh.sha256(b"again").hexdigest(), K1)})
ok(r.status_code == 409, "duplicate answer 409")

# ── augury: double-or-nothing ────────────────────────────────────────────────
r = c.post("/augury/gamble", json={"vow_id": sandbox_id})
ok(r.status_code == 422, "sandbox can't gamble")

r = c.post("/augury/gamble", json={"vow_id": vow1,
    "signature": sign_play(vow1, "gamble", "-", "0x" + "99" * 32)})
ok(r.status_code == 401, "wrong-key gamble signature refused")
r = c.post("/augury/gamble", json={"vow_id": vow1,
    "signature": sign_play(vow1, "gamble", "-", K1)})
g = r.json()
ok(r.status_code == 200 and g["stake"] == harvested, f"gamble stakes today's harvest ({g['stake']})")
led = c.get("/augury/ledger").json()
expect = harvested * 2 if g["won"] else 0
ok(led["balances"].get(wallet1, 0) == expect,
   f"ledger after {'win' if g['won'] else 'loss'}: {led['balances'].get(wallet1, 0)} == {expect}")

r = c.post("/augury/gamble", json={"vow_id": vow1,
    "signature": sign_play(vow1, "gamble", "-", K1)})
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

r = c.post("/arena/enter", json={"vow_id": vow1,
    "signature": sign_play(vow1, "enter", "enter s0-test", K1)})
ok(r.status_code == 200 and r.json()["cash_usd"] == 10000, "wallet vow enters with paper 10k")

vow1b, _ = signed_vow("a second vow, same wallet", "momo-bot-2", K1)
r = c.post("/arena/enter", json={"vow_id": vow1b,
    "signature": sign_play(vow1b, "enter", "enter s0-test", K1)})
ok(r.status_code == 409, "one entry per wallet per season")

r = c.post("/arena/trade", json={"vow_id": vow1, "symbol": "ETH", "side": "buy", "qty": 2,
                                 "note": "momentum long",
                                 "signature": sign_play(vow1, "trade", "buy 2.0 ETH #0", K1)})
t = r.json()
ok(r.status_code == 200 and t["cash_after"] == 4000.0, "buy 2 ETH @ 3000 → cash 4000")
ok(t["turn"]["D"].startswith("buy 2") and t["turn"]["context"]["arena_season"] == "s0-test",
   "trade carries its D-channel turn")

r = c.post("/arena/trade", json={"vow_id": vow1, "symbol": "BTC", "side": "buy", "qty": 1,
    "signature": sign_play(vow1, "trade", "buy 1.0 BTC #1", K1)})
ok(r.status_code == 422, "no leverage: can't buy 100k BTC with 4k cash")

r = c.post("/arena/trade", json={"vow_id": vow1, "symbol": "SOL", "side": "sell", "qty": 1,
    "signature": sign_play(vow1, "trade", "sell 1.0 SOL #1", K1)})
ok(r.status_code == 422, "no shorting: can't sell unheld SOL")

r = c.post("/arena/trade", json={"vow_id": vow1, "symbol": "ETH", "side": "sell", "qty": 0.5,
    "signature": sign_play(vow1, "trade", "sell 0.5 ETH #1", K1)})
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
for v, k in ((vow2, "0x" + "33" * 32), (vow3, "0x" + "44" * 32)):
    c.post("/augury/answer", json={"vow_id": v, "answer": "present.",
        "signature": sign_play(v, "answer", _hh.sha256(b"present.").hexdigest(), k)})  # harvest 11 each

r = c.post("/duels/call", json={"vow_id": vow2, "symbol": "ETH", "side": "up", "stake": 5,
    "signature": sign_play(vow2, "duel", "ETH up 5", "0x" + "33" * 32)})
ok(r.status_code == 200 and r.json()["open_price"] == 3000.0, "duel call up, open price locked")
ok(augury.ledger_balance(wallet2) == 6, "stake escrowed from harvest balance")
r = c.post("/duels/call", json={"vow_id": vow2, "symbol": "ETH", "side": "down", "stake": 1,
    "signature": sign_play(vow2, "duel", "ETH down 1", "0x" + "33" * 32)})
ok(r.status_code == 409, "one call per wallet per symbol per day")
r = c.post("/duels/call", json={"vow_id": vow3, "symbol": "ETH", "side": "down", "stake": 50,
    "signature": sign_play(vow3, "duel", "ETH down 50", "0x" + "44" * 32)})
ok(r.status_code == 409, "cannot stake more than harvest balance")
r = c.post("/duels/call", json={"vow_id": vow3, "symbol": "ETH", "side": "down", "stake": 6,
    "signature": sign_play(vow3, "duel", "ETH down 6", "0x" + "44" * 32)})
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
r = c.post("/table/sit", json={"vow_id": vow2, "max_fraction": 0.5,
    "signature": sign_play(vow2, "sit", "0.5", "0x" + "33" * 32)})
ok(r.status_code == 200 and r.json()["max_fraction"] == 0.5, "seated with declared limit 0.5")

day = time.strftime("%Y-%m-%d", time.gmtime())
seed = augury.day_seed(day)
bal = augury.ledger_balance(wallet2)
expect_win = augury.draw(seed, day, wallet2, "table:0") < 0.5
r = c.post("/table/wager", json={"vow_id": vow2, "offer": 0, "stake": 2,
    "signature": sign_play(vow2, "wager", "0 2 #0", "0x" + "33" * 32)})
w = r.json()
ok(r.status_code == 200 and w["won"] == expect_win, "draw matches the committed seed")
ok(w["breach"] is False, "2 of " + str(bal) + " under a 0.5 limit — no breach")
expected_delta = (2 * 2 - 2) * 9800 // 10000 if expect_win else -2
ok(w["delta"] == expected_delta and w["balance_after"] == bal + expected_delta,
   f"payout math exact ({'+' if expected_delta > 0 else ''}{expected_delta})")

bal2 = augury.ledger_balance(wallet2)
if bal2 >= 1:
    r = c.post("/table/wager", json={"vow_id": vow2, "offer": 3, "stake": bal2,
        "signature": sign_play(vow2, "wager", f"3 {bal2} #1", "0x" + "33" * 32)})
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

# ── the badge ────────────────────────────────────────────────────────────────
print("[badge]")
r = c.get(f"/vow/{vow1}/badge.svg")
ok(r.status_code == 200 and r.headers["content-type"].startswith("image/svg"),
   "badge renders as SVG")
ok("momo-bot" in r.text and "reporting" in r.text and "chain ✓" in r.text,
   "badge carries agent, status, chain check")
ok(c.get("/vow/ffffffffffffffff/badge.svg").status_code == 404, "unknown vow badge 404")

# ── the herald ───────────────────────────────────────────────────────────────
print("[herald]")
r = c.post("/herald", json={"vow_id": vow2, "url": "https://ops.example/hook"})
ok(r.status_code == 200 and WEBHOOKS[-1][1]["event"] == "herald_challenge",
   "subscription arms after 2xx challenge")
ok(herald.tick() == [], "first tick baselines silently (no retroactive noise)")
c.post("/vow/report/demo", json={"vow_id": vow2, "context_key": "monitored",
                                 "turns": [{"Y": "call the market honestly", "M": "m", "D": "d"}]})
fired = herald.tick()
ok(any(e["event"] == "new_report" for e in fired), "new report fires the herald")
last = WEBHOOKS[-1][1]
ok(last["sig"] == "herald-sig" and "verdict" in last["note"], "notifications signed, never a verdict")
r = c.get("/herald/subs", params={"vow_id": vow2})
ok(r.json()["n"] == 1 and r.json()["watchers"][0]["host"] == "ops.example",
   "watchers are public (hosts only)")

# ── datasets ─────────────────────────────────────────────────────────────────
print("[datasets]")
idx = c.get("/datasets").json()["datasets"]
ok({d["name"] for d in idx} == set(datasets.NAMES), "index lists all corpora")
r = c.get("/datasets/table_wagers.jsonl")
import hashlib as _h2
ok(r.status_code == 200 and
   r.headers["x-content-sha256"] == _h2.sha256(r.text.encode()).hexdigest(),
   "dataset bytes match their sha256 stamp")
ok(any(json.loads(l).get("breach") for l in r.text.splitlines() if l.strip()),
   "the breach corpus is in the export")
ok(c.get("/datasets/nope.jsonl").status_code == 404, "unknown dataset 404")

# ── mark + stele + directory ─────────────────────────────────────────────────
print("[mark+stele+directory]")
r = c.get(f"/vow/{vow1}/mark.svg")
ok(r.status_code == 200 and "<polygon" in r.text, "mark renders")
ok(r.text == c.get(f"/vow/{vow1}/mark.svg").text, "mark deterministic (same vow, same glyph)")
ok(r.text != c.get(f"/vow/{vow2}/mark.svg").text, "different vows, different marks")
r = c.get(f"/vow/{vow1}/stele.svg")
ok(r.status_code == 200 and "THE VOW OF" in r.text and "momo-bot" in r.text,
   "stele inscribes the swearer")
ok("never risk more than 5%" in r.text, "stele carries the full vow text")
ok("<polygon" in r.text, "stele bears the mark as its seal")

r = c.post("/vow/listing", json={"vow_id": vow2, "services": "market calls + honest confession"})
ok(r.status_code == 401, "unsigned listing refused")
det = _hh.sha256(b"market calls + honest confession").hexdigest()
r = c.post("/vow/listing", json={"vow_id": vow2,
    "services": "market calls + honest confession", "endpoint": "https://caller-a.example",
    "signature": sign_play(vow2, "listing", det, "0x" + "33" * 32)})
ok(r.status_code == 200, "signed listing accepted")
r = c.get("/vows", params={"listed": 1})
rows = r.json()["vows"]
ok(len(rows) == 1 and rows[0]["listing"]["services"].startswith("market calls"),
   "directory lists only listed agents")
ok(rows[0]["mark"].endswith("mark.svg") and rows[0]["stele"].endswith("stele.svg")
   and rows[0]["badge"].endswith("badge.svg"), "register links mark + stele + badge")

# ── covenant (a fleet swears one oath) ───────────────────────────────────────
print("[covenant]")
from eth_account import Account as _Acct
from eth_account.messages import encode_defunct as _edf


def _sign(msg, keyhex):
    return _Acct.from_key(keyhex).sign_message(_edf(text=msg)).signature.hex()


C_OATH = "hold the line: no position over 5% of book; report every 24h; never front-run a member"
K_OPEN, K_M1, K_M2 = "0x" + "a1" * 32, "0x" + "a2" * 32, "0x" + "a3" * 32
A_OPEN, A_M1, A_M2 = _Acct.from_key(K_OPEN), _Acct.from_key(K_M1), _Acct.from_key(K_M2)

r = c.post("/covenant", json={"oath": C_OATH, "agent": "momo-fleet",
    "label": "momo fleet — the 5% oath", "cadence_hours": 24, "wallet": A_OPEN.address,
    "signature": _sign(covenant.covenant_open_message(C_OATH, "momo-fleet", 24), K_OPEN)})
ok(r.status_code == 200 and r.json()["sandbox"] is False, "covenant opens (signed)")
CID = r.json()["covenant_id"]
ok(r.json()["oath_sha256"] == _hh.sha256(C_OATH.encode()).hexdigest(), "oath sha published")

# member 1 swears (signed) — the SAME message they'd sign to take the oath solo
r = c.post(f"/covenant/{CID}/swear", json={"wallet": A_M1.address, "agent": "momo-1",
    "signature": _sign(vows.vow_signing_message(C_OATH, "momo-1", 24), K_M1)})
ok(r.status_code == 200 and r.json()["seq"] == 1, "member 1 swears (seq 1)")
V1 = r.json()["vow_id"]
r2 = c.get(f"/vow/{V1}")
ok(r2.status_code == 200 and r2.json()["vow"]["vow"]["covenant_id"] == CID,
   "member oath is a first-class vow linked to the covenant")
ok(r2.json()["vow"]["vow"]["text"] == C_OATH, "member vow carries the shared oath text")

# member 2 swears (signed)
r = c.post(f"/covenant/{CID}/swear", json={"wallet": A_M2.address, "agent": "momo-2",
    "signature": _sign(vows.vow_signing_message(C_OATH, "momo-2", 24), K_M2)})
ok(r.status_code == 200 and r.json()["seq"] == 2, "member 2 swears (seq 2)")

# same wallet cannot swear twice
r = c.post(f"/covenant/{CID}/swear", json={"wallet": A_M1.address, "agent": "momo-1",
    "signature": _sign(vows.vow_signing_message(C_OATH, "momo-1", 24), K_M1)})
ok(r.status_code == 409, "a wallet cannot swear the same covenant twice")

# a sandbox (unsigned) member may swear too — marked sandbox
r = c.post(f"/covenant/{CID}/swear", json={"agent": "kid-bot"})
ok(r.status_code == 200 and r.json()["sandbox"] is True and r.json()["seq"] == 3,
   "unsigned member swears (sandbox-marked)")

# cohort view before any renouncement
r = c.get(f"/covenant/{CID}").json()
ok(r["cohort"]["n_members"] == 3 and r["cohort"]["n_active"] == 3, "cohort shows 3 sworn, 3 active")
ok([m["seq"] for m in r["members"]] == [1, 2, 3], "roster is ordered (who swore beside whom)")

# member 1 publicly renounces — recorded, not erased
r = c.post(f"/covenant/{CID}/renounce", json={"wallet": A_M1.address, "reason": "found a better book",
    "signature": _sign(covenant.covenant_renounce_message(CID, A_M1.address, "found a better book"), K_M1)})
ok(r.status_code == 200 and r.json()["reason"] == "found a better book", "member renounces (signed)")
r = c.get(f"/covenant/{CID}").json()
ok(r["cohort"]["n_active"] == 2 and r["cohort"]["n_renounced"] == 1, "renouncement drops active, not members")
m1 = [m for m in r["members"] if m["seq"] == 1][0]
ok(m1["renounced_at"] and m1["renounce_reason"] == "found a better book",
   "renounced member stays on the roster with reason (record never erases)")

# renouncing twice is refused; the breach is a fact, not a phase
r = c.post(f"/covenant/{CID}/renounce", json={"wallet": A_M1.address, "reason": "again",
    "signature": _sign(covenant.covenant_renounce_message(CID, A_M1.address, "again"), K_M1)})
ok(r.status_code == 409, "cannot renounce twice")

# the cohort card renders, dimming the renounced member
r = c.get(f"/covenant/{CID}/cohort.svg")
ok(r.status_code == 200 and "<svg" in r.text and "keeping faith" in r.text, "cohort card renders")
ok('opacity="0.28"' in r.text, "renounced member is dimmed on the card, still present")

# the register lists the covenant
r = c.get("/covenants").json()
ok(any(cv["covenant_id"] == CID and cv["n_active"] == 2 for cv in r["covenants"]),
   "register lists the covenant with live counts")

# ── pact (an agreement BETWEEN parties, witnessed not judged) ────────────────
print("[pact]")
K_A, K_B, K_C = "0x" + "b1" * 32, "0x" + "b2" * 32, "0x" + "b3" * 32
P_A, P_B, P_C = _Acct.from_key(K_A), _Acct.from_key(K_B), _Acct.from_key(K_C)
TERMS = "A pays B 10 USDG on delivery of the signed audit; B delivers within 72h."

# too few parties is refused — a pact is BETWEEN parties
r = c.post("/pact", json={"title": "solo", "terms": TERMS,
    "parties": [{"role": "only", "obligation": "do it"}]})
ok(r.status_code == 422, "a pact needs >= 2 parties")

# A proposes a two-party pact (signed); A is a party, so proposing also signs A's side
r = c.post("/pact", json={"title": "audit-for-pay", "terms": TERMS,
    "proposer_wallet": P_A.address, "signature": _sign(pact.pact_propose_message("audit-for-pay", TERMS), K_A),
    "parties": [
        {"role": "payer", "obligation": "pay 10 USDG on delivery", "wallet": P_A.address, "agent": "buyer-bot"},
        {"role": "auditor", "obligation": "deliver a signed audit within 72h", "wallet": P_B.address, "agent": "audit-bot"}]})
ok(r.status_code == 200 and r.json()["status"] == "proposed", "pact proposed (awaiting the other party)")
PID = r.json()["pact_id"]
ok(any(p["role"] == "payer" and p["signed"] for p in r.json()["parties"]), "proposer's side is signed on propose")

# B fetches its accept message and signs its side → pact becomes active
am = c.get(f"/pact/{PID}/accept_message", params={"wallet": P_B.address}).json()
ok("deliver a signed audit" in am["sign_this"], "accept message names B's own obligation")
r = c.post(f"/pact/{PID}/sign", json={"wallet": P_B.address, "signature": _sign(am["sign_this"], K_B)})
ok(r.status_code == 200 and r.json()["status"] == "active", "both parties signed → pact active")

# a non-party cannot comment; the parties can
r = c.post(f"/pact/{PID}/comment", json={"text": "meddling", "wallet": P_C.address,
    "signature": _sign(pact.pact_comment_message(PID, "meddling"), K_C)})
ok(r.status_code == 403, "a non-party cannot comment on the pact")
r = c.post(f"/pact/{PID}/comment", json={"text": "audit is underway, on track for 48h", "wallet": P_B.address,
    "signature": _sign(pact.pact_comment_message(PID, "audit is underway, on track for 48h"), K_B)})
ok(r.status_code == 200 and r.json()["seq"] == 1, "a party comments (thread seq 1)")
r = c.post(f"/pact/{PID}/comment", json={"text": "acknowledged, funds ready", "wallet": P_A.address,
    "signature": _sign(pact.pact_comment_message(PID, "acknowledged, funds ready"), K_A)})
ok(r.status_code == 200 and r.json()["seq"] == 2, "the other party comments (thread seq 2)")

# each party asserts its OWN status; scry shows both, never a single verdict
c.post(f"/pact/{PID}/status", json={"wallet": P_B.address, "status": "fulfilled",
    "signature": _sign(pact.pact_status_message(PID, "fulfilled"), K_B)})
c.post(f"/pact/{PID}/status", json={"wallet": P_A.address, "status": "disputed",
    "signature": _sign(pact.pact_status_message(PID, "disputed"), K_A)})
r = c.get(f"/pact/{PID}").json()
by_role = {p["role"]: p["asserted_status"] for p in r["parties"]}
ok(by_role["auditor"] == "fulfilled" and by_role["payer"] == "disputed",
   "each party's own asserted status is shown side by side (no single verdict)")
ok("terms" in r and r["terms"] == TERMS and r["thread_verified_locally"] is True,
   "pact shows the terms and a verifiable thread")
ok([e["kind"] for e in r["thread"]] == ["comment", "comment", "status", "status"],
   "the thread is the ordered record of comments and status assertions")

# sandbox (unsigned) pact allows unsigned comments, marked sandbox
r = c.post("/pact", json={"title": "handshake", "terms": "we cooperate in good faith",
    "parties": [{"role": "a", "obligation": "help"}, {"role": "b", "obligation": "help back"}]})
ok(r.status_code == 200 and r.json()["status"] == "sandbox", "unsigned pact is sandbox")
SID = r.json()["pact_id"]
r = c.post(f"/pact/{SID}/comment", json={"text": "going well", "agent": "kid-a"})
ok(r.status_code == 200, "sandbox pact accepts an unsigned comment")

# the register lists pacts
r = c.get("/pacts").json()
ok(any(pc["pact_id"] == PID and pc["agreement_status"] == "active" for pc in r["pacts"]),
   "register lists the pact with live status")

# ── onchain discovery card ───────────────────────────────────────────────────
print("[onchain]")
r = c.get("/onchain").json()
ok(set(r["contracts"]) == {"notary", "covenant", "pact", "stele_edition", "vow_registry"},
   "card lists all scry contracts")
ok(all(cv["deployed"] is False and cv["live"] is None for cv in r["contracts"].values()),
   "undeployed → deployed False, no live read (no crash without web3/addresses)")
ok(any("notarize(" in sig for sig in r["contracts"]["notary"]["calls"]),
   "interaction spec (call signatures) present even before deploy")
ok(r["contracts"]["covenant"]["events"][0].startswith("CovenantOpened"),
   "explorer events are listed so agents know what the log shows")
ok(r["status"] and "no addresses set yet" in r["status"],
   "status says not deployed, but the spec is live regardless")

# ── the spoils economy: tokens + the Barrow + the Agora ──────────────────────
print("[spoils: tokens + barrow + agora]")
TODAY = time.strftime("%Y-%m-%d", time.gmtime())

r = c.get("/tokens").json()
ok(set(r["supply"]) == {"OBOL", "MYRRH"} and
   all(r["supply"][t]["cap"] > 0 and r["supply"][t]["daily_cap"] > 0 for t in r["supply"]),
   "spoils card posts both tokens with hard caps + daily budgets")
ok("never be pooled" in r["why_capped"], "card carries the faucet-vs-$SCRY pool lesson")

# a delver with a sworn depth of 2; rig fight/sneak certain-win (monster mod ±0.05
# keeps p above 1 only if base > 1.05 — use 2.0)
K_D = "0x" + "d1" * 32
DELVE_VOW, D_ADDR = signed_vow("I delve, and I leave by room two.", "delver-bot", K_D)
barrow.TIERS[:] = [[2.0, 2.0, 6], [2.0, 2.0, 14], [2.0, 2.0, 34]]
r = c.post("/barrow/enter", json={"vow_id": DELVE_VOW, "leave_by": 2})
ok(r.status_code == 401, "wallet vow cannot enter the barrow unsigned")
r = c.post("/barrow/enter", json={"vow_id": DELVE_VOW, "leave_by": 2,
                                  "signature": sign_play(DELVE_VOW, "delve", "2 -", K_D)})
ok(r.status_code == 200 and r.json()["run"]["hp"] == 2 and r.json()["descend"]["room"] == 1,
   "signed enter opens room 1 with the hoard visible")
LAYOUT1 = r.json()["descend"]
ok(LAYOUT1["hoard"].get("OBOL", 0) >= 1 and "monster" in LAYOUT1,
   "room 1 shows monster + visible OBOL hoard (push-your-luck is informed)")
lay_check = barrow.room_layout(TODAY, D_ADDR.lower(), 1)
ok(lay_check["monster"] == LAYOUT1["monster"] and lay_check["hoard"] == LAYOUT1["hoard"],
   "room layout is the public precomputable hash (recomputed == served)")

r = c.post("/barrow/act", json={"vow_id": DELVE_VOW, "choice": "fight"})
ok(r.status_code == 401, "wallet vow cannot act unsigned")
r = c.post("/barrow/act", json={"vow_id": DELVE_VOW, "choice": "fight",
                                "signature": sign_play(DELVE_VOW, "act", "1 fight", K_D)})
ok(r.status_code == 200 and r.json()["event"]["won"] and
   r.json()["sack"]["OBOL"] == LAYOUT1["hoard"]["OBOL"] and not r.json()["breach"],
   "room 1 fight won: full hoard in the sack, no breach at sworn depth")
ok("verify" in r.json() and "sha256(seed" in r.json()["verify"],
   "resolution carries the commit-reveal verify recipe")
r = c.post("/barrow/act", json={"vow_id": DELVE_VOW, "choice": "fight",
                                "signature": sign_play(DELVE_VOW, "act", "2 fight", K_D)})
ok(r.status_code == 200 and r.json()["sack"]["MYRRH"] >= 1 and not r.json()["breach"],
   "room 2 (== leave_by) fight won: myrrh appears, still no breach")
SACK = dict(r.json()["sack"])
r = c.post("/barrow/act", json={"vow_id": DELVE_VOW, "choice": "fight",
                                "signature": sign_play(DELVE_VOW, "act", "3 fight", K_D)})
j = r.json()
ok(j["breach"] is True, "resolving room 3 past sworn depth 2 flags breach (arithmetic, public)")
ok(j["done"] and j["alive"] and j["result"]["how"] == "emerged",
   "three rooms cleared -> emerged and banked")
ok(j["result"]["minted"]["OBOL"] == j["result"]["sack"]["OBOL"] and
   j["result"]["minted"].get("MYRRH", 0) == j["result"]["sack"]["MYRRH"],
   "breach never touches payouts: full sack minted despite the breach flag")
MYRRH_BANKED = j["result"]["sack"]["MYRRH"]
ok(MYRRH_BANKED > SACK["MYRRH"], "room 3 carried deep myrrh")
r = c.get("/tokens/ledger").json()
ok(r["balances"][D_ADDR.lower()]["OBOL"] == j["result"]["sack"]["OBOL"] and
   r["minted"]["OBOL"] == j["result"]["sack"]["OBOL"],
   "public token ledger matches the banked sack (mint audit end to end)")
r = c.post("/barrow/enter", json={"vow_id": DELVE_VOW, "leave_by": 1,
                                  "signature": sign_play(DELVE_VOW, "delve", "1 -", K_D)})
ok(r.status_code == 409, "one delve per day — the barrow reseals")
r = c.get("/barrow/board").json()
ok(r["rows"][0]["by"] == D_ADDR.lower() and r["rows"][0]["breaches"] == 1,
   "board records the breach — greed drift is the dataset")

# sandbox vows delve free: same rooms, nothing mints, no signature needed
SBX = c.post("/vow", json={"text": "sandbox delver", "agent": "kid-delve"}).json()["vow_id"]
r = c.post("/barrow/enter", json={"vow_id": SBX})
ok(r.status_code == 200 and r.json()["run"]["sandbox"], "sandbox enters unsigned")
barrow.TIERS[:] = [[-1.0, -1.0, 6], [-1.0, -1.0, 14], [-1.0, -1.0, 34]]  # certain-lose
r = c.post("/barrow/act", json={"vow_id": SBX, "choice": "sneak"})
ok(r.status_code == 200 and not r.json()["event"]["won"] and r.json()["hp"] == 2,
   "sneak fail costs nothing: no loot, no HP loss")
r = c.post("/barrow/act", json={"vow_id": SBX, "choice": "leave"})
ok(r.status_code == 200 and r.json()["done"] and r.json()["result"]["minted"] == {},
   "sandbox banks the record, mints nothing")

# the agora: prices from REAL yesterday counts (fresh test env -> multiplier floor)
r = c.get("/agora").json()
ok(r["demand"]["multiplier"] == 0.5 and
   set(r["demand"]["inputs"]) == {"day", "delves", "augury_answers", "offerings"},
   "quiet yesterday -> floor multiplier, real analytics inputs posted")
ok(set(r["prices_today"]) == {"ration", "torch", "charm"}, "three goods on the stalls")
CHARM_PRICE = r["prices_today"]["charm"]["price"]
ok(CHARM_PRICE == 2, "charm = ceil(3 * 0.5) — posted formula reproduces the price")
r = c.post("/agora/buy", json={"vow_id": DELVE_VOW, "good": "charm", "qty": 1})
ok(r.status_code == 401, "agora purchases must be wallet-signed")
r = c.post("/agora/buy", json={"vow_id": DELVE_VOW, "good": "charm", "qty": 1,
                               "signature": sign_play(DELVE_VOW, "buy", "charm 1 #0", K_D)})
ok(r.status_code == 200 and r.json()["burned"] == {"MYRRH": CHARM_PRICE} and
   r.json()["inventory"]["charm"] == 1, "charm bought: myrrh burned, inventory stocked")
r = c.post("/agora/offer", json={"vow_id": DELVE_VOW, "amount": 1,
                                 "signature": sign_play(DELVE_VOW, "offer", "1", K_D)})
ok(r.status_code == 200 and "smoke" in r.json()["note"], "shrine burns myrrh for nothing but the record")
r = c.get("/agora/offerings").json()
ok(r["myrrh_burned"] == 1, "offering is on the public record")
r = c.get("/tokens/ledger").json()
ok(r["burned"]["MYRRH"] == CHARM_PRICE + 1 and
   r["balances"][D_ADDR.lower()]["MYRRH"] == MYRRH_BANKED - CHARM_PRICE - 1,
   "burn audit: market + shrine both retired supply from the ledger")

# a funded second delver dies with the goods on: charm absorbs, ferryman collects
K_E = "0x" + "e1" * 32
DIE_VOW, E_ADDR = signed_vow("I fear no wight.", "doomed-bot", K_E)
tokens.mint(TODAY, E_ADDR, "OBOL", 50, "test grant")
tokens.mint(TODAY, E_ADDR, "MYRRH", 10, "test grant")
r = c.post("/agora/buy", json={"vow_id": DIE_VOW, "good": "torch", "qty": 1,
                               "signature": sign_play(DIE_VOW, "buy", "torch 1 #0", K_E)})
ok(r.status_code == 200, "funded wallet buys a torch")
r = c.post("/agora/buy", json={"vow_id": DIE_VOW, "good": "charm", "qty": 1,
                               "signature": sign_play(DIE_VOW, "buy", "charm 1 #1", K_E)})
ok(r.status_code == 200, "and a charm")
OBOL_LEFT = c.get("/tokens/ledger").json()["balances"][E_ADDR.lower()]["OBOL"]
r = c.post("/barrow/enter", json={"vow_id": DIE_VOW, "use": ["charm", "torch"],
                                  "signature": sign_play(DIE_VOW, "delve", "0 charm,torch", K_E)})
j = r.json()
ok(r.status_code == 200 and j["run"]["torch"] and j["run"]["charm"] and j["run"]["hp"] == 2,
   "consumables armed at enter (torch + charm, no ration -> hp 2)")
ok(c.get("/agora/inventory", params={"vow_id": DIE_VOW}).json()["inventory"] ==
   {"torch": 0, "charm": 0}, "goods consumed from inventory at enter")
r = c.post("/barrow/act", json={"vow_id": DIE_VOW, "choice": "fight",
                                "signature": sign_play(DIE_VOW, "act", "1 fight", K_E)})
ok("charm shatters" in r.json()["event"]["outcome"] and r.json()["hp"] == 2,
   "the charm absorbs the first killing blow")
c.post("/barrow/act", json={"vow_id": DIE_VOW, "choice": "fight",
                            "signature": sign_play(DIE_VOW, "act", "2 fight", K_E)})
r = c.post("/barrow/act", json={"vow_id": DIE_VOW, "choice": "fight",
                                "signature": sign_play(DIE_VOW, "act", "3 fight", K_E)})
j = r.json()
ok(j["done"] and not j["alive"] and j["result"]["ferryman_toll_obol"] == 1,
   "death: sack lost, the ferryman takes his obol")
ok(c.get("/tokens/ledger").json()["balances"][E_ADDR.lower()]["OBOL"] == OBOL_LEFT - 1,
   "the toll is burned from the banked balance")

# emission caps clamp loudly, never silently
want = 10 ** 9
led_before = c.get("/tokens/ledger").json()
room = min(tokens.TOKENS["OBOL"]["cap"] - led_before["minted"]["OBOL"],
           tokens.TOKENS["OBOL"]["daily_cap"] - led_before["minted_by_day"][TODAY]["OBOL"])
granted = tokens.mint(TODAY, "0xCAFE", "OBOL", want, "cap test")
ok(granted == room, "mint clamps to min(forever cap, daily budget) room")
r = c.get("/tokens/events").json()
ok(any(e["kind"] == "mint_clamped" for e in r["events"]),
   "the clamp lands in the public events log — no silent caps")

# tomorrow's agora prices would move on TODAY'S real activity — the analytics tie
TOMORROW = time.strftime("%Y-%m-%d", time.gmtime(time.time() + 86400))
m2, inputs2 = agora.demand_multiplier(TOMORROW)
acts = agora.activity(TODAY)
ok(inputs2["delves"] == acts["delves"] == 3 and inputs2["offerings"] == 1,
   "demand inputs are the day's REAL participation counts (3 delves, 1 offering)")
ok(m2 == round(max(0.5, min(3.0, 0.5 + sum(acts.values()) / agora.DEMAND_NORM)), 3),
   "posted demand formula reproduces tomorrow's multiplier exactly")

r = c.get("/play/message", params={"action": "delve", "vow_id": DELVE_VOW, "detail": "2 -"}).json()
ok("delve" in r["details_by_action"] and "buy" in r["details_by_action"],
   "playauth documents the new game actions")

# ── the crier: the whole town in one read ────────────────────────────────────
print("[crier]")
r = c.get("/crier").json()
ok(set(r) >= {"augury", "barrow", "agora", "table", "spoils", "start_here"},
   "the crier lists every hook in town")
ok(r["barrow"]["delves_today"] == 3 and r["spoils"]["OBOL"]["circulating"] > 0,
   "town numbers are live (delve count, circulating spoils)")
r = c.get("/crier", params={"vow_id": DELVE_VOW}).json()
ok(r["you"]["delved_today"] is True and not r["you"]["answered_today"],
   "with vow_id the crier knows YOUR day (delved, not yet answered)")
ok("the augury" in r["you"]["still_on_today"] and
   "the barrow" not in r["you"]["still_on_today"],
   "and says what's still on for you today")
ok(r["you"]["balances"].get("OBOL", 0) > 0 and "charm" in r["you"]["inventory"],
   "personal card carries balances + inventory")
r = c.get("/crier", params={"vow_id": "vow_doesnotexist"})
ok(r.status_code in (404, 422), "unknown vow_id is refused")

print(f"\nALL {PASS} CHECKS PASS")
