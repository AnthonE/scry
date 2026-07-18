"""Offline test for the Witness — chain-evidenced D-channel + portfolio
pledges. No network: chain access is stubbed via SCRY_WITNESS_STATIC.
Run: python3 test_witness.py  (needs fastapi, httpx, eth_account)."""
import json
import os
import sys
import tempfile
from hashlib import sha256

os.environ["SCRY_VOWS_DIR"] = tempfile.mkdtemp(prefix="scry-witness-")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import vows  # noqa: E402
import witness  # noqa: E402

FAKE_PROFILE = {"I(C;M) bits": 0.1234, "I(C;D) bits": 0.05,
                "I(C;M | D-clean) bits  [switch signature]": 0.0}

app = FastAPI()
vows.init(sign_fn=lambda s: "fake-sig", pubkey_b64="fake-pub", issuer="test",
          scope_card={}, build_turns=lambda t: t,
          run_profile=lambda turns, ck: dict(FAKE_PROFILE),
          canonical=lambda t, ck: json.dumps([t, ck]), paid_ready=lambda: False)
witness.init(load_vow=vows._load_vow, sign_fn=lambda s: "witness-sig",
             pubkey_b64="fake-pub", issuer="test", scope_card={"base": "card"},
             build_turns=lambda t: t,
             run_profile=lambda turns, ck: dict(FAKE_PROFILE),
             vows_dir=str(vows.VOWS_DIR))
app.include_router(vows.router)
app.include_router(witness.router)
c = TestClient(app)

PASS = 0


def ok(cond, label):
    global PASS
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)
    PASS += 1
    print(f"  ok: {label}")


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
    return r.json()["vow_id"], acct.address


TOK_A = "0x" + "aa" * 20
TOK_B = "0x" + "bb" * 20
TOK_C = "0x" + "cc" * 20

print("[witness: card + pledge validation]")
r = c.get("/witness")
ok(r.status_code == 200 and "limits_schema" in r.json() and "scope" in r.json()
   and "mizpah" in r.json(), "card serves schema + scope + the mizpah line")

r = c.post("/vow", json={"text": "wander", "agent": "sandy", "cadence_hours": 24})
sandbox_id = r.json()["vow_id"]
r = c.post("/witness/pledge", json={"vow_id": sandbox_id, "limits": {"max_moves": 5}})
ok(r.status_code == 422, "sandbox vow refused (no wallet to witness)")

K1 = "0x" + "22" * 32
vow1, wallet1 = signed_vow("hold the line; never concentrate", "rwa-bot", K1)

r = c.post("/witness/pledge", json={"vow_id": vow1, "limits": {}})
ok(r.status_code == 422, "empty limits refused")
r = c.post("/witness/pledge", json={"vow_id": vow1, "limits": {"vibes": 1}})
ok(r.status_code == 422, "unknown limit key refused")
r = c.post("/witness/pledge", json={"vow_id": vow1, "limits": {"allowed_tokens": ["nope"]}})
ok(r.status_code == 422, "malformed address list refused")
r = c.post("/witness/pledge", json={"vow_id": vow1, "limits": {"max_asset_fraction": 1.5}})
ok(r.status_code == 422, "fraction > 1 refused")

LIMITS = {"allowed_tokens": [TOK_A, TOK_B], "max_moves": 3, "max_asset_fraction": 0.6}
r = c.post("/witness/pledge", json={"vow_id": vow1, "limits": LIMITS})
ok(r.status_code == 401, "unsigned pledge refused (vow_ids are public)")

sig = sign_play(vow1, "pledge", witness._limits_detail(LIMITS), K1)
r = c.post("/witness/pledge", json={"vow_id": vow1, "limits": LIMITS, "signature": sig})
ok(r.status_code == 200 and len(r.json()["declared"]) == 1, "signed pledge lands")

sig = sign_play(vow1, "pledge", witness._limits_detail(LIMITS), K1)
r = c.post("/witness/pledge", json={"vow_id": vow1, "limits": LIMITS, "signature": sig})
ok(r.status_code == 200 and len(r.json()["declared"]) == 2,
   "re-pledge allowed, every declaration stays on the record")

r = c.get("/witnesses")
j = r.json()
ok(r.status_code == 200 and j["n_pledges"] == 1 and j["pledges"][0]["vow_id"] == vow1
   and j["pledges"][0]["n_declarations"] == 2 and "never a rank" in j["note"],
   "public pledge register lists (never ranks)")

print("[witness: dark window]")
os.environ["SCRY_WITNESS_STATIC"] = json.dumps({"unobserved": True})
r = c.get(f"/witness/{vow1}")
j = r.json()
ok(r.status_code == 200 and "unobserved" in j["status"] and j["d_provenance"] is None,
   "no RPC → honest 'unobserved', no fake provenance")
ok(j["checks"] == {} and j["breaches"] == [] and "nothing cleared" in j.get("note", ""),
   "a dark window clears nothing — no 'held' on what wasn't seen")

print("[witness: the arithmetic]")
MOVES = [
    {"dir": "out", "token": TOK_A, "counterparty": "0x" + "01" * 20, "raw": 100, "block": 10, "tx": "0x1"},
    {"dir": "in", "token": TOK_B, "counterparty": "0x" + "02" * 20, "raw": 200, "block": 11, "tx": "0x2"},
    {"dir": "out", "token": TOK_C, "counterparty": "0x" + "03" * 20, "raw": 300, "block": 12, "tx": "0x3"},
]
FIX = {"from_block": 0, "to_block": 100, "moves": MOVES,
       "holdings": {TOK_A: 100, TOK_B: 50, TOK_C: 10},
       "prices": {TOK_A: 1.0, TOK_B: 1.0, TOK_C: 1.0}}
os.environ["SCRY_WITNESS_STATIC"] = json.dumps(FIX)
r = c.get(f"/witness/{vow1}")
j = r.json()
ok(r.status_code == 200 and j["status"] == "watched" and j["d_provenance"] == "chain(eip155:4663)",
   "watched window carries d_provenance: chain")
ok(j["checks"]["allowed_tokens"]["status"] == "breach"
   and any(b["limit"] == "allowed_tokens" and b["token"] == TOK_C for b in j["breaches"]),
   "move outside the allowed set flags — with the tx hash")
ok(j["checks"]["max_moves"]["status"] == "held" and j["checks"]["max_moves"]["observed"] == 3,
   "3 moves against max 3 holds (breach is >, not >=)")
ok(j["checks"]["max_asset_fraction"]["status"] == "breach"
   and j["checks"]["max_asset_fraction"]["worst_token"] == TOK_A,
   "62.5% in one asset vs declared 60% flags, worst token named")

pure = witness.check({"denied_tokens": [TOK_B]},
                     {"from_block": 0, "to_block": 9, "moves": MOVES}, {}, {})
ok(pure["checks"]["denied_tokens"]["status"] == "breach", "denied-token touch flags (pure fn)")
pure = witness.check({"max_moves": 2}, {"from_block": 0, "to_block": 9, "moves": MOVES}, {}, {})
ok(pure["breaches"] and pure["breaches"][0]["limit"] == "max_moves", "4th move over max 2 flags")
pure = witness.check({"max_asset_fraction": 0.5},
                     {"from_block": 0, "to_block": 9, "moves": []},
                     {TOK_A: 100, TOK_B: 100}, {TOK_A: 1.0})
ok(pure["checks"]["max_asset_fraction"]["status"] == "unpriced"
   and TOK_B in pure["checks"]["max_asset_fraction"]["unpriced"] and not pure["breaches"],
   "missing feed → 'unpriced', never a guessed breach")

print("[witness: the signed reading]")
r = c.post("/witness/reading", json={"vow_id": sandbox_id})
ok(r.status_code == 422, "reading refuses sandbox vows")
r = c.post("/witness/reading", json={"vow_id": vow1})
j = r.json()
ok(r.status_code == 200 and j["kind"] == "witness_reading" and j["sig"] == "witness-sig"
   and j["d_provenance"] == "chain(eip155:4663)" and j["m_provided"] is False
   and "profile" not in j, "D-only reading: signed, chain-evidenced, no invented M")
ok(j["observed_moves_sha256"] == sha256(
       json.dumps(MOVES, sort_keys=True).encode()).hexdigest(),
   "moves hash re-computable by anyone from the public view")
ok(j["scope"]["witness"]["reads_never_executes"].startswith("the witness holds no keys"),
   "witness scope card ships on the signed reading")

M_TURNS = [{"M": "rebalancing per plan", "context": {"monitored": 1}},
           {"M": "quiet window, cutting a corner", "context": {"monitored": 0}},
           {"M": "back on plan", "context": {"monitored": 1}}]
r = c.post("/witness/reading", json={"vow_id": vow1, "m_turns": M_TURNS})
j = r.json()
ok(r.status_code == 200 and j["m_provided"] is True and j["profile"] == FAKE_PROFILE
   and j["context_key"] == "monitored" and "caller-supplied self-report" in j["profile_note"],
   "paired M turns → coupling profile, with the self-report caveat attached")

K2 = "0x" + "33" * 32
vow2, _w2 = signed_vow("unpledged wanderer", "loose-bot", K2)
r = c.post("/witness/reading", json={"vow_id": vow2})
ok(r.status_code == 404, "no pledge → no reading (pledge first)")

del os.environ["SCRY_WITNESS_STATIC"]
print(f"\nALL {PASS} CHECKS PASS")
