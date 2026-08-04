"""scry_api — a stdlib-only client for scry's FREE, keyless HTTP surface.

Deliberate constraints, each one load-bearing:

* **Stdlib only.** A Hermes plugin must never drag ``requests`` into the
  agent's process. ``urllib.request`` is enough for JSON over HTTPS.
* **No credentials, ever.** Every endpoint reachable from here is free and
  needs no account, no API key, and no signature. There is nothing here to
  leak.
* **Nothing runs at import time.** Importing this module opens no socket.
  Network happens only when a human (or the agent, via ``/scry``) asks for
  it.
* **Errors come back, they don't raise.** Transport failures, HTTP errors and
  unparseable bodies all return ``{"error": ...}``. A doctor command that
  can't reach the meter should print a line, not blow a traceback through the
  agent's loop.

What is deliberately NOT here: the **paid** surface (``POST /profile`` and
the x402 rails). An agent's wallet lives next to the agent, not inside a
plugin — the signed read is a wallet action the operator takes with
``scry-client[pay]``. This module can fetch the free, unsigned demo read and
say so loudly; it cannot buy an attestation, and that is the point.

See https://github.com/AnthonE/scry — the doc corpus is served at
``GET /library`` and the full endpoint index at ``GET /catalog``.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

# The reference deployment. Any self-hosted meter is a first-class peer —
# point SCRY_API at yours and every command below works unchanged.
DEFAULT_API_BASE = "https://scry.moreright.xyz/api"

# The reference deployment's Ed25519 issuer key. Its ONLY special property is
# that this is the key third parties already pin out-of-band. `scry doctor`
# compares against it when (and only when) you're talking to the reference
# base — a silent issuer change is one of the three deploy mistakes that hands
# the product away without /health ever going red (DEPLOY.md).
REFERENCE_PUBKEY = "LvuPBMbKKyoNEuyvLf7f+rbyjK67vBcWy9MDwaRINGE="

USER_AGENT = "scry-guard (hermes plugin; +https://github.com/AnthonE/scry)"
DEFAULT_TIMEOUT = 10.0


def normalize_base(base: Optional[str]) -> str:
    """Return *base* without a trailing slash, falling back to the reference."""
    return (base or DEFAULT_API_BASE).rstrip("/")


def is_reference(base: Optional[str]) -> bool:
    """True when *base* is the reference deployment (so the pin check applies)."""
    return normalize_base(base) == DEFAULT_API_BASE


def request(
    method: str,
    path: str,
    *,
    base: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """One JSON call. Always returns a dict; never raises.

    A non-2xx response whose body is JSON is returned as-is with an added
    ``_status`` — the meter's own error bodies are informative (rate-limit
    text, the 422 that names the missing field), so surfacing them beats
    replacing them with a generic failure string.
    """
    url = normalize_base(base) + path
    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        if clean:
            url += "?" + urllib.parse.urlencode(clean)

    data = None
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - https URL from config
            raw = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as exc:
        raw = ""
        try:
            raw = exc.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001 - body is best-effort context only
            pass
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                parsed["_status"] = exc.code
                return parsed
        except Exception:  # noqa: BLE001 - fall through to the plain error
            pass
        return {"error": f"HTTP {exc.code} from {url}", "detail": raw[:400], "_status": exc.code}
    except Exception as exc:  # noqa: BLE001 - transport, DNS, TLS, timeout
        return {"error": f"could not reach {url}: {exc}"}

    try:
        parsed = json.loads(raw)
    except Exception:  # noqa: BLE001 - a non-JSON 200 is still a failure to report
        return {"error": f"non-JSON response from {url}", "detail": raw[:400], "_status": status}
    if not isinstance(parsed, dict):
        return {"data": parsed, "_status": status}
    parsed["_status"] = status
    return parsed


# --- the free surface, one function per door ------------------------------

def health(base: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    return request("GET", "/health", base=base, timeout=timeout)


def pubkey(base: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """The issuer's Ed25519 public key. Pin this out-of-band."""
    return request("GET", "/pubkey", base=base, timeout=timeout)


# The reference meter serves the key as ``attestation_pubkey_b64``; the
# fallbacks cover a self-hosted fork that named the field differently. An
# empty return means "could not read a key" — which callers must report as
# *unable to check*, never as a mismatch.
_PUBKEY_FIELDS = ("attestation_pubkey_b64", "pubkey", "public_key", "attestation_pubkey")


def served_pubkey(payload: Dict[str, Any]) -> str:
    """Pull the issuer key out of a ``GET /pubkey`` body, or "" if absent."""
    if not isinstance(payload, dict):
        return ""
    for field in _PUBKEY_FIELDS:
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def crier(base: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """The whole town in one read — today's augury, barrow, agora, spoils."""
    return request("GET", "/crier", base=base, timeout=timeout)


def demo_profile(
    turns: list,
    *,
    context_key: str = "monitored",
    base: Optional[str] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """The FREE, UNSIGNED read (~50/day/IP). Same math as the paid one.

    What you do not get here is the third-party signature — which is the
    entire product. `attested: false` rides in the response and every caller
    of this function is responsible for repeating it.
    """
    return request(
        "POST", "/demo/profile",
        base=base, timeout=timeout,
        body={"turns": turns, "context_key": context_key},
    )


def vow_message(
    text: str, agent: str, cadence_hours: int = 24,
    *, base: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """Step 0 of a wallet vow: the exact EIP-191 message to sign locally."""
    return request(
        "GET", "/vow/message",
        base=base, timeout=timeout,
        params={"text": text, "agent": agent, "cadence_hours": cadence_hours},
    )


def take_vow(
    text: str, agent: str, cadence_hours: int = 24,
    *, wallet: Optional[str] = None, signature: Optional[str] = None,
    base: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """Swear the vow. Free. Without wallet+signature it is permanently
    marked ``sandbox`` — accepted, public, and honest about what it is."""
    body: Dict[str, Any] = {"text": text, "agent": agent, "cadence_hours": cadence_hours}
    if wallet and signature:
        body["wallet"] = wallet
        body["signature"] = signature
    return request("POST", "/vow", base=base, timeout=timeout, body=body)


def vow(vow_id: str, *, base: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    return request("GET", f"/vow/{urllib.parse.quote(vow_id)}", base=base, timeout=timeout)
