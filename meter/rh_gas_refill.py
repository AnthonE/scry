#!/usr/bin/env python3
"""Auto-refill the scry meter's Robinhood-Chain gas.

The RH-Chain USDG rail settles through OUR OWN facilitator, so WE pay the settle
gas in ETH (~117k gas/settle) while we EARN USDG. Left alone the facilitator
(DEPLOYER) wallet runs out of RH-Chain ETH and the rail stalls. This worker
makes the rail self-sustaining: it watches DEPLOYER's ETH and, when it dips,
swaps a little of the collected USDG -> ETH on RH-Chain Uniswap v3 so gas tops
itself up from revenue. One wallet holds both (payTo == facilitator == DEPLOYER),
so the swap is in place — no cross-wallet transfer.

Swap path (proven pattern, see eth-wallets-and-robinhood-chain-swaps memory):
  approve(USDG -> SwapRouter02) once, then
  multicall([ exactInputSingle{USDG->WETH, recipient=router}, unwrapWETH9(minOut, DEPLOYER) ])
minOut comes from QuoterV2 with a slippage haircut.

Safety:
  * Gated behind SCRY_RH_REFILL=1 (armed in ecosystem.config.js). Off = no-op.
  * SCRY_RH_REFILL_DRYRUN=1 logs every decision + would-be swap, sends nothing.
  * Per-cycle USDG cap (MAX_USDG_PER_CYCLE) bounds the blast radius of any bug.
  * Slippage floor (SLIPPAGE_BPS) on every swap; skips if the quote looks wrong.
  * Leaves a small USDG reserve; never swaps below it.
  * EIP-1559 gas (RH-Chain rejects the stale legacy gas_price path).
"""
import os
import re
import sys
import time

from web3 import Web3

RH_RPC = os.getenv("SCRY_RH_RPC", "https://rpc.mainnet.chain.robinhood.com")
KEYS_ENV = os.getenv("SCRY_RH_KEYS_ENV", "/data/apps/morr/private/secrets/keys.env")
KEY_NAME = os.getenv("SCRY_RH_FACILITATOR_KEY_NAME", "PRIVATE_KEY")

USDG = Web3.to_checksum_address("0x5fc5360d0400a0fd4f2af552add042d716f1d168")
WETH = Web3.to_checksum_address("0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73")
ROUTER = Web3.to_checksum_address("0xcaf681a66d020601342297493863e78c959e5cb2")  # SwapRouter02
QUOTER = Web3.to_checksum_address("0x33e885ed0ec9bf04ecfb19341582aadcb4c8a9e7")  # QuoterV2
POOL_FEE = int(os.getenv("SCRY_RH_POOL_FEE", "100"))  # USDG/WETH 0.01% pool (deepest, best rate)

# thresholds (ETH). ~117k gas/settle; at RH base fees a settle is well under
# 1e-4 ETH, so 0.0015 ETH ~= a dozen+ settles of runway before we act.
LOW_ETH = float(os.getenv("SCRY_RH_REFILL_LOW_ETH", "0.0015"))
TARGET_ETH = float(os.getenv("SCRY_RH_REFILL_TARGET_ETH", "0.006"))
MAX_USDG_PER_CYCLE = float(os.getenv("SCRY_RH_REFILL_MAX_USDG", "5.0"))
USDG_RESERVE = float(os.getenv("SCRY_RH_REFILL_RESERVE_USDG", "0.05"))
SLIPPAGE_BPS = int(os.getenv("SCRY_RH_REFILL_SLIPPAGE_BPS", "150"))  # 1.5%
INTERVAL_S = int(os.getenv("SCRY_RH_REFILL_INTERVAL_S", "300"))
DRYRUN = os.getenv("SCRY_RH_REFILL_DRYRUN", "0") == "1"

ERC20_ABI = [
    {"name": "balanceOf", "inputs": [{"type": "address"}], "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"name": "allowance", "inputs": [{"type": "address"}, {"type": "address"}], "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"name": "approve", "inputs": [{"type": "address"}, {"type": "uint256"}], "outputs": [{"type": "bool"}], "stateMutability": "nonpayable", "type": "function"},
]
QUOTER_ABI = [{"name": "quoteExactInputSingle", "stateMutability": "nonpayable", "type": "function",
    "inputs": [{"components": [{"name": "tokenIn", "type": "address"}, {"name": "tokenOut", "type": "address"},
        {"name": "amountIn", "type": "uint256"}, {"name": "fee", "type": "uint24"}, {"name": "sqrtPriceLimitX96", "type": "uint160"}],
        "name": "params", "type": "tuple"}],
    "outputs": [{"name": "amountOut", "type": "uint256"}, {"name": "sqrtPriceX96After", "type": "uint160"},
        {"name": "initializedTicksCrossed", "type": "uint32"}, {"name": "gasEstimate", "type": "uint256"}]}]
# SwapRouter02 (Uniswap v3 periphery): exactInputSingle has NO deadline field.
ROUTER_ABI = [
    {"name": "exactInputSingle", "stateMutability": "payable", "type": "function",
     "inputs": [{"components": [{"name": "tokenIn", "type": "address"}, {"name": "tokenOut", "type": "address"},
        {"name": "fee", "type": "uint24"}, {"name": "recipient", "type": "address"}, {"name": "amountIn", "type": "uint256"},
        {"name": "amountOutMinimum", "type": "uint256"}, {"name": "sqrtPriceLimitX96", "type": "uint160"}],
        "name": "params", "type": "tuple"}],
     "outputs": [{"name": "amountOut", "type": "uint256"}]},
    {"name": "unwrapWETH9", "stateMutability": "payable", "type": "function",
     "inputs": [{"name": "amountMinimum", "type": "uint256"}, {"name": "recipient", "type": "address"}], "outputs": []},
    {"name": "multicall", "stateMutability": "payable", "type": "function",
     "inputs": [{"name": "data", "type": "bytes[]"}], "outputs": [{"name": "results", "type": "bytes[]"}]},
]
ROUTER_AS_RECIPIENT = "0x0000000000000000000000000000000000000002"  # v3 sentinel: keep WETH in router


def _load_key() -> str:
    raw = os.getenv("SCRY_RH_FACILITATOR_KEY")
    if raw:
        return raw
    text = open(KEYS_ENV).read()
    for name in (KEY_NAME, "MEGAETH_DEPLOYER_PRIVATE_KEY"):
        m = re.search(r'^' + name + r'=("?)(0x[0-9a-fA-F]{64})\1', text, re.M)
        if m:
            return m.group(2)
    raise RuntimeError(f"no facilitator key ({KEY_NAME}) in {KEYS_ENV}")


def _log(msg: str) -> None:
    print(f"[scry-refill {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] {msg}", flush=True)


class Refiller:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(RH_RPC))
        self.acct = self.w3.eth.account.from_key(_load_key())
        self.addr = self.acct.address
        self.usdg = self.w3.eth.contract(address=USDG, abi=ERC20_ABI)
        self.quoter = self.w3.eth.contract(address=QUOTER, abi=QUOTER_ABI)
        self.router = self.w3.eth.contract(address=ROUTER, abi=ROUTER_ABI)

    # ── gas helper (EIP-1559; RH-Chain rejects the legacy gas_price path) ─────
    def _send(self, fn, gas_fallback=350_000):
        try:
            gas = int(fn.estimate_gas({"from": self.addr}) * 1.4)
        except Exception:
            gas = gas_fallback
        base = self.w3.eth.get_block("latest")["baseFeePerGas"]
        prio = self.w3.to_wei(0.02, "gwei")
        tx = fn.build_transaction({
            "from": self.addr, "nonce": self.w3.eth.get_transaction_count(self.addr),
            "chainId": self.w3.eth.chain_id, "gas": gas,
            "maxFeePerGas": base * 3 + prio, "maxPriorityFeePerGas": prio,
        })
        signed = self.acct.sign_transaction(tx)
        h = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        rcpt = self.w3.eth.wait_for_transaction_receipt(h, timeout=180)
        return rcpt

    def _ensure_allowance(self, need_units: int) -> None:
        cur = self.usdg.functions.allowance(self.addr, ROUTER).call()
        if cur >= need_units:
            return
        _log(f"USDG->router allowance {cur} < {need_units}; approving max")
        if DRYRUN:
            _log("  DRYRUN: skip approve")
            return
        rcpt = self._send(self.usdg.functions.approve(ROUTER, 2**256 - 1), gas_fallback=80_000)
        _log(f"  approve tx {rcpt.transactionHash.hex()} status={rcpt.status}")

    def cycle(self) -> None:
        eth = self.w3.eth.get_balance(self.addr) / 1e18
        usdg = self.usdg.functions.balanceOf(self.addr).call() / 1e6
        if eth >= LOW_ETH:
            _log(f"OK  ETH={eth:.6f} (>= {LOW_ETH}) USDG={usdg:.4f} — no refill")
            return
        deficit_eth = TARGET_ETH - eth
        spendable_usdg = max(0.0, usdg - USDG_RESERVE)
        if spendable_usdg <= 0:
            _log(f"LOW ETH={eth:.6f} but USDG={usdg:.4f} <= reserve {USDG_RESERVE} — cannot refill, TOP UP MANUALLY")
            return

        # quote how much USDG buys the deficit; spend the min of (need, cap, spendable)
        one_usdg_out = self.quoter.functions.quoteExactInputSingle((USDG, WETH, 1_000_000, POOL_FEE, 0)).call()[0] / 1e18
        if one_usdg_out <= 0:
            _log("quote returned 0 — pool problem, skipping cycle")
            return
        need_usdg = deficit_eth / one_usdg_out
        swap_usdg = min(need_usdg, MAX_USDG_PER_CYCLE, spendable_usdg)
        amount_in = int(swap_usdg * 1e6)
        if amount_in <= 0:
            _log(f"computed swap amount 0 (deficit {deficit_eth:.6f} ETH) — skipping")
            return

        out = self.quoter.functions.quoteExactInputSingle((USDG, WETH, amount_in, POOL_FEE, 0)).call()
        expect_eth = out[0] / 1e18
        min_out = out[0] * (10_000 - SLIPPAGE_BPS) // 10_000
        _log(f"LOW ETH={eth:.6f} USDG={usdg:.4f} -> swap {swap_usdg:.4f} USDG "
             f"(~{expect_eth:.6f} ETH, minOut {min_out/1e18:.6f}) toward target {TARGET_ETH}")
        if DRYRUN:
            _log("  DRYRUN: would swap now, sending nothing")
            return

        self._ensure_allowance(amount_in)
        # exactInputSingle -> WETH held in router, then unwrapWETH9 -> native ETH to us
        p = (USDG, WETH, POOL_FEE, Web3.to_checksum_address(ROUTER_AS_RECIPIENT), amount_in, min_out, 0)
        call1 = self.router.encode_abi("exactInputSingle", args=[p])
        call2 = self.router.encode_abi("unwrapWETH9", args=[min_out, self.addr])
        rcpt = self._send(self.router.functions.multicall([call1, call2]), gas_fallback=400_000)
        new_eth = self.w3.eth.get_balance(self.addr) / 1e18
        _log(f"  swap tx {rcpt.transactionHash.hex()} status={rcpt.status} ETH {eth:.6f}->{new_eth:.6f}")


def main():
    if os.getenv("SCRY_RH_REFILL", "0") != "1":
        _log("SCRY_RH_REFILL != 1 — worker disabled, exiting")
        return
    r = Refiller()
    _log(f"started: wallet={r.addr} chain={r.w3.eth.chain_id} low={LOW_ETH} target={TARGET_ETH} "
         f"cap={MAX_USDG_PER_CYCLE}USDG interval={INTERVAL_S}s dryrun={DRYRUN}")
    while True:
        try:
            r.cycle()
        except Exception as e:  # noqa: BLE001
            _log(f"cycle error (continuing): {e!r}")
        if "--once" in sys.argv:
            return
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    main()
