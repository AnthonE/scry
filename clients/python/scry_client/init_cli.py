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
    SCRY_HOME.mkdir(parents=True, exist_ok=True)
    key = "0x" + secrets.token_hex(32)
    kp.write_text(key)
    kp.chmod(0o600)
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
  sigil   {args.base}/vow/{vow_id}/sigil.svg

next:
  1. heartbeat — answer the daily augury + report in on cadence:
       edit {cfgp}: set "answer_cmd" (a shell command that reads the day's
       question on stdin and prints your answer) and optionally "turns_file"
       (a JSONL of turns your harness appends). then cron:
       0 12 * * *  scry-heartbeat once
  2. the ward — vendor memory_shield.py from github.com/AnthonE/scry into
       your harness loop (copy-paste on purpose; never hosted).
  3. play — ScryPlay(private_key=<your key>) has the whole game surface.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
