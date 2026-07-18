#!/usr/bin/env python3
"""herald_worker — run the Herald's tick on a timer (pm2, like anchor_worker).

    pm2 start herald_worker.py --interpreter python3 --name scry-herald

Env: SCRY_HERALD_INTERVAL_S (default 300). All state lives in the vows dir;
the worker is stateless and safe to restart any time.
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INTERVAL = int(os.getenv("SCRY_HERALD_INTERVAL_S", "300"))


def main() -> None:
    # borrow the server's fully-initialized modules by importing it (it wires
    # vows/herald init at import time). Heavy but correct: one source of truth.
    import server  # noqa: F401
    import herald
    print(f"[scry-herald] up — tick every {INTERVAL}s")
    while True:
        try:
            fired = herald.tick()
            if fired:
                print(f"[scry-herald] {time.strftime('%H:%M:%S')} fired: {fired}")
        except Exception as e:  # noqa: BLE001
            print(f"[scry-herald] tick error: {e!r}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
