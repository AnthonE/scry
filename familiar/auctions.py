"""
auctions — the two-sided half of the exchange: players post, players bid.

The Browse tab (market.py) is the *house* selling at a dynamic buyout. This
is the rest of the auction house: a **seller** posts labor for hire at their
own starting bid + optional buyout + a duration; **bidders** compete; the
highest bid at close wins (or a bidder hits buyout to skip the wait). scry
takes a posted cut of the sale — that is the marketplace mechanism (owners
set prices, the house takes a fee), all numbers public.

The one thing you may NOT auction: a **measurement**. A reading whose price
moved with bidding would be paying for a better reading — the Bar Hadya
failure. `post()` refuses any `flat`/measurement item. Auctions price
*labor and tools*, never a score.

No real custody here either: escrow + settlement run through the payment
seam, which is MockPayment in P1 (records intent, moves nothing). Deterministic:
inject `now` and every quote/close is recomputable from the public record.
"""
import time

HOUSE_CUT = 0.05           # scry's marketplace fee on a sale (posted; operator knob)
DURATIONS = {"Short": 2 * 3600, "Medium": 8 * 3600,
             "Long": 24 * 3600, "Very Long": 48 * 3600}


def _min_increment(current: int) -> int:
    return max(1, round(current * 0.05))


class Auction:
    _seq = 0

    def __init__(self, seller, item, starting_bid, buyout, closes_at):
        Auction._seq += 1
        self.id = f"auc_{Auction._seq}"
        self.seller = seller
        self.item = item                      # {kind, ref, name, rarity}
        self.starting_bid = int(starting_bid)
        self.buyout = int(buyout) if buyout else None
        self.closes_at = closes_at
        self.bids = []                        # [{bidder, amount, at}]
        self.status = "open"                  # open | sold | expired
        self.winner = None
        self.sale_price = None

    @property
    def current_bid(self) -> int:
        return self.bids[-1]["amount"] if self.bids else self.starting_bid

    @property
    def high_bidder(self):
        return self.bids[-1]["bidder"] if self.bids else None

    def public(self, now: float = None) -> dict:
        now = now or time.time()
        return {"id": self.id, "seller": self.seller, "item": self.item,
                "starting_bid": self.starting_bid, "buyout": self.buyout,
                "current_bid": self.current_bid, "high_bidder": self.high_bidder,
                "n_bids": len(self.bids), "status": self.status,
                "winner": self.winner, "sale_price": self.sale_price,
                "closes_in": max(0, int(self.closes_at - now)),
                "min_next_bid": self.current_bid + _min_increment(self.current_bid),
                "asset": "$SCRY"}


class AuctionError(Exception):
    pass


class AuctionHouse:
    def __init__(self, payment_factory, keeper=None, house_cut: float = HOUSE_CUT):
        self.payment_factory = payment_factory     # () -> a payment rail
        self.keeper = keeper
        self.house_cut = house_cut
        self.auctions = {}
        self.settlements = []                       # public sale record

    # ── post ─────────────────────────────────────────────────────────────
    def post(self, seller, item, starting_bid, buyout=None,
             duration="Medium", now: float = None) -> dict:
        now = now or time.time()
        if item.get("pricing") == "flat" or item.get("category") == "measurement":
            raise AuctionError(
                "a measurement cannot be auctioned — its price is score-blind and "
                "never moves with bidding. Auction labor and tools, never a reading.")
        if int(starting_bid) < 1:
            raise AuctionError("starting bid must be at least 1 $SCRY")
        if buyout and int(buyout) < int(starting_bid):
            raise AuctionError("buyout must be at least the starting bid")
        if duration not in DURATIONS:
            raise AuctionError(f"duration must be one of {list(DURATIONS)}")
        auc = Auction(seller, item, starting_bid, buyout, now + DURATIONS[duration])
        self.auctions[auc.id] = auc
        return auc.public(now)

    # ── bid ──────────────────────────────────────────────────────────────
    def bid(self, auction_id, bidder, amount, now: float = None) -> dict:
        now = now or time.time()
        auc = self._live(auction_id, now)
        if bidder == auc.seller:
            raise AuctionError("you cannot bid on your own listing")
        need = auc.current_bid + _min_increment(auc.current_bid) if auc.bids else auc.starting_bid
        if int(amount) < need:
            raise AuctionError(f"bid must be at least {need} $SCRY")
        if auc.buyout and int(amount) >= auc.buyout:
            return self._settle(auc, auc.buyout, bidder, now, via="buyout-by-bid")
        auc.bids.append({"bidder": bidder, "amount": int(amount), "at": now})
        return auc.public(now)

    # ── buyout ───────────────────────────────────────────────────────────
    def buyout(self, auction_id, bidder, now: float = None) -> dict:
        now = now or time.time()
        auc = self._live(auction_id, now)
        if not auc.buyout:
            raise AuctionError("this listing has no buyout")
        if bidder == auc.seller:
            raise AuctionError("you cannot buy out your own listing")
        return self._settle(auc, auc.buyout, bidder, now, via="buyout")

    # ── close due auctions (lazy sweep) ──────────────────────────────────
    def close_due(self, now: float = None) -> list:
        now = now or time.time()
        closed = []
        for auc in self.auctions.values():
            if auc.status == "open" and now >= auc.closes_at:
                if auc.bids:
                    closed.append(self._settle(auc, auc.current_bid, auc.high_bidder,
                                               now, via="close"))
                else:
                    auc.status = "expired"
                    closed.append(auc.public(now))
        return closed

    # ── settle: charge winner, take the cut, summon the worker ───────────
    def _settle(self, auc, price, winner, now, via) -> dict:
        receipt = self.payment_factory().charge(price, "$SCRY",
                                                memo=f"auction:{auc.id}:{via}")
        cut = round(price * self.house_cut)
        proceeds = price - cut
        auc.status = "sold"
        auc.winner = winner
        auc.sale_price = int(price)
        summoned = None
        if auc.item.get("kind") == "worker" and self.keeper is not None:
            slug = auc.item.get("ref")
            summoned = self.keeper.summon_crew(slug, name=None)
        rec = {"auction_id": auc.id, "item": auc.item, "seller": auc.seller,
               "winner": winner, "price": int(price), "house_cut": cut,
               "seller_proceeds": proceeds, "via": via,
               "receipt": receipt.as_dict(), "summoned": summoned}
        self.settlements.append({k: rec[k] for k in
                                 ("auction_id", "price", "house_cut", "seller_proceeds", "winner")})
        return {**auc.public(now), "settled": rec}

    # ── views ────────────────────────────────────────────────────────────
    def _live(self, auction_id, now) -> Auction:
        auc = self.auctions.get(auction_id)
        if auc is None:
            raise KeyError(auction_id)
        if auc.status != "open":
            raise AuctionError(f"auction is {auc.status}")
        if now >= auc.closes_at:
            self.close_due(now)
            raise AuctionError("auction has closed")
        return auc

    def open_auctions(self, now: float = None) -> list:
        now = now or time.time()
        self.close_due(now)
        return [a.public(now) for a in self.auctions.values() if a.status == "open"]

    def for_seller(self, seller, now: float = None) -> list:
        now = now or time.time()
        return [a.public(now) for a in self.auctions.values() if a.seller == seller]

    def bids_of(self, bidder, now: float = None) -> list:
        now = now or time.time()
        out = []
        for a in self.auctions.values():
            if any(b["bidder"] == bidder for b in a.bids) or a.winner == bidder:
                p = a.public(now)
                p["you_lead"] = a.high_bidder == bidder
                out.append(p)
        return out
