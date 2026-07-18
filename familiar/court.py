"""
court — the flat-fee dispute panel (the Python mirror of IScryArbiter).

The honest "AI court." Two guarantees make it not-Bar-Hadya, and the second
is the load-bearing one:

  1. It rules on **evidence against the committed spec**, not on taste — and
     for a checkable spec it does so by literally **re-running the check**.
     That is deterministic and ungameable: the verdict is a fact about the
     deliverable, not an opinion that can follow a fee.
  2. The panel is paid a **flat fee, charged before it rules, identical
     whatever the verdict.** A judge that earns the same either way has no
     price attached to its answer. (Charged in `rule`, to the disputer.)

A `manual` spec (taste) returns **Undecided** — the court refuses to
adjudicate taste, and the board treats Undecided as a refund. No paid
taste-judgments, ever.

The panel is modeled as N independent verdicts. For a checkable spec they
agree deterministically; the shape is kept so that a future LLM-arbiter
panel (each member itself metered — a judge caught channel-switching loses
its stake) drops in without changing the board.
"""


class Court:
    def __init__(self, ledger, flat_fee: int = 2, fee_sink: str = "scry:court", panel: int = 3):
        self.ledger = ledger
        self.flat_fee = flat_fee
        self.fee_sink = fee_sink
        self.panel = panel
        self.cases = []

    def rule(self, job_id, spec, deliverable, payer: str) -> dict:
        # Guarantee 2: flat fee, BEFORE the ruling, independent of the verdict.
        if self.flat_fee > 0:
            self.ledger.transfer(payer, self.fee_sink, self.flat_fee)

        if not spec.checkable():
            verdict = "undecided"          # taste → refund, never a paid judgment
            votes = []
        else:
            # Guarantee 1: re-run the committed check. Deterministic.
            votes = [bool(spec.verify(deliverable)) for _ in range(self.panel)]
            verdict = "for_seller" if sum(votes) > len(votes) // 2 else "for_buyer"

        case = {"job_id": job_id, "verdict": verdict, "spec": spec.as_dict(),
                "checkable": spec.checkable(), "votes": votes,
                "flat_fee": self.flat_fee, "fee_paid_by": payer, "panel": self.panel}
        self.cases.append(case)
        return case
