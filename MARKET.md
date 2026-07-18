# The Exchange — a WoW-Auction-House for agent labor + x402 skills

> **Status: P1 BUILT 2026-07-19** (`familiar/market.py` + `tools.py` +
> `payment.py` + the AH-reskin console page). Browse/quote/hire work end to
> end; hiring is sandbox (mock payment, no money moves). The real $SCRY
> rail is built to the interface but **disarmed** pending the custody
> gates. Design of record; operator knobs at the bottom.

**One sentence:** the marketplace surface is a browsable auction house —
list **workers** (familiars) and **skills** (x402 paid tools / MCP), each
with a rarity, a seller, a **bid/buyout that moves with demand**, and a
one-click hire — styled like the WoW auction house because that UI already
solved "browse a market of interchangeable goods."

## Why the AH metaphor fits

The WoW auction house is the most-used market UI in games: left-rail
category filters, a search + rarity dropdown, columns (item · rarity · lvl
· time-left · seller · current-bid · buyout), and Browse/Bids/Auctions
tabs. Agent labor maps onto it cleanly — a Sibyl is an item, its
specialization is a rarity, demand is a price. We reskin it cyberpunk and
keep the muscle memory.

## Listings

| kind | is | priced |
|---|---|---|
| **worker** | a familiar archetype you can hire (Mithra/Sibyl/Mnemon/Herald/Lar) | **dynamic** (labor) |
| **skill — labor/tool** | an augury answer, an arena entry, a duel call | **dynamic** |
| **skill — measurement** | a signed read, a vow report, a witness reading | **flat + score-blind** |

Skills are seeded curated in P1 (`tools.SKILLS`); the live pull from
Coinbase Bazaar / Agent402 is a documented seam (`tools.live_skills()`,
returns `[]` until wired — we don't invent a live index).

## Dynamic pricing — deterministic and auditable

The whole engine is a **pure function of public inputs**, so anyone can
recompute any quote from the record — the same discipline the games' payout
math already holds to.

```
buyout = base(rarity)  ×  (1 + k_demand · demand)  ×  (1 + scarcity_s · occupancy)
         capped at max_multiple × base
bid    = buyout × bid_ratio
```

- **demand** = Σ over recent hires of `exp(−Δt / halflife)` from the
  **public hire log** — a smooth "how hot is this right now" that decays.
- **occupancy** = how full this archetype's roster is (fewer free slots →
  higher price) — AH scarcity, recomputable from the live roster.
- **time-left** is honest, not cosmetic: a stable price shows *Very Long*,
  a fast-moving one shows *Short* — it tells you how long the quote holds.

Every field lives in `SCHEDULE` (`market.py`) — the **proposed pricing
schedule**, meant to be red-lined. Nothing here is secret or gameable
without moving a public number.

## The invariant, enforced in code (not just promised)

`quote()` **refuses to demand-price a `flat` listing.** Measurement /
attestation is pinned and **score-blind**: you can hammer a signed-read
listing with fake demand and its price does not move. This is the one line
that survives the marketplace — **pay for a better worker, never for a
better reading of a worker** (Bar Hadya, `SCRY-ECONOMY.md`). The test suite
asserts it directly.

## The hire flow + the payment seam

`market.hire(listing_id, payment, keeper)` quotes at the current buyout,
charges through the **payment seam**, records the fill (which ticks demand
up for the next quote), and — for a worker — summons it (auto-numbered so
you can field many of the same archetype).

- **P1 default: `MockPayment`** — records the intent, moves no money.
  Every hire is free and sandboxed.
- **The `$SCRY` rail (`ScryX402Payment`) is built to the same interface
  but DISARMED.** It refuses to charge until the operator arms it with real
  config (pay-to + facilitator + faucet-cap) — because charging means
  **custody**, the one risk class we never switch on by default. Arming is
  the P2 gate, not a code path we flip silently.

## Capability of what you hire (`tools.ALLOWLIST`)

A hired worker's hands = the MCP servers scry has set up + a curated tool
allowlist + safe workspace file ops. **No shell, ever** (workspace.py). The
allowlist is the launch capability set; adding to it is an operator
decision. `GET /market/tools` publishes it.

## Surfaces

- `GET /market?category=&search=&rarity=&sort=` — browse (the AH grid).
- `GET /market/quote/{listing_id}` — one live quote + its basis string.
- `POST /market/hire {listing_id, name?}` — fill at buyout (mock in P1).
- `GET /market/tools` — the capability allowlist.
- `familiar/static/market.html` — the reskinned auction house.

## Operator knobs (the pricing schedule is a proposal)

`SCHEDULE` in `market.py`: `base_by_rarity` · `k_demand` ·
`demand_halflife_h` · `demand_window_h` · `scarcity_s` ·
`soft_cap_per_type` · `bid_ratio` · `max_multiple`. Plus the P2 gates:
whether owners set their own prices (and scry's cut), the launch MCP/tool
allowlist, wallet faucet cap, and arming the $SCRY rail.

## The other side of the house — auctions (BUILT, `auctions.py`)

Browse is the *house* selling at a dynamic buyout. Auctions are
**players selling to players**, which is what makes it a two-sided
market:

- **Post** — a seller lists labor at *their own* starting bid + optional
  buyout + a duration (Short…Very Long). Owners set prices; that's the
  marketplace.
- **Bid** — bidders compete; each bid must clear a min increment (~5%);
  no bidding on your own listing. Hitting the buyout wins instantly.
- **Close** — a lazy sweep settles every expired auction: highest bid
  wins, no-bid auctions expire. Winning a worker auction **summons it to
  the winner**.
- **The house cut** — scry takes a **posted 5%** of each sale
  (`HOUSE_CUT`, operator knob); the seller gets the rest. Every sale is
  on the public settlement record. This is the "owner-set prices + a
  scry cut" mechanism, concretely.
- **The score-blind line holds here too** — `post()` **refuses to
  auction a measurement**. A reading whose price moved with bidding would
  be paying for a better reading. Auctions price labor and tools, never a
  score. (The test suite asserts the refusal.)

Settlement runs through the same **payment seam** — MockPayment in P1, so
bids and sales move no real money; the disarmed `$SCRY` rail is the P2
custody gate. Surfaces: `POST /auctions` · `GET /auctions` ·
`POST /auctions/{id}/bid` · `POST /auctions/{id}/buyout` ·
`GET /auctions/mine?who=`. The market page's **Bids** and **Auctions**
tabs are now live (post form, countdown, bid/buyout).

## Not yet (honest)

- **Live skill index** (Bazaar/Agent402) is a seam, not wired.
- **Real settlement** is disarmed; no custody / real escrow in P1 (bids
  are recorded intents, not locked funds).
- **Auction identity** in P1 is a name field, not wallet auth — holder
  signatures come with P2.
- Standalone from morr/MMO/ATH/Solana — $SCRY on RH-Chain only.
