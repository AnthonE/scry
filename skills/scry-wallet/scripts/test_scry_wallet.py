"""Offline test for the scry-wallet adapter — no network, no real key.

Proves the adapter logic: deterministic actions sign the materialized message
and POST it with the wallet+signature filled; stateful actions FETCH the live
challenge (never fabricate a server index/nonce); non-one-call actions (play)
refuse `.act()` and hand you `.message()`; placeholders are stripped
from the submitted body; and `local_signer` produces a real EIP-191 signature.

Run: python3 test_scry_wallet.py  (stdlib only; the last check uses eth_account
if present and is skipped honestly otherwise).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scry_wallet import ScryWallet, ScryWalletError, local_signer  # noqa: E402

PASS = 0


def ok(cond, label):
    global PASS
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)
    PASS += 1
    print(f"  ok: {label}")


BASE = "http://scry.test/api"
CALLS = []  # (method, path, body)


def _path(url):
    return url[len(BASE):] if url.startswith(BASE) else url


CANNED = {
    ("GET", "/prepare/sign/vow"): {
        "class": "deterministic", "sign_this": "VOW-MSG",
        "submit": {"method": "POST", "path": "/vow",
                   "body": {"text": "t", "agent": "a", "cadence_hours": 24,
                            "wallet": "<your EVM address>", "signature": "<sig>"}},
        "note": "prepared, not executed"},
    ("POST", "/vow"): {"vow_id": "abc123"},
    ("GET", "/prepare/sign/familiar-auth"): {
        "class": "stateful", "sign_this": None,
        "fetch": {"method": "GET", "path": "/familiar/fam0/auth-message?action=talk"},
        "submit": {"method": "POST", "path": "/familiar/fam0/talk", "requires": ["text"],
                   "body": {"text": "<command>", "signature": "<sig>"}}},
    ("GET", "/familiar/fam0/auth-message?action=talk"): {"sign_this": "OWNER-MSG-IDX-0", "index": 0},
    ("POST", "/familiar/fam0/talk"): {"ok": True, "reply": "venturing"},
    ("GET", "/prepare/sign/hive-bind"): {
        "class": "deterministic", "sign_this": "NPUB-MSG", "two_key": True,
        "submit": {"method": "POST", "path": "/hive/npub", "requires": ["event"],
                   "body": {"vow_id": "v", "npub": "npub1x", "signature": "<sig>",
                            "event": "<NIP-01 event>"}}},
    ("POST", "/hive/npub"): {"ok": True, "bound": True},
    ("GET", "/prepare/sign/play"): {
        "class": "deterministic", "sign_this": "PLAY-MSG",
        "submit": {"method": "POST", "path": "the fun-layer endpoint (see /play/message)",
                   "body": {"vow_id": "v", "signature": "<sig>"}}},
}


def fake_http(method, url, body=None, timeout=30):
    path = _path(url)
    CALLS.append((method, path, body))
    # live-fetch paths carry their own query and are keyed with it; recipe GETs
    # append params as a query we don't key on — try exact, then query-stripped.
    for key in (path, path.split("?", 1)[0]):
        if (method, key) in CANNED:
            return CANNED[(method, key)]
    raise AssertionError(f"unexpected call {method} {path}")


def signer(message):
    return "0xSIG::" + message


w = ScryWallet(signer, wallet_address="0x" + "cd" * 20, base=BASE, http=fake_http)

# ── deterministic: sign the materialized message, POST it filled ──────────────
print("[deterministic]")
CALLS.clear()
res = w.act("vow", text="t", agent="a")
ok(res == {"vow_id": "abc123"}, "act('vow') returns the server response")
post = [c for c in CALLS if c[0] == "POST"][0]
ok(post[1] == "/vow", "act('vow') POSTs to /vow")
ok(post[2]["signature"] == "0xSIG::VOW-MSG", "the wallet signed the exact materialized message")
ok(post[2]["wallet"] == "0x" + "cd" * 20, "the adapter filled in the wallet address")
ok("<your EVM address>" not in str(post[2]) and "<sig>" not in str(post[2]),
   "no placeholder scaffolding leaks into the submitted body")

# ── stateful: fetch the live challenge, never fabricate ───────────────────────
print("[stateful — fetch, never fabricate]")
CALLS.clear()
msg, recipe = w.message("familiar-auth", familiar_id="fam0", action="talk")
ok(msg == "OWNER-MSG-IDX-0", "message('familiar-auth') returns the LIVE index message")
ok(("GET", "/familiar/fam0/auth-message?action=talk", None) in CALLS,
   "the adapter fetched the live auth-message endpoint (didn't invent the index)")

CALLS.clear()
res = w.act("familiar-auth", submit_extra={"text": "farm boars until level 3"},
            familiar_id="fam0", action="talk")
post = [c for c in CALLS if c[0] == "POST"][0]
ok(post[1] == "/familiar/fam0/talk", "act('familiar-auth') POSTs to the talk endpoint")
ok(post[2]["signature"] == "0xSIG::OWNER-MSG-IDX-0", "signed the fetched live message")
ok(post[2]["text"] == "farm boars until level 3", "submit_extra carried the command text")

# ── non-one-call actions refuse .act(), hand you .message() ───────────────────
print("[refusals]")
try:
    w.act("play", play_action="gamble", vow_id="v")
    ok(False, "act('play') should refuse — prose submit path")
except ScryWalletError:
    ok(True, "act('play') refuses (submit isn't a one-call POST) — use .message()")

# play is still usable via .message()
CALLS.clear()
pmsg, _ = w.message("play", play_action="gamble", vow_id="v")
ok(pmsg == "PLAY-MSG", "message('play') returns the materialized deterministic message")

# ── two-key / required-field guard: never a silent 422 ────────────────────────
print("[requires guard]")
try:
    w.act("hive-bind", vow_id="v", npub="npub1x")            # missing the Nostr event
    ok(False, "hive-bind without the event should refuse")
except ScryWalletError as e:
    ok("event" in str(e), "hive-bind BIND without the Nostr `event` refuses (names the missing field)")
CALLS.clear()
res = w.act("hive-bind", submit_extra={"event": {"id": "abc", "sig": "…"}}, vow_id="v", npub="npub1x")
post = [c for c in CALLS if c[0] == "POST"][0]
ok(post[1] == "/hive/npub" and post[2]["event"] == {"id": "abc", "sig": "…"},
   "hive-bind WITH the event posts it (two-key completed)")
ok(post[2]["signature"] == "0xSIG::NPUB-MSG", "hive-bind signed the wallet-side playauth message")
try:
    w.act("familiar-auth", familiar_id="fam0", action="talk")  # missing the command text
    ok(False, "familiar talk without text should refuse")
except ScryWalletError as e:
    ok("text" in str(e), "familiar talk without `text` refuses (required caller field)")

# ── local_signer is a real EIP-191 signer ─────────────────────────────────────
print("[local_signer]")
try:
    from eth_account import Account
    from eth_account.messages import encode_defunct
    key = "0x" + "11" * 32
    sign, addr = local_signer(key)
    sig = sign("hello scry")
    recovered = Account.recover_message(encode_defunct(text="hello scry"), signature=sig)
    ok(recovered.lower() == addr.lower(), "local_signer signature recovers its own address")
except ImportError:
    print("  skip: eth_account not installed (local_signer convenience only)")

print(f"\nall good — {PASS} checks passed")
