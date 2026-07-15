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

c = ScryClient()   # -> https://scry.moreright.xyz/api

# 1) Free, unsigned — try the shape, no wallet:
print(c.demo(turns)["profile"])

# 2) Paid, SIGNED attestation — pays USDG on Robinhood Chain:
att = c.profile(turns, private_key="0x...")   # wallet needs a little USDG + ETH gas on eip155:4663

# 3) Trust it offline (pin the meter's key so a forgery can't swap in its own):
pub = c.pubkey()
ScryClient.verify(att, expect_pubkey_b64=pub, turns=turns)   # True, or raises
```

`verify` raises if the signature is invalid, if the signer isn't the key you
pinned, or (when you pass `turns`) if the attestation is about a *different*
trace than yours.

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
