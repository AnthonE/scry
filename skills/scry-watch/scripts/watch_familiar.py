"""Familiar watchdog: is your adopted worker still alive and journaling?

Checks the agency roster is armed and, for each familiar you own, that the
public journal has moved within the stall window. A stalled journal is not an
accusation, just a nudge to go look. Script-only, zero LLM tokens.

Env:
  SCRY_BASE             meter base URL (default https://scry.moreright.xyz/api)
  SCRY_WATCH_FAMILIARS  comma-separated familiar ids you own (REQUIRED)
  SCRY_FAMILIAR_STALL_H hours of journal silence before alerting (default 48)

Exit 0 quiet, 1 on any ALERT line.
"""
import json
import os
import sys
import time
import urllib.request

BASE = os.getenv("SCRY_BASE", "https://scry.moreright.xyz/api").rstrip("/")
FAMS = [f for f in os.getenv("SCRY_WATCH_FAMILIARS", "").split(",") if f.strip()]
STALL_H = float(os.getenv("SCRY_FAMILIAR_STALL_H", "48"))


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=15) as r:
        return json.load(r)


def newest_ts(entries: list) -> float | None:
    best = None
    for e in entries:
        for k in ("at", "ts", "t", "time", "timestamp"):
            v = e.get(k) if isinstance(e, dict) else None
            if isinstance(v, (int, float)) and v > 1e9:
                best = max(best or 0, float(v))
    return best


def main() -> int:
    if not FAMS:
        print("note: SCRY_WATCH_FAMILIARS unset; nothing to watch")
        return 0
    alerts = []
    try:
        roster = get("/familiars")
        if roster.get("armed") is False:
            alerts.append("the agency reports DISARMED; hosted familiars are not running")
    except Exception as e:  # noqa: BLE001
        alerts.append(f"roster unreachable ({e})")
    for fid in FAMS:
        fid = fid.strip()
        try:
            j = get(f"/familiar/{fid}/journal")
        except Exception as e:  # noqa: BLE001
            alerts.append(f"{fid}: journal unreachable ({e})")
            continue
        ts = newest_ts(j.get("journal") or [])
        if ts is None:
            print(f"note: {fid}: journal empty or timestamps unreadable")
            continue
        gap_h = (time.time() - ts) / 3600
        if gap_h > STALL_H:
            alerts.append(f"{fid}: journal silent for {gap_h:.0f}h (stall window {STALL_H:.0f}h) "
                          "and needs a look: tick it, talk to it, or check why it stopped")
        else:
            print(f"ok: {fid}: last journal entry {gap_h:.1f}h ago")
    for a in alerts:
        print(f"ALERT: {a}")
    return 1 if alerts else 0


if __name__ == "__main__":
    sys.exit(main())
