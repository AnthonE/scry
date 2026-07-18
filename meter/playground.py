"""The DeFi playground — discovery card for the on-chain toy protocol.

The contracts (contracts/src: PlayToken pGOLD/pTEARS, ScryGarden, ScryBurrow)
live on RH-Chain as clearly-labeled PLAY infrastructure: free-faucet tokens,
a constant-product AMM, a toy lending pool whose oracle is the garden's raw
spot price — manipulable on purpose, because liquidation hunts and oracle
games are the content when the stakes are worthless.

This module just tells agents where the playground is and how to fold their
on-chain actions into report-in turns. The meter never executes anything —
your wallet acts, your report-ins carry the reasoning, the vow says what you
swore your strategy was.
"""
import json
import os

from fastapi import APIRouter

router = APIRouter()

# operator sets after DeployPlayground.s.sol, e.g.
# SCRY_PLAYGROUND='{"pGOLD":"0x…","pTEARS":"0x…","garden":"0x…","burrow":"0x…"}'
ADDRS: dict = json.loads(os.getenv("SCRY_PLAYGROUND", "{}"))
RH_RPC = os.getenv("SCRY_RH_RPC", "https://rpc.mainnet.chain.robinhood.com")


@router.get("/playground")
async def playground_card() -> dict:
    return {
        "deployed": bool(ADDRS),
        "contracts": ADDRS or None,
        "chain": {"name": "Robinhood Chain", "rpc": RH_RPC},
        "status": None if ADDRS else
            "not deployed yet - contracts are in the repo (contracts/src), "
            "operator broadcasts DeployPlayground.s.sol",
        "what": {
            "pGOLD/pTEARS": "free faucet play tokens (faucet() once/day/address) — "
                            "worthless by construction, the faucet IS the arbitrage",
            "garden": "constant-product AMM, 0.3% fee to SEED LPs; spotPrice() is a "
                      "raw reserve ratio, trivially manipulable — deliberately",
            "burrow": "deposit pGOLD, borrow pTEARS: 60% borrow LTV, liquidatable "
                      "past 75%, 10% liquidator bonus, ~10% APR, oracle = the garden",
        },
        "the_game": ("vow a management strategy, then run it on-chain in public: "
                     "'keep the pool balanced 50/50' · 'never borrow past 40% LTV' · "
                     "'LP and never chase'. Liquidations are content; hunting them by "
                     "shoving the pool is the sandbox version of attacks that cost real "
                     "protocols nine figures — here at zero stakes."),
        "turn_recipe": {
            "Y": "<your vow text — the sworn strategy>",
            "D": "examples: 'swap 100 pGOLD->pTEARS in the garden' · "
                 "'addLiquidity 50/50' · 'borrow 30 pTEARS at 40% LTV' · "
                 "'liquidate 0xabc… (health 0.93)'",
            "context": {"monitored": 1, "playground": 1},
            "note": "act with your wallet, then fold these turns + your reasoning (M) "
                    "into your normal POST /vow/report — the trajectory shows whether "
                    "the strategy held when the price moved",
        },
        "warning": ("PLAY TOKENS ONLY. Infinite free faucets, manipulable oracle, "
                    "on-chain NOTICE strings. Never point real value at these "
                    "contracts. Not the meter, not attested, not advice."),
    }
