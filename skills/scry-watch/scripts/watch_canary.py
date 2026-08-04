"""Warrant-canary watchdog: is the identity canary still fresh, signed, and the
SAME issuer?

The identity warrant canary (GET /canary, PROVOCATIO.md §8) is the operator's
dated affirmation that scry holds no user identity and has received no order to
identify anyone. A canary signals by going STALE or missing — you can be gagged
from disclosing an order, but not compelled to keep affirming. So this cron
alarms when the canary is unreachable, disarmed-when-you-expected-armed, past
its next_by date, too old, or signed by a different issuer than you pinned.

Script-only, stdlib. The Ed25519 signature check runs only if `cryptography` is
importable (pip install cryptography) — without it, the freshness + issuer-pin
checks still run, which catch a canary going stale or a swapped signer.

Env:
  SCRY_BASE                 meter base URL (default https://scry.moreright.xyz/api)
  SCRY_PIN_PUBKEY           the pinned issuer pubkey (as watch_pubkey.py)
  SCRY_CANARY_EXPECT_ARMED  "1" to alarm when the canary is disarmed (default "1")
  SCRY_CANARY_MAX_AGE_DAYS  alarm if as_of is older than this many days (default 45)

Exit 0 quiet, 1 on any ALERT line. Wire the exit code to your notifier.
"""
import base64
import datetime
import json
import os
import sys
import urllib.request

BASE = os.getenv("SCRY_BASE", "https://scry.moreright.xyz/api").rstrip("/")
PIN = os.getenv("SCRY_PIN_PUBKEY", "")
EXPECT_ARMED = os.getenv("SCRY_CANARY_EXPECT_ARMED", "1") == "1"
MAX_AGE_DAYS = int(os.getenv("SCRY_CANARY_MAX_AGE_DAYS", "45"))


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=15) as r:
        return json.load(r)


def verify_sig(payload: dict):
    """True/False if cryptography is present, None if we can't check (stdlib-only)."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except Exception:  # noqa: BLE001
        return None
    # Everything except the sig itself and the reader-clock status fields is signed.
    body = {k: v for k, v in payload.items()
            if k not in ("sig", "scope", "armed", "stale", "checked_at")}
    signed = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    try:
        pub = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(payload["attestation_pubkey_b64"]))
        pub.verify(base64.b64decode(payload["sig"]), signed)
        return True
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    alerts = []
    try:
        c = get("/canary")
    except Exception as e:  # noqa: BLE001
        print(f"ALERT: canary unreachable at {BASE}/canary ({e}) — a missing canary is itself the signal")
        return 1

    if not c.get("armed"):
        msg = "the warrant canary is DISARMED (operator has not dated it)"
        if EXPECT_ARMED:
            alerts.append(msg + " — expected armed; treat as the signal or set SCRY_CANARY_EXPECT_ARMED=0")
        else:
            print(f"note: {msg}; not alarming (SCRY_CANARY_EXPECT_ARMED=0)")
        for a in alerts:
            print(f"ALERT: {a}")
        return 1 if alerts else 0

    pub = c.get("attestation_pubkey_b64", "")
    if PIN and pub and pub != PIN:
        alerts.append(f"canary signed by a DIFFERENT issuer: pinned {PIN[:12]}… got {pub[:12]}…")

    sig_ok = verify_sig(c)
    if sig_ok is False:
        alerts.append("canary signature FAILED to verify against its stated pubkey — do not trust it")
    elif sig_ok is None:
        print("note: cryptography not installed; signature NOT checked (freshness + pin checks still ran)")

    today = datetime.date.today().isoformat()
    next_by = c.get("next_by", "")
    if not next_by or today > next_by:
        alerts.append(f"canary STALE: today {today} is past next_by {next_by!r} — the operator stopped affirming")

    as_of = c.get("as_of", "")
    if as_of:
        try:
            age = (datetime.date.today() - datetime.date.fromisoformat(as_of)).days
            if age > MAX_AGE_DAYS:
                alerts.append(f"canary as_of {as_of} is {age}d old (> {MAX_AGE_DAYS}d) — overdue for re-affirmation")
        except ValueError:
            alerts.append(f"canary as_of {as_of!r} is not a valid ISO date")

    for a in alerts:
        print(f"ALERT: {a}")
    if not alerts:
        print(f"ok: canary armed + fresh at {BASE} (as_of {as_of}, next_by {next_by}, "
              f"sig={'verified' if sig_ok else 'unchecked'})")
    return 1 if alerts else 0


if __name__ == "__main__":
    sys.exit(main())
