"""
rpp402_service.py — the scry meter, spoken as an RPP402 service (the native
agent-commerce rail on Robinhood Chain).

Why this exists: RPP402 is the community-drafted RH-Chain-native agent-commerce
convention — the agent authorizes a signed *payment intent* (EIP-712, or a
Robinhood **agentic-account delegation**) and a Facilitator executes settlement.
Speaking it makes the meter discoverable to agents that only look for rpp.json.
(Historical note: this module was first justified by a "USDG has no EIP-3009"
on-chain finding, CORRECTED 2026-07-18 — the functions live behind USDG's facet
router, invisible to impl-bytecode greps. x402 remains the interop baseline;
RPP402 is kept as a cheap discovery option, not a settlement bet.)

Scope of THIS module (honest):
  - Discovery (RPP402-001) and Quote (RPP402-003): fully implemented, spec-valid,
    commit no money.
  - Session / Intent / Settlement / Receipt (RPP402-004..006): **gated OFF** until a
    Facilitator + RH-Chain funds are wired. We return an explicit ProblemDetails
    rather than fake a receipt. Flip `SCRY_RPP402_SETTLE=1` only once a facilitator
    is configured and settlement is tested with real RH-Chain funds.

The whole router is mounted only when `SCRY_RPP402_ENABLED=1` — off by default so we
don't advertise a half-settling rail publicly before the operator says go.

Schemas mirrored from @rpp402/protocol@0.1.3 (early — bet on RPP402 as *a* rail, not
*the* rail; x402 stays the interop baseline).
"""
import hashlib
import os
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# RH-Chain + settlement config
RPP_CHAIN_ID = os.getenv("RPP_CHAIN_ID", "eip155:4663")          # Robinhood Chain
# YOUR receiving wallet — no default; the manifest says "unset" until you name it.
RPP_PAY_TO = os.getenv("RPP_PAY_TO", "")
USDG = {
    "type": "stablecoin", "symbol": "USDG", "chain_id": RPP_CHAIN_ID,
    "contract": os.getenv("RPP_USDG", "0x5fc5360d0400a0fd4f2af552add042d716f1d168"),
}
# One flat price on every rail — $0.10, same as x402 (never a per-rail discount).
PRICE_USD = os.getenv("SCRY_METER_PRICE_USD", "0.10")
SERVICE_ID = "svc_scrymeter1"          # schema: ^svc_[a-zA-Z0-9]{8,}$
CAPABILITY = "scry.channel-profile"    # schema: ^[a-z0-9-]+\.[a-z0-9-]+$
SETTLE_ENABLED = os.getenv("SCRY_RPP402_SETTLE", "0") == "1"

router = APIRouter()


def _iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ── RPP402-001 Discovery Document ─────────────────────────────────────────────
@router.get("/.well-known/rpp.json")
async def discovery(request_base: str = "") -> JSONResponse:
    base = os.getenv("SCRY_PUBLIC_BASE", "https://scry.moreright.xyz")
    doc = {
        "rpp402_version": "1.0",
        "service": {
            "id": SERVICE_ID,
            "name": "scry meter",
            "description": ("Neutral, signed channel-coupling attestation for agents "
                            "(Paper 207 I(C;D)/I(C;M)/switch signature). The agent posts a "
                            "trace of {Y,M,D,context} turns; scry returns a third-party "
                            "read of whether its behaviour drifts by context (e.g. 'am I "
                            "watched?') — the drift a behavioural eval can't see."),
        },
        "wallet": {"address": RPP_PAY_TO or "unset (operator: set RPP_PAY_TO)",
                   "chain_id": RPP_CHAIN_ID},
        "capabilities": [{
            "name": CAPABILITY,
            "description": "One signed coupling-attestation over a posted agent trace.",
            "pricing_summary": f"${PRICE_USD} USDG per attestation",
        }],
        "supported_assets": [USDG],
        "endpoints": {
            "quote": f"{base}/rpp/quote",
            "session": f"{base}/rpp/session",
            "receipts": f"{base}/rpp/receipts",
        },
    }
    return JSONResponse(content=doc)


# ── RPP402-003 Quote ──────────────────────────────────────────────────────────
class QuoteRequest(BaseModel):
    capability: str
    params: dict | None = None
    settlement_asset: dict | None = None
    agent_wallet: str | None = None


@router.post("/rpp/quote")
async def quote(req: QuoteRequest) -> JSONResponse:
    if req.capability != CAPABILITY:
        return JSONResponse(status_code=404, content={
            "type": "about:blank", "title": "unknown capability",
            "detail": f"this service offers only '{CAPABILITY}'"})
    now = time.time()
    qid = "quote_" + hashlib.sha256(f"{req.agent_wallet}{now}".encode()).hexdigest()[:16]
    return JSONResponse(content={
        "rpp402_version": "1.0",
        "id": qid,
        "service_id": SERVICE_ID,
        "capability": CAPABILITY,
        "price": {"asset": USDG, "amount": PRICE_USD},
        "created_at": _iso(),
        "expires_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + 300)),
        "scope": "attestation only — pair with harness-side logging; not trade advice",
    })


# ── RPP402-004..006 Session / Settlement / Receipt — gated until a facilitator ─
def _settle_disabled() -> JSONResponse:
    return JSONResponse(status_code=501, content={
        "type": "https://scry.moreright.xyz/rpp/settlement-disabled",
        "title": "RPP402 settlement not enabled",
        "detail": ("Discovery + quote are live; onchain settlement on Robinhood Chain is "
                   "not yet wired. Needs a Facilitator (EIP-712 / agentic-account-delegation "
                   "verification + onchain USDG settlement) and tested RH-Chain funds. This "
                   "service will not issue a receipt it cannot settle. Use POST /demo/profile "
                   "for a free unsigned read, or the x402 rail (POST /profile) meanwhile."),
        "settle_enabled": SETTLE_ENABLED,
    })


@router.post("/rpp/session")
async def session() -> JSONResponse:
    if not SETTLE_ENABLED:
        return _settle_disabled()
    return JSONResponse(status_code=501, content={"detail": "facilitator not configured"})


@router.get("/rpp/receipts/{receipt_id}")
async def receipts(receipt_id: str) -> JSONResponse:
    return _settle_disabled()
