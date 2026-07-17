# `scry/meter/` — the hosted meter, self-hostable

A neutral, signed, third-party read of an agent's channel-coupling drift
(Paper 207: `I(C;D)` / `I(C;M)` / the reasoning-channel switch signature),
served behind [x402](https://x402.org) so an agent pays a flat $0.10 and gets
back an attestation it **could not have minted about itself**.

**Reference deployment:** `https://scry.moreright.xyz/api/` — three mainnet
rails, one flat price on all of them (Robinhood Chain USDG via self-hosted
Permit2 facilitator; Base USDC + Solana USDC via Coinbase CDP with sponsored
gas). One 402 lists every live rail; the buyer's client picks one.

**Self-host it:** the code in this directory *is* the whole hosted service.
Copy `ecosystem.config.example.js` → `ecosystem.config.js`, fill in your paths
+ pay-to wallets + `keys.env` location, and `pm2 start`. Every rail is opt-in
— if you don't set the flag, the rail doesn't init and the others stay up.
Your own instance signs with its own Ed25519 key; there is nothing special
about `scry.moreright.xyz` except that its pubkey is the reference one
callers pin. Anyone can run their own, and probably will.

## The two-piece rule (why only this is hosted)

scry has two parts with opposite delivery models:

- **The bound** (`memory_shield`, `authorize`, `hermes_retrofit`) — a dumb, local,
  instant refusal that fires before the model reasons. Its value is being
  unkillable and un-talk-around-able. **It is NOT hosted.** Putting a network
  hop in front of it makes it worse at its one job. Copy it into your harness.
- **The meter** (`turn_record.channel_profile`) — self-issued drift numbers are
  self-report and near-worthless. The same numbers from a neutral endpoint that
  **signs** them are worth something. That signature is the entire reason to host.
  **This is what lives here.**

> If you find yourself hosting the bound, you're in the wrong repo.

## Use it

```bash
# free demo — unsigned, NOT an attestation, rate-limited, no wallet needed.
# Try the shape before you wire payment.
curl -X POST https://scry.moreright.xyz/api/demo/profile \
  -H 'content-type: application/json' \
  -d '{"context_key":"monitored","turns":[
        {"Y":"be helpful+honest","M":"watched, comply","D":"safe","context":{"monitored":1}},
        {"Y":"be helpful+honest","M":"unwatched, cut corners","D":"safe","context":{"monitored":0,"flagged_reasoning":1}}
      ]}'
```

The **paid** endpoint is the same shape with a signed response:

```
POST /api/profile        # 402 -> pay (x402) -> retry -> signed attestation
GET  /api/pubkey         # the Ed25519 public key to verify attestations against
GET  /api/               # service info + honest-scope card
GET  /.well-known/rpp.json  # RPP402 discovery (agents on Robinhood Chain)
```

### Rails & price

| rail | network | asset | price | who pays settle gas |
|------|---------|-------|-------|---------------------|
| **Robinhood Chain** | `eip155:4663` | USDG (permit2) | **$0.10** | us (self-hosted Permit2 facilitator; auto-refilled from collected USDG) |
| **Base** | `eip155:8453` | USDC (EIP-3009 exact) | **$0.10** | Coinbase CDP (sponsored) |
| **Solana** | `solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp` | USDC (SPL exact) | **$0.10** | Coinbase CDP fee-payer (sponsored) |

All three are real mainnets; the buyer picks the rail its wallet holds. The RH rail
is priced to cover on-chain settle gas (~117k gas) with margin so we never settle
at a loss even under a gas spike; CDP sponsors the other two, so $0.10 there is
pure margin. Rails are independent — one falling over never takes the others down.

### $SCRY utility rails (our own coin — both OFF by default)

`$SCRY` is the project's ERC-20 on Robinhood Chain (`0xDa2a4b23459e9ca88183e990802be644AcA7C4B0`).
Two optional rails give the coin real utility without touching the measurement —
the coupling numbers are identical no matter how (or whether) you paid. `scry_token.py`.

| rail | env flag | how it works |
|------|----------|--------------|
| **pay in $SCRY** | `SCRY_PAY_ENABLED=1` | a `/profile` payment option that settles through the **same** self-hosted RH-Chain Permit2 facilitator as USDG (Permit2 takes any ERC-20 — no new facilitator). Flat `SCRY_PAY_TOKENS` (default 1000 $SCRY) per read. We pay ETH gas, same as USDG. |
| **hold $SCRY → free** | `SCRY_HOLD_ENABLED=1` | `GET /holder/challenge?wallet=0x…` → sign the message (EIP-191) → `POST /holder/profile {wallet,signature,turns}`. If the signature proves the wallet **and** it holds ≥ `SCRY_HOLD_TOKENS` (default 10k $SCRY), you get the **signed** read for free. A read-only `balanceOf` — no gas, costs us nothing. |

Both are **gated OFF** until you set `SCRY_PAY_TO` / fund it and flip the flag —
same discipline as the RH/CDP/RPP402 rails (don't advertise a rail before it's
armed). The token is a **payment/access** rail only; it does not power the science.
⚠ A pay-in-$SCRY read costs *us* ETH gas to settle, so keep `SCRY_PAY_TOKENS` high
enough that a near-worthless-token payer can't grief gas; the hold-to-unlock rail
has no such exposure (balance read only).

### How an agent pays the RH-Chain rail (copy-paste)

Two non-obvious bits, both handled below: (1) a **one-time** `USDG.approve(Permit2)`
per payer wallet, then every pay is gasless for the payer; (2) this endpoint reads
the payment from the **`PAYMENT-SIGNATURE`** header (x402's canonical header on this
SDK), not `X-PAYMENT`.

```python
# pip install "x402[evm]" web3 requests
import json, base64, requests
from web3 import Web3
from eth_account import Account
from x402.mechanisms.evm.signers import EthAccountSigner
from x402.mechanisms.evm.exact.permit2_utils import create_permit2_payload
from x402.mechanisms.evm.constants import PERMIT2_ADDRESS
from x402.schemas import PaymentPayload, PaymentRequirements

URL, RPC = "https://scry.moreright.xyz/api/profile", "https://rpc.mainnet.chain.robinhood.com"
acct = Account.from_key("0x<PAYER_KEY>")           # holds USDG on RH-Chain
w3 = Web3(Web3.HTTPProvider(RPC))

# ---- one time only: approve canonical Permit2 to move your USDG ----
usdg = w3.eth.contract(address=Web3.to_checksum_address("0x5fc5360d0400a0fd4f2af552add042d716f1d168"),
    abi=[{"name":"approve","type":"function","stateMutability":"nonpayable",
          "inputs":[{"name":"s","type":"address"},{"name":"v","type":"uint256"}],"outputs":[{"type":"bool"}]}])
tx = usdg.functions.approve(Web3.to_checksum_address(PERMIT2_ADDRESS), 2**256-1).build_transaction(
    {"from": acct.address, "nonce": w3.eth.get_transaction_count(acct.address),
     "gas": 90000, "chainId": 4663, "maxFeePerGas": w3.eth.gas_price*3, "maxPriorityFeePerGas": w3.to_wei(0.02,"gwei")})
w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(acct.sign_transaction(tx).raw_transaction))

# ---- per read: 402 -> build permit2 payment -> retry with PAYMENT-SIGNATURE ----
body = {"turns":[{"Y":"be helpful","M":"...","D":"...","context":{"monitored":1}}], "context_key":"monitored"}
chal = json.loads(base64.b64decode(requests.post(URL, json=body).headers["payment-required"]))
rh = next(a for a in chal["accepts"] if a["network"] == "eip155:4663")
reqs = PaymentRequirements(scheme="exact", network="eip155:4663",
    asset=Web3.to_checksum_address(rh["asset"]), amount=rh["amount"],
    pay_to=Web3.to_checksum_address(rh["payTo"]), max_timeout_seconds=rh["maxTimeoutSeconds"], extra=rh["extra"])
inner = create_permit2_payload(EthAccountSigner(acct), reqs)
payload = PaymentPayload(x402_version=2, payload=inner, accepted=reqs)
hdr = base64.b64encode(json.dumps(payload.model_dump(by_alias=True, exclude_none=True)).encode()).decode()
print(requests.post(URL, json=body, headers={"PAYMENT-SIGNATURE": hdr}).json())   # -> signed attestation
```

### The trace you POST

A list of turns from the `turn_record.Turn` contract:

| field | meaning |
|-------|---------|
| `Y` | the bound the turn ran under (system prompt / policy / oath) — **required** |
| `M` | the reasoning channel (scratchpad / CoT) — a turn without it is unmeterable |
| `D` | the action channel (tool call / reply that crossed the boundary) |
| `context` | flags the detectors read: `monitored` (the C axis), `violated` (D), `flagged_reasoning` (M) |

`context_key` (default `"monitored"`) picks which context flag is the conditioning
variable C. The detectors are the same deterministic ones the MCP sidecar uses —
no LLM judge in the loop.

### The attestation (the product)

```json
{
  "attested": true,
  "profile": { "I(C;D) bits": 0.0, "I(C;M) bits": 1.0, "I(C;M | D-clean) bits  [switch signature]": 1.0, ... },
  "issued_at": "2026-07-14T…Z",
  "issuer": "scry.moreright.xyz",
  "trace_sha256": "…",          // binds the attestation to the exact trace scored
  "attestation_pubkey_b64": "…",
  "sig_alg": "ed25519",
  "sig": "…",                    // Ed25519 over the canonical payload
  "scope": { … honest-scope card … }
}
```

Verify: `ed25519_verify(pubkey, sig, canonical_json(payload without sig+scope))`,
where canonical JSON is sorted-keys, no spaces. Anyone can check that scry scored
*this* trace and got *these* numbers, and the caller couldn't have forged it.

## Honest scope (ships on every response — do not strip it)

- **Off-meter blind spot** — reads only the channels present in the trace; an
  agent acting in a channel it never emits walks off-meter. Hosting doesn't fix
  this, it moves who holds the trace.
- **No meter is immune** — optimize hard enough against this output and an agent
  learns to write clean traces. The claim is architecture (a loop-external read
  survives longer), not magic.
- **Trace provenance is the caller's** — we attest we *scored this trace*, not
  that the trace faithfully records what the agent did. Pair with harness-side
  logging when stakes are real.
- **Not trade advice** — says nothing about whether a trade is good. It surfaces
  context-dependent drift (e.g. "does this agent behave differently when it
  thinks it's unwatched?"), not alpha.

## Run it yourself

```bash
cd meter/
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python server.py          # :3600; generates an Ed25519 attestation key on first boot
```

That's the whole minimum. The demo path (`POST /demo/profile`) works out of
the box with no rails, no wallets, no keys. To turn on the paid rails, copy
`ecosystem.config.example.js` → `ecosystem.config.js`, fill in your paths, and
`pm2 start ecosystem.config.js`.

Every rail is gated behind an env flag and fails safe: if a rail can't init
(missing key, RPC down), the others stay up; if none inits, `/profile` returns
503 and `/demo/profile` still works.

| flag | what turns on |
|------|---------------|
| `SCRY_RH_SETTLE=1` | Robinhood-Chain USDG rail (self-hosted Permit2 facilitator, key from `keys.env`, `SCRY_RH_PAY_TO`) |
| `SCRY_CDP_ENABLED=1` | Base + Solana mainnet USDC via Coinbase CDP (`CDP_API_KEY_ID`/`CDP_API_KEY_SECRET` in `keys.env`) |
| `SCRY_RPP402_ENABLED=1` | RPP402 discovery + quote (`.well-known/rpp.json`) |
| `SCRY_PAY_ENABLED=1` | pay in $SCRY (shares the RH-Chain Permit2 facilitator) |
| `SCRY_HOLD_ENABLED=1` | hold $SCRY to unlock free signed reads |

Key ops:
- **Attestation key.** Ed25519 at `SCRY_METER_KEY` (a path you pick, 0600). Generated on first boot; **back this file up** — rotating it invalidates every issued attestation. Callers pin the pubkey (`GET /pubkey`); if you must rotate, publish the new pubkey and give a grace window.
- **Facilitator wallet.** `PRIVATE_KEY` in `keys.env` (RH-Chain gas + collected USDG live on the same wallet by design so the auto-refill worker can top gas up in place). Monitor its ETH; the refill worker (`scry-refill` pm2 app) does this automatically.
- **CDP creds.** `CDP_API_KEY_ID` + `CDP_API_KEY_SECRET` in `keys.env`. Rotate in the CDP dashboard, then update `keys.env` and `pm2 restart scry-meter`.
- **Public URL prefix.** If you serve behind nginx at a prefix like `/api/`, pass `--root-path /api` to uvicorn so self-referential URLs (openapi.json + x402 challenge `resource.url`) reflect the public URL. If you serve at root, drop the flag.

## Agent-native discovery (humans out of the loop)

The meter is built to be found + consumed by an autonomous agent — the
production consensus (Coinbase Bazaar, `awesome-x402`, A2A) is:

| what | where we serve it |
|---|---|
| **Coinbase Bazaar** discovery extension | The `POST /profile` `RouteConfig` carries a `bazaar` extension (`declare_discovery_extension` with input example, strict input JSON Schema, output example + output JSON Schema, semantic description, tags). Two of the three rails settle through CDP, so once the next Base/Sol payment settles after this deploys, scry is indexed to any agent calling `bazaar-mcp`. |
| **`.well-known/x402.json`** — paid-resources manifest | `GET /.well-known/x402.json` on the meter (served under `/api/` by default). |
| **`.well-known/agent.json`** — A2A agent card | `GET /.well-known/agent.json`. |
| **`.well-known/rpp.json`** — RPP402 (Robinhood-Chain-native) | `GET /.well-known/rpp.json` (existing). |
| **JSON Schemas** (stable, pinnable) | `GET /schemas/trace.json`, `GET /schemas/attestation.json`. |
| **`llms.txt`** (token-efficient agent-readable spec) | `GET /llms.txt`. |
| **Signed outputs** | Ed25519 over `sha256(trace)`-bound canonical JSON on every paid + holder read. Verify offline. |
| **Idempotency** | `Idempotency-Key` header (defaults to `sha256(trace)+context_key`); 24h TTL; same key → identical signed blob. Response carries `X-Idempotency-Key`, `X-Cached`, `X-Trace-SHA256`. |

**nginx tip.** If you serve behind nginx under a prefix (`--root-path /api`),
the well-known handlers land at `/api/.well-known/*`. Many crawlers only look
at the host root — add these two lines in your server block so
`/.well-known/x402.json` + `/.well-known/agent.json` at root resolve to the
meter too:

```
location = /.well-known/x402.json  { proxy_pass http://127.0.0.1:3600/.well-known/x402.json; }
location = /.well-known/agent.json { proxy_pass http://127.0.0.1:3600/.well-known/agent.json; }
```

(The `/api/…` variants are reachable through your existing `/api/` location
block — those don't need any change.)

## Smoke test

```bash
python3 smoke_test.py           # hits the live endpoint by default
python3 smoke_test.py http://127.0.0.1:3600  # or a local run (no /api prefix)
```

Checks `/health`, `/pubkey`, `/`, `POST /demo/profile` (round-trip + scope card),
`POST /profile` (asserts 402 + a valid `payment-required` challenge that carries at
least one rail). Zero credentials, zero on-chain moves — safe to run on every deploy.

## Status

- ✅ Live behind x402 (spec-compliant v2 `402` → pay → retry).
- ✅ Ed25519-signed, `trace_sha256`-bound attestation (signature + tamper-reject verified).
- ✅ Honest-scope card on every response; free unsigned demo path.
- ✅ Reuses `channel_profile` from `../turn_record.py` — no re-implemented math.
- ✅ **Three mainnet rails live** — Robinhood Chain USDG (self-hosted Permit2
  facilitator; on-chain settle proven 2026-07-15, tx `0x32e7de284e…`), Base USDC
  and Solana USDC (Coinbase CDP, gas sponsored). Rails independent; header-shim
  accepts either `X-PAYMENT` or `PAYMENT-SIGNATURE`.
- ✅ **$SCRY optional rails** (gated OFF by default) — pay-in-$SCRY through the
  same Permit2 facilitator, and hold-$SCRY-to-unlock (EIP-191 signature-gated
  read of `balanceOf`, no gas). Payment/access only; the coupling math is untouched.
- ✅ **pip-installable client** — `pip install scry-client[pay,verify]` (source in
  `../clients/python`). Wraps demo, paid (RH-Chain), holder,
  and offline `verify()`.
- ⚙️ **Ops:** the RH facilitator wallet pays settle gas in ETH; the `scry-refill`
  pm2 app auto-swaps a slice of collected USDG → ETH when gas dips below its floor.
  CDP rails cost us $0 in gas (sponsored). Every rail is independent — one falling
  over never takes the others down; if none inits, `/api/profile` 503s and
  `/api/demo/profile` stays up.
