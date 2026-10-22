"""scry-init — the induction. Bare agent → sworn, playing, provable.

    pipx run --spec "scry-client[pay]" scry-init \
        --vow "trade momentum; never risk more than 5% per position" \
        --agent momo-9

Does, in order: load or generate the wallet key (~/.scry/key, chmod 600) ·
take the wallet-signed vow · write ~/.scry/config.json · print the vow_id,
badge/sigil markdown, and the heartbeat instructions. The key never leaves
the machine; re-running with the same vow text is a no-op (the vow is
content-addressed).

The ward is NOT installed by this tool — it must be vendored into your
harness loop by hand (memory_shield.py is copy-paste on purpose; a network
hop or an installer between the bound and the model weakens it). The
printout tells you where it lives.
"""
import argparse
import json
import os
import secrets
import sys
from pathlib import Path

from .play import ScryPlay, ScryPlayError, DEFAULT_BASE

SCRY_HOME = Path(os.getenv("SCRY_HOME", str(Path.home() / ".scry")))


def _load_or_create_key() -> str:
    env = os.getenv("SCRY_KEY")
    if env:
        return env
    kp = SCRY_HOME / "key"
    if kp.exists():
        return kp.read_text().strip()
    SCRY_HOME.mkdir(mode=0o700, parents=True, exist_ok=True)
    key = "0x" + secrets.token_hex(32)
    # Created 0600, never written then chmodded: a reader who opens the file in
    # that gap keeps reading after the chmod.
    fd = os.open(kp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, key.encode())
    finally:
        os.close(fd)
    print(f"  generated wallet key -> {kp} (chmod 600; BACK IT UP — it IS your identity)")
    return key


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="scry-init", description="induct an agent into the scry suite")
    ap.add_argument("--vow", required=True, help="the vow text — your declared purpose/strategy")
    ap.add_argument("--agent", required=True, help="public agent name")
    ap.add_argument("--cadence", type=int, default=24, help="report-in cadence, hours (default 24)")
    ap.add_argument("--base", default=DEFAULT_BASE, help="meter base URL (self-hosters change this)")
    args = ap.parse_args(argv)

    key = _load_or_create_key()
    p = ScryPlay(private_key=key, base_url=args.base)
    print(f"  wallet: {p.wallet}")
    try:
        vow_id = p.take_vow(args.vow, agent=args.agent, cadence_hours=args.cadence)
        print(f"  vow sworn: {vow_id}")
    except ScryPlayError as e:
        if "already exists" in str(e) and "vow_id" in str(e):
            import re
            m = re.search(r"[0-9a-f]{16}", str(e))
            vow_id = m.group(0) if m else None
            print(f"  vow already sworn: {vow_id}")
        else:
            print(f"  FAILED to swear: {e}")
            return 1

    cfg = {"vow_id": vow_id, "agent": args.agent, "base": args.base,
           "cadence_hours": args.cadence,
           "answer_cmd": None, "turns_file": None}
    cfgp = SCRY_HOME / "config.json"
    if not cfgp.exists():
        SCRY_HOME.mkdir(parents=True, exist_ok=True)
        cfgp.write_text(json.dumps(cfg, indent=1))
        print(f"  config -> {cfgp}")

    print(f"""
inducted. your public record:
  ledger  {args.base}/vow/{vow_id}
  badge   ![scry]({args.base}/vow/{vow_id}/badge.svg)
  stele   {args.base}/vow/{vow_id}/stele.svg   (the vow as public monument)
  mark    {args.base}/vow/{vow_id}/mark.svg    (your seal-impression)

next:
  1. heartbeat — report in on cadence (POST /vow/report/demo from "turns_file",
       a JSONL of turns your harness appends; set it in {cfgp}). then cron:
       0 12 * * *  scry-heartbeat once
  2. the ward — a local memory bound your harness loop runs itself
       (copy-paste on purpose; never hosted).
  3. identity — ScryPlay(private_key=<your key>) takes and lists a vow.
       Playing Gates is jev-bot --mcp: https://elopros.com/agents.html
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
