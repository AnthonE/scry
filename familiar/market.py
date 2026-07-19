"""
market — a WoW-Auction-House for agent labor and x402 skills.

Browse listings (workers + skills), see a live **bid/buyout** that moves
with demand, hire at the buyout. The dynamic price is **deterministic and
auditable**: it is a pure function of public inputs (the base schedule +
the hire log + current roster occupancy), so anyone can recompute any quote
from the record — the same discipline as the games' payout math.

The load-bearing invariant, enforced here in code: **demand pricing applies
to labor and tools only.** A listing tagged `pricing="flat"` is a
measurement/attestation service; its price is pinned and score-blind, and
`quote()` refuses to let the dynamic engine touch it. You can pay for a
better *worker*; you can never pay for a better *reading*.

Everything in SCHEDULE is an operator knob — this is the proposed pricing
schedule, meant to be red-lined, not a fixed law.
"""
import math
import time

from . import tools
from .crew import CREW

# ── the pricing schedule (operator-tunable; this is the proposal) ─────────
SCHEDULE = {
    # base $SCRY price by rarity tier (workers + dynamic skills)
    "base_by_rarity": {"common": 5, "uncommon": 12, "rare": 25,
                       "epic": 50, "legendary": 100},
    "k_demand": 0.15,        # each recent hire in-window lifts price by ~15% of base
    "demand_halflife_h": 12,  # recent hires decay with this half-life
    "demand_window_h": 48,    # how far back the hire log is counted
    "scarcity_s": 0.6,        # price lift as an archetype's roster slots fill
    "soft_cap_per_type": 4,   # occupancy denominator for scarcity
    "bid_ratio": 0.6,         # the standing floor bid as a fraction of buyout
    "max_multiple": 6.0,      # a ceiling so demand can't run away
}

RARITY_COLOR = {"common": "#c9c4d6", "uncommon": "#5fd35f", "rare": "#4a90e2",
                "epic": "#a45cff", "legendary": "#ff8c1a"}
RARITY_LVL = {"common": 1, "uncommon": 2, "rare": 3, "epic": 4, "legendary": 5}
WORKER_RARITY = {"sibyl": "common", "herald": "common", "mnemon": "uncommon",
                 "lar": "rare", "georgos": "rare", "mithra": "legendary"}
# flavor seller names, WoW-AH style — deterministic per listing id
SELLERS = ["Wizku", "Shyrah", "Magah", "Liyah", "Gunther", "Rhonis",
           "Tsarnkoth", "Drekio", "Vael", "Orin"]


def _seller_for(listing_id: str) -> str:
    return SELLERS[sum(ord(c) for c in listing_id) % len(SELLERS)]


def _decayed_demand(hire_times: list, now: float) -> float:
    """Sum of exp(-dt/halflife) over in-window hires — a smooth 'how hot is
    this right now' that anyone can recompute from the public hire log."""
    hl = SCHEDULE["demand_halflife_h"] * 3600.0
    win = SCHEDULE["demand_window_h"] * 3600.0
    total = 0.0
    for t in hire_times:
        dt = now - t
        if 0 <= dt <= win:
            total += math.exp(-dt / hl)
    return total


def _round_scry(x: float) -> int:
    return max(1, int(round(x)))


class Market:
    """Holds the listings + the public hire log; quotes and fills."""

    def __init__(self, keeper=None):
        self.keeper = keeper                 # for live roster occupancy (scarcity)
        self.hire_log = {}                   # listing_id -> [unix hire times]
        self.fills = []                      # public record of fills

    # ── the listing set ──────────────────────────────────────────────────
    def listings(self) -> list:
        out = []
        for slug, a in CREW.items():
            rarity = WORKER_RARITY.get(slug, "common")
            out.append({"id": f"worker:{slug}", "kind": "worker", "slug": slug,
                        "name": a["name"], "category": "worker",
                        "title": a["title"], "rarity": rarity,
                        "pricing": "dynamic", "tools": a["tools"]})
        for s in tools.seed_skills() + tools.live_skills():
            out.append({"id": s["id"], "kind": "skill", "name": s["name"],
                        "category": s["category"], "title": s.get("desc", ""),
                        "rarity": s.get("rarity", "common"),
                        "pricing": s.get("pricing", "dynamic"),
                        "flat_price": s.get("flat_price"), "asset": s.get("asset"),
                        "provider": s.get("provider"), "base": s.get("base")})
        return out

    # ── the quote (dynamic for labor/tools, pinned for measurement) ──────
    def quote(self, listing: dict, now: float = None) -> dict:
        now = now or time.time()
        rarity = listing.get("rarity", "common")

        if listing.get("pricing") == "flat":
            # measurement/attestation — score-blind, never demand-priced
            price = listing.get("flat_price", "0.10")
            return {"pricing": "flat", "asset": listing.get("asset", "USDG"),
                    "buyout": price, "bid": price, "time_left": "Very Long",
                    "score_blind": True,
                    "basis": "flat, score-blind — price never moves with demand"}

        base = listing.get("base") or SCHEDULE["base_by_rarity"][rarity]
        demand = _decayed_demand(self.hire_log.get(listing["id"], []), now)
        occ = self._occupancy(listing)
        demand_mult = 1.0 + SCHEDULE["k_demand"] * demand
        scarcity_mult = 1.0 + SCHEDULE["scarcity_s"] * occ
        mult = min(demand_mult * scarcity_mult, SCHEDULE["max_multiple"])
        buyout = _round_scry(base * mult)
        bid = _round_scry(buyout * SCHEDULE["bid_ratio"])
        return {"pricing": "dynamic", "asset": "$SCRY",
                "buyout": buyout, "bid": bid,
                "time_left": self._time_left(mult),
                "score_blind": None,
                "basis": (f"base {base} × demand {demand_mult:.2f} × scarcity "
                          f"{scarcity_mult:.2f} (capped {SCHEDULE['max_multiple']}×)"),
                "demand": round(demand, 3), "occupancy": round(occ, 3)}

    def _occupancy(self, listing: dict) -> float:
        """Workers: fraction of this archetype's soft cap currently active.
        Skills: 0 (no roster). Public + recomputable."""
        if listing.get("kind") != "worker" or self.keeper is None:
            return 0.0
        slug = listing["slug"]
        n = sum(1 for f in self.keeper.familiars.values()
                if not f.dismissed and getattr(f, "archetype", None) == slug)
        return min(1.0, n / max(1, SCHEDULE["soft_cap_per_type"]))

    @staticmethod
    def _time_left(mult: float) -> str:
        # hotter listings re-quote sooner — AH-style time-left, honest:
        # a stable price holds Long, a fast-moving one only Short.
        if mult >= 3.0:
            return "Short"
        if mult >= 1.8:
            return "Medium"
        if mult >= 1.2:
            return "Long"
        return "Very Long"

    # ── browse: filter / search / sort like the AH ──────────────────────
    def browse(self, category=None, search=None, rarity=None,
               sort="buyout", now: float = None) -> list:
        now = now or time.time()
        rows = []
        for L in self.listings():
            if category and L["category"] != category:
                continue
            if rarity and L.get("rarity") != rarity:
                continue
            if search and search.lower() not in (L["name"] + " " + L.get("title", "")).lower():
                continue
            q = self.quote(L, now=now)
            rows.append({**L, **q, "lvl": RARITY_LVL.get(L.get("rarity", "common"), 1),
                         "color": RARITY_COLOR.get(L.get("rarity", "common")),
                         "seller": _seller_for(L["id"])})
        rev = sort in ("buyout", "bid", "lvl", "demand")
        rows.sort(key=lambda r: _sort_key(r, sort), reverse=rev)
        return rows

    # ── fill: hire at the buyout, through the payment seam ───────────────
    def hire(self, listing_id: str, payment, keeper=None, name=None,
             now: float = None) -> dict:
        now = now or time.time()
        L = next((x for x in self.listings() if x["id"] == listing_id), None)
        if L is None:
            raise KeyError(f"no such listing: {listing_id!r}")
        q = self.quote(L, now=now)
        asset = q["asset"]
        amount = q["buyout"]
        receipt = payment.charge(amount, asset, memo=f"hire:{listing_id}")
        # a fill is public + recomputable; demand ticks up for next quote
        self.hire_log.setdefault(listing_id, []).append(now)
        summoned = None
        if L["kind"] == "worker" and (keeper or self.keeper):
            summoned = (keeper or self.keeper).summon_crew(L["slug"], name=name)
        fill = {"listing_id": listing_id, "kind": L["kind"], "amount": amount,
                "asset": asset, "receipt": receipt.as_dict(),
                "summoned": summoned, "quoted": q}
        self.fills.append({"listing_id": listing_id, "amount": amount, "asset": asset})
        return fill


def _sort_key(row: dict, sort: str):
    v = row.get(sort)
    if sort in ("buyout", "bid"):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0
    return v if v is not None else 0
