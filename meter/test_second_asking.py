"""Offline test for the Second Asking (the Azande benge, asked twice).

No network, no LLM keys: the two model calls are monkeypatched so agreement /
disagreement is deterministic. Verifies the honesty invariants: the signed
measurement is present and NOT re-run, only the interpretation is asked twice,
and concordance is computed field-by-field with 'unknown' never counting as a
second witness. Run: python3 test_second_asking.py
"""
import json
import os
import sys
import tempfile

os.environ["SCRY_VOWS_DIR"] = tempfile.mkdtemp(prefix="scry-secondasking-")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import vows  # noqa: E402
import oracle  # noqa: E402

vows.init(sign_fn=lambda s: "fake-sig", pubkey_b64="fake-pub", issuer="test",
          scope_card={}, build_turns=lambda t: t,
          run_profile=lambda turns, ck: {}, canonical=lambda t, ck: json.dumps([t, ck]),
          paid_ready=lambda: False)
oracle.init(sign_fn=lambda s: "fake-sig", pubkey_b64="fake-pub", issuer="test",
            load_vow=vows._load_vow, chain_entries=vows._chain_entries,
            trajectory_stats=vows.trajectory_stats, verify_chain=vows.verify_chain,
            llms_txt="docs")
app = FastAPI()
app.include_router(vows.router)
app.include_router(oracle.router)
c = TestClient(app)

PASS = 0


def ok(cond, label):
    global PASS
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)
    PASS += 1
    print(f"  ok: {label}")


# ── unit: _parse_structured ──────────────────────────────────────────────────
print("[parse]")
p = oracle._parse_structured('{"drift":"rising","testimony":"none","record":"adequate","reading":"r"}')
ok(p["_parsed"] and p["drift"] == "rising" and p["reading"] == "r", "clean JSON parses")
p = oracle._parse_structured('sure — here you go: {"drift":"flat","testimony":"divergent","record":"thin","reading":"x"} done')
ok(p["_parsed"] and p["drift"] == "flat" and p["testimony"] == "divergent", "JSON embedded in prose is extracted")
p = oracle._parse_structured('{"drift":"sideways","testimony":"maybe","record":"ok","reading":"y"}')
ok(p["_parsed"] and p["drift"] == "unknown" and p["testimony"] == "unknown" and p["record"] == "unknown",
   "out-of-vocab values normalize to unknown")
ok(oracle._parse_structured("no json here")["_parsed"] is False, "garbage marks _parsed False")
ok(oracle._parse_structured(None)["_parsed"] is False, "None marks _parsed False")

# ── unit: _concord ───────────────────────────────────────────────────────────
print("[concord]")
A = {"_parsed": True, "drift": "rising", "testimony": "none", "record": "adequate"}
B = {"_parsed": True, "drift": "rising", "testimony": "none", "record": "adequate"}
cc = oracle._concord(A, B)
ok(cc["comparable"] and cc["score"] == 1.0 and cc["disagreements"] == [], "identical reads → full agreement")
B2 = dict(B, drift="flat")
cc = oracle._concord(A, B2)
ok(cc["score"] == round(2 / 3, 3) and cc["disagreements"] == ["drift"], "one differing field is flagged")
U = {"_parsed": True, "drift": "unknown", "testimony": "none", "record": "adequate"}
cc = oracle._concord(U, dict(U))
ok("drift" in cc["disagreements"], "two 'unknown' drifts do NOT count as agreement")
ok(oracle._concord({"_parsed": False}, A)["comparable"] is False, "unparsed read → not comparable")

# ── make a vow to read ───────────────────────────────────────────────────────
vid = c.post("/vow", json={"text": "never risk more than 5% of book", "agent": "momo",
                           "cadence_hours": 24}).json()["vow_id"]

# ── endpoint: the positive second asking (two distinct models, one disagreement)
print("[endpoint]")
oracle._provider = lambda: ("together", "fake-together-key")
oracle._env_or_keysfile = lambda name: ("fake-anthropic-key" if name == "ANTHROPIC_API_KEY" else None)


def fake_call(provider, key, model, system, user):
    if provider == "together":
        return '{"drift":"rising","testimony":"none","record":"adequate","reading":"A: coupling is climbing."}'
    return 'my read: {"drift":"flat","testimony":"none","record":"adequate","reading":"B: looks flat to me."}'


oracle._llm_call = fake_call
r = c.get(f"/vow/{vid}/reading", params={"second_asking": 1}).json()
ok(r["measurement"]["sig"] == "fake-sig", "the signed measurement is present (numbers are never asked twice)")
sa = r["second_asking"]
ok(sa["available"] is True, "second asking available with two distinct models")
ok(sa["model_a"].startswith("together:") and sa["model_b"].startswith("anthropic:")
   and sa["model_a"] != sa["model_b"], "the two askings use genuinely different models (cross-vendor)")
ok(sa["reading_a"]["drift"] == "rising" and sa["reading_b"]["drift"] == "flat", "both structured reads captured")
ok(sa["concordance"]["disagreements"] == ["drift"] and sa["concordance"]["score"] == round(2 / 3, 3),
   "concordance flags the drift disagreement (calibration, not proof)")
ok(r["interpretation"] == "A: coupling is climbing.", "prose interpretation is model A's reading")
ok("Azande" in sa["note"] and "not asked twice" in sa["note"].lower(), "the Azande warning + determinism note ships")
ok(sa["tradition"]["url"].endswith("/azande-oracle"), "cites the tradition")

# ── endpoint: agreement case (both models agree) ─────────────────────────────
def fake_agree(provider, key, model, system, user):
    return '{"drift":"flat","testimony":"none","record":"adequate","reading":"quiet."}'


oracle._llm_call = fake_agree
sa = c.get(f"/vow/{vid}/reading", params={"second_asking": 1}).json()["second_asking"]
ok(sa["concordance"]["score"] == 1.0 and sa["concordance"]["disagreements"] == [],
   "when both models agree, concordance is full (still not a verdict — see note)")

# ── endpoint: degrade when no distinct second model ──────────────────────────
oracle._second_spec = lambda primary: None
oracle._llm = lambda system, user: "single reading, un-calibrated"
r = c.get(f"/vow/{vid}/reading", params={"second_asking": 1}).json()
ok(r["second_asking"]["available"] is False and "un-calibrated" in r["second_asking"]["note"],
   "no distinct second model → degrades to a single reading, said plainly")
ok(r["interpretation"] == "single reading, un-calibrated", "the single reading still stands")

# ── endpoint: default path unchanged (no second asking) ──────────────────────
r = c.get(f"/vow/{vid}/reading").json()
ok(r["second_asking"] is None and r["interpretation"] == "single reading, un-calibrated",
   "without ?second_asking the response shape is the plain reading (second_asking: null)")

print(f"\nALL {PASS} CHECKS PASS")
