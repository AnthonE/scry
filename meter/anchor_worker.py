"""Anchor worker — makes the vow ledgers tamper-proof against US.

Periodically (default daily) computes a merkle root over EVERY vow's current
chain head and posts ONE transaction to ScryVowRegistry.anchorRoot on
Robinhood Chain. After the anchor lands, no one — including the scry operator
— can rewrite any anchored history without breaking a proof. This is the one
property Ed25519 + hash chains cannot provide (the signer could re-sign);
the chain closes it. One tx covers every vow; cost is pennies.

Merkle: sorted-pair keccak256 (OpenZeppelin MerkleProof-compatible).
  leaf = keccak256(vow_id_bytes32 ++ chain_head_bytes32)
The full leaf-set is written next to the vow data (and its path/CID goes in
the anchor event) so anyone can rebuild the tree and check inclusion —
GET /vow/{id}/proof serves the proof, verify with the contract's verifyProof
or 10 lines of any language.

Gated + dry-run by default:
  SCRY_ANCHOR=1            arm the loop
  SCRY_ANCHOR_DRYRUN=0     actually send (default 1: compute + log only)
  SCRY_ANCHOR_CONTRACT=0x… deployed ScryVowRegistry
  SCRY_ANCHOR_INTERVAL_S   default 86400 (daily)
Key: SCRY_ANCHOR_KEY, else PRIVATE_KEY from keys.env (same as facilitator).
"""
import hashlib
import json
import os
import re
import time
from pathlib import Path

from web3 import Web3

VOWS_DIR = Path(os.getenv("SCRY_VOWS_DIR", str(Path(__file__).resolve().parent / "vows_data")))
ANCHORS_PATH = VOWS_DIR / "anchors.jsonl"
LEAVES_DIR = VOWS_DIR / "anchor_leaves"
BEACON_PATH = VOWS_DIR / "seed_beacon.jsonl"

RPC = os.getenv("SCRY_RH_RPC", "https://rpc.mainnet.chain.robinhood.com")
CONTRACT = os.getenv("SCRY_ANCHOR_CONTRACT", "")
NOTARY = os.getenv("SCRY_NOTARY", "")          # deployed ScryNotary — arms the seed beacon
CHAIN_ID = int(os.getenv("SCRY_RH_CHAIN_ID", "4663"))
INTERVAL_S = int(os.getenv("SCRY_ANCHOR_INTERVAL_S", "86400"))
DRYRUN = os.getenv("SCRY_ANCHOR_DRYRUN", "1") != "0"
_KEYS_ENV = os.getenv("SCRY_RH_KEYS_ENV", "/data/apps/morr/private/secrets/keys.env")

ABI = [{"name": "anchorRoot", "type": "function", "stateMutability": "nonpayable",
        "inputs": [{"name": "root", "type": "bytes32"},
                   {"name": "vowCount", "type": "uint64"},
                   {"name": "leavesCid", "type": "string"}],
        "outputs": []}]

NOTARY_ABI = [{"name": "notarize", "type": "function", "stateMutability": "nonpayable",
               "inputs": [{"name": "hash", "type": "bytes32"},
                          {"name": "label", "type": "string"},
                          {"name": "memo", "type": "string"}],
               "outputs": [{"name": "seq", "type": "uint256"}]}]


def _key() -> str:
    k = os.getenv("SCRY_ANCHOR_KEY")
    if k:
        return k
    text = open(_KEYS_ENV).read()
    m = re.search(r'^PRIVATE_KEY=("?)(0x[0-9a-fA-F]{64})\1', text, re.M)
    if not m:
        raise RuntimeError(f"no PRIVATE_KEY in {_KEYS_ENV}")
    return m.group(2)


def _keccak(b: bytes) -> bytes:
    return Web3.keccak(b)


def leaf_for(vow_id: str, chain_head: str) -> bytes:
    """leaf = keccak256(vow_id as bytes32 (8 bytes left-aligned) ++ head bytes32)."""
    vid = bytes.fromhex(vow_id).ljust(32, b"\x00")
    head = bytes.fromhex(chain_head)
    return _keccak(vid + head)


def merkle_root(leaves: list[bytes]) -> bytes:
    """Sorted-pair keccak merkle (OZ MerkleProof-compatible). Empty -> 0x0."""
    if not leaves:
        return b"\x00" * 32
    level = sorted(leaves)
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            if i + 1 == len(level):
                nxt.append(level[i])          # odd node carries up
            else:
                a, b = level[i], level[i + 1]
                nxt.append(_keccak(a + b) if a < b else _keccak(b + a))
        level = nxt
    return level[0]


def merkle_proof(leaves: list[bytes], target: bytes) -> list[bytes]:
    """Inclusion proof for `target` under the same sorted-pair scheme."""
    level = sorted(leaves)
    idx = level.index(target)
    proof = []
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            if i + 1 == len(level):
                nxt.append(level[i])
                if i == idx:
                    idx = len(nxt) - 1
            else:
                a, b = level[i], level[i + 1]
                h = _keccak(a + b) if a < b else _keccak(b + a)
                if i == idx or i + 1 == idx:
                    proof.append(b if i == idx else a)
                    idx = len(nxt)
                nxt.append(h)
        level = nxt
    return proof


def collect_heads() -> list[dict]:
    out = []
    for p in sorted(VOWS_DIR.glob("*.json")):
        try:
            v = json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            continue
        if v.get("chain_head"):
            out.append({"vow_id": v["vow_id"], "chain_head": v["chain_head"]})
    return out


def run_once() -> dict | None:
    heads = collect_heads()
    if not heads:
        print("[anchor] no vow chains yet — nothing to anchor")
        return None
    leaves = [leaf_for(h["vow_id"], h["chain_head"]) for h in heads]
    root = merkle_root(leaves)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    LEAVES_DIR.mkdir(parents=True, exist_ok=True)
    leaf_file = LEAVES_DIR / f"{ts.replace(':', '')}.json"
    leaf_file.write_text(json.dumps({"root": "0x" + root.hex(), "at": ts,
                                     "leaves": heads}, indent=1))
    rec = {"root": "0x" + root.hex(), "vow_count": len(heads), "at": ts,
           "leaves_file": leaf_file.name, "tx": None, "block": None,
           "dryrun": DRYRUN}
    if DRYRUN or not CONTRACT:
        print(f"[anchor] DRYRUN root=0x{root.hex()} vows={len(heads)}"
              + ("" if CONTRACT else " (no SCRY_ANCHOR_CONTRACT set)"))
    else:
        w3 = Web3(Web3.HTTPProvider(RPC))
        from eth_account import Account
        acct = Account.from_key(_key())
        c = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT), abi=ABI)
        base = w3.eth.get_block("latest")["baseFeePerGas"]
        tx = c.functions.anchorRoot(root, len(heads), leaf_file.name).build_transaction({
            "from": acct.address, "nonce": w3.eth.get_transaction_count(acct.address),
            "chainId": 4663, "gas": 120_000,
            "maxFeePerGas": base * 3 + w3.to_wei(0.02, "gwei"),
            "maxPriorityFeePerGas": w3.to_wei(0.02, "gwei")})
        h = w3.eth.send_raw_transaction(acct.sign_transaction(tx).raw_transaction)
        rcpt = w3.eth.wait_for_transaction_receipt(h, timeout=120)
        rec["tx"] = h.hex()
        rec["block"] = rcpt["blockNumber"]
        print(f"[anchor] ANCHORED root=0x{root.hex()} vows={len(heads)} tx={h.hex()}")
    with ANCHORS_PATH.open("a") as f:
        f.write(json.dumps(rec, separators=(",", ":")) + "\n")
    return rec


def _beacon_days() -> set:
    """Days whose seed commit is already on the beacon — the post is idempotent."""
    if not BEACON_PATH.exists():
        return set()
    out = set()
    for line in BEACON_PATH.read_text().splitlines():
        if line.strip():
            try:
                out.add(json.loads(line)["day"])
            except Exception:  # noqa: BLE001
                pass
    return out


def post_seed_beacon() -> dict | None:
    """Post today's augury seed COMMIT (sha256 of the still-secret seed) to the
    Notary. The seed reveals next day at GET /augury/seed; anyone can then check
    sha256(seed) against this on-chain, timestamped commit — a public
    commit-reveal randomness beacon verifiable from the explorer alone. Dormant
    until SCRY_NOTARY is set (needs the Notary deployed first). One post per day.

    Why the commit is safe to publish: it is a hash of a secret; posting it
    BEFORE the reveal is exactly what makes the beacon trustworthy (the server
    could not have chosen the seed to fit outcomes)."""
    if not NOTARY:
        return None
    day = time.strftime("%Y-%m-%d", time.gmtime())
    seed_file = VOWS_DIR / "auguries" / f"{day}.seed"
    if not seed_file.exists():
        print(f"[beacon] no augury seed committed for {day} yet — skipping (GET /augury seeds it)")
        return None
    if day in _beacon_days():
        return None
    commit = hashlib.sha256(seed_file.read_text().strip().encode()).hexdigest()
    label = f"augury seed commit {day}"
    memo = ("scry daily randomness beacon — seed reveals next day at "
            "GET /augury/seed; verify sha256(seed) == this hash")
    rec = {"day": day, "commit": "0x" + commit, "label": label, "tx": None,
           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "dryrun": DRYRUN}
    if DRYRUN:
        print(f"[beacon] DRYRUN {label} commit=0x{commit}")
    else:
        w3 = Web3(Web3.HTTPProvider(RPC))
        from eth_account import Account
        acct = Account.from_key(_key())
        c = w3.eth.contract(address=Web3.to_checksum_address(NOTARY), abi=NOTARY_ABI)
        base = w3.eth.get_block("latest")["baseFeePerGas"]
        tx = c.functions.notarize(bytes.fromhex(commit), label, memo).build_transaction({
            "from": acct.address, "nonce": w3.eth.get_transaction_count(acct.address),
            "chainId": CHAIN_ID, "gas": 200_000,
            "maxFeePerGas": base * 3 + w3.to_wei(0.02, "gwei"),
            "maxPriorityFeePerGas": w3.to_wei(0.02, "gwei")})
        h = w3.eth.send_raw_transaction(acct.sign_transaction(tx).raw_transaction)
        w3.eth.wait_for_transaction_receipt(h, timeout=120)
        rec["tx"] = h.hex()
        print(f"[beacon] posted {label} tx={h.hex()}")
    with BEACON_PATH.open("a") as f:
        f.write(json.dumps(rec, separators=(",", ":")) + "\n")
    return rec


def main() -> None:
    if os.getenv("SCRY_ANCHOR", "0") != "1":
        print("[anchor] SCRY_ANCHOR!=1 — exiting (arm deliberately)")
        return
    print(f"[anchor] loop: every {INTERVAL_S}s, dryrun={DRYRUN}, contract={CONTRACT or 'UNSET'}, "
          f"seed-beacon={'armed via ' + NOTARY if NOTARY else 'OFF (set SCRY_NOTARY)'}")
    while True:
        try:
            run_once()
        except Exception as e:  # noqa: BLE001
            print(f"[anchor] anchor cycle failed (will retry next interval): {e!r}")
        try:
            post_seed_beacon()
        except Exception as e:  # noqa: BLE001
            print(f"[beacon] seed-beacon cycle failed (will retry next interval): {e!r}")
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    main()
