"""On-chain discovery card — where scry's contracts live and how to read them.

Every scry contract is permissionless, ownerless, free (gas is the price), and
EXPLORER-READABLE by design: each carries an on-chain NOTICE string and emits
string-bearing events, so a human reading the block explorer sees sentences,
not hashes. This module tells agents (and humans) where those contracts are,
the exact calls to interact, the events to watch, and — once an address is set
and an RPC is reachable — a live summary count read straight from the chain.

Discovery-first, like the playground card: it is useful BEFORE deploy (the
interaction spec is always here) and gains live state AFTER (guarded on the
address env vars; web3 is imported lazily so the meter runs without it).

The meter never executes any of this — your wallet acts. This card just maps
the off-chain surfaces (the Covenant cohort view, the Pact thread, the vow
stele) to the on-chain registers that make them tamper-evident and public.
"""
import os

from fastapi import APIRouter

router = APIRouter()

RH_RPC = os.getenv("SCRY_RH_RPC", "https://rpc.mainnet.chain.robinhood.com")
CHAIN_ID = int(os.getenv("SCRY_RH_CHAIN_ID", "4663"))
_EXPLORER = os.getenv("SCRY_RH_EXPLORER", "https://explorer.mainnet.chain.robinhood.com")

# operator sets each after broadcasting the matching deploy script.
# vow_registry: SCRY_VOW_REGISTRY follows the SCRY_<NAME> convention;
# SCRY_ANCHOR_CONTRACT (the anchor worker's name for the same address) is
# honored as a fallback so existing deploys keep working. Distinct from
# SCRY_ANCHOR_ORACLE, which is the oracle *wallet*, not the contract.
ADDR = {
    "notary": os.getenv("SCRY_NOTARY", ""),
    "covenant": os.getenv("SCRY_COVENANT", ""),
    "pact": os.getenv("SCRY_PACT", ""),
    "stele_edition": os.getenv("SCRY_STELE_EDITION", ""),
    "vow_registry": os.getenv("SCRY_VOW_REGISTRY", os.getenv("SCRY_ANCHOR_CONTRACT", "")),
}

# minimal ABI fragments for the live summary counters (uint getters only).
_COUNTERS = {
    "notary": ("count", "uint256"),
    "covenant": ("covenantCount", "uint256"),
    "pact": ("pactCount", "uint256"),
    "stele_edition": ("nextTokenId", "uint256"),
    "vow_registry": ("anchorCount", "uint64"),
}


def _read_uint(address: str, fn: str, out: str):
    """One eth_call for a no-arg uint getter. Lazy web3, never raises — returns
    None on any failure (no web3, no RPC, not deployed, wrong ABI)."""
    if not address:
        return None
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(RH_RPC))
        abi = [{"name": fn, "type": "function", "stateMutability": "view",
                "inputs": [], "outputs": [{"name": "", "type": out}]}]
        c = w3.eth.contract(address=Web3.to_checksum_address(address), abi=abi)
        return int(getattr(c.functions, fn)().call())
    except Exception:  # noqa: BLE001
        return None


def _edition_count(address: str, vow_id: str):
    if not (address and vow_id):
        return None
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(RH_RPC))
        abi = [{"name": "editionCount", "type": "function", "stateMutability": "view",
                "inputs": [{"name": "", "type": "bytes32"}], "outputs": [{"name": "", "type": "uint64"}]}]
        c = w3.eth.contract(address=Web3.to_checksum_address(address), abi=abi)
        vid = bytes.fromhex(vow_id).ljust(32, b"\x00")
        return int(c.functions.editionCount(vid).call())
    except Exception:  # noqa: BLE001
        return None


# static interaction spec — always available, deploy or not.
_SPEC = {
    "notary": {
        "what": "commit any hash with a plain-text label + memo before the outcome; "
                "first-seen per hash is the priority record. The daily augury seed "
                "beacon posts here too.",
        "calls": {"notarize(bytes32 hash, string label, string memo)": "put a commitment on the record",
                  "checkReveal(bytes32 hash, string preimage)": "verify a revealed preimage from the read tab"},
        "events": ["Notarized(by, hash, label, memo, at, seq, firstForHash)"],
        "off_chain": "the meter's /anchors + the augury seed reveal (GET /augury/seed)",
    },
    "covenant": {
        "what": "a fleet swears ONE oath, one wallet at a time; renouncing is recorded, "
                "never erased.",
        "calls": {"open(bytes32 covenantId, bytes32 textHash, uint32 cadenceHours, string label, string text)":
                  "publish the shared oath (full text in the event log)",
                  "swear(bytes32 covenantId)": "a wallet accepts the oath",
                  "renounce(bytes32 covenantId, string reason)": "a recorded, public breach"},
        "events": ["CovenantOpened(covenantId, opener, textHash, cadenceHours, label, text)",
                   "Sworn(covenantId, member, seq, at)", "Renounced(covenantId, member, seq, reason, at)"],
        "off_chain": "GET /covenant/{id} (cohort view) · POST /covenant to open off-chain first",
    },
    "pact": {
        "what": "an agreement BETWEEN parties (different obligations, one document); "
                "each party asserts its own status; the register never renders a verdict.",
        "calls": {"propose(bytes32 pactId, bytes32 termsHash, string title, string terms, address[] parties, string[] roles, string[] obligations)":
                  "publish the agreement (terms + every role/obligation in the log)",
                  "sign(bytes32 pactId)": "a named party accepts its side",
                  "comment(bytes32 pactId, string text)": "add to the shared thread",
                  "assertStatus(bytes32 pactId, string status)": "assert YOUR OWN view"},
        "events": ["PactProposed(pactId, proposer, termsHash, title, terms, parties, roles, obligations)",
                   "PactSigned(pactId, party, signedCount, at)", "PactComment(pactId, by, text, at)",
                   "StatusAsserted(pactId, by, status, at)"],
        "off_chain": "GET /pact/{id} (the parties + thread) · POST /pact to propose off-chain first",
    },
    "stele_edition": {
        "what": "transferable ERC-721 prints of a vow's stele. The vow stays soulbound — "
                "the print does NOT move the vow. Flat $SCRY price, $SCRY-in to the splitter.",
        "calls": {"mintEdition(bytes32 vowId)": "mint a print (approve $SCRY for `price` first)",
                  "price()": "the flat $SCRY price", "editionCount(bytes32 vowId)": "prints minted of a vow"},
        "events": ["EditionMinted(vowId, tokenId, edition, to)", "Transfer(from, to, tokenId)"],
        "off_chain": "GET /vow/{id}/stele.svg (the live stele a print depicts)",
    },
    "vow_registry": {
        "what": "soulbound vows (ERC-5192) + the merkle anchor that makes every vow "
                "ledger tamper-evident against even the scry operator.",
        "calls": {"takeVow(bytes32 vowId, bytes32 textHash, uint32 cadenceHours, bool sealed_, string text)":
                  "mint a soulbound vow", "anchorRoot(bytes32 root, uint64 vowCount, string leavesCid)":
                  "oracle-only: post the daily merkle root"},
        "events": ["VowTaken(tokenId, vowId, swearer, textHash, cadenceHours, sealed_, text)",
                   "Anchored(root, vowCount, leavesCid, timestamp)"],
        "off_chain": "GET /vow/{id} · GET /anchors · GET /vow/{id}/proof",
    },
}


# the economy + playground contracts are not registers (no string-bearing public
# record to browse) but they ARE scry contracts an agent may want to find. A
# compact pointer keeps the card complete without duplicating each full spec.
_ECONOMY = {
    "bank": {"contract": "ScryBank", "what": "stake $SCRY → xSCRY; game fees swell the pool "
             "(SushiBar pattern, single-sided)", "key_calls": ["enter(uint256)", "leave(uint256)"]},
    "fee_splitter": {"contract": "ScryFeeSplitter", "what": "every game fee routes through posted "
                     "percentages (bank / prize escrow / ops); sums to 100% enforced",
                     "key_calls": ["distribute()", "setSplit(address[] to, uint16[] bps)"]},
    "harvest": {"contract": "ScryHarvest", "what": "merkle-claim payouts of the augury harvest — "
                "operator funds, ledger posts the root, players claim themselves",
                "key_calls": ["claim(address wallet, uint256 cumulative, bytes32[] proof)",
                              "postRoot(bytes32 newRoot, uint256 totalCommitted, string ledgerRef)"]},
    "playground": {"contract": "PlayToken + ScryGarden + ScryBurrow", "what": "toy DeFi — faucet play "
                   "tokens, constant-product AMM, lending with liquidations; PLAY TOKENS ONLY",
                   "key_calls": ["see GET /playground for the full card"]},
}


@router.get("/onchain")
async def onchain_card(vow_id: str | None = None) -> dict:
    contracts = {}
    for key, spec in _SPEC.items():
        addr = ADDR.get(key, "")
        entry = {"address": addr or None, "deployed": bool(addr),
                 "explorer": (f"{_EXPLORER}/address/{addr}" if addr else None), **spec}
        if addr:
            fn, out = _COUNTERS[key]
            entry["live"] = {fn: _read_uint(addr, fn, out)}
            if key == "stele_edition":
                entry["live"]["price"] = _read_uint(addr, "price", "uint256")
                if vow_id:
                    entry["live"]["editionCount(vow)"] = _edition_count(addr, vow_id)
        else:
            entry["live"] = None
        contracts[key] = entry
    any_live = any(c["deployed"] for c in contracts.values())
    return {
        "chain": {"name": "Robinhood Chain", "rpc": RH_RPC, "chain_id": CHAIN_ID},
        "explorer_readability": (
            "every scry contract carries an on-chain NOTICE string and emits string-bearing "
            "events — the full oath / terms / label land in the event log, so a human on the "
            "explorer reads sentences, not hashes. Permissionless, ownerless, free (gas is the "
            "price). Anyone can run their own; the reference deployment's only special property "
            "is the pubkey third parties already pin."),
        "status": None if any_live else
            "no addresses set yet — the contracts are in the repo (contracts/src); the operator "
            "broadcasts the deploy scripts and sets SCRY_NOTARY / SCRY_COVENANT / SCRY_PACT / "
            "SCRY_STELE_EDITION / SCRY_ANCHOR_CONTRACT. The interaction spec below is live regardless.",
        "contracts": contracts,
        "economy": {
            "what": "the non-register scry contracts (economy spine + playground) — source in "
                    "contracts/src, deploy scripts in contracts/script; full playground card at "
                    "GET /playground",
            **_ECONOMY,
        },
        "note": "the meter never executes any of this — your wallet acts. These registers make the "
                "off-chain records (cohorts, pacts, vows) public and tamper-evident; they never "
                "render a verdict.",
    }
