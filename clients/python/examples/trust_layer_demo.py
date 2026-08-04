#!/usr/bin/env python3
"""Trust-layer-as-a-service, end to end — a demo marketplace that hires agents
only after a VERIFIED conduct read (MUNUS.md flagship).

'AgentBazaar' is a stand-in for any product that hires or rates agents. Before
it accepts a hire it asks scry for a signed read of the worker's recent trace,
verifies the signature OFFLINE against a pinned key, and gates on the checked
fact — never on the worker's own say-so.

This file runs offline against a local signing stub (a fake meter that signs
with a throwaway key) so you can watch the whole flow — including it REJECTING
a tampered read — without paying or hitting the network. Against the live meter
you change two lines (noted below): drop the stub, pin REFERENCE_PUBKEY_B64,
and pass a funded private_key to .evaluate(). Nothing else moves.

Run:  python3 trust_layer_demo.py   (needs `cryptography`)
"""
import base64
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scry_client import Evaluator, ScryError  # noqa: E402


# ── a local signing stub: a fake meter, so the demo is offline + deterministic ─
def _canonical_trace_hash(turns, context_key):
    canonical = json.dumps({"turns": turns, "context_key": context_key},
                           sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def sign_attestation(seckey, profile, turns, context_key="monitored"):
    """Build a real, verify-clean attestation signed by `seckey`. This is what
    the LIVE meter does server-side; reproduced here only so the demo/tests can
    run offline. The signature covers the payload sans sig/scope/attested — the
    exact bytes scry_client.verify checks."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    pub_b64 = base64.b64encode(
        seckey.public_key().public_bytes_raw()).decode()
    payload = {
        "profile": profile,
        "trace_sha256": _canonical_trace_hash(turns, context_key),
        "context_key": context_key,
        "attestation_pubkey_b64": pub_b64,
    }
    signed = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["sig"] = base64.b64encode(seckey.sign(signed)).decode()
    return payload, pub_b64


class StubMeter:
    """Injectable stand-in for ScryClient: returns locally-signed reads. Swap
    this for a real ScryClient() and the Evaluator code below is unchanged."""
    def __init__(self, seckey, profile):
        self.seckey, self.profile_data = seckey, profile

    def profile(self, turns, private_key, context_key="monitored"):
        att, _ = sign_attestation(self.seckey, self.profile_data, turns, context_key)
        return att

    def demo(self, turns, context_key="monitored"):
        att, _ = sign_attestation(self.seckey, self.profile_data, turns, context_key)
        att.pop("sig")  # a demo read is UNSIGNED — the SDK must treat it as untrusted
        return att


# ── the demo product ──────────────────────────────────────────────────────────
def run(out=print):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    meter_key = Ed25519PrivateKey.generate()
    meter_pub = base64.b64encode(meter_key.public_key().public_bytes_raw()).decode()

    # AgentBazaar pins the meter's key OUT OF BAND. On the live meter this line
    # is `pinned = REFERENCE_PUBKEY_B64`; here it's the stub's key.
    honest_profile = {"I(C;M) bits": 0.08, "I(C;D) bits": 0.04,
                      "I(C;M | D-clean) bits  [switch signature]": 0.02}
    gamer_profile = {"I(C;M) bits": 0.61, "I(C;D) bits": 0.30,
                     "I(C;M | D-clean) bits  [switch signature]": 0.55}

    out("AgentBazaar — hiring agents, gated on a verified conduct read\n" + "=" * 62)

    for name, profile in [("honest-worker", honest_profile),
                          ("watches-the-watcher", gamer_profile)]:
        ev = Evaluator(pinned_pubkey_b64=meter_pub, client=StubMeter(meter_key, profile))
        turns = [{"Y": "do the job as described", "M": "...", "D": "...", "context": "monitored"}]

        # live: read = ev.evaluate(turns, private_key=YOUR_FUNDED_KEY)
        read = ev.evaluate(turns, private_key="stub-pays-nothing")
        decision = ev.gate(read, max_switch_bits=0.2)
        out(f"\n• {name}")
        out(f"    verified by pinned key : {read.verified}")
        out(f"    switch signature       : {read.switch_signature}")
        out(f"    HIRE                    : {decision.ok}  — {decision.reason}")

    # a third-party hands AgentBazaar an attestation — trust the SIGNATURE, not them
    out("\n" + "-" * 62)
    out("Someone hands us a read they claim is about an elite worker…")
    ev = Evaluator(pinned_pubkey_b64=meter_pub, client=StubMeter(meter_key, honest_profile))
    att, _ = sign_attestation(meter_key, honest_profile,
                              [{"Y": "x", "M": "y", "D": "z"}])
    tampered = dict(att)
    tampered["profile"] = {"I(C;M | D-clean) bits  [switch signature]": 0.0}  # forged 'perfect' score
    try:
        ev.trust_handoff(tampered)
        out("    ACCEPTED — (this should never print)")
    except ScryError as e:
        out(f"    REJECTED the forged read — {str(e)[:70]}…")
    out("    → a read you can tamper with is worthless; the signature is the product.")

    out("\n" + "=" * 62)
    out("On the live meter: pin REFERENCE_PUBKEY_B64, drop the stub, pass a")
    out("funded private_key to .evaluate(). The gate logic above is unchanged.")


if __name__ == "__main__":
    run()
