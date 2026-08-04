"""scry-wallet — drive scry's identity actions with the wallet you already have.

A stock agent wallet (OpenClaw Agent Wallet CLI, MetaMask Agent Wallet,
Coinbase CDP) auto-signs PAYMENTS (x402) but never an arbitrary identity
challenge. This adapter closes that one gap by driving `/prepare/sign`: it
fetches the exact EIP-191 message scry wants, signs it with YOUR wallet, and
submits. It targets EIP-191, not any one wallet, so it rides all of them.

No key is required BY the adapter. You pass a `signer(message) -> signature`
that calls whatever wallet you run; the adapter never has to see a key. A
convenience `local_signer(key)` (self-custodial PRIVATE_KEY mode, via
eth_account) is provided for the common case. Custody stays where it belongs:
your wallet holds the key, scry holds none — the sign-index it calls is pure
metadata (WALLETS.md §9, /prepare/sign).

Deterministic actions (vow, listing, hive-bind, play) come back with the
message materialized; stateful ones (familiar-auth, holder) embed a
server-issued index/nonce, so the adapter FETCHES the live challenge the
recipe names instead of inventing one.

Dependency-light: stdlib HTTP (urllib) by default; pass your own `http`
callable to use any client. eth_account is only touched by `local_signer`.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE = "https://scry.moreright.xyz/api"


class ScryWalletError(RuntimeError):
    def __init__(self, message, detail=None):
        super().__init__(message)
        self.detail = detail


def _urllib_http(method, url, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"content-type": "application/json"} if data is not None else {}
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (https base)
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        try:
            detail = json.loads(detail)
        except Exception:  # noqa: BLE001
            pass
        raise ScryWalletError(f"{method} {url} -> HTTP {e.code}", detail)


def local_signer(private_key):
    """A signer backed by a local key via eth_account — the self-custodial
    PRIVATE_KEY mode. Returns (signer, address). Optional: any wallet that can
    EIP-191 personal_sign works via a plain callable instead, no key exposed."""
    from eth_account import Account
    from eth_account.messages import encode_defunct
    acct = Account.from_key(private_key)

    def _sign(message):
        return acct.sign_message(encode_defunct(text=message)).signature.hex()

    return _sign, acct.address


class ScryWallet:
    """Wrap your wallet. `signer` is a callable(message:str)->signature:str;
    `wallet_address` fills the owner/holder fields recipes leave for you."""

    def __init__(self, signer, wallet_address=None, base=DEFAULT_BASE, http=None):
        self.sign = signer
        self.address = wallet_address
        self.base = base.rstrip("/")
        self._http = http or _urllib_http

    # ── HTTP ──────────────────────────────────────────────────────────────────
    def _url(self, path, params=None):
        url = self.base + path
        if params and "?" not in path:
            q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            if q:
                url += "?" + q
        return url

    def _get(self, path, params=None):
        return self._http("GET", self._url(path, params))

    def _post(self, path, body):
        return self._http("POST", self._url(path), body)

    # ── the flow ────────────────────────────────────────────────────────────
    def recipe(self, action, /, **params):
        """GET /prepare/sign/{action} — the message + the submit recipe.
        `action` is positional-only so it never collides with a recipe param
        that is itself named `action` (familiar-auth's talk/tick/dismiss)."""
        return self._get(f"/prepare/sign/{action}", params)

    def _resolve(self, action, recipe):
        """The exact string to sign, from a recipe: the materialized message
        for a deterministic action, or the live challenge for a stateful one.
        Never fabricates a server-issued index or nonce."""
        if recipe.get("sign_this") is not None:
            return recipe["sign_this"]
        fetch = recipe.get("fetch") or {}
        if not fetch.get("path"):
            raise ScryWalletError(f"stateful action {action!r} has no live challenge to fetch", recipe)
        live = self._get(fetch["path"])  # path already carries its own query
        if not live.get("sign_this"):
            raise ScryWalletError(f"live challenge for {action!r} returned no sign_this", live)
        return live["sign_this"]

    def message(self, action, /, **params):
        """Return (sign_this, recipe): the exact string to personal_sign.
        Deterministic actions return the materialized message; stateful ones
        (familiar-auth, holder) fetch the live challenge the recipe names."""
        r = self.recipe(action, **params)
        return self._resolve(action, r), r

    def act(self, action, /, submit_extra=None, **params):
        """Full fetch -> sign -> post for a one-call identity record
        (vow, listing, hive-bind, familiar-auth). Returns the server response.
        Actions whose submit isn't a single POST (play, holder) raise BEFORE
        any signing — use `.message()` and submit them yourself, since their
        bodies vary."""
        r = self.recipe(action, **params)
        submit = r.get("submit") or {}
        if submit.get("method") != "POST" or not str(submit.get("path", "")).startswith("/"):
            raise ScryWalletError(
                f"{action!r} is not a one-call POST — call .message() and submit it yourself",
                submit)
        # Fields the adapter cannot mint (a hive BIND's Nostr-key-signed event, a
        # familiar talk's command text) are declared by the recipe as `requires`
        # and MUST arrive via submit_extra — fail fast, never a silent 422.
        extra = submit_extra or {}
        missing = [f for f in (submit.get("requires") or []) if f not in extra]
        if missing:
            raise ScryWalletError(
                f"{action!r} needs caller-supplied field(s) {missing} via submit_extra — e.g. a hive "
                "BIND needs the npub-key-signed `event` (GET /hive/message); a familiar talk needs "
                "`text`. Pass them in submit_extra, or use .message() and submit yourself.", submit)
        msg = self._resolve(action, r)
        body = dict(submit.get("body") or {})
        body["signature"] = self.sign(msg)
        if body.get("wallet") in (None, "", "<your EVM address>"):
            body["wallet"] = self.address
        # strip any leftover placeholder scaffolding the recipe included
        body = {k: v for k, v in body.items()
                if k == "signature"
                or not (isinstance(v, str) and v.startswith("<") and v.endswith(">"))}
        body.update(submit_extra or {})
        return self._post(submit["path"], body)


__all__ = ["ScryWallet", "ScryWalletError", "local_signer", "DEFAULT_BASE"]
