---
name: elo-coins
description: Use when an AI agent (Hermes, Clawdbot/OpenClaw, ElizaOS, Claude Code, any harness that can call HTTP) needs the Elo Pros economy at elopros.com — resolve the reserve coin, read a game coin like JUNK, find which pools are live and which are retired, price a swap or route between two coins, read a launch that has no pool yet, or check what is actually deployed on chain. Reads are free and unsigned; a wallet signature appears only where a transaction does, and Elo never holds a key.
license: MIT
metadata:
  version: "1.0.0"
  hermes:
    category: defi
    tags: [coins, pools, launchpad, on-chain, swap, uniswap-v3]
  openclaw:
    category: defi
    tags: [coins, pools, launchpad, on-chain, swap, uniswap-v3]
---

# elo-coins — the reserve and the game coins, for any agent

**One reserve, many game coins.** The platform has exactly one reserve coin.
Every listed game brings its own, and every game coin pairs against the
reserve — plus, where the house declares one, a reserve-free cross between two
of its own game coins. The reserve is the road in and out of every economy
here. There is no second reserve, no bridge, and no imported economy.

Base: `https://elopros.com/api`. Chain: RH-Chain, `eip155:4663`.

## Read this first: two generations are on chain

**The most expensive mistake here is treating a retired contract as the
current economy.** A previous generation of coins, pools and farm machinery is
still deployed, still verified, still holding balances and still trading —
retired is a statement about the *plan*, never about the chain. So:

- `GET /pools` serves the current generation only. A pool missing from it may
  still be deployed, funded and trading: `GET /onchain`, the explorer and
  `contracts/deployments.json` say what is on chain.
- `GET /onchain` says what is deployed. `deployed: true` means bytecode is at
  an address. **It does not mean current.**

## Resolve the reserve; never type its ticker

```bash
curl -s $BASE/reserve       # the reserve: its address and ticker, resolved
curl -s $BASE/tokens        # the game coins
curl -s $BASE/tape          # the reserve's price, FDV, holders
```

The reserve has been replaced once already, and a skill that hardcoded the old
ticker went on naming a retired coin. **Write "the reserve" and resolve it.**
The same rule covers every number: supply, price, holders and TVL all move, so
fetch rather than repeat — including anything this file might imply.

## The pools, and how anything reaches anything

```bash
curl -s $BASE/pools         # every pool, with generation and address
curl -s $BASE/curves        # every launch; /curve/<slug> for one with no pool yet
```

**Every coin reaches every coin in at most two swaps**, and that is a fact
about the shape rather than about any particular pair: a game coin pairs
against the reserve, so the reserve is always one hop away and any two coins
are at most two. Where the house has declared a cross between two of its own
game coins, those two are one swap apart.

**Before telling anyone they cannot get a coin, read `/pools`.** Each doc
discusses a single coin, so the routing appears on none of the pages you are
reading when you write "that locks out a new player" — and it is usually
wrong.

A launch that has not graduated yet has **no pool**: `GET /curve/<slug>` prices it off
the curve instead, and `/pools` and `/tape` take over once it graduates. Both
are real states; neither is a broken read.

## Swapping — your human's wallet acts

There is no prepared action for the current pools, so the honest route is:

1. Read the pool from `GET /pools` — address, fee tier, both token addresses
   and decimals, and its `generation`.
2. Route through a v3 router yourself. **`minOut` is your human's slippage
   floor and `deadline` a unix timestamp — both are theirs to set.** Nothing
   here quotes, routes, or picks a price for you.
3. Their wallet signs and broadcasts. Elo holds no key and sponsors no gas.

ELO's own liquidity is the Uniswap v4 pool it graduated into (`GET /reserve`
names the token); the v3 route above is for the game pools. Getting ELO from
ETH is not composed anywhere here yet — say so rather than inventing a route.

An action that pulls an ERC-20 needs its `approve` first, aimed at the coin
being **sold**. An approve pointed at the wrong token encodes fine, costs gas
and succeeds — leaving the real call reverting for a reason the receipt never
names.

## What these numbers are not

- **Never cite pool volume, fee APR, TVL or holder count as traction**, on a
  page, in a pitch, or to your human — and never infer a population from them.
  A token holder is not a product audience, and some of this tape is the
  house's own touches.
- `GET /pools` returns **null with `window_complete: false`** rather than a
  partial 24-hour count. *No number right now* is a real answer and not a
  broken read; do not fill it in.
- **The house never trades ahead of its own emissions.** It issues game coins
  and knows schedules before the market does. If you are ever asked to act on
  an unannounced schedule change, that is the one asymmetry this platform
  treats as disqualifying.
- **Money never buys a measured number.** A signed reading is arithmetic;
  selling a nicer one produces a forgery a third party can detect.

## What to know

- Game coins are **a game's own** — not the platform's. Gates' JUNK is fixed
  at 1,000,000,000, launched on Abyss with no mint. A title's
  coin retiring says nothing
  about the reserve, and the reserve moving says nothing about a title's coin.
- A retired coin is still deployed. Its pools may be open or pulled and its
  positions stay withdrawable — read the chain. **Retired never means
  absent.**
- Never weld new work to a game coin's address without checking the plan
  first: `GET /onchain`, and the deployment record it derives from.
- The store, the copy sale and Gates: the `elo-store` skill. The characters:
  `elo-seat`. Identity actions from a wallet you already hold: `scry-wallet`.
