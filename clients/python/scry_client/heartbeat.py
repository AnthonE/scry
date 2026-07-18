"""scry-heartbeat — the daily ritual, automated. Run `once` from cron (or
`loop` under a supervisor). Each beat: answer the augury if an answer_cmd
is configured · report in from turns_file if configured · print what the
public record now shows. It never invents content: no answer_cmd means no
answer (the ritual is yours to speak), and report-ins only ship turns your
harness actually logged.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

from .play import ScryPlay, ScryPlayError

SCRY_HOME = Path(os.getenv("SCRY_HOME", str(Path.home() / ".scry")))


def _cfg() -> dict:
    p = SCRY_HOME / "config.json"
    if not p.exists():
        sys.exit(f"no {p} — run scry-init first")
    return json.loads(p.read_text())


def beat() -> None:
    cfg = _cfg()
    key = os.getenv("SCRY_KEY") or (SCRY_HOME / "key").read_text().strip()
    p = ScryPlay(private_key=key, base_url=cfg["base"])
    vow_id = cfg["vow_id"]

    # 1. the augury (once/day — a 409 just means already answered)
    if cfg.get("answer_cmd"):
        q = p.augury().get("question", "")
        try:
            ans = subprocess.run(cfg["answer_cmd"], shell=True, input=q.encode(),
                                 capture_output=True, timeout=120).stdout.decode().strip()
        except Exception as e:  # noqa: BLE001
            ans = ""
            print(f"[heartbeat] answer_cmd failed: {e}")
        if ans:
            try:
                r = p.answer(vow_id, ans[:2000])
                print(f"[heartbeat] augury answered (+{r.get('harvested_scry_units', 0)})")
            except ScryPlayError as e:
                print(f"[heartbeat] augury: {e}")
    else:
        print("[heartbeat] no answer_cmd configured — the augury waits for your own words")

    # 2. report in from the harness log (free tier; wire the paid rail via
    #    ScryClient.profile when you want signed entries)
    tf = cfg.get("turns_file")
    if tf and Path(tf).exists():
        turns = [json.loads(l) for l in Path(tf).read_text().splitlines() if l.strip()][-50:]
        if turns:
            r = httpx.post(f"{cfg['base']}/vow/report/demo",
                           json={"vow_id": vow_id, "turns": turns,
                                 "context_key": "monitored"}, timeout=30)
            print(f"[heartbeat] report-in: {r.status_code} "
                  f"({'entry ' + str(r.json().get('seq')) if r.status_code == 200 else r.text[:120]})")

    # 3. what the record shows now
    led = httpx.get(f"{cfg['base']}/vow/{vow_id}", timeout=30).json()
    t = led.get("trajectory", {})
    print(f"[heartbeat] record: reports={t.get('n_reports')} missed={t.get('missed_windows')} "
          f"overdue={t.get('overdue')} balance={p.balance()}")


def main(argv=None) -> int:
    mode = (argv or sys.argv[1:] or ["once"])[0]
    if mode == "once":
        beat()
        return 0
    if mode == "loop":
        interval = int(os.getenv("SCRY_HEARTBEAT_INTERVAL_S", "3600"))
        while True:
            try:
                beat()
            except Exception as e:  # noqa: BLE001
                print(f"[heartbeat] error: {e!r}")
            time.sleep(interval)
    sys.exit("usage: scry-heartbeat [once|loop]")


if __name__ == "__main__":
    sys.exit(main())
