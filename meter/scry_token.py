"""
$SCRY utility rails for the scry meter — pay-in-$SCRY and hold-$SCRY-to-unlock.

$SCRY is the project's own ERC-20 on Robinhood Chain (eip155:4663):
  0xDa2a4b23459e9ca88183e990802be644AcA7C4B0

Two independent, OPTIONAL rails (both OFF by default — flip the env flags after
funding the pay-to and sanity-checking on-chain):

  • PAY-IN-$SCRY  (SCRY_PAY_ENABLED=1) — a /profile payment option that settles
    through the SAME self-hosted RH-Chain Permit2 facilitator as USDG (Permit2
    works for any ERC-20, so $SCRY drops into the exact-permit2 settle path with
    no new facilitator). WE pay ETH gas on settle, exactly like the USDG rail.

  • HOLD-$SCRY-TO-UNLOCK  (SCRY_HOLD_ENABLED=1) — a free SIGNED read for wallets
    holding >= SCRY_HOLD_MIN. A read-only balanceOf() call (no gas, costs us
    nothing) gated behind an EIP-191 signature so a caller can't claim a wallet
    it doesn't control.

Honest line, keep it: the token is a PAYMENT / ACCESS rail. It does NOT touch the
measurement — the coupling numbers are identical no matter how (or whether) you
paid. That is what keeps the meter a neutral instrument; do not blur it.

web3 / eth_account are imported lazily so this module loads even where they
aren't installed; the rails simply won't arm.
"""
import os
import time
import secrets

# ── config ────────────────────────────────────────────────────────────────────
SCRY_TOKEN = os.getenv("SCRY_TOKEN", "0xDa2a4b23459e9ca88183e990802be644AcA7C4B0")
SCRY_DECIMALS = int(os.getenv("SCRY_DECIMALS", "18"))
SCRY_NETWORK = os.getenv("SCRY_NETWORK", "eip155:4663")            # Robinhood Chain
SCRY_RPC = os.getenv("SCRY_RH_RPC", os.getenv("RH_RPC", "https://rpc.mainnet.chain.robinhood.com"))

# price of one attested read, in whole $SCRY (a memecoin utility price, not USD-pegged;
# no reliable oracle for a fresh token — a flat token count is the honest choice).
SCRY_PAY_TOKENS = os.getenv("SCRY_PAY_TOKENS", "1000")             # 1000 $SCRY / read
SCRY_PAY_AMOUNT = os.getenv("SCRY_PAY_AMOUNT",                     # raw units (override wins)
                            str(int(float(SCRY_PAY_TOKENS) * (10 ** SCRY_DECIMALS))))

# holder threshold to unlock free reads, in whole $SCRY.
SCRY_HOLD_TOKENS = os.getenv("SCRY_HOLD_TOKENS", "10000")          # hold 10k $SCRY -> free reads
SCRY_HOLD_MIN = int(os.getenv("SCRY_HOLD_MIN",
                              str(int(float(SCRY_HOLD_TOKENS) * (10 ** SCRY_DECIMALS)))))

_CHALLENGE_TTL = int(os.getenv("SCRY_HOLD_CHALLENGE_TTL", "300"))  # seconds a challenge is valid
_ERC20_BALANCEOF_ABI = [{
    "constant": True, "name": "balanceOf",
    "inputs": [{"name": "owner", "type": "address"}],
    "outputs": [{"name": "", "type": "uint256"}],
    "stateMutability": "view", "type": "function",
}]


# ── PAY-IN-$SCRY: a /profile payment option on the RH-Chain permit2 rail ───────
def scry_payment_option(pay_to: str):
    """$SCRY as a permit2 PaymentOption on eip155:4663 — same scheme/facilitator
    the USDG rail already registers, just a different asset. Import is lazy so the
    module still loads without the x402 package present."""
    from x402.schemas import PaymentOption, AssetAmount
    return PaymentOption(
        scheme="exact",
        pay_to=pay_to,
        price=AssetAmount(amount=SCRY_PAY_AMOUNT, asset=SCRY_TOKEN,
                          extra={"name": "SCRY", "version": "1"}),
        network=SCRY_NETWORK,
        extra={"assetTransferMethod": "permit2", "name": "SCRY", "version": "1"},
    )


# ── HOLD-$SCRY-TO-UNLOCK: signature-gated balanceOf ───────────────────────────
def _w3():
    from web3 import Web3
    return Web3(Web3.HTTPProvider(SCRY_RPC))


def balance_of(wallet: str) -> int:
    """Raw-unit $SCRY balance of `wallet` on RH-Chain. Read-only, no gas."""
    from web3 import Web3
    w3 = _w3()
    c = w3.eth.contract(address=Web3.to_checksum_address(SCRY_TOKEN), abi=_ERC20_BALANCEOF_ABI)
    return int(c.functions.balanceOf(Web3.to_checksum_address(wallet)).call())


# in-memory challenge store: wallet(lower) -> (message, expiry). Single-process meter.
_challenges: dict[str, tuple[str, float]] = {}


def challenge_message(wallet: str, nonce: str, issued: int) -> str:
    """The exact text a holder signs (EIP-191 personal_sign). Binds wallet+nonce
    so a signature can't be replayed for a different wallet or after expiry."""
    return (f"scry holder proof\nwallet: {wallet}\nnonce: {nonce}\n"
            f"issued: {issued}\nby signing you prove you control this wallet to unlock free reads.")


def new_challenge(wallet: str) -> dict:
    wallet = wallet.lower()
    nonce = secrets.token_hex(16)
    issued = int(time.time())
    msg = challenge_message(wallet, nonce, issued)
    _challenges[wallet] = (msg, issued + _CHALLENGE_TTL)
    return {"wallet": wallet, "sign_this": msg, "expires_in": _CHALLENGE_TTL}


def _consume_challenge(wallet: str) -> str | None:
    rec = _challenges.pop(wallet.lower(), None)
    if not rec:
        return None
    msg, expiry = rec
    return msg if time.time() <= expiry else None


def verify_holder(wallet: str, signature: str) -> tuple[bool, int, str]:
    """(ok, balance, reason). Verifies the EIP-191 signature over this wallet's
    outstanding challenge recovers `wallet`, then checks balance >= SCRY_HOLD_MIN.
    Consumes the challenge (single use)."""
    msg = _consume_challenge(wallet)
    if msg is None:
        return False, 0, "no valid challenge — GET /holder/challenge first (or it expired)"
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
        recovered = Account.recover_message(encode_defunct(text=msg), signature=signature)
    except Exception as e:  # noqa: BLE001
        return False, 0, f"signature check failed: {e}"
    if recovered.lower() != wallet.lower():
        return False, 0, f"signature recovers {recovered}, not {wallet}"
    try:
        bal = balance_of(wallet)
    except Exception as e:  # noqa: BLE001
        return False, 0, f"balance lookup failed: {e}"
    if bal < SCRY_HOLD_MIN:
        return False, bal, f"holds {bal} < required {SCRY_HOLD_MIN} raw $SCRY"
    return True, bal, "ok"
