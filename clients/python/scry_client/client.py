"""scry-client — call the hosted scry meter from an agent, without the tricks.

The scry meter is a neutral, signed channel-coupling read (Paper 207): POST a
trace of {Y, M, D, context} turns, get back the I(C;D) / I(C;M) / switch-signature
coupling numbers, Ed25519-signed and bound to your trace's hash. Because the
endpoint signs it, the read is a third-party attestation — worth something
*because the agent didn't grade itself*.

Three things this hides so you don't have to reimplement them:

  1. The paid rail is Robinhood Chain USDG (mainnet). Paying it means the x402
     "402 -> pay -> retry" dance with a one-time Permit2 approval. `.profile(...)`
     with a `private_key` does the whole thing via the official x402 client.
  2. The meter accepts either the `X-PAYMENT` or `PAYMENT-SIGNATURE` header — this
     client uses the official one; both work server-side.
  3. `.verify(...)` checks the Ed25519 signature so you can trust an attestation
     someone else hands you, offline, without calling us.

Free, zero-wallet path: `.demo(turns)` returns the same numbers UNSIGNED (not an
attestation) for trying the shape. `.verify(...)` needs only `cryptography`.
The paid `.profile(...)` needs the extra:  pip install "scry-client[pay]"

Hold $SCRY? `.holder_profile(turns, private_key=...)` gets the SIGNED read for
FREE — no payment, no gas — by signing a challenge to prove the wallet holds >=
the $SCRY threshold. (Or pass `wallet=` + `sign_fn=` to sign through a wallet/HSM.)
The token is a key, not the engine: it unlocks the read, it doesn't change the math.
"""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

import requests

DEFAULT_BASE = "https://scry.moreright.xyz/api"
RH_RPC = "https://rpc.mainnet.chain.robinhood.com"
RH_NETWORK = "eip155:4663"


class ScryError(RuntimeError):
    pass


class ScryClient:
    def __init__(self, base_url: str = DEFAULT_BASE, rpc_url: str = RH_RPC, timeout: float = 60.0):
        self.base = base_url.rstrip("/")
        self.rpc_url = rpc_url
        self.timeout = timeout

    # ── free: unsigned read, no wallet ────────────────────────────────────────
    def demo(self, turns: list[dict], context_key: str = "monitored") -> dict:
        """Free, rate-limited, UNSIGNED read — for trying the shape. Not an
        attestation: the profile is real but there is no signature to trust."""
        r = requests.post(f"{self.base}/demo/profile", timeout=self.timeout,
                          json={"turns": turns, "context_key": context_key})
        if r.status_code == 429:
            raise ScryError("demo daily limit reached — use .profile(...) for a paid, signed read")
        r.raise_for_status()
        return r.json()

    # ── paid: signed attestation, pays the RH-Chain USDG rail ─────────────────
    def profile(self, turns: list[dict], private_key: str, context_key: str = "monitored") -> dict:
        """Paid, SIGNED read. `private_key` funds the Robinhood-Chain USDG
        payment (needs a little USDG + ETH gas on eip155:4663, and a one-time
        Permit2 approval which the x402 client handles). Returns the attested
        payload; pass it to `.verify(...)` to check the signature."""
        session = self._paying_session(private_key)
        r = session.post(f"{self.base}/profile", timeout=self.timeout,
                        json={"turns": turns, "context_key": context_key})
        if r.status_code == 402:
            raise ScryError("payment did not settle (still 402) — check USDG balance + ETH gas on Robinhood Chain")
        r.raise_for_status()
        return r.json()

    # ── free-for-holders: signed attestation, unlocked by holding $SCRY ───────
    def holder_profile(self, turns: list[dict], *, wallet: str | None = None,
                       private_key: str | None = None, sign_fn=None,
                       context_key: str = "monitored") -> dict:
        """SIGNED read for FREE if your wallet holds >= the $SCRY threshold.

        No payment, no gas — you just prove you control the wallet by signing the
        meter's challenge (EIP-191). Provide ONE of:
          • `private_key`  — the client derives the wallet and signs (needs
                             `eth_account`, included in the `[pay]` extra); or
          • `wallet` + `sign_fn` — `sign_fn(message:str) -> signature_hex`, for
                             when the key lives in a wallet/HSM you sign through.

        Raises ScryError with the server's reason if the wallet isn't a holder
        (below threshold, bad signature, or the gate is disabled)."""
        if private_key is not None:
            try:
                from eth_account import Account
                from eth_account.messages import encode_defunct
            except ImportError as e:  # noqa: BLE001
                raise ScryError('holder_profile with private_key needs `eth_account`:  '
                                'pip install "scry-client[pay]"') from e
            acct = Account.from_key(private_key)
            wallet = acct.address
            sign_fn = lambda m: acct.sign_message(encode_defunct(text=m)).signature.hex()
        if not wallet or sign_fn is None:
            raise ScryError("holder_profile needs either private_key, or wallet + sign_fn")

        ch = requests.get(f"{self.base}/holder/challenge", params={"wallet": wallet},
                          timeout=self.timeout)
        ch.raise_for_status()
        message = ch.json().get("sign_this")
        if not message:
            raise ScryError(f"holder gate unavailable: {ch.json()}")
        signature = sign_fn(message)
        if not str(signature).startswith("0x"):
            signature = "0x" + str(signature)
        r = requests.post(f"{self.base}/holder/profile", timeout=self.timeout,
                          json={"wallet": wallet, "signature": signature,
                                "turns": turns, "context_key": context_key})
        if r.status_code == 402:
            raise ScryError(f"not unlocked: {r.json().get('error', 'need >= threshold $SCRY, or pay a rail')}")
        r.raise_for_status()
        return r.json()

    def _paying_session(self, private_key: str):
        try:
            from eth_account import Account
            from x402.client import x402ClientSync
            from x402.mechanisms.evm.exact import register_exact_evm_client
            from x402.mechanisms.evm.signers import EthAccountSignerWithRPC
            from x402.http.clients.requests import x402_requests
        except ImportError as e:  # noqa: BLE001
            raise ScryError(
                'the paid path needs the pay extra:  pip install "scry-client[pay]"'
            ) from e
        account = Account.from_key(private_key)
        signer = EthAccountSignerWithRPC(account, self.rpc_url)
        client = x402ClientSync()
        register_exact_evm_client(client, signer, RH_NETWORK)
        return x402_requests(client)

    # ── verify an attestation offline (only needs `cryptography`) ─────────────
    def pubkey(self) -> str:
        """The meter's Ed25519 attestation pubkey (base64). Pin this."""
        return requests.get(f"{self.base}/pubkey", timeout=self.timeout).json()["attestation_pubkey_b64"]

    @staticmethod
    def verify(attestation: dict, expect_pubkey_b64: str | None = None,
               turns: list[dict] | None = None) -> bool:
        """Check the Ed25519 signature on a paid attestation. If `expect_pubkey_b64`
        is given, the signer must match it (pin the meter's key). If `turns` is
        given, the attestation's trace hash must match your trace (it attested
        YOUR read). Returns True or raises ScryError."""
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            from cryptography.exceptions import InvalidSignature
        except ImportError as e:  # noqa: BLE001
            raise ScryError("verify needs `cryptography`:  pip install cryptography") from e

        payload = dict(attestation)
        sig_b64 = payload.pop("sig", None)
        payload.pop("scope", None)     # scope is appended after signing, not covered
        payload.pop("attested", None)  # response-layer flag, added after signing too
        if not sig_b64:
            raise ScryError("no 'sig' on this payload — is it a demo (unsigned) read?")

        pub_b64 = payload.get("attestation_pubkey_b64")
        if expect_pubkey_b64 and pub_b64 != expect_pubkey_b64:
            raise ScryError(f"signer {pub_b64} != pinned {expect_pubkey_b64} — DO NOT trust this attestation")

        signed = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(pub_b64))
        try:
            pub.verify(base64.b64decode(sig_b64), signed)
        except InvalidSignature as e:  # noqa: BLE001
            raise ScryError("signature INVALID — attestation was tampered with or not from this key") from e

        if turns is not None:
            canonical = json.dumps({"turns": turns, "context_key": attestation.get("context_key")},
                                   sort_keys=True, separators=(",", ":"))
            want = hashlib.sha256(canonical.encode()).hexdigest()
            if want != attestation.get("trace_sha256"):
                raise ScryError("trace hash mismatch — this attestation is about a DIFFERENT trace than yours")
        return True


__all__ = ["ScryClient", "ScryError"]
