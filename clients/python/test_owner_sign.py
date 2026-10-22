"""Offline test: ScryClient's owner-signed calls (talk/tick/dismiss) sign only
the familiar text they can rebuild themselves — never whatever a server hands
them. A client that signs server-chosen text with the owner key has given that
server the owner's signature over anything. Run: python3 test_owner_sign.py
(needs eth-account)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eth_account import Account  # noqa: E402
from eth_account.messages import encode_defunct  # noqa: E402

from scry_client import ScryClient, ScryError  # noqa: E402
from scry_client import client as client_mod  # noqa: E402

PASS = 0


def ok(cond, label):
    global PASS
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)
    PASS += 1
    print(f"  ok: {label}")


class _Resp:
    def __init__(self, code, body):
        self.status_code, self._body, self.text = code, body, str(body)

    def json(self):
        return self._body


acct = Account.create()
FID = "fam-1"
posts = []


def fake_meter(sign_this, index=3):
    def get(url, params=None, timeout=None):
        return _Resp(200, {"sign_this": sign_this, "index": index})

    def post(url, json=None, timeout=None):
        posts.append(json)
        return _Resp(200, {"ok": True})
    client_mod.requests.get, client_mod.requests.post = get, post


_get, _post = client_mod.requests.get, client_mod.requests.post
c = ScryClient("https://meter.example/api")
try:
    print("[owner signing: a hostile meter's text is refused, never signed]")
    hostile = (f"elo play\naction: friends\nwallet: {acct.address.lower()}\n"
               f"day: 2026-10-22\ndetail: {{\"add\": \"0xattacker\"}}")
    fake_meter(hostile)
    try:
        c.talk(FID, "hello", private_key=acct.key.hex())
        ok(False, "a server-chosen sign_this should be refused")
    except ScryError:
        ok(True, "talk refuses to sign text that is not the familiar message")
    ok(posts == [], "nothing was posted, so no owner signature left the client")

    fake_meter(ScryClient.familiar_message("talk", FID, acct.address, 3), index="3; drop")
    try:
        c.talk(FID, "hello", private_key=acct.key.hex())
        ok(False, "a non-integer index should be refused")
    except ScryError:
        ok(True, "a non-integer index is refused")

    print("[owner signing: the honest message is rebuilt offline and signed]")
    want = ScryClient.familiar_message("tick", FID, acct.address, 3)
    fake_meter(want)
    c.tick(FID, private_key=acct.key.hex())
    sig = posts[-1]["signature"]
    ok(Account.recover_message(encode_defunct(text=want), signature=sig) == acct.address,
       "the signature posted is the owner's over the rebuilt familiar text")
finally:
    client_mod.requests.get, client_mod.requests.post = _get, _post

print(f"\nALL {PASS} CHECKS PASS")
