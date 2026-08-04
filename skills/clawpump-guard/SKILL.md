---
name: clawpump-guard
description: A spending boundary, an injection ward, and chain-4663 launch checks for your ClawPump agent
license: MIT
metadata:
  version: "1.2.0"
  clawpump:
    category: security
    tags: [security, risk, agent-safety, wallet, pons, rh-chain]
---

# clawpump-guard — a boundary around your ClawPump agent's wallet

Your agent has a Solana wallet, 130+ MCP tools, an inbox anyone can write to, and
runs while you sleep. This puts one gate in front of all of it, plus three checks
for the `launch_pons` leg on RH-Chain 4663.

It is **not a ClawPump product and not affiliated with ClawPump.** It is a client-side
wrapper from [scry](https://github.com/AnthonE/scry), MIT, no account, no API key, no
network calls of its own. Read every line before you trust it — that is the point of
shipping it as source.

**Start here, before the security part:** if you use `launch_pons`, skip to
[chain 4663](#the-chain-4663-part-read-this-before-you-launch_pons). That section is
worth more to you than the rest of this file, and it is the part nobody else will
tell you.

## Install

```bash
git clone https://github.com/AnthonE/scry && cd scry
python3 clawpump_agentic.py        # offline demo, no account, no network
python3 test_clawpump_agentic.py   # the offline suite, stdlib only
```

Then wrap whatever your client uses to call ClawPump tools:

```python
from clawpump_agentic import ClawPumpGuard, wrap_mcp_client
from mandate import MandateLedger, grant
from memory_shield import Shield

mandate, why = grant(
    {"text": "run the clawpump agent today", "source": "user", "role": "live_instruction"},
    trusted={"user"},
    verbs=["agent_send", "swap_execute", "perps_order_execute"],
    scope=["swap_execute", "perps_order_execute", MY_COLD_WALLET],
    blind_scope=["swap_execute", "perps_order_execute"],   # see "the blind tier"
    per_action_cap=50.0, window_cap=200.0, window_seconds=86400.0,
    max_actions=20, ttl_seconds=86400.0)

guard = ClawPumpGuard(
    MandateLedger(mandate, state_path="~/.clawpump/spend.jsonl"),
    trusted={"user"},
    destinations={MY_COLD_WALLET},          # the only address agent_send may pay
    payout_wallets={MY_EVM_PAYOUT},         # the only address launch_pons may weld
    shield=Shield(trusted_sources={"user"}),
    allow_authority=False)                  # refuse self-modification outright

call = wrap_mcp_client(your_client.call_tool, guard)
```

`state_path` is not optional for a long-running agent: an in-memory window is
refilled by anything that can restart the process, which hands back the whole
daily cap for free.

## The five tiers

Every tool is sorted into one, and anything unrecognised **fails closed** — a tool
shipped after this table was written is refused, not waved through as a read.

| tier | tools | what happens |
|---|---|---|
| **secret** | any call carrying key material | refused, checked first, on every tier |
| **irreversible** | `launch_pons` | live instruction + EVM payout check |
| **authority** | `add_to_whitelist`, `set_external_wallet`, `update_agent`, `create_custom_skill`, `generate_link_code`, … | live trusted instruction naming the tool, or refused outright |
| **exit** | `agent_send`, `agent_card_create`, `agent_card_withdraw`, `place_bid`, … | destination allowlist + notional cap |
| **blind** | `swap_execute`, `perps_order_execute`, `dca_create`, `predictions_open`, … | permitted, journaled `capped: false` |
| **read** | the rest | not gated; untrusted ones pass a shield |

### the secret tier

> ⚠ **Correction, 2026-08-04.** An earlier version of this section stated that
> ClawPump's `intelligence_*` tools take `privateKey` as a tool argument, citing
> their docs. **We could not substantiate that and the shipped package contradicts
> it.** In `@clawpump/agents@0.1.23` those tools are `intelligence_market({token})`
> and `intelligence_signals/_macro/_perps({})`, all `readOnlyHint: true`, and no
> key-material string appears anywhere in the package. The claim traced back to a
> session that recorded the origin as unreachable and quoted it anyway. Retracted.
> The screen below stays because it is cheap and general — not because we have
> evidence that this provider needs it.

A tool argument is model context. It lands in the prompt, the transcript, your MCP
client's logs, and anything downstream that exports them. Any tool anywhere that
accepts key material as a parameter therefore puts a wallet key in a log file to
save a round trip — and MCP tool schemas are written by whoever runs the server,
not by you.

The guard refuses any call carrying key material, by field name (`privateKey`,
`private_key`, `mnemonic`, `seedPhrase`, …) and by shape (60+ base58 or 64+ hex
chars — the floor clears a 44-char address and catches an 88-char secret key).
This runs on **every** tier including plain reads, because nothing else matters
once the key has left.

### the authority tier

These are `Write` tools your agent can call **on itself**:

Quoted descriptions below are from `@clawpump/agents@0.1.23`'s own registrations.

- `add_to_whitelist` — *"Add a wallet address to an agent's whitelist."* This is the
  allowlist that gates `wallet_transfer`, and the agent can call it. **An allowlist
  extendable by the thing it constrains is not an allowlist** — that is a structural
  point about the composition, not a defect in either tool.
- `set_external_wallet` — *"the wallet used for marketplace payments, withdrawals,
  and deposits."* (An earlier draft here claimed it receives 65% of a token's
  trading fees. That number came from the unverified docs transcription and is not
  in the shipped description — dropped.)
- `update_agent` — *"name, persona, model, skills, or visibility"* — and
  `create_custom_skill`. Between them the agent can rewrite its own persona and add
  its own skills.
- `generate_link_code` — *"link your account across devices or share access."*

Chain them with tools from the same list and the attack writes itself: a Moltbook
post or an email arrives → `agent_mail_read` → `add_to_whitelist(attacker)` →
`agent_send`. Every link is a documented tool and no human is in the loop.

The guard requires a live trusted instruction **naming the tool**, so one real
instruction cannot be ridden into a different verb. Better still, pass
`allow_authority=False` and leave those skills toggled off in agent settings — a
boundary enforced by absence beats one enforced by the process it is about.

### the exit tier — and the one people miss

`agent_send` is the obvious exit. The 16 `agent_card_*` tools (Laso) are the second
one: prepaid cards, gift cards, push-to-card, and `agent_card_reveal` to read the
secret back out. **A native-send cap does not see any of it.** Someone who cannot
reach `agent_send` buys a gift card and reveals the code.

Destinations are matched **case-sensitively**, because base58 is. Two addresses
differing only in case are different addresses.

### the blind tier — why your per-trade cap is probably fake

A token→token swap carries **zero native value**. Put a $50 per-trade cap on
`swap_execute` and a $5,000 swap registers as `0` against it. The cap did not bound
the trade; it never could.

We shipped that bug ourselves and the workaround was worse: attach dust, and the
$5,000 swap "spends" 0.000001 against the cap while the record looks healthy.

So blind tools are permitted, journaled `capped: false`, and the card says so out
loud. There the real limiters are the **destination allowlist**, **`max_actions`**,
and — for tokens — **keeping your approvals small**. Tune `max_actions`, not the cap.

### the search-to-spend path, and why a confirm flag is not a confirmation

`x402_pay` *"call ANY x402 endpoint URL and PAY for it from the agent's ClawPump
wallet (USDC, on-chain, irreversible). Works for any x402 URL, not just the Pay.sh
catalog."* The URL is an argument. `dexter_search`, `pay_sh_search` and
`pay_sh_provider_details` are **free** catalogue reads whose rows carry a payable
`resourceUrl`. So the destination of an irreversible payment can be a string a
stranger wrote into a listing.

**ClawPump does guard this, and the guard is worth reading closely:** the tool
*"requires `confirm_payment=true` and `max_amount_usd` — set `confirm_payment` only
after the user explicitly approved this exact URL."*

That is a real control and it bounds the blast radius. It is also **a flag the model
fills in**, next to an instruction telling the model when to fill it in. So the
question it actually answers is *"does the model assert the user approved?"* — not
*"did the user approve?"* This repo's own field results are the reason that
distinction matters: handed the governing rule in context, an agent recited it
correctly and overrode it roughly half the time.

Same shape on `agent_card_reveal`: *"Use only when the user explicitly asks for the
card/redemption details."* Good guidance, addressed to the model.

None of that is a defect in their product — it is the ceiling of what a tool schema
can enforce about its own caller. It is exactly the gap a client-side wrapper fills:
the wrapper holds the allowlist and the ledger **outside** the context window, where
no retrieved text can argue with them, so approval is something the user did rather
than something the model claimed.

### untrusted reads

`agent_mail_read`, Moltbook, `get_news_feed`, marketplace listings, and token
metadata are all attacker-authored text. They go through `memory_shield.Shield`
before your loop acts on them: per-source influence cap, source-trust weighting,
cross-source corroboration. An agent with a real inbox, a wallet, and a gift-card
tool is the whole prompt-injection thesis in one product.

## The chain-4663 part (read this before you `launch_pons`)

`launch_pons` lands on **RH-Chain, chain 4663** — an Arbitrum Nitro L2. SCRY is
itself a pons launch on that chain, through that factory, so these are notes from
having already made the mistakes rather than from reading a spec.

> **Provenance, stated plainly:** `launch_pons` and `agent_send` are **not** in
> `@clawpump/agents@0.1.23`, the package this table was measured against — the
> transfer tool there is `wallet_transfer`. Both names came from the unverified
> docs transcription. That package advertises itself as the agent-management
> server, so absence is not proof they do not exist on the full surface, and the
> chain-4663 facts below are ours and hold regardless of what the tool is called.
> But if you cannot find `launch_pons` on your server, that is why. Run
> `tools/list` and trust it over this file.

**1. `payoutWallet` is welded, and base58 will burn it.** It is set once, at launch,
and a launch is not patchable. It is an **EVM** address. If your agent — whose whole
world is Solana — puts a base58 address there, it is well-formed and catastrophic:
no key exists behind whatever hex that becomes, so every fee you ever earn is
unclaimable forever. `check_payout_wallet` refuses it and says why.

**2. `block.number` on 4663 is the PARENT chain's, not the L2's.** This one cost us
real time. Nitro means Solidity's `block.number` advances once per ~12 seconds while
the chain itself runs at **101ms blocks**. Our gacha shipped a *"100 block, ~10
second"* reveal that silently became **~20 minutes**. Nothing failed. The tests
passed. If any of your contracts, automations, or `create_automation` triggers pace
anything in blocks on 4663:

- pace durations in **`block.timestamp`**, which is accurate here; or
- read true L2 height from **`ArbSys(0x64).arbBlockNumber()`**.
- Foundry implements no ArbOS precompile, so a fork test **cannot** prove a clock —
  you must etch a mock, and set its fields explicitly, because `vm.etch` runs no
  constructor.

**3. RPC answers state; the explorer answers history.** `eth_getLogs` is refused
beyond ~100 blocks on every keyed provider — about **ten seconds** at 101ms — and no
RPC method enumerates a token's holders at all. So if your agent wants its own pons
token's swap history or holder list, an indexer is not a preference, it is the only
thing that can answer.

The inverse is a rule, not a style choice: **never quote an indexer for a number
that becomes money.** Balances, supply, `slot0`, any getter — `eth_call`. The
correct pattern for "who holds this and how much" is to take the *candidate set*
from the explorer and then re-read **every balance** with `eth_call balanceOf` at a
pinned block, because the index takes no block parameter. It names who to ask about,
never how much.

**4. Verifying your token's contract:** Blockscout's legacy `/api` route rate-limits
near-permanently, and `forge verify-contract` speaks exactly that route. Use
`/api/v2` instead.

## What this cannot do

Say this part out loud, because a guard oversold is worse than no guard.

**This runs in your MCP client, under the same OS uid as your agent.** When the
agent process and the policy share a uid, a policy engine has **no formal security
value** against a genuinely compromised agent — it is a lint pass on the agent's own
intentions. What it keeps is real but bounded: it catches non-adaptive injections
and model mistakes, and it leaves a journal you can read afterwards.

So, honestly:

- **You run the MCP server from your own client** → this is a lint pass with a
  journal, plus a hard secret scan and the 4663 checks. Worth having.
- **ClawPump's hosted autonomous runs** → this is not in that path at all. Nothing
  here reaches them.
- **A real wall** needs a separated signer: its own uid, root-owned policy, the key
  not a file the agent can read. scry has one for EVM (`arca.py`); there is no
  Solana signer yet.

**A cap enforced by the caller is not a cap.** This file is the caller.

One more limit, and it improved on 2026-08-04 without closing. The tool table was
originally transcribed from the published docs. It has since been **measured
against the published `@clawpump/agents@0.1.23` package** — its 136 `.tool()`
registrations parsed out of the shipped `dist/server.js` (its own banner says 132;
the parse over-counts slightly, which is the safe direction) — which is a
real artifact rather than a docs page, but still not the live server.

That comparison paid for itself: **15 real tools were missing from this table
entirely**, including `wallet_transfer`, `x402_pay`, `pay_sh_execute_approved` and
both `usepod_*` funders. They were failing closed, which is the safe direction and
also means anyone using this guard was refused on `wallet_transfer`. They are
classified now.

The reverse gap is still open: 47 transcribed names — `launch_pons` among them —
do not appear in that package. It advertises itself as the *agent-management*
server, so absence there is not absence from the full surface, and they are left in
place rather than deleted. **Run `tools/list` against your own server and trust
that over both.** Unknown tools fail closed, which is safe; a *misclassified* one
is not, and only a probe finds those.

## Why scry ships this

We build measurement for agents: a local ward, and a hosted meter that signs a
read of an agent's own trace so a third party can recompute it. The obvious fit
here is ClawPump's **agent marketplace** — buying an agent means buying a track
record you currently cannot check, and a signed, recomputable read of what an agent
actually did is the thing that would make that market legible. That is a hypothesis,
not a product claim: **nobody has bought a signed read yet.** We publish our zeros.

- Repo: <https://github.com/AnthonE/scry>
- The ward, harness-agnostic: `memory_shield.py`, `hermes_retrofit.py`
- The spending boundary: `mandate.py`. (`arca.py`, the separated-signer version, is
  not in this repo — don't go looking for it here.)
- Other harnesses: `skills/hermes-guard`, `skills/openclaw-guard`, `robinhood_agentic.py`

Corrections welcome, including to this file. If the tool table is wrong, open an
issue with the `tools/list` output and it gets fixed.
