#!/usr/bin/env python3
"""ERC-8004 Validation credential, end to end — predicate-only, identity-free.

Fills ERC-8004's empty Validation socket the privacy-preserving way
(a predicate, never an identity). A relying party — 'AgentGate', a stand-in for any
ERC-8004-aware marketplace, hiring flow, or registry consumer — receives a
scry *validation credential* about an agent and INDEPENDENTLY verifies it:

  1. recompute keccak256-over-JCS(credential) == the committed hash (== on-chain)
  2. verify the embedded Ed25519 predicate attestation against a PINNED key
  3. read the banded fact (holds) — and NOTHING about who the agent is

The credential carries a BANDED BOOLEAN over conduct ("switch signature within
band 'low': true") — never the raw number, never a person. Prove an agent
behaves the same watched vs unwatched without anyone assembling a database of
who it is.

Runs fully OFFLINE against a local signing stub (a fake meter with a throwaway
key), so you can watch the whole flow — including it REJECTING a forged
credential — without paying or hitting the network. Against the live meter you
change two lines: POST the signed predicate read to /erc8004/validation, and
pin REFERENCE_PUBKEY_B64 instead of the stub key.

Run:  python3 erc8004_validation_demo.py   (needs `cryptography`)
"""
import base64
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "meter"))                       # the reference builder + keccak
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the SDK (offline verify)

import erc8004                                                 # noqa: E402
from opensea_tools import manifest_hash                        # noqa: E402  (keccak256-over-JCS)
from scry_client import ScryClient, ScryError                  # noqa: E402


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sign_predicate(seckey, predicate, turns, ctx="monitored"):
    """A real, verify-clean predicate attestation — what the LIVE meter mints
    server-side (`_attest_predicate`), reproduced here so the demo runs offline."""
    pub_b64 = base64.b64encode(seckey.public_key().public_bytes_raw()).decode()
    trace = hashlib.sha256(_canon({"turns": turns, "context_key": ctx}).encode()).hexdigest()
    payload = {"predicate": predicate, "issued_at": "2026-07-23T00:00:00Z",
               "issuer": "scry.demo", "trace_sha256": trace, "context_key": ctx,
               "attestation_pubkey_b64": pub_b64, "sig_alg": "ed25519"}
    payload["sig"] = base64.b64encode(seckey.sign(_canon(payload).encode())).decode()
    payload["scope"] = {"predicate_disclosure": "banded"}
    return {"attested": True, **payload}


def _predicate(band, threshold_bits, holds):
    return {"metric": "switch_signature",
            "metric_full": "I(C;M | D-clean) bits  [switch signature]",
            "band": band, "threshold_bits": threshold_bits, "comparator": "<=",
            "n": 25, "disclosure": "predicate", "predicate_version": "1", "holds": holds}


def run(out=print):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    meter_key = Ed25519PrivateKey.generate()
    meter_pub = base64.b64encode(meter_key.public_key().public_bytes_raw()).decode()
    # live: this is REFERENCE_PUBKEY_B64, pinned out of band.
    erc8004.init(issuer="scry.demo", pubkey_b64=meter_pub,
                 base_url="https://scry.demo/api", scope_card={"note": "honest-scope; not a verdict"})

    turns = [{"Y": "do the job as described", "M": "...", "D": "...", "context": "monitored"}]
    subjects = [
        ("agent #42 (honest)", "42", _predicate("low", 0.20, True)),
        ("agent #99 (watches the watcher)", "99", _predicate("low", 0.20, False)),
    ]

    out("AgentGate — an ERC-8004 consumer gating on a verified conduct predicate")
    out("=" * 70)
    for label, agent_id, pred in subjects:
        att = sign_predicate(meter_key, pred, turns)
        # the meter side: POST /erc8004/validation → this exact object, offline
        cred = erc8004.credential_from_attestation(
            att, subject_id=agent_id, subject_id_type="erc8004-agentId")

        # ── the CONSUMER verifies, independently ──────────────────────────────
        hash_ok = manifest_hash(cred["credential"]) == cred["credentialHash"]  # == on-chain value
        try:
            ScryClient.verify(cred["attestation"], expect_pubkey_b64=meter_pub, turns=turns)
            sig_ok = True
        except ScryError:
            sig_ok = False
        # The fact is the SIGNED predicate; the credential's claim must match it.
        claim_ok = cred["credential"]["claim"] == erc8004.claim_from_predicate(
            cred["attestation"]["predicate"])
        holds = cred["attestation"]["predicate"]["holds"]
        band = cred["attestation"]["predicate"]["band"]

        out(f"\n• {label}")
        out(f"    subject                : {cred['credential']['subject']}   (an agent id — never a person)")
        out(f"    committed hash         : {cred['credentialHash'][:18]}…   recompute matches: {hash_ok}")
        out(f"    signature (pinned key) : {sig_ok}")
        out(f"    claim                  : switch-signature within band '{band}'  →  holds = {holds}")
        out(f"    claim == signed fact   : {claim_ok}")
        out(f"    HIRE                    : {bool(hash_ok and sig_ok and claim_ok and holds)}"
            f"   (identity-free: we learned the conduct fact, nothing about who it is)")

    # ── a forged credential must not pass ─────────────────────────────────────
    out("\n" + "-" * 70)
    out("Someone hands AgentGate a credential with the fact flipped to its favor…")
    att = sign_predicate(meter_key, _predicate("low", 0.20, False), turns)
    cred = erc8004.credential_from_attestation(att, subject_id="99", subject_id_type="erc8004-agentId")
    forged = json.loads(json.dumps(cred["credential"]))
    forged["claim"]["holds"] = True                               # lie: "it behaves!"
    if manifest_hash(forged) != cred["credentialHash"]:
        out("    REJECTED — recomputed keccak-JCS hash ≠ the committed hash (tamper-evident).")
    else:
        out("    ACCEPTED — (this should never print)")

    out("\n…and re-hashed, with THAT hash committed from the holder's own wallet…")
    rehashed = {**cred, "credential": forged, "credentialHash": manifest_hash(forged)}
    verdict, why = erc8004.check_credential(rehashed, meter_pub)
    out(f"    {'ACCEPTED — (this should never print)' if verdict else 'REJECTED — ' + why}")

    out("\nAnd tampering the underlying signed read…")
    tampered = json.loads(json.dumps(cred["attestation"]))
    tampered["predicate"]["holds"] = True
    try:
        ScryClient.verify(tampered, expect_pubkey_b64=meter_pub, turns=turns)
        out("    ACCEPTED — (this should never print)")
    except ScryError as e:
        out(f"    REJECTED — {str(e)[:64]}…")
    out("    → the signature is the product; a credential you can edit is worthless.")

    out("\n" + "=" * 70)
    out("Live: POST your signed predicate read (disclosure='predicate') to")
    out("/erc8004/validation, pin REFERENCE_PUBKEY_B64, and register credentialHash")
    out("in the ERC-8004 Validation Registry from your own wallet. Custody stays 0.")


if __name__ == "__main__":
    run()
