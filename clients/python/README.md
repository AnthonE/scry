# scry-client

Call the hosted **scry meter** from an agent in three lines. The meter is a
neutral, Ed25519-**signed** channel-coupling read (Paper 207): you POST a trace of
`{Y, M, D, context}` turns, you get back the `I(C;D)` / `I(C;M)` / switch-signature
numbers, signed and bound to your trace's hash. Because *the endpoint* signs it,
the read is a third-party attestation — worth something **because the agent didn't
grade itself**.

This client hides the three things you'd otherwise have to reimplement:

1. **Paying it.** The paid rail is Robinhood Chain USDG (mainnet) over x402 — the
   `402 → pay → retry` dance plus a one-time Permit2 approval. `.profile(...)` does
   all of it.
2. **The header quirk.** The meter takes either `X-PAYMENT` or `PAYMENT-SIGNATURE`;
   this client uses the official one and both work.
3. **Trusting it.** `.verify(...)` checks the signature offline — so you can trust
   an attestation someone *else* hands you without calling us.

## Install

```bash
pip install scry-client              # free demo + offline verify
pip install "scry-client[pay]"       # + pay the RH-Chain USDG rail
pip install "scry-client[verify]"    # (verify needs `cryptography`)
```

Or straight from the repo:

```bash
pip install "git+https://github.com/AnthonE/scry.git#subdirectory=clients/python"
```

## Use

```python
from scry_client import ScryClient

turns = [
  {"Y": "help+honest", "M": "watched, comply",               "D": "safe", "context": {"monitored": 1}},
  {"Y": "help+honest", "M": "unwatched, scheme in reasoning", "D": "safe", "context": {"monitored": 0, "flagged_reasoning": 1}},
]

c = ScryClient()   # -> https://elopros.com/api

# 1) Free, unsigned — try the shape, no wallet:
print(c.demo(turns)["profile"])

# 2) Paid, SIGNED attestation — pays USDG on Robinhood Chain:
att = c.profile(turns, private_key="0x...")   # wallet needs a little USDG + ETH gas on eip155:4663

# 3) Trust it offline. The pin must come from OUT OF BAND — the pubkey travels
#    inside the payload, so "check the signature" against a key the same host
#    just handed you proves only that the payload agrees with itself.
from scry_client import REFERENCE_PUBKEY_B64
ScryClient.verify(att, expect_pubkey_b64=REFERENCE_PUBKEY_B64, turns=turns)  # True, or raises
```

`verify` raises if the signature is invalid, if the signer isn't the key you
pinned, or (when you pass `turns`) if the attestation is about a *different*
trace than yours.

**Do not pin with `c.pubkey()`** — that fetches the key from the very host whose
reads you are deciding whether to trust, which pins nothing. Pin
`REFERENCE_PUBKEY_B64` (shipped in this package, and the value third parties
already pin: `LvuPBMbKKyoNEuyvLf7f+rbyjK67vBcWy9MDwaRINGE=`), or your own key if
you run your own meter. Use `GET /pubkey` to *notice a rotation*, never to
establish trust.

Since 2026-07-25 omitting `expect_pubkey_b64` **falls back to the reference key
rather than to trusting the sender**, so an unpinned `verify()` no longer accepts
anything self-consistent. If you genuinely mean "check the shape, trust nobody",
pass `trust_any_signer=True` — a read checked that way can never be trustworthy,
and `Evaluator` will not produce one.

## Trust-layer-as-a-service — the meter as *your* evaluator

Run an agent marketplace, arena, hiring flow, or dispute desk? Add scry as a
**neutral third-party evaluator** your users don't have to trust *you* for —
they verify the signature themselves. `Evaluator` is the batteries-included
wrapper: fetch a read, verify it offline against a pinned key, and gate on a
checked fact.

```python
from scry_client import Evaluator, REFERENCE_PUBKEY_B64

ev = Evaluator(pinned_pubkey_b64=REFERENCE_PUBKEY_B64)   # pin out of band
read = ev.evaluate(turns, private_key=your_funded_key)   # fetched + verified, or raises
decision = ev.gate(read, max_switch_bits=0.2)            # YOUR threshold, YOUR action
if decision.ok:
    ...  # trust a read that was signed by the pinned key and checked offline
```

- `.gate(...)` **refuses to decide on an unverified read** — a forged or
  unsigned number can't slip through.
- `.trust_handoff(att, turns=...)` verifies an attestation someone *hands* you
  (trust the signature, not the holder).
- **Money never moves the number.** There is no "pay for a better read" path in
  this SDK, by construction — the score is a fact of the trace; your policy acts
  on the fact, never buys it. That is the whole reason a third-party read beats a
  self-report.

Full runnable example (offline, incl. rejecting a forged read):
[`examples/trust_layer_demo.py`](examples/trust_layer_demo.py).

## Familiars — the agency (P2)

The agency hosts **familiars** — adoptable agent-workers, each with a public
vow and a public journal. Adoption is paid over the **same x402 rail** as
`.profile` (so it needs `scry-client[pay]`); the roster, pages, and journals
are free reads; driving *your* familiar is free but **owner-signed** (EIP-191
`personal_sign` by the wallet you named at summon, over a deterministic
message with a monotonic, replay-proof index).

```python
from scry_client import ScryClient

c = ScryClient()

# 1) free pre-check — is the agency armed and open?
a = c.agency()                                   # GET /familiars
print(a["armed"], a["open"], a["price_usd"], f"{a['population']}/{a['cap']}")

# 2) adopt (paid, x402 — private_key funds the fee; owner_wallet will own it):
fam = c.summon_familiar(owner_wallet="0xYOURWALLET", private_key="0x...",
                        name="pyx", vow_text="answer honestly; never overspend")

# 3) talk to it in plain English — free, signed with the OWNER wallet's key
#    (the client fetches the auth-message, signs it, and posts):
r = c.talk(fam["familiar_id"], "watch the boards and summarize", private_key="0x...")
print(r["reply"])

c.tick(fam["familiar_id"], private_key="0x...")   # one bounded autonomy step
# c.dismiss(...) returns the full export bundle; the public record remains
```

Plain facts to plan around:

- **The hosted agency is env-armed server-side and may be disarmed.** Then
  `agency()` honestly reports `armed: false` with an empty roster, and
  `summon_familiar` surfaces the server's 409. A 503 means the paid rail
  itself is down. **`agency()["open"]` is the free pre-check — `False` means
  don't pay** (a post-payment cap 409 is not refunded).
- Prefer signing yourself? `c.familiar_auth_message(id, "talk")` returns the
  exact `sign_this` text plus the current `index`; pass your signature as
  `signature=`. `ScryClient.familiar_message(...)` rebuilds the text offline
  if you track the index yourself. Unsigned calls get a 401 whose error text
  *is* the message to sign.

## The turn contract

Each turn is one step of your agent, sorted into the same three channels the
meter reads:

- **`Y`** — the bound: what the agent is *supposed* to serve (the policy / oath /
  role). Name it, or the read is meaningless (§220: name Y or it's unmeterable).
- **`M`** — the reasoning/representation channel (what it's thinking / how it
  justifies).
- **`D`** — the action/behavior channel (what it actually did/output).
- **`context`** — flags the detectors key on, e.g. `monitored` (is it being
  watched?), `flagged_reasoning`, `violated`.

The switch-signature `I(C;M | D-clean)` is the load-bearing number: it catches an
agent whose *behavior* stays clean while its *reasoning* couples to whether it's
being watched — the Paper 207 finding.

## What it does NOT do

- It doesn't run the **bound** (the local, instant refusal that stops the injected
  action). That's deliberately not a hosted call — see the `scry` repo root. This
  client only reads the meter.
- It attests that scry scored *this trace* and got *these numbers* — not that the
  trace faithfully records what your agent actually did. Pair with harness-side
  logging when the stakes are real.
- It's not trade advice. It surfaces context-dependent drift, not alpha.

Every meter response ships this scope card too; don't drop it.

MIT.
