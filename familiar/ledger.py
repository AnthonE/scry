"""
ledger — a sandbox $SCRY balance book for the local economy.

This is **play money**, stated plainly. It mirrors what the on-chain
contracts do with real $SCRY (balances move as jobs settle) so the whole
economy is visible and testable locally — seller gets paid, the house
takes its cut, the pool covers a default — without any custody, wallet, or
chain. Real settlement is the disarmed on-chain rail (`payment.py` +
`contracts/`); this ledger never touches it.
"""


class LedgerError(Exception):
    pass


class Ledger:
    def __init__(self):
        self.balances = {}

    def mint(self, account: str, amount: int):
        """Seed a demo account. Sandbox only — there is no real supply here."""
        self.balances[account] = self.balances.get(account, 0) + int(amount)

    def balance(self, account: str) -> int:
        return self.balances.get(account, 0)

    def transfer(self, frm: str, to: str, amount: int):
        amount = int(amount)
        if amount < 0:
            raise LedgerError("negative transfer")
        if self.balances.get(frm, 0) < amount:
            raise LedgerError(f"{frm} has insufficient balance for {amount}")
        self.balances[frm] = self.balances.get(frm, 0) - amount
        self.balances[to] = self.balances.get(to, 0) + amount

    def snapshot(self) -> dict:
        return dict(self.balances)
