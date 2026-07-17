"""CDP (Coinbase Developer Platform) facilitator — Base + Solana MAINNET USDC.

The free public x402.org facilitator is testnet-only (verified 2026-07-15:
/supported lists Base Sepolia + Solana devnet, no mainnet). To let agents pay us
in REAL Base-mainnet and Solana-mainnet USDC, we route those two rails through
Coinbase's hosted CDP facilitator. Unlike the self-hosted RH-Chain rail (where WE
sign the settle and pay gas), CDP SPONSORS the gas — its /supported advertises a
feePayer for both mainnets — so these rails cost us $0 in gas.

Auth is a per-request EdDSA JWT signed with the CDP API secret, bound to the
exact METHOD+HOST+PATH of each facilitator call. The x402 HTTPFacilitatorClient
calls create_headers() fresh on every verify/settle/supported request
(facilitator_client_base: _get_{verify,settle,supported}_headers each invoke the
auth provider), so short-lived (120s) JWTs never go stale.

Gated: only imported/mounted when SCRY_CDP_ENABLED=1 and CDP keys resolve. Keys
read from keys.env at runtime, never committed.
"""
import os
import re

from x402.http import (
    HTTPFacilitatorClient,
    FacilitatorConfig,
    PaymentOption,
    CreateHeadersAuthProvider,
)
from x402.schemas.base import AssetAmount
from cdp.auth.utils.jwt import generate_jwt, JwtOptions

# ── CDP facilitator endpoint ──────────────────────────────────────────────────
CDP_URL = os.getenv("SCRY_CDP_URL", "https://api.cdp.coinbase.com/platform/v2/x402")
CDP_HOST = "api.cdp.coinbase.com"
CDP_BASE_PATH = "/platform/v2/x402"

# ── mainnet rails (network ids + USDC mints are x402/CDP canonical) ────────────
BASE_NETWORK = "eip155:8453"
BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"  # native USDC on Base, 6dp
# Base USDC EIP-712 domain — set explicitly so building requirements never depends
# on an on-chain asset_info RPC lookup.
BASE_USDC_DOMAIN = {"name": "USD Coin", "version": "2"}

SOL_NETWORK = "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"  # Solana mainnet CAIP-2
SOL_USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # native USDC mint, 6dp

# Same $ as the RH rail — the attestation is the product, priced per-read not
# per-gas. On CDP we don't even pay gas, so $0.10 is pure margin.
AMOUNT = os.getenv("SCRY_CDP_AMOUNT", "100000")  # 0.10 USDC (6dp)

_KEYS_ENV = os.getenv("SCRY_CDP_KEYS_ENV", "/data/apps/morr/private/secrets/keys.env")


def _load_creds() -> tuple[str, str]:
    """CDP API key id + secret from env, falling back to keys.env (never committed)."""
    kid = os.getenv("CDP_API_KEY_ID")
    sec = os.getenv("CDP_API_KEY_SECRET")
    if kid and sec:
        return kid, sec
    text = open(_KEYS_ENV).read()
    for name, cur in (("CDP_API_KEY_ID", kid), ("CDP_API_KEY_SECRET", sec)):
        if cur:
            continue
        m = re.search(r'^' + name + r'=("?)(.+?)\1\s*$', text, re.M)
        if not m:
            raise RuntimeError(f"no {name} in env or {_KEYS_ENV}")
        if name == "CDP_API_KEY_ID":
            kid = m.group(2)
        else:
            sec = m.group(2)
    return kid, sec


def _cdp_create_headers() -> dict[str, dict[str, str]]:
    """Fresh per-endpoint EdDSA JWTs. Called on every facilitator request."""
    kid, sec = _load_creds()

    def bearer(method: str, path: str) -> dict[str, str]:
        jwt = generate_jwt(JwtOptions(
            api_key_id=kid, api_key_secret=sec,
            request_method=method, request_host=CDP_HOST,
            request_path=path, expires_in=120))
        return {"Authorization": f"Bearer {jwt}"}

    return {
        "verify": bearer("POST", f"{CDP_BASE_PATH}/verify"),
        "settle": bearer("POST", f"{CDP_BASE_PATH}/settle"),
        "supported": bearer("GET", f"{CDP_BASE_PATH}/supported"),
    }


def build_cdp_facilitator() -> HTTPFacilitatorClient:
    """HTTPFacilitatorClient bound to CDP with per-request JWT auth."""
    # Fail fast if creds are missing so server.py can log + fall back cleanly.
    _load_creds()
    auth = CreateHeadersAuthProvider(_cdp_create_headers)
    return HTTPFacilitatorClient(FacilitatorConfig(url=CDP_URL, auth_provider=auth))


def base_payment_option(pay_to: str) -> PaymentOption:
    """Base-mainnet USDC rail (EIP-3009 exact; CDP sponsors gas)."""
    return PaymentOption(
        scheme="exact",
        pay_to=pay_to,
        price=AssetAmount(amount=AMOUNT, asset=BASE_USDC, extra=dict(BASE_USDC_DOMAIN)),
        network=BASE_NETWORK,
        extra=dict(BASE_USDC_DOMAIN),
    )


def sol_payment_option(pay_to: str) -> PaymentOption:
    """Solana-mainnet USDC rail (SPL exact; CDP fee-payer sponsors gas)."""
    return PaymentOption(
        scheme="exact",
        pay_to=pay_to,
        price=AssetAmount(amount=AMOUNT, asset=SOL_USDC),
        network=SOL_NETWORK,
        extra={},
    )
