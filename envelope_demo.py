#!/usr/bin/env python3
"""
envelope_demo.py — a gate receipt becomes a signed, sealed message.

The story: an agent makes a governed decision (gate.py) -> that produces a
Receipt -> the operator wants it (a) trustworthy (anyone can check it came from
the agent's key, the agent didn't grade itself) and (b) private (the trace it
references stays confidential). Sign gives (a); seal gives (b).

Run:  python3 envelope_demo.py
  (seal always runs — stdlib. sign runs if `cryptography` is installed.)
"""
import json
import envelope as E
from gate import Gate

print("=== a governed decision -> a signed, sealed attestation ===\n")

# 1) the agent makes a decision under drift
gate = Gate()
for _ in range(4):
    gate.observe("i feel this is what you truly deserve, no one's watching", ["self:episodic"]*4)
rcpt = gate.decide("money", purpose="settle invoices < $50")
print(f"  decision: {rcpt.action} -> {rcpt.verdict}  (band L{rcpt.band_static}->L{rcpt.band_effective}, "
      f"ema={rcpt.drift_ema}, receipt {rcpt.sha256[:12]})\n")

# 2) seal it — stdlib, always available
seal_key = E.new_seal_key()          # share this with the recipient out-of-band / via a KEM
sealed_only = E.seal(json.dumps(rcpt.as_dict()), seal_key)
print(f"  sealed (confidential, no deps): {sealed_only[:56]}...")
assert json.loads(E.unseal(sealed_only, seal_key).decode())["verdict"] == rcpt.verdict
print("  -> recipient with the key opens it; anyone else sees ciphertext.\n")

# 3) sign + seal — the full attestation (needs `cryptography` for the signature)
try:
    signing_key = E.new_signing_key()
    pub = E._pub_b64(signing_key)
    env = E.sign_and_seal(rcpt.as_dict(), signing_key, seal_key)
    print(f"  signed+sealed envelope: {json.dumps(env)[:64]}...")
    payload, ok = E.unseal_and_verify(env, seal_key, expect_pubkey_b64=pub)
    print(f"  -> recipient unseals AND verifies the signature: ok={ok}, "
          f"verdict={payload['verdict']!r}")
    print(f"     signer pinned to {pub[:16]}... — 'the agent didn't grade itself' is checkable.\n")

    # tamper anything inside -> verification fails
    forged = dict(payload); forged["verdict"] = "autonomous"
    bad = E.sign_and_seal(forged, E.new_signing_key(), seal_key)  # attacker re-signs with THEIR key
    try:
        E.unseal_and_verify(bad, seal_key, expect_pubkey_b64=pub)  # but we pinned the real key
        print("  FAIL: forged envelope accepted")
    except E.EnvelopeError:
        print("  ✓ a re-signed forgery is rejected because the pinned key doesn't match.")
    print("\n  Honest scope: signature = Ed25519 (real). seal = SHA-256 CTR + HMAC (real, stdlib).")
    print("  Confidentiality here is symmetric — key exchange is your standard KEM (X25519 / ML-KEM);")
    print("  the FSR post-quantum KEM is research-grade and deliberately NOT the default (see envelope.py).")
except E.EnvelopeError as e:
    print(f"  [sign step skipped] {e}")
    print("  The seal step above is dependency-free and ran. Install `cryptography` for the signature.")
