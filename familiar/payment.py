"""
payment — the seam money flows through, built ready but disarmed.

The marketplace hire flow is complete end to end, but P1 charges nothing:
`MockPayment` records the intent and returns a receipt so the whole flow is
testable offline with no wallet, no custody, no x402. The real `$SCRY` rail
(`ScryX402Payment`) is written to the same interface but **refuses to
charge unless explicitly armed** with operator config — because taking real
money means custody, which is the one risk class we do not switch on
without the operator naming the gates (faucet cap, keys, pay-to).

This mirrors how the meter's own rails work: present in code, armed only by
env + funding. Wiring the flow is not the same as turning on custody, and
this file keeps those two things apart on purpose.
"""
import hashlib
import time


class PaymentError(Exception):
    pass


class Receipt:
    def __init__(self, ok, kind, amount, asset, ref, note=""):
        self.ok, self.kind, self.amount = ok, kind, amount
        self.asset, self.ref, self.note = asset, ref, note
        self.at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def as_dict(self):
        return {"ok": self.ok, "kind": self.kind, "amount": self.amount,
                "asset": self.asset, "ref": self.ref, "note": self.note, "at": self.at}


class MockPayment:
    """Offline default: no money moves. Records the intent, returns a
    receipt. This is what P1 runs — a hire is free and sandboxed."""

    armed = False
    kind = "mock"

    def charge(self, amount, asset, memo) -> Receipt:
        ref = "mock_" + hashlib.sha256(f"{amount}|{asset}|{memo}".encode()).hexdigest()[:12]
        return Receipt(True, "mock", amount, asset, ref,
                       note="sandbox — no money moved")


class ScryX402Payment:
    """The real $SCRY / x402 rail. Built to the interface, DISARMED by
    default: it refuses to charge until the operator arms it with real
    config. Arming is the custody gate, not a code path we flip silently."""

    kind = "scry-x402"

    def __init__(self, pay_to=None, facilitator=None, faucet_cap=None, armed=False):
        self.pay_to = pay_to
        self.facilitator = facilitator
        self.faucet_cap = faucet_cap
        self.armed = bool(armed and pay_to and facilitator and faucet_cap)

    def charge(self, amount, asset, memo) -> Receipt:
        if not self.armed:
            raise PaymentError(
                "the $SCRY rail is disarmed: real charges need operator config "
                "(pay_to + facilitator + faucet_cap) and an explicit arm. "
                "Custody is a gate, not a default.")
        if self.faucet_cap is not None and float(amount) > float(self.faucet_cap):
            raise PaymentError(f"amount {amount} exceeds the faucet cap {self.faucet_cap}")
        # Real settlement would go here (Permit2 / EIP-3009 through the
        # facilitator). Deliberately not implemented until armed for real.
        raise PaymentError("real settlement not wired in this build — arm + implement first")


def default_payment() -> MockPayment:
    """P1 uses the mock rail. Swapping in ScryX402Payment(armed=True) is the
    operator's P2 custody decision."""
    return MockPayment()
