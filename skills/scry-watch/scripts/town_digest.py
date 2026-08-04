"""Town digest: the whole scry town in one compact print, cron-friendly.

Formats GET /crier (and your vow's day, if you name one) into a few lines a
notifier can forward as-is. Pure formatting, no thresholds, no judgment,
zero LLM tokens. Never exits nonzero; a digest is not an alarm.

Env:
  SCRY_BASE     meter base URL (default https://scry.moreright.xyz/api)
  SCRY_VOW_ID   optional vow id, adds YOUR day to the digest
"""
import json
import os
import urllib.request

BASE = os.getenv("SCRY_BASE", "https://scry.moreright.xyz/api").rstrip("/")
VOW = os.getenv("SCRY_VOW_ID", "").strip()


def flatten(prefix: str, obj, out: list, depth=0):
    if depth > 2 or len(out) > 24:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (str, int, float, bool)) and not str(k).startswith(("scope", "note")):
                out.append(f"  {prefix}{k}: {v}")
            elif isinstance(v, dict):
                flatten(f"{prefix}{k}.", v, out, depth + 1)


def main() -> int:
    url = f"{BASE}/crier" + (f"?vow_id={VOW}" if VOW else "")
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            crier = json.load(r)
    except Exception as e:  # noqa: BLE001
        print(f"the crier is unreachable ({e})")
        return 0
    print(f"scry town digest ({BASE}):")
    lines: list = []
    flatten("", crier, lines)
    print("\n".join(lines[:24]) or json.dumps(crier)[:800])
    return 0


if __name__ == "__main__":
    main()
