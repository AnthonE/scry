"""Issuer watchdog: is the meter up, on its rails, and STILL THE SAME SIGNER?

The two silent deploy failures in DEPLOY.md (a --root-path serving paid calls
unpaid; a missing SCRY_METER_KEY minting a brand-new issuer) keep /health
green while the product quietly changes hands. This cron catches the second
one from the outside: it pins the pubkey and alerts the moment GET /pubkey
returns anything else. Script-only, zero LLM tokens, stdlib only.

Env:
  SCRY_BASE        meter base URL (default https://scry.moreright.xyz/api)
  SCRY_PIN_PUBKEY  the base64 pubkey you pinned out-of-band (REQUIRED for the
                   pin check; without it this only checks liveness + rails)

Exit 0 quiet, 1 on any ALERT line. Wire the exit code to your notifier.
"""
import json
import os
import sys
import urllib.request

BASE = os.getenv("SCRY_BASE", "https://scry.moreright.xyz/api").rstrip("/")
PIN = os.getenv("SCRY_PIN_PUBKEY", "")


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=15) as r:
        return json.load(r)


def main() -> int:
    alerts = []
    try:
        health = get("/health")
    except Exception as e:  # noqa: BLE001
        print(f"ALERT: meter unreachable at {BASE}/health ({e})")
        return 1
    if health.get("status") != "ok":
        alerts.append(f"health status is {health.get('status')!r}")
    if health.get("paid_rail_ready") is False:
        alerts.append("paid rails are DOWN (paid_rail_ready false); paid calls will 503")
    try:
        pub = get("/pubkey").get("attestation_pubkey_b64", "")
    except Exception as e:  # noqa: BLE001
        alerts.append(f"GET /pubkey failed ({e})")
        pub = None
    if PIN and pub is not None and pub != PIN:
        alerts.append(f"PUBKEY CHANGED: pinned {PIN[:12]}… but the meter now signs as "
                      f"{(pub or '(empty)')[:12]}…, so a different issuer is answering. "
                      "Verify the deployment before trusting any new attestation.")
    if not PIN:
        print("note: SCRY_PIN_PUBKEY unset; liveness checked, issuer NOT pinned")
    for a in alerts:
        print(f"ALERT: {a}")
    if not alerts:
        print(f"ok: meter live at {BASE}, rails {health.get('networks')}, issuer pinned={bool(PIN)}")
    return 1 if alerts else 0


if __name__ == "__main__":
    sys.exit(main())
