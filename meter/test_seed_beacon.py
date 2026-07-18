"""Offline test for the seed beacon (anchor_worker.post_seed_beacon).

No web3, no network, no chain: `web3` is stubbed and the beacon runs in DRYRUN,
so only the pure logic is exercised — the commit is sha256 of the day's secret
seed, the post is idempotent per day, and it skips cleanly when no seed exists.
Run: python3 test_seed_beacon.py
"""
import hashlib
import json
import os
import sys
import tempfile
import time
import types

# stub web3 so the module imports without the dependency (DRYRUN never calls it)
_w3 = types.ModuleType("web3")
_w3.Web3 = type("Web3", (), {"HTTPProvider": staticmethod(lambda *a, **k: None)})
sys.modules["web3"] = _w3

_A = tempfile.mkdtemp(prefix="scry-beacon-A-")
os.environ["SCRY_VOWS_DIR"] = _A
os.environ["SCRY_NOTARY"] = "0x000000000000000000000000000000000000dEaD"  # arms the beacon
os.environ["SCRY_ANCHOR_DRYRUN"] = "1"                                    # never send
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anchor_worker as aw  # noqa: E402

PASS = 0


def ok(cond, label):
    global PASS
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)
    PASS += 1
    print(f"  ok: {label}")


DAY = time.strftime("%Y-%m-%d", time.gmtime())
SEED = "a1b2c3d4e5f6" * 8
seed_dir = aw.VOWS_DIR / "auguries"
seed_dir.mkdir(parents=True, exist_ok=True)
(seed_dir / f"{DAY}.seed").write_text(SEED)

print("[seed-beacon]")
rec = aw.post_seed_beacon()
ok(rec is not None and rec["day"] == DAY, "posts today's seed commit")
ok(rec["commit"] == "0x" + hashlib.sha256(SEED.encode()).hexdigest(),
   "commit is sha256 of the (still-secret) seed")
ok(rec["label"] == f"augury seed commit {DAY}" and rec["dryrun"] is True and rec["tx"] is None,
   "explorer-readable label; dry-run leaves tx null")
ok(aw.BEACON_PATH.exists() and len(aw.BEACON_PATH.read_text().splitlines()) == 1,
   "beacon log records the post")

ok(aw.post_seed_beacon() is None, "second call same day is a no-op (idempotent)")
ok(len(aw.BEACON_PATH.read_text().splitlines()) == 1, "no duplicate beacon entry")
ok(DAY in aw._beacon_days(), "the day is remembered as posted")

# a fresh dir with no seed → clean skip
_B = tempfile.mkdtemp(prefix="scry-beacon-B-")
aw.VOWS_DIR = __import__("pathlib").Path(_B)
aw.BEACON_PATH = aw.VOWS_DIR / "seed_beacon.jsonl"
ok(aw.post_seed_beacon() is None, "no seed committed yet → clean skip (no crash)")

# NOTARY unset → beacon stays dormant
aw.NOTARY = ""
ok(aw.post_seed_beacon() is None, "SCRY_NOTARY unset → beacon dormant")

print(f"\nALL {PASS} CHECKS PASS")
