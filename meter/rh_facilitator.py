"""Self-hosted x402 facilitator for the Robinhood-Chain (eip155:4663) USDG rail.

Primer's live facilitator only runs the eip3009 verifier on direct calls, and
USDG has no EIP-3009 (verified on-chain). So scry settles RH-Chain payments
ITSELF via the standard x402 Permit2 rail: the canonical Permit2 and the x402
exact-permit2 proxy are both deployed on RH-Chain, and the official x402 python
pkg's FacilitatorWeb3Signer submits the proxy `settle`. Proven live 2026-07-15
(tx 0x32e7de284e…). See private/notes/research-robinhood-chain-2026-07.md §15c.

Gated: only imported/mounted when SCRY_RH_SETTLE=1. The facilitator signs the
on-chain settle and pays gas — its key is read from keys.env at runtime, never
committed. Payers approve canonical Permit2 once, then pay gaslessly per read.
"""
import os
import re

from web3 import Web3

from x402 import x402Facilitator
from x402.mechanisms.evm.exact import register_exact_evm_facilitator
from x402.mechanisms.evm.signers import FacilitatorWeb3Signer
from x402.mechanisms.evm.data_suffix import append_data_suffix
from x402.schemas.base import AssetAmount
from x402.http import PaymentOption

RH_NETWORK = "eip155:4663"
RH_RPC = os.getenv("SCRY_RH_RPC", "https://rpc.mainnet.chain.robinhood.com")
RH_USDG = Web3.to_checksum_address(
    os.getenv("SCRY_RH_USDG", "0x5fc5360d0400a0fd4f2af552add042d716f1d168"))
RH_AMOUNT = os.getenv("SCRY_RH_AMOUNT", "1000")  # 0.001 USDG (6 dp)
_KEYS_ENV = os.getenv("SCRY_RH_KEYS_ENV", "/data/apps/morr/private/secrets/keys.env")
_KEY_NAME = os.getenv("SCRY_RH_FACILITATOR_KEY_NAME", "PRIVATE_KEY")


def _load_facilitator_key() -> str:
    """Read the facilitator (gas) wallet key from keys.env — never committed."""
    raw = os.getenv("SCRY_RH_FACILITATOR_KEY")
    if raw:
        return raw
    text = open(_KEYS_ENV).read()
    for name in (_KEY_NAME, "MEGAETH_DEPLOYER_PRIVATE_KEY"):
        m = re.search(r'^' + name + r'=("?)(0x[0-9a-fA-F]{64})\1', text, re.M)
        if m:
            return m.group(2)
    raise RuntimeError(f"no RH facilitator key ({_KEY_NAME}) in {_KEYS_ENV}")


class _Eip1559FacilitatorSigner(FacilitatorWeb3Signer):
    """FacilitatorWeb3Signer, but with EIP-1559 gas. The base class builds txs
    with a stale legacy gas_price that dips under RH-Chain's base fee ("max fee
    per gas less than block base fee"); estimate gas and set a healthy
    maxFeePerGas instead."""

    def write_contract(self, address, abi, function_name, *args, data_suffix=None):
        c = self._w3.eth.contract(address=Web3.to_checksum_address(address), abi=abi)
        fn = getattr(c.functions, function_name)(*args)
        try:
            gas = int(fn.estimate_gas({"from": self._account.address}) * 1.4)
        except Exception:
            gas = 400_000
        base = self._w3.eth.get_block("latest")["baseFeePerGas"]
        prio = self._w3.to_wei(0.02, "gwei")
        tx = fn.build_transaction({
            "from": self._account.address,
            "nonce": self._reserve_nonce(),
            "chainId": self.get_chain_id(),
            "gas": gas,
            "maxFeePerGas": base * 3 + prio,
            "maxPriorityFeePerGas": prio,
        })
        if data_suffix:
            cd = tx["data"]
            if isinstance(cd, (bytes, bytearray)):
                cd = "0x" + bytes(cd).hex()
            tx["data"] = append_data_suffix(cd, data_suffix)
        signed = self._account.sign_transaction(tx)
        h = self._w3.eth.send_raw_transaction(signed.raw_transaction)
        return h.hex()


def build_rh_facilitator():
    """Return (x402Facilitator for eip155:4663, facilitator_gas_wallet_address)."""
    signer = _Eip1559FacilitatorSigner(private_key=_load_facilitator_key(), rpc_url=RH_RPC)
    fac = x402Facilitator()
    register_exact_evm_facilitator(fac, signer, RH_NETWORK)
    return fac, signer.address


def rh_payment_option(pay_to: str) -> PaymentOption:
    """The Robinhood-Chain USDG rail as a /profile payment option (permit2)."""
    return PaymentOption(
        scheme="exact",
        pay_to=pay_to,
        price=AssetAmount(amount=RH_AMOUNT, asset=RH_USDG,
                          extra={"name": "USDG", "version": "1"}),
        network=RH_NETWORK,
        extra={"assetTransferMethod": "permit2", "name": "USDG", "version": "1"},
    )
