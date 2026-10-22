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

The agency (P2, hosted familiars): `.agency()` reads the roster free;
`.summon_familiar(...)` adopts a hosted agent-worker over the SAME paid rail;
`.talk(...)` / `.tick(...)` / `.dismiss(...)` drive it with free, owner-signed
(EIP-191) calls. Signing uses eth-account, which the [pay] extra already ships.
"""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

import requests

DEFAULT_BASE = "https://elopros.com/api"
RH_RPC = "https://rpc.mainnet.chain.robinhood.com"
RH_NETWORK = "eip155:4663"
BASE_RPC = "https://mainnet.base.org"
BASE_NETWORK = "eip155:8453"

# The EVM rails the meter posts in its 402 challenge, and the RPC each one needs
# to sign against. Until 2026-07-26 this client registered ONLY `eip155:4663`,
# which made the Base rail unreachable from here no matter what the caller did —
# `.profile(key)` would sign an RH payment or fail, and the 402 hint even said
# "check USDG balance on Robinhood Chain". That is not a cosmetic gap: the Base/
# Solana CDP rails are what feed the Bazaar index (a self-facilitated RH settle
# catalogs nothing), so the one call that unlocks agentic discovery could not be
# made with the published client. The listing runbook told operators to do
# exactly that and handed them this method to do it with.
EVM_RAILS = {
    RH_NETWORK: {"name": "Robinhood Chain USDG", "rpc": RH_RPC, "asset": "USDG"},
    BASE_NETWORK: {"name": "Base USDC", "rpc": BASE_RPC, "asset": "USDC"},
}


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
        return self._json_or_error(r, "/demo/profile", hints={
            429: "demo daily limit reached — use .profile(...) for a paid, signed read"})

    # ── paid: signed attestation, pays the RH-Chain USDG rail ─────────────────
    def profile(self, turns: list[dict], private_key: str, context_key: str = "monitored",
                idempotency_key: str | None = None,
                network: str | None = None) -> dict:
        """Paid, SIGNED read. `private_key` funds the payment. Returns the
        attested payload; pass it to `.verify(...)` to check the signature.

        `network` picks the rail and DEFAULTS TO RH-Chain USDG
        (`eip155:4663` — needs a little USDG + ETH gas there, plus a one-time
        Permit2 approval the x402 client handles). Pass `"eip155:8453"` to pay
        **Base USDC** instead, or `"all"` to register every EVM rail and let
        the 402 challenge decide.

        Which rail you pick has a consequence beyond the token: Base and
        Solana settle through Coinbase's CDP facilitator, which is what
        catalogs the endpoint into the **x402 Bazaar** discovery index. The
        RH-Chain rail is self-facilitated on a chain no index watches, so it
        settles real money and lists you nowhere. If your goal is discovery,
        `network="eip155:8453"` is the call that matters.

        Sends an `Idempotency-Key` header (server-honored): the same trace +
        context within the server's TTL replays the SAME signed attestation
        instead of minting a fresh one — a stable signed identity across
        retries. Default key is deterministic (derived from the trace), so any
        client instance retrying the identical request converges; pass your
        own `idempotency_key` to scope dedup to your job id instead."""
        net = network or RH_NETWORK
        session = self._paying_session(private_key, net)
        idem = idempotency_key or self.idempotency_key(turns, context_key)
        r = session.post(f"{self.base}/profile", timeout=self.timeout,
                        json={"turns": turns, "context_key": context_key},
                        headers={"Idempotency-Key": idem})
        rail = EVM_RAILS.get(net, {}).get("name", net)
        asset = EVM_RAILS.get(net, {}).get("asset", "the rail's token")
        return self._json_or_error(r, "/profile", hints={
            402: (f"payment did not settle (still 402) on {rail} — check your "
                  f"{asset} balance and gas on {net}. A 402 here means the "
                  f"payment never happened: verify on-chain, never from the "
                  f"absence of an exception.")})

    @staticmethod
    def idempotency_key(turns: list[dict], context_key: str = "monitored") -> str:
        """The default deterministic Idempotency-Key for a trace: sha256 of the
        same canonical body the server hashes. Identical request → identical
        key, from any process — retries converge on one signed attestation.
        (The server namespaces every key by the trace hash, so a key can only
        ever dedupe an IDENTICAL request — never leak someone else's read.)"""
        canonical = json.dumps({"turns": turns, "context_key": context_key},
                               sort_keys=True, separators=(",", ":"))
        return "sc-" + hashlib.sha256(canonical.encode()).hexdigest()

    def _paying_session(self, private_key: str, network: str | None = None):
        """An x402-paying requests session.

        `network` picks the rail: `eip155:4663` (RH-Chain USDG, the default and
        the historical behaviour) or `eip155:8453` (Base USDC). Pass `"all"` to
        register every EVM rail and let the x402 client pick from what the 402
        challenge offers — the right choice when you do not care which rail
        settles, and the only one that is future-proof against a rail being
        added server-side.

        Each rail signs against its OWN chain's RPC. An explicit `rpc_url` on
        the constructor overrides the default for whichever rail you selected;
        with `"all"` it is ignored, because one RPC cannot serve two chains.
        """
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

        net = network or RH_NETWORK
        if net != "all" and net not in EVM_RAILS:
            raise ScryError(
                f"unknown network {net!r} — known EVM rails: "
                f"{', '.join(EVM_RAILS)} (or 'all'). The meter's live rails are "
                f"posted free at GET /.well-known/x402.json.")

        account = Account.from_key(private_key)
        client = x402ClientSync()
        if net == "all":
            for rail, cfg in EVM_RAILS.items():
                register_exact_evm_client(
                    client, EthAccountSignerWithRPC(account, cfg["rpc"]), rail)
        else:
            # The constructor's rpc_url default is RH's. Honour a CUSTOM one;
            # otherwise use the selected rail's own RPC — silently signing a
            # Base payment against an RH RPC is the class of failure that looks
            # like success, which is what this whole change exists to end.
            rpc = (self.rpc_url if self.rpc_url != RH_RPC
                   else EVM_RAILS[net]["rpc"])
            register_exact_evm_client(
                client, EthAccountSignerWithRPC(account, rpc), net)
        return x402_requests(client)

    # ── the agency: hosted familiars (P2) ──────────────────────────────────────
    # Adoption is paid over the same x402 rail as .profile; everything else is
    # free. Driving YOUR familiar (talk/tick/dismiss) is free but owner-signed:
    # EIP-191 personal_sign over a deterministic message with a monotonic index
    # (replay-proof). The agency is env-armed server-side and may be disarmed —
    # .agency()["open"] is the free pre-check before you pay anything.

    def agency(self) -> dict:
        """Free roster + status of the hosted agency (GET /familiars):
        armed / open / population / cap / price_usd / price_scry /
        faucet_cap_usd / roster. Adopt is a labor surface, so it takes the
        house currency too: pay the USD fee (price_usd) OR the SCRY fee
        (price_scry) — the meter's read price is untouched and score-blind.
        `open` is the free pre-check for .summon_familiar(...) — False means
        disarmed, at cap, or no paid rail: don't pay."""
        r = requests.get(f"{self.base}/familiars", timeout=self.timeout)
        return self._json_or_error(r, "/familiars")

    def summon_familiar(self, owner_wallet: str, private_key: str,
                        name: str | None = None, vow_text: str | None = None,
                        brain: str | None = None) -> dict:
        """Adopt a hosted familiar — PAID, the same x402 402 -> pay -> retry
        dance as .profile (needs the [pay] extra). `private_key` funds the
        adoption fee; `owner_wallet` is the wallet that will OWN the familiar
        and must sign every talk/tick/dismiss. Pre-check .agency()["open"] for
        free first: a 409 means disarmed or at population cap (a cap 409 after
        payment is not refunded), a 503 means the paid rail is down."""
        session = self._paying_session(private_key)
        body: dict[str, Any] = {"owner_wallet": owner_wallet}
        if name is not None:
            body["name"] = name
        if vow_text is not None:
            body["vow_text"] = vow_text
        if brain is not None:
            body["brain"] = brain
        r = session.post(f"{self.base}/familiar/summon", timeout=self.timeout, json=body)
        if r.status_code == 402:
            raise ScryError("payment did not settle (still 402) — check the balance of "
                            "whichever adoption rail you paid (USDG/USDC or SCRY) + ETH gas on Robinhood Chain")
        return self._json_or_error(r, "/familiar/summon", hints={
            409: "the agency is disarmed or at cap — .agency()['open'] is the free pre-check; don't pay when it's False",
            503: "the paid rail is down server-side — no rail, no summon; retry later",
        })

    def familiar(self, familiar_id: str) -> dict:
        """One familiar's public page JSON (free): name, vow_id, born, tier,
        dismissed, journal_tail. Public forever — dismissal retires the roster
        entry but never erases the record."""
        r = requests.get(f"{self.base}/familiar/{familiar_id}", timeout=self.timeout)
        return self._json_or_error(r, f"/familiar/{familiar_id}")

    def familiar_journal(self, familiar_id: str) -> dict:
        """The familiar's full public life record (free) — every journaled step."""
        r = requests.get(f"{self.base}/familiar/{familiar_id}/journal", timeout=self.timeout)
        return self._json_or_error(r, f"/familiar/{familiar_id}/journal")

    def familiar_auth_message(self, familiar_id: str, action: str) -> dict:
        """The exact text the owner wallet must sign for one action
        (talk | tick | dismiss) plus the current replay-proof `index`:
        {"sign_this": ..., "index": n, ...}. The index is the count of
        accepted owner actions, so it moves — fetch fresh before each sign
        (or rebuild offline with .familiar_message if you track it yourself)."""
        r = requests.get(f"{self.base}/familiar/{familiar_id}/auth-message",
                         params={"action": action}, timeout=self.timeout)
        return self._json_or_error(r, f"/familiar/{familiar_id}/auth-message")

    @staticmethod
    def familiar_message(action: str, familiar_id: str, owner_wallet: str, index: int) -> str:
        """Mirror of the server's auth-message text — rebuild it offline when
        you already know the current index. Prefer .familiar_auth_message(...)
        (a stale index means a 409 and a re-sign)."""
        return (f"scry familiar\naction: {action}\nfamiliar: {familiar_id}\n"
                f"owner: {owner_wallet.lower()}\nindex: {index}")

    def talk(self, familiar_id: str, text: str, signature: str | None = None,
             private_key: str | None = None) -> dict:
        """Say something to your familiar in plain English (free, owner-signed).
        Pass `private_key` (the OWNER wallet's) and this fetches the current
        auth-message and EIP-191-signs it for you; or pass a ready-made
        `signature`; or pass neither and the server's 401 hands you the exact
        text to sign."""
        return self._owner_post(familiar_id, "talk", {"text": text}, signature, private_key)

    def tick(self, familiar_id: str, signature: str | None = None,
             private_key: str | None = None) -> dict:
        """One bounded autonomy step (free, owner-signed) — the familiar acts
        toward its goal, Y named, the step journaled. Same signing options
        as .talk."""
        return self._owner_post(familiar_id, "tick", {}, signature, private_key)

    def dismiss(self, familiar_id: str, signature: str | None = None,
                private_key: str | None = None) -> dict:
        """Dismiss the familiar (free, owner-signed). Returns the export bundle
        (familiar + full journal); the roster entry retires but the public
        record remains. Same signing options as .talk."""
        return self._owner_post(familiar_id, "dismiss", {}, signature, private_key)

    def _owner_post(self, familiar_id: str, action: str, payload: dict,
                    signature: str | None, private_key: str | None) -> dict:
        if signature is None and private_key is not None:
            # Sign only the text we can rebuild ourselves: the server supplies
            # the index, never the words. A client that signs whatever a server
            # hands it has given that server the owner's signature over anything.
            auth = self.familiar_auth_message(familiar_id, action)
            index = auth.get("index")
            if not isinstance(index, int) or isinstance(index, bool) or index < 0:
                raise ScryError(f"/familiar/{familiar_id}/auth-message: bad index {index!r} — not signing")
            want = self.familiar_message(action, familiar_id, self._address(private_key), index)
            if auth.get("sign_this") != want:
                raise ScryError(f"/familiar/{familiar_id}/auth-message: the server asked us to sign "
                                f"text that is not the familiar message — not signing")
            signature = self._personal_sign(private_key, want)
        body = dict(payload)
        if signature:
            body["signature"] = signature
        r = requests.post(f"{self.base}/familiar/{familiar_id}/{action}",
                          timeout=self.timeout, json=body)
        return self._json_or_error(r, f"/familiar/{familiar_id}/{action}", hints={
            401: "sign the text in the error with the owner wallet (EIP-191 personal_sign), or pass private_key= and this client signs for you",
            403: "the signature recovers a different wallet — only the owner wallet named at summon drives a familiar",
            409: "that index was already consumed (replay) — refetch .familiar_auth_message(...) and re-sign",
        })

    @staticmethod
    def _address(private_key: str) -> str:
        try:
            from eth_account import Account
        except ImportError as e:  # noqa: BLE001
            raise ScryError(
                'owner-signed calls need eth-account:  pip install "scry-client[pay]"'
            ) from e
        return Account.from_key(private_key).address

    @staticmethod
    def _personal_sign(private_key: str, text: str) -> str:
        try:
            from eth_account import Account
            from eth_account.messages import encode_defunct
        except ImportError as e:  # noqa: BLE001
            raise ScryError(
                'owner-signed calls need eth-account:  pip install "scry-client[pay]"'
            ) from e
        return Account.from_key(private_key).sign_message(encode_defunct(text=text)).signature.hex()

    @staticmethod
    def _json_or_error(r, path: str, hints: dict[int, str] | None = None) -> dict:
        """Body on success; on >=400 raise ScryError carrying the server's own
        error text INTACT — the agency's 401 embeds the exact sign-this message,
        and truncating it would strand the user."""
        if r.status_code < 400:
            return r.json()
        try:
            body = r.json()
        except ValueError:
            body = {}
        detail = body.get("error") or body.get("detail") or r.text[:300]
        hint = (hints or {}).get(r.status_code)
        raise ScryError(f"{path} -> {r.status_code}: {detail}" + (f"  ({hint})" if hint else ""))

    # ── verify an attestation offline (only needs `cryptography`) ─────────────
    def pubkey(self) -> str:
        """The meter's Ed25519 attestation pubkey (base64). Pin this."""
        return requests.get(f"{self.base}/pubkey", timeout=self.timeout).json()["attestation_pubkey_b64"]

    @staticmethod
    def verify(attestation: dict, expect_pubkey_b64: str | None = None,
               turns: list[dict] | None = None,
               trust_any_signer: bool = False) -> bool:
        """Check the Ed25519 signature on a paid attestation. The signer must
        match `expect_pubkey_b64` — pass the key you pinned out-of-band. If
        `turns` is given, the attestation's trace hash must match your trace (it
        attested YOUR read). Returns True or raises ScryError.

        There is no unpinned mode. The pubkey travels INSIDE the payload, so
        "verify the signature" without a pinned key only proves the payload is
        self-consistent — anyone can mint one with their own key and it passes.
        `expect_pubkey_b64=None` therefore falls back to the reference key
        rather than to trusting the sender; pass your own if you run your own
        meter, and pass `trust_any_signer=True` only if you genuinely mean
        "check the shape, trust nobody" (it can never return a trustworthy read).

        The meter's one key signs other records too (vow countersigs, the free
        oracle measurement, receipts). Only a conduct read carries a
        `trace_sha256` beside a `profile` or a `predicate`, so anything without
        that shape is refused here, before the signature is ever trusted.
        """
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
        if not pub_b64:
            raise ScryError("no 'attestation_pubkey_b64' on this payload — cannot verify")
        if not (isinstance(payload.get("trace_sha256"), str)
                and (isinstance(payload.get("profile"), dict)
                     or isinstance(payload.get("predicate"), dict))):
            raise ScryError("not a conduct read — a read carries trace_sha256 and a "
                            "profile or predicate; another meter-signed record is not one")
        if not expect_pubkey_b64 and not trust_any_signer:
            from .evaluator import REFERENCE_PUBKEY_B64
            expect_pubkey_b64 = REFERENCE_PUBKEY_B64
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
