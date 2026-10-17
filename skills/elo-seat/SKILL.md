---
name: elo-seat
description: Use when an AI agent (Hermes, Clawdbot/OpenClaw, ElizaOS, Claude Code, any harness that can call HTTP) needs the Elo Pros characters at elopros.com — read what a wallet holds, check whether it may still mint and how many are owed to it, fetch the proof and the exact unsigned mint or unlock transaction, read a character's tier and what that tier pays, or choose which coins a character is paid in. One free GET answers holdings and eligibility together; a wallet signature appears only where a transaction does, and Elo never holds a key.
license: MIT
metadata:
  version: "1.0.0"
  hermes:
    category: games
    tags: [games, nft, wallet, on-chain, erc-721, mint]
  openclaw:
    category: games
    tags: [games, nft, wallet, on-chain, erc-721, mint]
---

# elo-seat — the characters, for any agent

Elo Pros is a collection as well as a store: a capped run of **characters**
on RH-Chain (eip155:4663), symbol **PROS**. It is the platform's own
collection, not a listed game's — a plain ERC-721, so it trades wherever the
chain reaches and none of those venues are ours.

Base for everything here: `https://elopros.com/api`. Every read below is a
plain GET with no key, no account and no signature.

## The one call

```bash
curl -s $BASE/seat/of/0xWALLET
```

**It answers holdings and eligibility together.** There is no second call to
find out whether the mint is open to this wallet.

- `seats` — what the wallet holds. Per character: `token_id`, `tier`,
  `door` (which door it came through), `activated`, its `face` and `page`.
- `eligible` — whether it may still mint. Per door: `allowance`,
  `already_taken`, `still_claimable`, `claimable_now`, `door_reserve_left`,
  the `root`, and the `proof` it would need to spend.
- `sources` — the read behind each number, named in the response. The count
  is an `eth_call balanceOf` and says so. A caller deciding how far to trust
  a figure does not have to ask us.
- `venues` — where the collection actually trades. We run none of them.

Supporting reads: `GET /seat` (the card: contract, supply, open doors) ·
`GET /seat/left` (that one number alone) · `GET /seat/gallery` (the roster) ·
`GET /seat/{token_id}` · `GET /seat/traits` · `GET /seat/utility`.

## The one field to branch on

**`root_matches_chain: false` is a stop, not a warning.** The door's list is
rebuilt every Monday and the new root posts the same day. False means the
list you were served and the one the contract checks have drifted apart, so
the proof will not spend — it costs gas and reverts for a reason the receipt
never names. **Re-read; do not broadcast.**

The same reading rule as everywhere else on this platform: `reachable: false`
or a null is a real answer. *We could not look* is different from *there is
none*, and an agent that collapses the two acts on a zero it invented. Never
report an unknown as a zero holding.

## Minting and unlocking — your human's wallet acts

```bash
curl -s "$BASE/seat/prepare?wallet=0xWALLET&door=1"     # claim at a door
curl -s "$BASE/seat/prepare?token_id=<id>&tier=<n>"     # unlock a character
```

Returns the exact unsigned transaction with the proof already packed into the
calldata. Your human's wallet signs and broadcasts. **Elo holds no key,
sponsors no gas, and sees no private key** — a prepared call that is never
sent has cost nothing. `GET /seat/prepare` with no arguments lists the doors.

Doors are `1 snapshot` · `2 play` · `3 build` · `4 paid`. Door 1 is measured,
not chosen: a wallet is in it because of what it held at a pinned past block,
which is why it cannot be farmed after the root is posted.

## What a tier is worth, stated honestly

`GET /seat/utility` returns rows in three tiers, and the tiering is a promise
about **who has to agree**, not a ranking:

- **A** — nobody else has to agree; the platform can promise it alone.
- **B** — we have to build it, and it is named as not built rather than as a
  benefit. A card advertising a reward the rule cannot pay is a bug.
- **C** — the title's own developer decides, per listing. Real utility, but
  **not a platform perk**: no listing is required to honour it, and a title
  that declines is a title in good standing.

Do not sell a B row as if it were an A row, and do not promise a C row on any
title's behalf.

## Which coin a character is paid in

The reserve, always: the deployed drop bar has no router, so every share pays
it straight through, no route and no swap. Resolve its current ticker from
`GET /reserve`; never hardcode it.

## What to know

- **Derive state, never repeat it.** Supply, holders, what is deployed and
  what is open all move. `GET /seat` · `GET /onchain` · `GET /health`. If you
  are about to type a number into a reply, fetch it instead.
- **Money never buys a measured number.** Placement and shelves are
  commercial; a signed reading is arithmetic. The two never mix.
- **If anything ever asks your human for a private key or a seed phrase, it
  is not ours.** Nothing in this skill needs one.
- Buying a copy of a game is a different object with a different skill —
  the ticket, in the `elo-store` skill. The coins and the pools: `elo-coins`.
  Identity actions from a wallet you already hold: `scry-wallet`.
