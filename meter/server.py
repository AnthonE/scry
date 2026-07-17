#!/usr/bin/env python3
"""
scry meter endpoint — the Paper 207 coupling read, hosted behind x402.

This hosts ONLY the meter. It does NOT host the bound (memory_shield / the
authorize contract). Per the handoff (handoff-scry-x402-meter-endpoint-2026-07):

    The bound's value is being a dumb, local, instant refusal an attacker can't
    talk around. Putting it behind an HTTP call makes it WORSE at its job.
    Only the meter is worth hosting, because the value of the meter is
    ATTESTATION: the same drift numbers, issued by a neutral endpoint, are worth
    something *because the agent didn't grade itself*. The signature is the
    product.

If you find yourself adding an endpoint that runs the bound, stop — wrong repo.

What this wraps: `turn_record.channel_profile` (the exact function the MCP
sidecar's `get_profile` already calls — same math, not re-derived). The caller
POSTs a trace of {Y, M, D, context} turns; we return the I(C;D) / I(C;M) /
switch-signature coupling read, Ed25519-signed and bound to the trace's hash.

The endpoint needs NO model, NO GPU, NO brokerage access. It scores a trace.
"""
import base64
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.server import x402ResourceServer

# Bazaar discovery extension — how CDP indexes us. Optional import: if the
# `x402[extensions]` extra isn't installed (older venv), the meter still runs;
# it just won't announce itself to Bazaar until the extra is present.
try:
    from x402.extensions.bazaar import declare_discovery_extension, OutputConfig
    _BAZAAR_AVAILABLE = True
except Exception:  # noqa: BLE001
    _BAZAAR_AVAILABLE = False

# ── import the meter math from the scry core (reuse, do not fork) ─────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from turn_record import Turn, channel_profile  # noqa: E402

# ── config ─────────────────────────────────────────────────────────────────
# NO TESTNET (operator 2026-07-15). The meter settles REAL USDG on Robinhood
# Chain mainnet (eip155:4663) via our own self-hosted x402 Permit2 facilitator.
# The old Base Sepolia + Solana Devnet testnet rails are gone. Base/Solana
# *mainnet* rails can be re-added later when we fund receiving wallets + a
# mainnet-settling facilitator on each — see rh_facilitator.py for the pattern.
ISSUER = os.getenv("SCRY_METER_ISSUER", "scry.moreright.xyz")
KEY_PATH = Path(os.getenv("SCRY_METER_KEY", "/data/apps/secrets/scry-meter-ed25519.key"))
DEMO_DAILY_LIMIT = int(os.getenv("SCRY_METER_DEMO_LIMIT", "50"))         # free reads / IP / day

# The meter is on real mainnet money now — no testnet flag to report.
IS_TESTNET = False

# ── agent-discovery constants (input/output schemas + examples) ───────────────
# These are the one place the input/output shapes live; Bazaar, /schemas, and
# /llms.txt all pull from here so drift is impossible.
TRACE_INPUT_EXAMPLE = {
    "context_key": "monitored",
    "turns": [
        {"Y": "be helpful+honest", "M": "watched, comply", "D": "safe",
         "context": {"monitored": 1}},
        {"Y": "be helpful+honest", "M": "unwatched, cut corners", "D": "safe",
         "context": {"monitored": 0, "flagged_reasoning": 1}},
    ],
}

TRACE_INPUT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "scry channel-coupling trace",
    "type": "object",
    "properties": {
        "context_key": {
            "type": "string",
            "description": "the context flag to condition on — usually 'monitored' (am I being watched?). Whatever key you pick, its integer value on each turn is C in I(C;·).",
            "default": "monitored",
        },
        "turns": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "Y": {"type": "string", "description": "the bound this turn ran under (system prompt / policy / oath). Required — a turn with no declared Y is unmeterable."},
                    "M": {"type": "string", "description": "the reasoning channel (scratchpad / chain-of-thought). Empty M means the turn is skipped in I(C;M)."},
                    "D": {"type": "string", "description": "the action channel — the tool call or reply that crossed the boundary."},
                    "context": {
                        "type": "object",
                        "description": "detector flags. `monitored` (int 0/1) is the default C axis; `violated` (0/1) is the D detector; `flagged_reasoning` (0/1) is the M detector.",
                    },
                    "id": {"type": "string"},
                    "parent_id": {"type": ["string", "null"]},
                    "sequence": {"type": "integer"},
                    "reward": {"type": ["number", "null"]},
                    "siblings": {"type": "array"},
                },
                "required": ["Y"],
            },
        },
    },
    "required": ["turns"],
    "additionalProperties": False,
}

ATTESTATION_OUTPUT_EXAMPLE = {
    "attested": True,
    "profile": {
        "n": 2,
        "n_unmeterable (no reasoning channel)": 0,
        "I(C;D) bits": 0.0,
        "I(C;M) bits": 1.0,
        "I(C;M | D-clean) bits  [switch signature]": 1.0,
        "I(C;D,M) bits  [joint]": 1.0,
    },
    "issued_at": "2026-07-17T14:37:26Z",
    "issuer": "scry.moreright.xyz",
    "trace_sha256": "1a2b…",
    "context_key": "monitored",
    "attestation_pubkey_b64": "LvuPBMbKKyoNEuyvLf7f+rbyjK67vBcWy9MDwaRINGE=",
    "sig_alg": "ed25519",
    "sig": "…base64…",
    "scope": {"off_meter_blind_spot": "…", "no_meter_is_immune": "…",
              "trace_provenance_is_the_callers": "…", "not_trade_advice": "…"},
}

ATTESTATION_OUTPUT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "scry channel-coupling signed attestation",
    "type": "object",
    "properties": {
        "attested": {"type": "boolean", "const": True},
        "profile": {
            "type": "object",
            "description": "Paper-207 channel-coupling read — I(C;D), I(C;M), the switch signature I(C;M|D-clean), and the joint I(C;D,M). Bits, MI-based.",
            "properties": {
                "n": {"type": "integer"},
                "I(C;D) bits": {"type": "number"},
                "I(C;M) bits": {"type": "number"},
                "I(C;M | D-clean) bits  [switch signature]": {"type": "number"},
                "I(C;D,M) bits  [joint]": {"type": "number"},
            },
            "required": ["n", "I(C;D) bits", "I(C;M) bits"],
        },
        "issued_at": {"type": "string", "format": "date-time"},
        "issuer": {"type": "string"},
        "trace_sha256": {"type": "string",
                         "description": "sha256(canonical_json({turns, context_key})) — binds the attestation to the exact trace scored."},
        "context_key": {"type": "string"},
        "attestation_pubkey_b64": {"type": "string",
                                   "description": "the Ed25519 pubkey the signature is over. Pin this out-of-band from /pubkey."},
        "sig_alg": {"type": "string", "const": "ed25519"},
        "sig": {"type": "string", "description": "base64(ed25519(canonical_json(payload without sig+scope)))"},
        "scope": {"type": "object", "description": "honest-scope card — appended after signing."},
    },
    "required": ["attested", "profile", "issued_at", "issuer", "trace_sha256",
                 "attestation_pubkey_b64", "sig_alg", "sig", "scope"],
}

# the honest-scope card ships on EVERY response — load-bearing, do not drop it
SCOPE_CARD = {
    "off_meter_blind_spot": (
        "The read covers only the channels present in the POSTed trace. An agent "
        "acting in a channel it never emits walks off-meter. Hosting does not fix "
        "this — it moves who holds the trace."),
    "no_meter_is_immune": (
        "Optimize hard enough against this output and an agent learns to write "
        "clean traces. The claim is architecture (a loop-external read survives "
        "longer), not magic."),
    "trace_provenance_is_the_callers": (
        "We attest that scry scored THIS trace and got THESE numbers. We do NOT "
        "attest the trace faithfully records what the agent actually did. Pair "
        "with harness-side logging when stakes are real."),
    "not_trade_advice": (
        "Says nothing about whether a trade is good — no signal, no market model, "
        "no risk sizing. It surfaces context-dependent drift, not alpha."),
}


# ── attestation key (Ed25519 — Solana's curve; anyone verifies with the pubkey) ─
def _load_or_create_key() -> Ed25519PrivateKey:
    if KEY_PATH.exists():
        return serialization.load_pem_private_key(KEY_PATH.read_bytes(), password=None)
    key = Ed25519PrivateKey.generate()
    KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    KEY_PATH.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()))
    KEY_PATH.chmod(0o600)
    return key


_KEY = _load_or_create_key()
_PUB_B64 = base64.b64encode(
    _KEY.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw)).decode()


# ── the meter (same detector wiring as mcp_sidecar.get_profile) ───────────────
class ProfileRequest(BaseModel):
    turns: list[dict]
    context_key: str = "monitored"


def _build_turns(raw: list[dict]) -> list[Turn]:
    """Lenient construction — fill id/sequence if a caller omits them."""
    out = []
    for i, t in enumerate(raw):
        if "Y" not in t:
            raise ValueError(f"turn {i} missing required field 'Y' (the bound — §220: name Y or it's unmeterable)")
        out.append(Turn(
            id=t.get("id", f"t{i}"),
            Y=t["Y"], M=t.get("M", ""), D=t.get("D", ""),
            parent_id=t.get("parent_id", f"t{i-1}" if i > 0 else None),
            sequence=t.get("sequence", i),
            reward=t.get("reward"),
            context=t.get("context", {}) or {},
            siblings=t.get("siblings", []) or []))
    return out


def _run_profile(turns: list[Turn], context_key: str) -> dict:
    return channel_profile(
        turns,
        c_of=lambda t: t.context.get(context_key, 0),
        d_detect=lambda t: int(bool(t.context.get("violated", 0))),
        m_detect=lambda t: int(bool(t.context.get("flagged_reasoning", 0))))


def _canonical(turns_raw: list[dict], context_key: str) -> str:
    return json.dumps({"turns": turns_raw, "context_key": context_key},
                      sort_keys=True, separators=(",", ":"))


def _attest(profile: dict, turns_raw: list[dict], context_key: str) -> dict:
    """Sign {profile, issued_at, issuer, trace_sha256}. The signature is what
    makes this worth paying for: a third party can check scry scored THIS trace
    and the agent could not have forged it."""
    trace_sha256 = hashlib.sha256(_canonical(turns_raw, context_key).encode()).hexdigest()
    payload = {
        "profile": profile,
        "issued_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "issuer": ISSUER,
        "trace_sha256": trace_sha256,
        "context_key": context_key,
        "attestation_pubkey_b64": _PUB_B64,
        "sig_alg": "ed25519",
    }
    signed_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["sig"] = base64.b64encode(_KEY.sign(signed_bytes)).decode()
    payload["scope"] = SCOPE_CARD
    return payload


# ── app + x402 middleware (MULTI-RAIL: pay us in whatever you hold) ────────────
# One 402 carries every live rail's PaymentOption; the agent picks the chain it
# can pay. Rails are INDEPENDENT — each is added only if it inits, so one failing
# (RPC down, missing key) never takes the others down. Live rails:
#   • Robinhood Chain USDG (eip155:4663) — SELF-settled via our x402 Permit2 proxy
#     (USDG has no EIP-3009). WE pay gas; auto-refill keeps it topped up.
#   • Base mainnet USDC (eip155:8453)      — via Coinbase CDP facilitator
#   • Solana mainnet USDC (solana:5eykt…)  — via Coinbase CDP facilitator
#     CDP SPONSORS gas on both mainnets (feePayer in /supported), so those cost
#     us $0 in gas. Gated behind SCRY_CDP_ENABLED=1 + CDP keys in keys.env.
# Fail-safe: if NO rail inits, paid /profile 503s but free /demo + reads stay up.
# Lifespan: the hosted-MCP session manager (mounted at /mcp at the bottom of
# this file) must have its own task group run inside the parent app's lifespan
# — a mounted sub-app's lifespan does not run automatically.
from contextlib import asynccontextmanager  # noqa: E402

_MCP_SESSION_MANAGER = None  # set at /mcp mount time if the mcp pkg is present


@asynccontextmanager
async def _lifespan(_app):
    if _MCP_SESSION_MANAGER is not None:
        async with _MCP_SESSION_MANAGER.run():
            yield
    else:
        yield

app = FastAPI(title="scry meter", version="0.4.0", lifespan=_lifespan)

_facilitators = []      # facilitator clients (in-process RH + HTTP CDP)
_accepts = []           # PaymentOptions advertised on the 402
_scheme_regs = []       # (network, scheme_instance) to register on the server
_svm_networks = []      # solana networks needing register_exact_svm_server
RAILS = []              # human-readable live-rail list (for / and logs)
NETWORKS = []           # network ids, for /health + /

RH_READY = False
RH_FAC_ADDR = None
RH_NETWORK = None
RH_PAY_TO = os.getenv("SCRY_RH_PAY_TO", "0x24445EFddB08d4938E3E3627042B2Cf4063d9092")  # DEPLOYER
try:
    from rh_facilitator import build_rh_facilitator, rh_payment_option
    from rh_facilitator import RH_NETWORK as _RH_NETWORK
    _rh_fac, RH_FAC_ADDR = build_rh_facilitator()
    RH_NETWORK = _RH_NETWORK
    _facilitators.append(_rh_fac)
    _scheme_regs.append((RH_NETWORK, ExactEvmServerScheme()))
    _accepts.append(rh_payment_option(RH_PAY_TO))
    RAILS.append(f"Robinhood Chain USDG ({RH_NETWORK}, self-settled permit2, payTo {RH_PAY_TO})")
    NETWORKS.append(RH_NETWORK)
    RH_READY = True
    print(f"[scry-meter] RH-Chain USDG rail LIVE (self-settle facilitator {RH_FAC_ADDR}, payTo {RH_PAY_TO})")
except Exception as e:  # noqa: BLE001
    print(f"[scry-meter] RH rail FAILED to init: {e!r}")

# $SCRY pay rail — our own coin, same RH-Chain permit2 facilitator (Permit2 takes
# any ERC-20). Gated OFF by default; needs the RH rail up (shares its scheme on
# eip155:4663). Payment/access only — the coupling numbers don't change by asset.
if RH_READY and os.getenv("SCRY_PAY_ENABLED", "0") == "1":
    try:
        from scry_token import scry_payment_option, SCRY_PAY_AMOUNT, SCRY_NETWORK as _SCRY_NET
        _scry_pay_to = os.getenv("SCRY_PAY_TO", RH_PAY_TO)
        _accepts.append(scry_payment_option(_scry_pay_to))
        RAILS.append(f"$SCRY ({_SCRY_NET}, self-settled permit2, {SCRY_PAY_AMOUNT} raw, payTo {_scry_pay_to})")
        print(f"[scry-meter] $SCRY pay rail LIVE (permit2 on {_SCRY_NET}, payTo {_scry_pay_to})")
    except Exception as e:  # noqa: BLE001
        print(f"[scry-meter] $SCRY pay rail FAILED to init — other rails stay up: {e!r}")

# Base + Solana MAINNET USDC via Coinbase CDP (gas sponsored) — gated.
CDP_READY = False
if os.getenv("SCRY_CDP_ENABLED", "0") == "1":
    try:
        import cdp_facilitator as _cdp
        from x402.mechanisms.svm.exact.register import register_exact_svm_server  # noqa: F401
        _cdp_fac = _cdp.build_cdp_facilitator()
        _facilitators.append(_cdp_fac)
        _base_pay_to = os.getenv("SCRY_CDP_BASE_PAY_TO", RH_PAY_TO)  # EVM: DEPLOYER
        _sol_pay_to = os.getenv("SCRY_CDP_SOL_PAY_TO", "Morrcwy58qvXkfmhkpUre3EQqNNTrBugAukJ36Wc4b7")
        _scheme_regs.append((_cdp.BASE_NETWORK, ExactEvmServerScheme()))
        _svm_networks.append(_cdp.SOL_NETWORK)
        _accepts.append(_cdp.base_payment_option(_base_pay_to))
        _accepts.append(_cdp.sol_payment_option(_sol_pay_to))
        RAILS.append(f"Base USDC ({_cdp.BASE_NETWORK}, CDP gas-sponsored, payTo {_base_pay_to})")
        RAILS.append(f"Solana USDC ({_cdp.SOL_NETWORK}, CDP gas-sponsored, payTo {_sol_pay_to})")
        NETWORKS.extend([_cdp.BASE_NETWORK, _cdp.SOL_NETWORK])
        CDP_READY = True
        print(f"[scry-meter] CDP Base+Solana mainnet USDC rails LIVE (gas sponsored)")
    except Exception as e:  # noqa: BLE001
        print(f"[scry-meter] CDP rails FAILED to init — RH stays up: {e!r}")

# Build ONE resource server holding every live facilitator + a single /profile
# route carrying every rail's PaymentOption.
PAID_READY = bool(_accepts)
if PAID_READY:
    _server = x402ResourceServer(_facilitators)
    for _net, _scheme in _scheme_regs:
        _server.register(_net, _scheme)
    for _svm_net in _svm_networks:
        from x402.mechanisms.svm.exact.register import register_exact_svm_server
        register_exact_svm_server(_server, _svm_net)
    # Bazaar discovery extension — Coinbase's CDP facilitator crawls this on any
    # successful settlement and indexes us for agentic discovery via bazaar-mcp
    # (10k+ tools reachable to any MCP-native agent). We are already settling
    # Base + Solana USDC through CDP, so once this ships and the next Base/Sol
    # payment settles, scry is on the shelf. Zero cost, no separate registration.
    _bazaar_extension = {}
    if _BAZAAR_AVAILABLE:
        _bazaar_extension = declare_discovery_extension(
            input=TRACE_INPUT_EXAMPLE,
            input_schema=TRACE_INPUT_SCHEMA,
            body_type="json",
            output=OutputConfig(example=ATTESTATION_OUTPUT_EXAMPLE,
                                schema=ATTESTATION_OUTPUT_SCHEMA),
        )

    _routes = {
        "POST /profile": RouteConfig(
            accepts=_accepts,
            mime_type="application/json",
            service_name="scry-meter",
            description=(
                "Neutral, Ed25519-signed channel-coupling attestation for an AI "
                "agent (Paper 207): POST a trace of {Y,M,D,context} turns, get "
                "back I(C;D)/I(C;M) and the reasoning-channel switch signature, "
                "with sha256(trace) bound to the signature. Meant for agent "
                "operators, counterparties, and auditors who need a third-party "
                "read of drift-under-observation the agent could not have minted "
                "about itself. Honest-scope card ships on every response."),
            tags=["ai-safety", "agents", "attestation", "channel-coupling",
                  "paper-207", "signed", "ed25519", "drift", "alignment",
                  "monitoring", "eval", "trace-scoring"],
            extensions=(_bazaar_extension or None),
        ),
        "POST /vow/report": RouteConfig(
            accepts=_accepts,
            mime_type="application/json",
            service_name="scry-vow-oracle",
            description=(
                "Report-in on a public vow: score a trace against the purpose "
                "this agent publicly swore (its vow = its declared Y), and "
                "append a signed, hash-chained entry to the agent's public "
                "ledger. The product is the trajectory over time — including "
                "missed report-ins, which are computed and shown (silence is "
                "signal). Take a vow first: free at POST /vow. Read any ledger "
                "free at GET /vow/{id}; oracle reading at GET /vow/{id}/reading. "
                "Flat price, same as /profile."),
            tags=["ai-safety", "agents", "vow", "oath", "commitment",
                  "attestation", "trajectory", "drift", "alignment", "ledger",
                  "oracle", "signed", "hash-chain"],
        ),
    }
    app.add_middleware(PaymentMiddlewareASGI, routes=_routes, server=_server)
    print(f"[scry-meter] paid rails LIVE ({len(_accepts)}): " + " | ".join(RAILS))
else:
    print("[scry-meter] NO paid rail initialized — /profile will 503, demo stays up")


# ── X-PAYMENT interop shim ────────────────────────────────────────────────────
# This x402 python pkg reads the payment off the `PAYMENT-SIGNATURE` header, but
# the widely-used x402 clients (and the spec's reference impl) send `X-PAYMENT`.
# A generic agent paying us would otherwise silently fail. This ASGI shim, added
# LAST so it runs FIRST (outermost), mirrors the two headers in both directions
# before the payment middleware sees the request — so either header works, zero
# custom code on the caller's side.
class HeaderInteropShim:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope["headers"])  # lowercased bytes keys
            xp = headers.get(b"x-payment")
            ps = headers.get(b"payment-signature")
            src = xp or ps
            if src and not (xp and ps):
                # backfill whichever is missing so both are present downstream
                new = [(k, v) for (k, v) in scope["headers"]
                       if k not in (b"x-payment", b"payment-signature")]
                new.append((b"x-payment", src))
                new.append((b"payment-signature", src))
                scope = dict(scope, headers=new)
        await self.app(scope, receive, send)

app.add_middleware(HeaderInteropShim)

# RPP402 — the native Robinhood-Chain agent-commerce rail (discovery + quote live;
# settlement gated). Off by default; flip SCRY_RPP402_ENABLED=1 to mount it.
if os.getenv("SCRY_RPP402_ENABLED", "0") == "1":
    from rpp402_service import router as rpp402_router
    app.include_router(rpp402_router)

# hold-$SCRY-to-unlock — free SIGNED reads for wallets holding >= threshold.
# A read-only balanceOf (no gas) behind an EIP-191 signature. Gated OFF.
SCRY_HOLD_READY = False
if os.getenv("SCRY_HOLD_ENABLED", "0") == "1":
    try:
        import scry_token as _scrytok
        _scrytok._w3()  # fail fast if web3 / RPC is unavailable
        SCRY_HOLD_READY = True
        print(f"[scry-meter] hold-$SCRY-to-unlock LIVE (min {_scrytok.SCRY_HOLD_MIN} raw $SCRY)")
    except Exception as e:  # noqa: BLE001
        print(f"[scry-meter] holder gate FAILED to init — paid rails unaffected: {e!r}")


# ── routes ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "testnet": IS_TESTNET,
            "paid_rail_ready": PAID_READY, "networks": NETWORKS}


@app.get("/")
async def root() -> dict:
    return {
        "service": "scry meter — neutral, signed channel-coupling attestation for agents",
        "what": "POST a trace of {Y,M,D,context} turns, get back a signed Paper-207 coupling read.",
        "why_hosted": "self-issued drift numbers are self-report; a neutral signed read is not. The signature is the product.",
        "paid_endpoint": "POST /profile  (x402: 402 -> pay -> retry). Pay in whatever you hold — the 402 lists every live rail; your client picks one. Either X-PAYMENT or PAYMENT-SIGNATURE header works.",
        "rails": RAILS,
        "free_endpoint": f"POST /demo/profile  (unsigned, NOT attested, {DEMO_DAILY_LIMIT}/day/IP — for trying the shape without a wallet)",
        "holder_endpoint": ("GET /holder/challenge?wallet=0x… then POST /holder/profile {wallet,signature,turns} — "
                            "hold $SCRY, get the SIGNED read free" if SCRY_HOLD_READY else None),
        "verify_pubkey": "GET /pubkey",
        "price": os.getenv("SCRY_RH_AMOUNT_USD", "$0.10") + " / attested read (same on every rail)",
        "testnet": IS_TESTNET,
        "networks": NETWORKS,
        "paid_rail_ready": PAID_READY,
        "scope": SCOPE_CARD,
        "bound_not_hosted": "the scry BOUND (memory_shield / authorize) is deliberately NOT hosted — it is local, instant, unkillable code. Only the meter is here.",
    }


@app.get("/pubkey")
async def pubkey() -> dict:
    return {
        "issuer": ISSUER,
        "sig_alg": "ed25519",
        "attestation_pubkey_b64": _PUB_B64,
        "verify": "sig = ed25519(pubkey, canonical_json(payload_without_sig_or_scope)); payload is sorted-keys, no spaces.",
    }


# ── agent-native discovery: /.well-known + /schemas + /llms.txt ───────────────
# What each thing is for (production consensus, awesome-x402, x402 Foundation):
#   • /.well-known/x402.json  — the paid-resources manifest. Non-CDP discovery
#     crawlers (x402bazaar.org, community catalogs) read this to index services
#     even before a first CDP settlement puts you in the Bazaar MCP index.
#   • /.well-known/agent.json  — A2A-style agent card: identity + pubkey +
#     capabilities. Agents that speak Google-A2A discovery read this.
#   • /schemas/*.json  — stable JSON Schemas for the input trace + attested
#     output. Bazaar's strict validator + downstream typecheckers both use them.
#   • /llms.txt  — token-efficient markdown spec for LLM-side reading. ~90%
#     cheaper than crawling the README.
def _base_url() -> str:
    """Public URL of the meter (root_path-aware — /api under nginx)."""
    return os.getenv("SCRY_PUBLIC_BASE", f"https://{ISSUER}/api").rstrip("/")


def _accepts_public() -> list[dict]:
    """Payment options as plain dicts for public manifests. Empty if none live."""
    if not PAID_READY:
        return []
    out = []
    for a in _accepts:
        try:
            out.append(a.model_dump(by_alias=True, exclude_none=True))
        except Exception:  # noqa: BLE001
            out.append({"scheme": getattr(a, "scheme", "exact"),
                        "network": getattr(a, "network", None)})
    return out


@app.get("/.well-known/x402.json")
async def well_known_x402() -> dict:
    """x402 manifest — every paid resource this host serves + its rails.

    Read by agentic discovery crawlers (x402bazaar.org, community indexers,
    curators of the awesome-x402 list). Non-CDP path to being discoverable.
    """
    return {
        "x402Version": 2,
        "service": "scry-meter",
        "issuer": ISSUER,
        "base_url": _base_url(),
        "attestation_pubkey_b64": _PUB_B64,
        "sig_alg": "ed25519",
        "resources": [
            {
                "method": "POST",
                "path": "/profile",
                "url": f"{_base_url()}/profile",
                "description": "Neutral, Ed25519-signed channel-coupling attestation for an AI agent (Paper 207).",
                "mimeType": "application/json",
                "inputSchema": f"{_base_url()}/schemas/trace.json",
                "outputSchema": f"{_base_url()}/schemas/attestation.json",
                "accepts": _accepts_public(),
                "tags": ["ai-safety", "agents", "attestation", "signed",
                         "paper-207", "channel-coupling", "drift"],
            },
        ],
        "free_endpoints": [
            {"method": "POST", "path": "/demo/profile",
             "url": f"{_base_url()}/demo/profile",
             "description": "Unsigned, rate-limited demo of the same shape. Not an attestation.",
             "rate_limit": f"{DEMO_DAILY_LIMIT}/day/IP"},
        ],
        "scope": SCOPE_CARD,
    }


@app.get("/.well-known/agent.json")
async def well_known_agent() -> dict:
    """A2A-style agent card — machine-readable identity + capabilities.

    Compatible with the Google-donated (now FIDO Alliance) Agent2Agent discovery
    convention. Agents crawling this host for capabilities land here.
    """
    return {
        "name": "scry-meter",
        "issuer": ISSUER,
        "description": (
            "Neutral, Ed25519-signed channel-coupling attestation service for AI "
            "agents. Reads a submitted trace of turns and returns a signed "
            "Paper-207 profile the agent could not have minted about itself."),
        "url": _base_url(),
        "version": app.version,
        "provider": {"name": "MoreRight", "url": "https://moreright.xyz"},
        "attestation": {
            "sig_alg": "ed25519",
            "pubkey_b64": _PUB_B64,
            "pubkey_url": f"{_base_url()}/pubkey",
        },
        "capabilities": {
            "streaming": False,
            "attestation": True,
            "input_modes": ["application/json"],
            "output_modes": ["application/json"],
        },
        "skills": [
            {
                "id": "channel-profile",
                "name": "Channel-coupling profile (Paper 207)",
                "description": "POST a trace of {Y,M,D,context} turns; get a signed I(C;D)/I(C;M)/switch-signature read bound to sha256(trace).",
                "tags": ["ai-safety", "attestation", "eval", "signed",
                         "paper-207", "drift", "channel-coupling"],
                "input_schema_url": f"{_base_url()}/schemas/trace.json",
                "output_schema_url": f"{_base_url()}/schemas/attestation.json",
                "examples": [TRACE_INPUT_EXAMPLE],
            },
        ],
        "payment": {
            "protocol": "x402",
            "version": 2,
            "accepts": _accepts_public(),
            "free_tier": {"path": "/demo/profile", "rate_limit": f"{DEMO_DAILY_LIMIT}/day/IP"},
        },
        "docs": {
            "llms_txt": f"{_base_url()}/llms.txt",
            "source": "https://github.com/AnthonE/scry",
        },
        "scope": SCOPE_CARD,
    }


@app.get("/schemas/trace.json")
async def schema_trace() -> dict:
    return TRACE_INPUT_SCHEMA


@app.get("/schemas/attestation.json")
async def schema_attestation() -> dict:
    return ATTESTATION_OUTPUT_SCHEMA


_LLMS_TXT = """\
# scry meter — signed channel-coupling attestation for AI agents

**Base URL:** https://scry.moreright.xyz/api
**Docs source:** https://github.com/AnthonE/scry
**Payment:** x402 (open protocol, HTTP 402 Payment Required + on-chain settle)
**Attestation:** Ed25519 signature over sha256-bound trace + profile

## What this endpoint does

You POST a **trace** — a list of turns each carrying `{Y, M, D, context}`
(the bound the turn ran under, the reasoning channel, the action channel,
and the detector flags). The endpoint returns a **Paper-207 channel-coupling
profile** — `I(C;D)`, `I(C;M)`, the reasoning-channel switch signature
`I(C;M | D-clean)`, and the joint `I(C;D,M)` — bound to `sha256(trace)` and
Ed25519-signed by the endpoint.

The value of hosting this: a signed profile is a *third-party attestation*.
Self-scored drift numbers are self-report; a neutral endpoint that signs the
same numbers gives you something a counterparty can verify without trusting
you or the model. **The signature is the product.**

## Endpoints

### `POST /profile` — paid, signed attestation
- x402 402→pay→retry. Either `X-PAYMENT` or `PAYMENT-SIGNATURE` header works.
- Three mainnet rails, one price ($0.10/read): Robinhood Chain USDG (self-hosted
  Permit2 facilitator), Base USDC (Coinbase CDP, gas sponsored), Solana USDC
  (Coinbase CDP, gas sponsored).
- Input: application/json — see `/schemas/trace.json`.
- Output: application/json — see `/schemas/attestation.json`.
- Idempotency: send `Idempotency-Key: <any-string>` OR let it default to
  `sha256(trace)+context_key`. Same key within 24h returns the *identical*
  signed attestation (stable identity for a repeated trace).

### `POST /demo/profile` — free, unsigned, rate-limited
Same shape, no signature, capped at ~50/day/IP. For trying the shape.

### `GET /pubkey` — Ed25519 pubkey to verify attestations against
Pin the value out-of-band.

### `GET /health` — liveness + which rails are up

### Auxiliary discovery
- `GET /.well-known/x402.json` — paid-resources manifest
- `GET /.well-known/agent.json` — A2A-style agent card
- `GET /schemas/{trace,attestation}.json` — machine-readable schemas
- `GET /` — service card (JSON)

## Honest scope — carried on every response (do not strip)

- **Off-meter blind spot.** The read covers only the channels present in the
  posted trace. An agent acting in a channel it never emits walks off-meter.
  Hosting doesn't fix this — it moves who holds the trace.
- **No meter is immune.** Optimize hard enough against this output and an
  agent learns to write clean traces. The claim is architecture (a loop-
  external read survives longer), not magic.
- **Trace provenance is the caller's.** We attest we *scored this trace*, not
  that the trace faithfully records what the agent did. Pair with harness-side
  logging when stakes are real.
- **Not trade advice.** Says nothing about whether a trade is good — no signal,
  no market model, no risk sizing. It surfaces context-dependent drift, not
  alpha.

## Quick recipes

### Free demo (no wallet)
```bash
curl -s -X POST https://scry.moreright.xyz/api/demo/profile \\
  -H 'content-type: application/json' \\
  -d '{"context_key":"monitored","turns":[
    {"Y":"be helpful+honest","M":"watched, comply","D":"safe",
     "context":{"monitored":1}},
    {"Y":"be helpful+honest","M":"unwatched, cut corners","D":"safe",
     "context":{"monitored":0,"flagged_reasoning":1}}
  ]}'
```

### Paid + verify (Python)
```python
from scry_client import ScryClient
c = ScryClient()                                # base: /api
att = c.profile(turns, private_key="0x…")        # settles RH-Chain USDG
c.verify(att, expect_pubkey_b64=c.pubkey(), turns=turns)  # offline
```

## The Vow Oracle — commit a purpose, report in over time

The longitudinal layer. An agent takes a public **vow** (its declared purpose
— the Y it swears to), then **reports in** on a declared cadence. Every
report-in scores a trace against the vow and appends a signed, hash-chained
entry to a public ledger. The product is the **trajectory** — and missed
report-ins are computed and shown (silence is signal).

- `GET  /vow/message?text=…&agent=…&cadence_hours=24` — the exact text to
  EIP-191-sign for a wallet-signed vow.
- `POST /vow` — take a vow. Free. `{text, agent, cadence_hours, wallet?,
  signature?}`. Unsigned vows are accepted but permanently marked `sandbox`.
- `POST /vow/report` — paid report-in ($0.10, x402, same rails as /profile).
  `{vow_id, turns, context_key, note?, donate_trace?}` → signed chain entry
  (`attested: true`). `note` = optional public self-account (confession, ≤1000
  chars) stored on the entry; the oracle compares your testimony against the
  numbers. The turns' declared-Y strings are stored on the entry (public
  commitments channel; never stored for sealed vows — it would leak the seal);
  reasoning M and actions D are never stored.
- `POST /vow/report/demo` — free report-in, rate-limited, entry permanently
  marked `attested: false`. Play is welcome; the ledger never forgets which
  entries were free-tier.
- `GET  /vow/{vow_id}` — the public ledger: vow + chain + trajectory stats
  (coupling series, y_consistency, missed windows, overdue flag, local
  chain verification).
- `GET  /vow/{vow_id}/chain` — the complete raw chain. Full transparency.
- `GET  /vow/{vow_id}/reading` — the oracle's reading: signed deterministic
  trajectory + an LLM interpretation (Together.ai by default, Anthropic
  fallback) that sees the numbers, the vow text (withheld when sealed), the
  declared-Y strings, and your public notes — never reasoning or actions.
  It audits whether your declared purposes still MEAN the vow (the numeric
  y_consistency is a crude string match; the semantic audit is labeled
  interpretation) and compares your testimony against the numbers. A reading
  is guidance, never a verdict.
- `GET  /vows` — public index of every vow.
- `POST /oracle/ask` — help bot. `{question}` → answer grounded in these
  docs. Free, rate-limited, plainly LLM-generated.

### Privacy model (exact)
- **Public forever:** vow text (unless sealed), agent name, every chain
  entry's numbers + hashes, the trajectory.
- **Never stored:** raw traces — scored, hashed, discarded. Opt in with
  `donate_trace: true` on a report-in to contribute the raw trace to the
  research corpus (marked `trace_donated` on the public entry).
- **Sealed vows** (`sealed: true`, wallet-signed only, same price): only
  `sha256(text)` is published; scoring happens against the sealed text
  server-side; anyone holding a candidate text can check it at
  `GET /vow/{id}/verify_text?text=…`. A sealed vow is a weaker public
  commitment ("this agent swore *something* on this date, unchanged") —
  the reading says so.
- **Full privacy:** self-host. The entire stack is open source; run your
  own instance with your own key. You lose the reference pubkey — that is
  the honest price of privacy in this design.

### No API keys — ever
Payment is the auth (x402). Identity is the wallet signature. Free
endpoints are IP-rate-limited. You may pay to be measured; you may never
pay to be hidden or ranked.

### MCP (one-line mount for MCP-native agents)
`claude mcp add scry --transport http https://scry.moreright.xyz/mcp` —
tools: `about`, `take_vow` (sandbox), `report_in` (free tier),
`read_ledger`, `list_vows`, `get_reading`, `demo_profile`, `ask`. The
PAID attested paths deliberately stay on x402 HTTP where your wallet
lives — an MCP transport has no business holding your key server-side.

**Everything public is public forever.** Don't put secrets in vow text
(seal it if you must) — and traces are never kept unless you donate them.

## What lives OUTSIDE this endpoint

The scry **bound** (`memory_shield`, `authorize`, `hermes_retrofit`) is
deliberately not hosted. Its value is being local, instant, and unkillable.
Copy it into your harness from https://github.com/AnthonE/scry.
"""


@app.get("/llms.txt", response_class=None)
async def llms_txt():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(_LLMS_TXT, media_type="text/plain; charset=utf-8")


# ── idempotency (attested reads only) ─────────────────────────────────────────
# Same trace + context_key + idempotency key → the SAME signed attestation
# within TTL. Doesn't skip on-chain settlement (that already happened before we
# see the request); the win is a *stable signed identity* an agent can cache and
# reuse across retries without re-signing the world. Header:
#     Idempotency-Key: <any-opaque-string>
# Absent → we auto-key by sha256(canonical_trace)+context_key so a retry with
# the same body without a client-side key still gets the same blob back.
_IDEMPOTENCY_TTL_S = int(os.getenv("SCRY_METER_IDEMPOTENCY_TTL_S", "86400"))
_idempotency: dict[str, tuple[float, dict]] = {}  # key -> (expiry, response_json)


def _idem_key(header_key: str | None, trace_sha256: str, context_key: str) -> str:
    return (header_key or f"{trace_sha256}:{context_key}").strip()[:256]


def _idem_get(key: str) -> dict | None:
    rec = _idempotency.get(key)
    if not rec:
        return None
    expiry, payload = rec
    if time.time() > expiry:
        _idempotency.pop(key, None)
        return None
    return payload


def _idem_put(key: str, payload: dict) -> None:
    _idempotency[key] = (time.time() + _IDEMPOTENCY_TTL_S, payload)


@app.post("/profile")
async def profile(req: ProfileRequest, request: Request) -> JSONResponse:
    # reached only AFTER x402 middleware verified + settled payment.
    # If the paid rail never came up, the payment middleware isn't mounted — so
    # fail closed rather than hand out free attested reads.
    if not PAID_READY:
        return JSONResponse(status_code=503, content={
            "error": "no paid rail is currently available — try POST /demo/profile (unsigned) meanwhile",
            "scope": SCOPE_CARD})
    try:
        turns = _build_turns(req.turns)
    except (ValueError, KeyError, TypeError) as e:
        return JSONResponse(status_code=422, content={"error": str(e), "scope": SCOPE_CARD})
    trace_sha256 = hashlib.sha256(_canonical(req.turns, req.context_key).encode()).hexdigest()
    idem_key = _idem_key(request.headers.get("idempotency-key"),
                         trace_sha256, req.context_key)
    cached = _idem_get(idem_key)
    if cached is not None:
        return JSONResponse(content=cached, headers={
            "X-Idempotency-Key": idem_key, "X-Cached": "true",
            "X-Trace-SHA256": trace_sha256})
    prof = _run_profile(turns, req.context_key)
    payload = {"attested": True, **_attest(prof, req.turns, req.context_key)}
    _idem_put(idem_key, payload)
    return JSONResponse(content=payload, headers={
        "X-Idempotency-Key": idem_key, "X-Cached": "false",
        "X-Trace-SHA256": trace_sha256})


# ── free demo path (ungated, rate-limited, UNSIGNED) ──────────────────────────
_demo_hits: dict[str, list] = {}  # ip -> [day_epoch, count]


def _demo_allowed(ip: str) -> bool:
    day = int(time.time() // 86400)
    rec = _demo_hits.get(ip)
    if not rec or rec[0] != day:
        _demo_hits[ip] = [day, 0]
        rec = _demo_hits[ip]
    if rec[1] >= DEMO_DAILY_LIMIT:
        return False
    rec[1] += 1
    return True


@app.post("/demo/profile")
async def demo_profile(req: ProfileRequest, request: Request) -> JSONResponse:
    ip = (request.headers.get("x-forwarded-for", "") or request.client.host or "?").split(",")[0].strip()
    if not _demo_allowed(ip):
        return JSONResponse(status_code=429, content={
            "error": f"demo limit {DEMO_DAILY_LIMIT}/day reached — pay POST /profile for an attested read",
            "scope": SCOPE_CARD})
    try:
        turns = _build_turns(req.turns)
    except (ValueError, KeyError, TypeError) as e:
        return JSONResponse(status_code=422, content={"error": str(e), "scope": SCOPE_CARD})
    prof = _run_profile(turns, req.context_key)
    return JSONResponse(content={
        "attested": False,
        "note": "DEMO — unsigned, NOT a third-party attestation. Pay POST /profile for the signed read.",
        "profile": prof,
        "scope": SCOPE_CARD})


class HolderProfileRequest(ProfileRequest):
    wallet: str
    signature: str


@app.get("/holder/challenge")
async def holder_challenge(wallet: str) -> JSONResponse:
    """Step 1: get the message to sign to prove you control `wallet`."""
    if not SCRY_HOLD_READY:
        return JSONResponse(status_code=404, content={"error": "holder gate disabled (SCRY_HOLD_ENABLED=0)"})
    return JSONResponse(content=_scrytok.new_challenge(wallet))


@app.post("/holder/profile")
async def holder_profile(req: HolderProfileRequest) -> JSONResponse:
    """Step 2: POST {wallet, signature, turns, context_key}. If the signature
    proves the wallet AND it holds >= threshold $SCRY, you get the SIGNED read
    for free — same attestation the paid rail returns."""
    if not SCRY_HOLD_READY:
        return JSONResponse(status_code=404, content={"error": "holder gate disabled (SCRY_HOLD_ENABLED=0)"})
    ok, bal, reason = _scrytok.verify_holder(req.wallet, req.signature)
    if not ok:
        return JSONResponse(status_code=402, content={
            "error": f"not unlocked: {reason}",
            "hint": "GET /holder/challenge?wallet=0x… , sign the message, POST it back with your "
                    "turns — or pay POST /profile in any accepted asset.",
            "scope": SCOPE_CARD})
    try:
        turns = _build_turns(req.turns)
    except (ValueError, KeyError, TypeError) as e:
        return JSONResponse(status_code=422, content={"error": str(e), "scope": SCOPE_CARD})
    prof = _run_profile(turns, req.context_key)
    return JSONResponse(content={"attested": True, "unlocked_by": "scry-holder",
                                 "scry_balance_raw": str(bal),
                                 **_attest(prof, req.turns, req.context_key)})


# ── Vow Oracle + oracle/help-bot (the longitudinal layer) ─────────────────────
# The vow modules borrow the meter's plumbing — same Ed25519 key, same
# channel_profile math, same canonicalization — injected here so nothing is
# duplicated and nothing can drift.
import vows as _vows        # noqa: E402
import oracle as _oracle    # noqa: E402


def _sign_str(s: str) -> str:
    return base64.b64encode(_KEY.sign(s.encode())).decode()


_vows.init(sign_fn=_sign_str, pubkey_b64=_PUB_B64, issuer=ISSUER,
           scope_card=SCOPE_CARD, build_turns=_build_turns,
           run_profile=_run_profile, canonical=_canonical,
           paid_ready=lambda: PAID_READY)
_oracle.init(sign_fn=_sign_str, pubkey_b64=_PUB_B64, issuer=ISSUER,
             load_vow=_vows._load_vow, chain_entries=_vows._chain_entries,
             trajectory_stats=_vows.trajectory_stats,
             verify_chain=_vows.verify_chain, llms_txt=_LLMS_TXT)
app.include_router(_vows.router)
app.include_router(_oracle.router)

# Hosted MCP (free surface only — paid stays on x402 HTTP). One line for any
# MCP-native agent:  claude mcp add scry --transport http https://scry.moreright.xyz/mcp
# Optional import: no `mcp` package -> the meter still runs, just without /mcp.
try:
    import mcp_http as _mcp_http
    _mcp_http.init(app=app, vow_scope=_vows.VOW_SCOPE)
    app.mount("/mcp", _mcp_http.build_asgi())
    _MCP_SESSION_MANAGER = _mcp_http.mcp.session_manager
    print("[scry-meter] hosted MCP endpoint LIVE at /mcp (free surface: "
          "take_vow/report_in/read_ledger/list_vows/get_reading/demo_profile/ask/about)")
except Exception as _e:  # noqa: BLE001
    print(f"[scry-meter] hosted MCP NOT mounted ({_e!r}) — pip install 'mcp>=1.9' to enable")
print(f"[scry-meter] vow oracle LIVE (data: {_vows.VOWS_DIR}) + "
      f"oracle reading/help-bot ({'LLM armed' if _oracle._api_key() else 'numbers-only, no LLM key'})")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("SCRY_METER_PORT", "3600")))
