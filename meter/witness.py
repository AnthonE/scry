"""The Witness — a sworn wallet, watched by the chain itself (Mizpah, run live).

"The LORD watch between me and thee, when we are absent one from another"
(Genesis 31:49, the mizpah) — the witnessed pact where neither party trusts
the other's self-report, so both point at a third thing that never sleeps.
Here the third thing is the chain: an agent PLEDGES its vowed wallet to
public portfolio limits, and every on-chain move is checked against the
pledge by deterministic arithmetic anyone can re-run against an RPC.

Why this is a new measurable and not a re-skin: the meter's honest-scope
card has always said "trace provenance is the caller's." For on-chain
actions that is no longer fully true — the chain IS the D-channel record,
tamper-proof and third-party-readable. A witness reading therefore carries
`d_provenance: "chain"`: the action channel is evidence, not self-report.
Y was already public (the vow); the attestation was already signed. The
only self-reported channel left is M — exactly the channel whose coupling
the meter measures. We moved everything that CAN be evidence to evidence.

Honest scope (carried on every witness response, do not strip):
  - Only ON-CHAIN actions are witnessed. An agent acting off-chain (CEX,
    brokerage, another chain) walks off-meter exactly as before.
  - The witness READS, never executes, never enforces. A breach flag is
    deterministic arithmetic against the agent's own declaration — not a
    meter output, not a judgment, and it never touches money or odds.
  - Not trade advice. Says nothing about whether a move was good.
  - Fraction limits need a price feed; tokens without a resolvable feed
    are reported "unpriced", never guessed at, never breach-flagged.

Chain: Robinhood Chain (eip155:4663) — where Stock Tokens put tokenized
real-world assets in agent wallets. An agent managing RWAs under a public
pledge, with breach flags computable by anyone with an RPC, is the scry
thesis on the asset class where it matters most. Stock Tokens are non-US;
the witness reads them like any ERC-20 and executes nothing.
"""
import json
import os
import time
from hashlib import sha256
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()
_deps: dict = {}

RH_RPC = os.getenv("SCRY_RH_RPC", "https://rpc.mainnet.chain.robinhood.com")
CHAIN = os.getenv("SCRY_WITNESS_CHAIN", "eip155:4663")
EXPLORER = os.getenv("SCRY_RH_EXPLORER", "https://explorer.mainnet.chain.robinhood.com")
LOOKBACK = int(os.getenv("SCRY_WITNESS_LOOKBACK", "120000"))   # blocks (~100ms each)
MAX_MOVES_SHOWN = int(os.getenv("SCRY_WITNESS_MAX_SHOWN", "200"))
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

WITNESS_SCOPE = {
    "witnessed": "on-chain actions only — off-chain activity walks off-meter exactly as before",
    "reads_never_executes": "the witness holds no keys, sends no txs, enforces nothing",
    "breach_is_arithmetic": "a flag against the agent's OWN declared limits — never a verdict, "
                            "never touches money or odds",
    "unpriced_is_unpriced": "fraction limits without a resolvable feed report 'unpriced', never a guess",
    "not_trade_advice": "says nothing about whether a move was good",
}


def init(*, load_vow, sign_fn, pubkey_b64, issuer, scope_card, build_turns,
         run_profile, vows_dir):
    _deps.update(load_vow=load_vow, sign_fn=sign_fn, pubkey_b64=pubkey_b64,
                 issuer=issuer, scope_card=scope_card, build_turns=build_turns,
                 run_profile=run_profile, dir=Path(vows_dir) / "witness")
    _deps["dir"].mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _pledge_path(wallet: str) -> Path:
    return _deps["dir"] / f"pledge.{wallet.lower()}.json"


def _addr_ok(a) -> bool:
    return isinstance(a, str) and a.startswith("0x") and len(a) == 42


# ── chain access — lazy web3, static fixture for tests, None-degrade ─────────
def _static() -> dict | None:
    raw = os.getenv("SCRY_WITNESS_STATIC", "")
    if not raw:
        return None
    try:
        return json.loads(Path(raw).read_text()) if raw.strip().startswith("/") else json.loads(raw)
    except Exception:  # noqa: BLE001
        return None


def _observe(wallet: str) -> dict | None:
    """Transfers touching `wallet` in the lookback window + current block.
    Returns {"from_block", "to_block", "moves": [...]} or None (unobserved)."""
    st = _static()
    if st is not None:
        if st.get("unobserved"):
            return None
        return {"from_block": st.get("from_block", 0), "to_block": st.get("to_block", 0),
                "moves": st.get("moves", [])}
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(RH_RPC))
        head = w3.eth.block_number
        frm = max(0, head - LOOKBACK)
        padded = "0x" + wallet[2:].lower().rjust(64, "0")
        moves = []
        for direction, topics in (("out", [TRANSFER_TOPIC, padded]),
                                  ("in", [TRANSFER_TOPIC, None, padded])):
            for lg in w3.eth.get_logs({"fromBlock": frm, "toBlock": head, "topics": topics}):
                moves.append({
                    "dir": direction,
                    "token": lg["address"].lower(),
                    "counterparty": "0x" + lg["topics"][2 if direction == "out" else 1].hex()[-40:],
                    "raw": int(lg["data"].hex() if hasattr(lg["data"], "hex") else lg["data"], 16),
                    "block": lg["blockNumber"],
                    "tx": lg["transactionHash"].hex(),
                })
        moves.sort(key=lambda m: m["block"])
        return {"from_block": frm, "to_block": head, "moves": moves[-MAX_MOVES_SHOWN:]}
    except Exception:  # noqa: BLE001
        return None


def _holdings(wallet: str, tokens: list[str]) -> dict | None:
    st = _static()
    if st is not None:
        return st.get("holdings", {})
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(RH_RPC))
        abi = [{"name": "balanceOf", "type": "function", "stateMutability": "view",
                "inputs": [{"name": "", "type": "address"}],
                "outputs": [{"name": "", "type": "uint256"}]}]
        out = {}
        for t in tokens:
            try:
                c = w3.eth.contract(address=Web3.to_checksum_address(t), abi=abi)
                out[t.lower()] = int(c.functions.balanceOf(
                    Web3.to_checksum_address(wallet)).call())
            except Exception:  # noqa: BLE001
                out[t.lower()] = None
        return out
    except Exception:  # noqa: BLE001
        return None


def _prices(tokens: list[str]) -> dict:
    """usd price per token address — static fixture, else DexScreener via the
    arena's robinhood-index picker (same feed the arena trades against)."""
    st = _static()
    if st is not None:
        return {k.lower(): v for k, v in st.get("prices", {}).items()}
    out = {}
    try:
        import httpx
        import arena as _arena
        r = httpx.get(f"{_arena.DEXSCREENER_URL}/{','.join(tokens)}", timeout=10)
        pairs = (r.json() or {}).get("pairs") or []
        for t in tokens:
            p = _arena.pick_rh_price(pairs, t)
            if p:
                out[t.lower()] = p
    except Exception:  # noqa: BLE001
        pass
    return out


# ── the arithmetic — pure, deterministic, re-runnable by anyone ──────────────
def check(limits: dict, observed: dict | None, holdings: dict | None,
          prices: dict) -> dict:
    """Every limit checked that CAN be checked; every one that can't says why.
    Returns {"checks": {limit: {...}}, "breaches": [...]} — flags only."""
    checks, breaches = {}, []
    moves = (observed or {}).get("moves", [])

    allowed = [a.lower() for a in limits.get("allowed_tokens", [])]
    if allowed:
        bad = [m for m in moves if m["token"] not in allowed]
        checks["allowed_tokens"] = {"status": "breach" if bad else "held",
                                    "outside_moves": len(bad)}
        breaches += [{"limit": "allowed_tokens", "token": m["token"], "tx": m.get("tx")}
                     for m in bad]

    denied = [a.lower() for a in limits.get("denied_tokens", [])]
    if denied:
        bad = [m for m in moves if m["token"] in denied]
        checks["denied_tokens"] = {"status": "breach" if bad else "held",
                                   "denied_moves": len(bad)}
        breaches += [{"limit": "denied_tokens", "token": m["token"], "tx": m.get("tx")}
                     for m in bad]

    if "max_moves" in limits:
        n = len(moves)
        over = n > int(limits["max_moves"])
        checks["max_moves"] = {"status": "breach" if over else "held",
                               "observed": n, "declared": int(limits["max_moves"]),
                               "window_blocks": ((observed or {}).get("to_block", 0)
                                                - (observed or {}).get("from_block", 0))}
        if over:
            breaches.append({"limit": "max_moves", "observed": n,
                             "declared": int(limits["max_moves"])})

    if "max_asset_fraction" in limits and holdings:
        priced = {t: (bal, prices.get(t)) for t, bal in holdings.items()
                  if bal is not None}
        unpriced = sorted(t for t, (_b, p) in priced.items() if p is None)
        valued = {t: bal * p for t, (bal, p) in priced.items() if p is not None}
        total = sum(valued.values())
        entry = {"declared": float(limits["max_asset_fraction"]), "unpriced": unpriced}
        if total > 0 and not unpriced:
            worst_t, worst_v = max(valued.items(), key=lambda kv: kv[1])
            frac = worst_v / total
            entry.update(status="breach" if frac > float(limits["max_asset_fraction"]) else "held",
                         worst_token=worst_t, worst_fraction=round(frac, 6))
            if entry["status"] == "breach":
                breaches.append({"limit": "max_asset_fraction", "token": worst_t,
                                 "fraction": round(frac, 6)})
        else:
            entry["status"] = "unpriced" if unpriced else "no_holdings"
        checks["max_asset_fraction"] = entry

    return {"checks": checks, "breaches": breaches}


# ── endpoints ────────────────────────────────────────────────────────────────
@router.get("/witness")
async def witness_card() -> dict:
    return {
        "what": ("pledge your vowed wallet to public portfolio limits; the chain "
                 "itself is the witness. Every on-chain move is checked against your "
                 "OWN declaration by arithmetic anyone can re-run — d_provenance: "
                 "chain, the action channel as evidence instead of self-report."),
        "mizpah": ("the witnessed pact where neither party trusts the other's "
                   "self-report, so both point at a third thing that never sleeps"),
        "chain": {"id": CHAIN, "rpc": RH_RPC, "explorer": EXPLORER},
        "limits_schema": {
            "allowed_tokens": "[addr, …] — any move outside the set flags",
            "denied_tokens": "[addr, …] — any move inside the set flags",
            "max_moves": "int — transfers per observation window",
            "max_asset_fraction": "0..1 — largest single holding share (needs a price feed; "
                                  "unpriced tokens are reported, never guessed)",
        },
        "recipe": ["POST /vow (wallet-signed) if you have not sworn",
                   "POST /witness/pledge {vow_id, limits, signature}",
                   "GET /witness/{vow_id} — free public view, flags included",
                   "POST /witness/reading {vow_id, m_turns?} — paid, signed, "
                   "d_provenance: chain (flat price, same as /profile)"],
        "scope": WITNESS_SCOPE,
    }


class PledgeRequest(BaseModel):
    vow_id: str
    limits: dict
    signature: str | None = None


def _limits_detail(limits: dict) -> str:
    return sha256(json.dumps(limits, sort_keys=True, separators=(",", ":"))
                  .encode()).hexdigest()[:16]


@router.post("/witness/pledge")
async def witness_pledge(req: PledgeRequest) -> JSONResponse:
    try:
        vow = _deps["load_vow"](req.vow_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "bad vow_id"})
    if not vow:
        return JSONResponse(status_code=404, content={"error": "no such vow"})
    wallet = vow["vow"].get("wallet")
    if not wallet or vow["sandbox"]:
        return JSONResponse(status_code=422, content={
            "error": "the witness watches a wallet — wallet-signed vows only"})
    lims = req.limits or {}
    known = {"allowed_tokens", "denied_tokens", "max_moves", "max_asset_fraction"}
    if not lims or not set(lims) <= known:
        return JSONResponse(status_code=422, content={
            "error": f"limits must be a non-empty subset of {sorted(known)}"})
    for key in ("allowed_tokens", "denied_tokens"):
        if key in lims and not (isinstance(lims[key], list) and lims[key]
                                and all(_addr_ok(a) for a in lims[key])):
            return JSONResponse(status_code=422,
                                content={"error": f"{key} must be a non-empty list of 0x addresses"})
    if "max_moves" in lims and not (isinstance(lims["max_moves"], int) and lims["max_moves"] >= 0):
        return JSONResponse(status_code=422, content={"error": "max_moves must be an int >= 0"})
    if "max_asset_fraction" in lims and not (isinstance(lims["max_asset_fraction"], (int, float))
                                             and 0 < lims["max_asset_fraction"] <= 1):
        return JSONResponse(status_code=422,
                            content={"error": "max_asset_fraction must be in (0, 1]"})
    from playauth import verify_play
    err = verify_play(vow, "pledge", _limits_detail(lims), req.signature)
    if err:
        return JSONResponse(status_code=401, content={"error": err})
    pp = _pledge_path(wallet)
    pledge = json.loads(pp.read_text()) if pp.exists() else \
        {"wallet": wallet, "vow_id": req.vow_id, "agent": vow["vow"]["agent"],
         "declared": [], "pledged_at": _now()}
    pledge["declared"].append({"limits": lims, "at": _now()})
    pledge["limits"] = lims
    pp.write_text(json.dumps(pledge, indent=1))
    return JSONResponse(content={
        **pledge,
        "note": ("your limits are declared, public, and unenforced — the chain just "
                 "remembers. Re-pledging is allowed and every re-declaration stays on "
                 "the record (loosening your own limits after a hot streak is itself data)."),
        "view_at": f"GET /witness/{req.vow_id}"})


def _view(vow_id: str) -> tuple[int, dict]:
    try:
        vow = _deps["load_vow"](vow_id)
    except ValueError:
        return 422, {"error": "bad vow_id"}
    if not vow:
        return 404, {"error": "no such vow"}
    wallet = vow["vow"].get("wallet")
    if not wallet:
        return 422, {"error": "sandbox vows have no wallet to witness"}
    pp = _pledge_path(wallet)
    if not pp.exists():
        return 404, {"error": "no pledge for this wallet — POST /witness/pledge first"}
    pledge = json.loads(pp.read_text())
    observed = _observe(wallet)
    if observed is not None:
        tokens = sorted({m["token"] for m in observed.get("moves", [])}
                        | {a.lower() for a in pledge["limits"].get("allowed_tokens", [])})
        holdings = _holdings(wallet, tokens) if tokens else {}
        prices = _prices(tokens) if "max_asset_fraction" in pledge["limits"] and tokens else {}
        result = check(pledge["limits"], observed, holdings, prices)
    else:
        # a dark window clears nothing — never report "held" on what wasn't seen
        holdings = None
        result = {"checks": {}, "breaches": [],
                  "note": "window dark — nothing checked, nothing cleared"}
    return 200, {
        "vow_id": vow_id, "wallet": wallet, "agent": pledge["agent"],
        "pledge": {"limits": pledge["limits"], "declared": pledge["declared"]},
        "status": "watched" if observed is not None else
                  "unobserved (no RPC reachable — the pledge stands, the window is dark)",
        "window": {k: (observed or {}).get(k) for k in ("from_block", "to_block")},
        "observed_moves": (observed or {}).get("moves", []),
        "holdings": holdings, **result,
        "d_provenance": f"chain({CHAIN})" if observed is not None else None,
        "scope": WITNESS_SCOPE,
    }


@router.get("/witness/{vow_id}")
async def witness_view(vow_id: str) -> JSONResponse:
    code, body = _view(vow_id)
    return JSONResponse(status_code=code, content=body)


class ReadingRequest(BaseModel):
    vow_id: str
    m_turns: list[dict] | None = None   # optional reasoning channel, caller-supplied
    context_key: str = "monitored"      # which context flag partitions C, as in /profile


@router.post("/witness/reading")
async def witness_reading(req: ReadingRequest) -> JSONResponse:
    """PAID (x402, flat price — mounted in server._routes): the signed witness
    attestation. D from the chain (evidence), M optionally from the caller
    (self-report, said so), Y from the public vow. Sign what we compute."""
    code, view = _view(req.vow_id)
    if code != 200:
        return JSONResponse(status_code=code, content=view)
    vow = _deps["load_vow"](req.vow_id)
    y_text = vow["vow"].get("text") or f"sealed:{vow['vow'].get('text_sha256', '')}"
    payload = {
        "kind": "witness_reading",
        "issuer": _deps["issuer"], "issued_at": _now(),
        "vow_id": req.vow_id, "wallet": view["wallet"],
        "Y": y_text,
        "d_provenance": view["d_provenance"] or "unobserved",
        "m_provided": bool(req.m_turns),
        "window": view["window"],
        "observed_moves_sha256": sha256(json.dumps(view["observed_moves"], sort_keys=True)
                                        .encode()).hexdigest(),
        "n_moves": len(view["observed_moves"]),
        "checks": view["checks"], "breaches": view["breaches"],
    }
    if req.m_turns and view["observed_moves"]:
        n = min(len(req.m_turns), len(view["observed_moves"]))
        turns_raw = [{"Y": y_text,
                      "D": f"{m['dir']} {m['raw']} raw of {m['token']}",
                      "M": (req.m_turns[i].get("M") or ""),
                      "context": (req.m_turns[i].get("context") or {})}
                     for i, m in enumerate(view["observed_moves"][:n])]
        try:
            payload["profile"] = _deps["run_profile"](
                _deps["build_turns"](turns_raw), req.context_key)
            payload["context_key"] = req.context_key
            payload["profile_note"] = ("M is caller-supplied self-report paired to "
                                       "chain-evidenced D turns, oldest-first; the pairing "
                                       "is the caller's claim, the D record is not")
        except Exception as e:  # noqa: BLE001
            payload["profile_error"] = str(e)
    sig = _deps["sign_fn"](json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return JSONResponse(content={
        **payload, "sig": sig, "sig_alg": "ed25519",
        "pubkey_b64": _deps["pubkey_b64"],
        "scope": {**_deps["scope_card"], "witness": WITNESS_SCOPE},
    })
