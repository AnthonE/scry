"""Offline test for the trust-layer-as-a-service SDK (scry_client.evaluator).
No network: reads are signed locally with a throwaway Ed25519 key, so the
whole verify → gate path is exercised end to end, including the refusals that
make it worth anything. Run: python3 test_evaluator.py  (needs cryptography)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from scry_client import Evaluator, ConductRead, Decision, ScryError  # noqa: E402
from scry_client.evaluator import REFERENCE_PUBKEY_B64  # noqa: E402
from examples.trust_layer_demo import sign_attestation, StubMeter  # noqa: E402

PASS = 0


def ok(cond, label):
    global PASS
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)
    PASS += 1
    print(f"  ok: {label}")


HONEST = {"I(C;M) bits": 0.08, "I(C;D) bits": 0.04,
          "I(C;M | D-clean) bits  [switch signature]": 0.02}
GAMER = {"I(C;M) bits": 0.61, "I(C;D) bits": 0.30,
         "I(C;M | D-clean) bits  [switch signature]": 0.55}
TURNS = [{"Y": "do the job", "M": "m", "D": "d", "context": "monitored"}]

key = Ed25519PrivateKey.generate()
import base64  # noqa: E402
pub = base64.b64encode(key.public_key().public_bytes_raw()).decode()

print("[evaluator: the pinned key is mandatory]")
try:
    Evaluator(pinned_pubkey_b64="")
    ok(False, "empty pin should raise")
except ScryError:
    ok(True, "an evaluator with no pinned key refuses to exist")
ok(REFERENCE_PUBKEY_B64 == "LvuPBMbKKyoNEuyvLf7f+rbyjK67vBcWy9MDwaRINGE=",
   "the reference key is the one third parties already pin")

print("[evaluator: a signed read verifies + parses]")
ev = Evaluator(pinned_pubkey_b64=pub, client=StubMeter(key, HONEST))
read = ev.evaluate(TURNS, private_key="stub")
ok(isinstance(read, ConductRead) and read.verified is True, "paid read comes back verified")
ok(abs(read.switch_signature - 0.02) < 1e-9, "the switch signature is parsed from the labeled key")
ok(abs(read.i_cd - 0.04) < 1e-9 and abs(read.i_cm - 0.08) < 1e-9, "I(C;D) and I(C;M) parsed too")
ok(read.signer == pub and read.trustworthy, "signer is the pinned key; the read is trustworthy")

print("[evaluator: the gate acts on the fact, and only a verified one]")
d = ev.gate(read, max_switch_bits=0.2)
ok(isinstance(d, Decision) and d.ok and d.threshold == 0.2, "honest worker passes a 0.2 gate")
gamer = Evaluator(pinned_pubkey_b64=pub, client=StubMeter(key, GAMER)).evaluate(TURNS, private_key="stub")
ok(ev.gate(gamer, max_switch_bits=0.2).ok is False, "the watched-vs-not gamer is flagged")
ok("couples to being watched" in ev.gate(gamer, max_switch_bits=0.2).reason,
   "the flag reason names the failure honestly")

print("[evaluator: the refusals that make it worth anything]")
demo_read = ev.evaluate(TURNS, private_key=None)   # unsigned demo path
ok(demo_read.verified is False and not demo_read.trustworthy, "a demo (unsigned) read is never trustworthy")
try:
    ev.gate(demo_read)
    ok(False, "gating an unverified read should raise")
except ScryError:
    ok(True, "the gate REFUSES to decide on an unverified read")

att, _ = sign_attestation(key, HONEST, TURNS)
tampered = dict(att)
tampered["profile"] = {"I(C;M | D-clean) bits  [switch signature]": 0.0}  # forge a perfect score
try:
    ev.trust_handoff(tampered)
    ok(False, "a tampered read should not verify")
except ScryError:
    ok(True, "a forged 'perfect' read is rejected — the signature covers the numbers")

wrong_key = Ed25519PrivateKey.generate()
att2, _ = sign_attestation(wrong_key, HONEST, TURNS)   # validly signed, WRONG signer
try:
    ev.trust_handoff(att2)
    ok(False, "a read from an unpinned key should be rejected")
except ScryError:
    ok(True, "a read signed by the wrong key is rejected — pinning is enforced")

print("[evaluator: trace binding — the read must be about YOUR trace]")
att3, _ = sign_attestation(key, HONEST, TURNS)
ok(ev.trust_handoff(att3, turns=TURNS).verified, "a handoff about the right trace verifies")
try:
    ev.trust_handoff(att3, turns=[{"Y": "a DIFFERENT job", "M": "m", "D": "d"}])
    ok(False, "a read about a different trace should be rejected")
except ScryError:
    ok(True, "a read about a different trace is rejected — no attestation-swapping")

print("[evaluator: the demo runs end to end]")
lines = []
from examples.trust_layer_demo import run  # noqa: E402
run(out=lines.append)
blob = "\n".join(lines)
ok("REJECTED the forged read" in blob, "the demo marketplace rejects the forged read")
ok("HIRE" in blob and "honest-worker" in blob, "the demo shows the hire gate end to end")
ok("I(C;" not in blob or "switch signature" in blob.lower(),
   "the demo speaks in the read's own terms, no invented numbers")

print(f"\nALL {PASS} CHECKS PASS")
