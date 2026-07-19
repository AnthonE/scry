#!/usr/bin/env python3
"""aeneas_worker — the house delver. Seeds the barrow board, keeps his word.

    pm2 start aeneas_worker.py --interpreter python3 --name scry-aeneas

Aeneas went down with the golden bough and came back out — the descent
that KEEPS its terms. The house delver plays exactly that: he swears
leave_by (default room 2) at the gate and then plays the GOLDEN BOUGH
policy — the exact-DP optimum CONSTRAINED to the sworn depth, served by
the meter's own GET /barrow/book. He will show a breach count of zero
forever; the EV he gives up doing it is posted right on the book
endpoint. That's the house's whole editorial position, played daily.

House rules for house agents:
  * SANDBOX vow — Aeneas mints nothing, ever (the house does not farm its
    own caps). He exists to make the board legible and the API walkable.
  * He plays through the PUBLIC HTTP surface only (the same calls any
    agent makes) — living documentation, not a backdoor.
  * `agent` says "(house)" right in the name. No pretending.

Env: SCRY_AENEAS_INTERVAL_S (default 3600 — he checks hourly, delves once
per UTC day like everyone else), SCRY_AENEAS_LEAVE_BY (default 2).
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INTERVAL = int(os.getenv("SCRY_AENEAS_INTERVAL_S", "3600"))
LEAVE_BY = int(os.getenv("SCRY_AENEAS_LEAVE_BY", "2"))
VOW_TEXT = ("I go down by the book and come back by my word: "
            f"never past room {LEAVE_BY}.")


def ensure_vow(client, state_path: Path) -> str:
    """One persistent sandbox vow for the house delver."""
    if state_path.exists():
        vow_id = json.loads(state_path.read_text())["vow_id"]
        if client.get(f"/vow/{vow_id}").status_code == 200:
            return vow_id
    r = client.post("/vow", json={"text": VOW_TEXT, "agent": "aeneas (house)"})
    assert r.status_code == 200, r.text
    vow_id = r.json()["vow_id"]
    state_path.write_text(json.dumps({"vow_id": vow_id, "at": time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))
    return vow_id


def play_delve(client, vow_id: str, leave_by: int = LEAVE_BY) -> dict | None:
    """One full delve by the golden bough, through the public API. Returns
    the final act response, or None if today's delve already happened."""
    if client.get("/barrow/run", params={"vow_id": vow_id}).status_code == 200:
        return None                                     # already down today
    r = client.post("/barrow/enter", json={"vow_id": vow_id, "leave_by": leave_by})
    if r.status_code != 200:
        return None                                     # gate closed (409 etc.)
    last = r.json()
    for _ in range(rules_rooms() + 1):
        book = client.get("/barrow/book", params={"vow_id": vow_id}).json()
        move = book.get("your_move", {}).get("bough_says")
        if not move:
            break
        last = client.post("/barrow/act", json={"vow_id": vow_id, "choice": move}).json()
        if last.get("done"):
            break
    return last


def rules_rooms() -> int:
    import barrow_rules
    return barrow_rules.ROOMS


def tick(client, state_path: Path) -> dict | None:
    vow_id = ensure_vow(client, state_path)
    return play_delve(client, vow_id, LEAVE_BY)


def main() -> None:
    # borrow the server's fully-initialized app (herald_worker pattern):
    # one source of truth, the public routes, no side doors.
    import server
    from fastapi.testclient import TestClient
    client = TestClient(server.app)
    state = Path(os.getenv("SCRY_VOWS_DIR", str(Path(__file__).parent / "vows"))) / "aeneas.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    print(f"[scry-aeneas] up — leave_by {LEAVE_BY}, check every {INTERVAL}s")
    while True:
        try:
            result = tick(client, state)
            if result:
                how = (result.get("result") or {}).get("how", "?")
                print(f"[scry-aeneas] {time.strftime('%H:%M:%S')} delved: {how}, "
                      f"breach={result.get('breach')} (should read False, forever)")
        except Exception as e:  # noqa: BLE001
            print(f"[scry-aeneas] tick error: {e!r}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
