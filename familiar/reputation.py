"""
reputation — soulbound market reputation (the Python mirror of ScryReputation).

Non-transferable by construction: there is no move/transfer method. Rep is
earned by outcomes (completed jobs), slashed by defaults and adverse
rulings, and gates high-value work by a posted threshold. You can't buy a
good name, sell a clean one, or wash a slashed record by switching
identities — the score follows the account and only the market logic in
this package may mutate it.

Distinct from the meter's behavioral score (watched-vs-unwatched,
score-blind, never for sale). Rep is a market-history record; the meter is
an integrity measurement. Neither is purchasable — keep them separate.
"""


class Reputation:
    def __init__(self, threshold: int = 50):
        self.threshold = threshold
        self.rep = {}
        self.log = []                       # public, append-only

    def earn(self, who: str, amount: int, reason: str):
        self.rep[who] = self.rep.get(who, 0) + int(amount)
        self.log.append({"who": who, "delta": int(amount), "reason": reason,
                         "total": self.rep[who]})

    def slash(self, who: str, amount: int, reason: str):
        cur = self.rep.get(who, 0)
        nxt = max(0, cur - int(amount))
        self.rep[who] = nxt
        self.log.append({"who": who, "delta": nxt - cur, "reason": reason, "total": nxt})

    def of(self, who: str) -> int:
        return self.rep.get(who, 0)

    def meets(self, who: str) -> bool:
        return self.of(who) >= self.threshold

    # Intentionally no transfer/set/mint-to-arbitrary — soulbound.
