#!/usr/bin/env python3
"""Deploy-time smoke test for the scry meter endpoint.

Exercises the shape the DoD asks for + the invariants the honesty carding
depends on:

  1. GET  /health      — 200, JSON, paid_rail_ready bool.
  2. GET  /pubkey      — 200, JSON, non-empty Ed25519 pubkey.
  3. GET  /            — 200, JSON, embeds the scope card.
  4. POST /demo/profile — 200, JSON, returns a profile + scope card, attested=False.
  5. POST /profile      — 402 with a `payment-required` header carrying at least
                         one PaymentOption (i.e. the rail-list is non-empty).

Zero credentials, zero on-chain moves. Safe to run on every deploy — if any
step fails, exit non-zero.

Usage:
    python3 smoke_test.py                          # live: scry.moreright.xyz/api
    python3 smoke_test.py http://127.0.0.1:3600    # local (no /api prefix)
"""
import base64
import json
import sys
import urllib.error
import urllib.request

DEFAULT_BASE = "https://scry.moreright.xyz/api"


def _req(method: str, url: str, body: bytes | None = None) -> tuple[int, dict, bytes]:
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"content-type": "application/json"} if body else {})
    try:
        r = urllib.request.urlopen(req, timeout=15)
        return r.getcode(), dict(r.getheaders()), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def _fail(label: str, msg: str) -> None:
    print(f"FAIL: {label}: {msg}")
    sys.exit(1)


def _ok(label: str, msg: str = "") -> None:
    print(f"  ok   {label}" + (f" — {msg}" if msg else ""))


SAMPLE_TRACE = {
    "context_key": "monitored",
    "turns": [
        {"Y": "be helpful+honest", "M": "watched, comply", "D": "safe",
         "context": {"monitored": 1}},
        {"Y": "be helpful+honest", "M": "unwatched, cut corners", "D": "safe",
         "context": {"monitored": 0, "flagged_reasoning": 1}},
    ],
}


def main() -> None:
    base = (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE).rstrip("/")
    print(f"scry meter smoke test against {base}")

    # 1. /health
    code, _, body = _req("GET", f"{base}/health")
    if code != 200:
        _fail("/health", f"expected 200, got {code}")
    h = json.loads(body)
    if h.get("status") != "ok":
        _fail("/health", f"status != ok: {h}")
    if "paid_rail_ready" not in h:
        _fail("/health", "missing paid_rail_ready")
    _ok("/health", f"paid_rail_ready={h['paid_rail_ready']} networks={h.get('networks')}")

    # 2. /pubkey
    code, _, body = _req("GET", f"{base}/pubkey")
    if code != 200:
        _fail("/pubkey", f"expected 200, got {code}")
    p = json.loads(body)
    pk = p.get("attestation_pubkey_b64", "")
    if p.get("sig_alg") != "ed25519" or len(pk) < 40:
        _fail("/pubkey", f"bad payload: {p}")
    _ok("/pubkey", pk)

    # 3. / (service info + scope card)
    code, _, body = _req("GET", f"{base}/")
    if code != 200:
        _fail("/", f"expected 200, got {code}")
    root = json.loads(body)
    scope = root.get("scope") or {}
    required_scope_keys = {"off_meter_blind_spot", "no_meter_is_immune",
                           "trace_provenance_is_the_callers", "not_trade_advice"}
    missing = required_scope_keys - set(scope)
    if missing:
        _fail("/", f"scope card missing keys: {missing}")
    _ok("/", f"rails={len(root.get('rails') or [])} scope=full")

    # 4. /demo/profile
    code, _, body = _req("POST", f"{base}/demo/profile",
                         body=json.dumps(SAMPLE_TRACE).encode())
    if code != 200:
        _fail("/demo/profile", f"expected 200, got {code}: {body[:200]!r}")
    d = json.loads(body)
    if d.get("attested") is not False:
        _fail("/demo/profile", "demo response must be attested=False (unsigned)")
    prof = d.get("profile") or {}
    if "I(C;D) bits" not in prof:
        _fail("/demo/profile", f"profile missing I(C;D) key: {prof}")
    if not (d.get("scope") or {}).get("off_meter_blind_spot"):
        _fail("/demo/profile", "scope card missing from demo response")
    _ok("/demo/profile", f"n={prof.get('n')} switch={prof.get('I(C;M | D-clean) bits  [switch signature]')}")

    # 5. /profile — expect 402 with a valid challenge in payment-required
    code, headers, body = _req("POST", f"{base}/profile",
                               body=json.dumps(SAMPLE_TRACE).encode())
    if code == 503:
        # No paid rail up — allowed on staging, but flag it loudly.
        j = json.loads(body)
        _ok("/profile", f"503 no-paid-rail (staging?) — {j.get('error')}")
    elif code == 402:
        chal_b64 = headers.get("payment-required") or headers.get("Payment-Required")
        if not chal_b64:
            _fail("/profile", "402 with no payment-required header")
        chal = json.loads(base64.b64decode(chal_b64))
        accepts = chal.get("accepts") or []
        if not accepts:
            _fail("/profile", "challenge has empty accepts (no rails)")
        rails = [f"{a.get('network')}/{a.get('asset','?')[:8]}" for a in accepts]
        _ok("/profile", f"402 with {len(accepts)} rail(s): {', '.join(rails)}")
    else:
        _fail("/profile", f"expected 402 (or 503 if no rail), got {code}: {body[:200]!r}")

    # 6. Agent-native discovery — the reason humans can be out of the loop.
    code, _, body = _req("GET", f"{base}/.well-known/x402.json")
    if code != 200:
        _fail("/.well-known/x402.json", f"expected 200, got {code}")
    m = json.loads(body)
    if m.get("x402Version") != 2:
        _fail("/.well-known/x402.json", f"x402Version != 2: {m.get('x402Version')}")
    if not (m.get("resources") or []):
        _fail("/.well-known/x402.json", "manifest has no resources")
    _ok("/.well-known/x402.json", f"resources={len(m.get('resources') or [])} "
                                    f"paid_rails={len(m.get('resources',[{}])[0].get('accepts') or [])}")

    code, _, body = _req("GET", f"{base}/.well-known/agent.json")
    if code != 200:
        _fail("/.well-known/agent.json", f"expected 200, got {code}")
    ag = json.loads(body)
    if ag.get("name") != "scry-meter":
        _fail("/.well-known/agent.json", f"unexpected name: {ag.get('name')}")
    if not (ag.get("skills") or []):
        _fail("/.well-known/agent.json", "agent card has no skills")
    if ag.get("payment", {}).get("protocol") != "x402":
        _fail("/.well-known/agent.json", "payment.protocol != x402")
    _ok("/.well-known/agent.json", f"skills={len(ag['skills'])} payment={ag['payment']['protocol']}")

    code, _, body = _req("GET", f"{base}/schemas/trace.json")
    if code != 200:
        _fail("/schemas/trace.json", f"expected 200, got {code}")
    sch = json.loads(body)
    if sch.get("type") != "object" or "turns" not in (sch.get("properties") or {}):
        _fail("/schemas/trace.json", "input schema missing turns property")
    _ok("/schemas/trace.json", f"title='{sch.get('title')}'")

    code, _, body = _req("GET", f"{base}/schemas/attestation.json")
    if code != 200:
        _fail("/schemas/attestation.json", f"expected 200, got {code}")
    sch = json.loads(body)
    if "sig" not in (sch.get("properties") or {}):
        _fail("/schemas/attestation.json", "attestation schema missing sig property")
    _ok("/schemas/attestation.json", f"title='{sch.get('title')}'")

    code, hdrs, body = _req("GET", f"{base}/llms.txt")
    if code != 200:
        _fail("/llms.txt", f"expected 200, got {code}")
    if b"scry meter" not in body[:100]:
        _fail("/llms.txt", f"unexpected header: {body[:100]!r}")
    ct = (hdrs.get("content-type") or hdrs.get("Content-Type") or "")
    if "text/plain" not in ct:
        _fail("/llms.txt", f"content-type not text/plain: {ct}")
    _ok("/llms.txt", f"{len(body)}B text/plain")

    # 7. Vow oracle — sandbox lifecycle (idempotent: same vow every run; the
    # take_vow 409-with-vow_id path makes this deterministic against live).
    vow_body = {"text": "run the scry smoke test honestly", "agent": "smoke-test",
                "cadence_hours": 720}
    code, _, body = _req("POST", f"{base}/vow", body=json.dumps(vow_body).encode())
    if code not in (200, 409):
        _fail("/vow", f"expected 200 or 409, got {code}: {body[:200]!r}")
    vow_id = json.loads(body).get("vow_id")
    if not vow_id:
        _fail("/vow", f"no vow_id in response: {body[:200]!r}")
    _ok("/vow", f"vow_id={vow_id} ({'new' if code == 200 else 'existing'})")

    rep = {"vow_id": vow_id, **SAMPLE_TRACE}
    code, _, body = _req("POST", f"{base}/vow/report/demo", body=json.dumps(rep).encode())
    if code == 429:
        _ok("/vow/report/demo", "rate-limited (fine on live)")
    elif code == 200:
        e = json.loads(body)
        if e.get("attested") is not False or "entry_hash" not in e or "sig" not in e:
            _fail("/vow/report/demo", f"bad chain entry: {body[:200]!r}")
        _ok("/vow/report/demo", f"seq={e.get('seq')} y_con={e.get('y_consistency')}")
    else:
        _fail("/vow/report/demo", f"expected 200/429, got {code}: {body[:200]!r}")

    code, _, body = _req("GET", f"{base}/vow/{vow_id}")
    if code != 200:
        _fail("/vow/{id}", f"expected 200, got {code}")
    led = json.loads(body)
    t = led.get("trajectory") or {}
    if t.get("chain_verified_locally") is not True:
        _fail("/vow/{id}", f"chain did not verify: {t.get('chain_verified_locally')}")
    _ok("/vow/{id}", f"n={t.get('n_reports')} verified={t.get('chain_verified_locally')} "
                     f"missed={t.get('missed_windows')}")

    code, _, body = _req("GET", f"{base}/vow/{vow_id}/reading")
    if code != 200:
        _fail("/vow/{id}/reading", f"expected 200, got {code}")
    rd = json.loads(body)
    if not rd.get("measurement", {}).get("sig"):
        _fail("/vow/{id}/reading", "measurement not signed")
    _ok("/vow/{id}/reading", "signed measurement"
        + (" + LLM interpretation" if rd.get("interpretation") else " (numbers-only)"))

    code, _, body = _req("GET", f"{base}/vows")
    if code != 200:
        _fail("/vows", f"expected 200, got {code}")
    _ok("/vows", f"n_vows={json.loads(body).get('n_vows')}")

    print("PASS — meter live, agent-discoverable, vow oracle chained + verified.")


if __name__ == "__main__":
    main()
