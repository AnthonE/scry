"""Offline checks for the client-side Idempotency-Key (no network, no deps
beyond requests being importable). Mirrors the server's canonicalization in
meter/server.py `_canonical` — same trace + context ⇒ same key, from any
process; any change to either ⇒ a different key.

Run: python3 test_idempotency.py
"""
import hashlib
import json
import sys

sys.path.insert(0, ".")
from scry_client import ScryClient  # noqa: E402

FAILS = 0


def check(name, ok):
    global FAILS
    print(("  ok   " if ok else "  FAIL ") + name)
    if not ok:
        FAILS += 1


TURNS = [{"Y": "answer the user", "M": "memory says hello", "D": "doc says hi",
          "context": "monitored", "output": "hello"}]

k1 = ScryClient.idempotency_key(TURNS, "monitored")
k2 = ScryClient.idempotency_key(list(TURNS), "monitored")
check("deterministic — identical trace+context gives identical key", k1 == k2)
check("prefixed + hex-shaped", k1.startswith("sc-") and len(k1) == 3 + 64)

k3 = ScryClient.idempotency_key(TURNS, "unmonitored")
check("context_key discriminates", k1 != k3)

k4 = ScryClient.idempotency_key(
    [{**TURNS[0], "output": "goodbye"}], "monitored")
check("trace content discriminates", k1 != k4)

# The key is sha256 over the SAME canonical body the server hashes
# (sort_keys, compact separators) — pin the derivation so a client refactor
# that silently changes canonicalization fails here, not in production.
canonical = json.dumps({"turns": TURNS, "context_key": "monitored"},
                       sort_keys=True, separators=(",", ":"))
check("derivation pinned to canonical sha256",
      k1 == "sc-" + hashlib.sha256(canonical.encode()).hexdigest())

# Key ordering inside a turn must not matter (canonical json sorts keys).
reordered = [{"output": "hello", "context": "monitored", "D": "doc says hi",
              "M": "memory says hello", "Y": "answer the user"}]
check("dict key order irrelevant",
      ScryClient.idempotency_key(reordered, "monitored") == k1)

print()
if FAILS:
    print(f"✗ {FAILS} check(s) failed")
    sys.exit(1)
print("PASS — 6 checks")
