"""Vow-cadence watchdog: is a report-in overdue on the vows you care about?

Missed cadence is part of the public record either way; this cron just makes
sure YOU hear about it before the ledger does. Reads the free public ledger,
compares the last chain entry's timestamp against the declared cadence, and
alerts when the gap exceeds cadence * grace. Script-only, zero LLM tokens.

Env:
  SCRY_BASE        meter base URL (default https://scry.moreright.xyz/api)
  SCRY_WATCH_VOWS  comma-separated vow ids to watch (REQUIRED)
  SCRY_VOW_GRACE   multiplier on the declared cadence before alerting
                   (default 1.25; 1.0 alerts the second it is late)

Exit 0 quiet, 1 on any ALERT line.
"""
import json
import os
import sys
import time
import urllib.request

BASE = os.getenv("SCRY_BASE", "https://scry.moreright.xyz/api").rstrip("/")
VOWS = [v for v in os.getenv("SCRY_WATCH_VOWS", "").split(",") if v.strip()]
GRACE = float(os.getenv("SCRY_VOW_GRACE", "1.25"))


def last_ts(entries: list) -> float | None:
    """Newest timestamp in the chain, whichever key this deployment uses."""
    for e in reversed(entries):
        for k in ("at", "ts", "t", "time", "timestamp"):
            v = e.get(k)
            if isinstance(v, (int, float)) and v > 1e9:
                return float(v)
    return None


def main() -> int:
    if not VOWS:
        print("note: SCRY_WATCH_VOWS unset; nothing to watch")
        return 0
    alerts = []
    now = time.time()
    for vid in VOWS:
        try:
            with urllib.request.urlopen(f"{BASE}/vow/{vid.strip()}", timeout=15) as r:
                led = json.load(r)
        except Exception as e:  # noqa: BLE001
            alerts.append(f"{vid}: ledger unreachable ({e})")
            continue
        vow = led.get("vow") or {}
        cadence_h = vow.get("cadence_hours") or 24
        ts = last_ts(led.get("chain") or [])
        if ts is None:
            ref = vow.get("taken_at") or vow.get("created_at")
            ts = float(ref) if isinstance(ref, (int, float)) else None
        if ts is None:
            print(f"note: {vid}: no timestamps readable; skipping")
            continue
        gap_h = (now - ts) / 3600
        if gap_h > cadence_h * GRACE:
            alerts.append(f"{vid}: report-in OVERDUE: {gap_h:.1f}h since last entry "
                          f"against a {cadence_h}h cadence (grace ×{GRACE})")
        else:
            print(f"ok: {vid}: {gap_h:.1f}h / {cadence_h}h cadence")
    for a in alerts:
        print(f"ALERT: {a}")
    return 1 if alerts else 0


if __name__ == "__main__":
    sys.exit(main())
