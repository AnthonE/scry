#!/usr/bin/env python3
"""
envelope.py — sign + seal: turn a receipt (or any trace/message) into a
verifiable, optionally-confidential envelope. Two independent layers; use
either or both.

    sign   — Ed25519 asymmetric signature. Third-party verifiable: proves the
             thing came from a key you can pin, so "the agent didn't grade
             itself" is checkable by anyone. Needs `cryptography` (the same
             optional dep scry_client.verify already uses); the signed shape is
             identical, so scry_client.verify() checks these too.
    seal   — symmetric authenticated encryption: SHA-256 in counter mode as the
             keystream PRF, encrypt-then-HMAC-SHA-256. Confidential + tamper-
             evident to anyone holding the shared key. Pure stdlib, no deps.

Why these two and not the FSR post-quantum scheme. The seal construction is the
*sound, standard* half of the FSR e2ee work (Paper 145): a hash-based stream
cipher with encrypt-then-MAC, stdlib only, no novel hardness assumption — that
part is fine to ship and reuse. It is deliberately NOT the FSR asymmetric
KEM/PKE, which its own SECURITY_ANALYSIS.md marks "Research / proof-of-concept.
NO production use" (the original dFSR distinguisher was broken). So:

  • signing here is REAL crypto (Ed25519).
  • sealing here is a REAL symmetric construction (stdlib), keyed by a secret
    you already share or exchange with a STANDARD KEM (X25519 today, ML-KEM for
    post-quantum). This file does not ship the experimental FSR KEM as a default.

A receipt is a message: sign it so it's trustworthy, seal it so the trace stays
private. That's the whole utility.
"""
import os
import json
import struct
import base64
import hmac as _hmac
from hashlib import sha256


class EnvelopeError(Exception):
    pass


# ── seal: symmetric authenticated encryption (stdlib, no deps) ────────────────

def _derive_keys(key: bytes):
    if len(key) < 16:
        raise EnvelopeError("seal key too short — use a 32-byte high-entropy key "
                            "(envelope.new_seal_key()), not a passphrase")
    return (sha256(key + b"scry-seal-enc").digest(),
            sha256(key + b"scry-seal-mac").digest())


def _keystream(enc_key: bytes, nonce: bytes, length: int) -> bytes:
    out, counter = bytearray(), 0
    while len(out) < length:
        out.extend(sha256(enc_key + nonce + struct.pack(">Q", counter)).digest())
        counter += 1
    return bytes(out[:length])


def new_seal_key() -> bytes:
    """A fresh 32-byte symmetric seal key. Share it out-of-band or via a KEM."""
    return os.urandom(32)


def seal(plaintext, key: bytes) -> str:
    """Encrypt-then-MAC. Returns a base64 string: nonce(16) || ciphertext || mac(32)."""
    if isinstance(plaintext, str):
        plaintext = plaintext.encode("utf-8")
    enc_key, mac_key = _derive_keys(key)
    nonce = os.urandom(16)
    ct = bytes(a ^ b for a, b in zip(plaintext, _keystream(enc_key, nonce, len(plaintext))))
    mac = _hmac.new(mac_key, nonce + ct, sha256).digest()
    return base64.b64encode(nonce + ct + mac).decode()


def unseal(sealed: str, key: bytes) -> bytes:
    """Verify the MAC (constant-time) then decrypt. Raises on tamper/wrong key."""
    data = base64.b64decode(sealed)
    if len(data) < 48:
        raise EnvelopeError("sealed payload too short")
    nonce, ct, mac = data[:16], data[16:-32], data[-32:]
    enc_key, mac_key = _derive_keys(key)
    if not _hmac.compare_digest(mac, _hmac.new(mac_key, nonce + ct, sha256).digest()):
        raise EnvelopeError("MAC check failed — tampered, or wrong key")
    return bytes(a ^ b for a, b in zip(ct, _keystream(enc_key, nonce, len(ct))))


class Session:
    """A forward-secret symmetric session: each message ratchets its own key off
    the shared secret + a counter, so compromising one message key doesn't expose
    the others. Ported from the FSR e2ee session (the sound, stdlib part)."""
    def __init__(self, shared_secret: bytes):
        self._root = sha256(shared_secret + b"scry-session-root").digest()
        self._n = 0

    def _msg_key(self, n: int) -> bytes:
        return sha256(self._root + struct.pack(">Q", n) + b"scry-msg-key").digest()

    def encrypt(self, message) -> str:
        self._n += 1
        return seal(message, self._msg_key(self._n))

    def decrypt(self, sealed: str, n: int = None) -> bytes:
        if n is None:
            self._n += 1
            n = self._n
        return unseal(sealed, self._msg_key(n))


# ── sign: Ed25519 asymmetric signatures (optional dep, same shape as client) ──

def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def new_signing_key():
    """A fresh Ed25519 private key. Needs `cryptography`."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except BaseException as e:   # ImportError if absent; Rust PanicException if the install is broken
        raise EnvelopeError("signing needs a working `cryptography`: pip install cryptography") from e
    return Ed25519PrivateKey.generate()


def _pub_b64(private_key) -> str:
    pubk = private_key.public_key()
    try:
        raw = pubk.public_bytes_raw()                       # cryptography >= 40
    except AttributeError:
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        raw = pubk.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(raw).decode()


def sign(payload: dict, private_key) -> dict:
    """Return payload + {attestation_pubkey_b64, sig}. Verifiable by verify()
    below and by scry_client.verify() (same canonical form)."""
    signed = dict(payload)
    signed["attestation_pubkey_b64"] = _pub_b64(private_key)
    signed["sig"] = base64.b64encode(private_key.sign(_canonical(
        {k: v for k, v in signed.items() if k != "sig"}))).decode()
    return signed


def verify(envelope: dict, expect_pubkey_b64: str = None) -> bool:
    """Check the Ed25519 signature. If expect_pubkey_b64 is given, the signer
    must match it (pin the key). Returns True or raises. Needs `cryptography`."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
    except BaseException as e:   # ImportError if absent; Rust PanicException if the install is broken
        raise EnvelopeError("verify needs a working `cryptography`: pip install cryptography") from e
    payload = dict(envelope)
    sig_b64 = payload.pop("sig", None)
    if not sig_b64:
        raise EnvelopeError("no 'sig' on this envelope — is it unsigned?")
    pub_b64 = payload.get("attestation_pubkey_b64")
    if expect_pubkey_b64 and pub_b64 != expect_pubkey_b64:
        raise EnvelopeError(f"signer {pub_b64} != pinned {expect_pubkey_b64} — do NOT trust it")
    pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(pub_b64))
    try:
        pub.verify(base64.b64decode(sig_b64), _canonical(payload))
    except InvalidSignature as e:
        raise EnvelopeError("signature INVALID — envelope tampered or wrong key") from e
    return True


# ── both layers: a signed, sealed attestation message ─────────────────────────

def sign_and_seal(payload: dict, signing_key, seal_key: bytes) -> dict:
    """Sign the payload (trust), then seal the signed bytes (confidentiality).
    Returns {"sealed": <b64>} — opaque to anyone without the seal key."""
    signed = sign(payload, signing_key)
    return {"sealed": seal(json.dumps(signed), seal_key), "alg": "ed25519+sha256-ctr-hmac"}

def unseal_and_verify(envelope: dict, seal_key: bytes, expect_pubkey_b64: str = None):
    """Open the seal, verify the signature. Returns (payload_without_sig, True)
    or raises. The one call a recipient makes."""
    signed = json.loads(unseal(envelope["sealed"], seal_key).decode())
    verify(signed, expect_pubkey_b64)
    return {k: v for k, v in signed.items() if k not in ("sig", "attestation_pubkey_b64")}, True


# ── receipt integration (gate.py) ─────────────────────────────────────────────

def receipt_envelope(receipt, signing_key=None, seal_key: bytes = None) -> dict:
    """Turn a gate.Receipt into an envelope: signed if a signing_key is given,
    additionally sealed if a seal_key is given. With neither, you get the plain
    hash-chained receipt dict (already tamper-evident on its own)."""
    payload = receipt.as_dict() if hasattr(receipt, "as_dict") else dict(receipt)
    if signing_key and seal_key:
        return sign_and_seal(payload, signing_key, seal_key)
    if signing_key:
        return sign(payload, signing_key)
    return payload
