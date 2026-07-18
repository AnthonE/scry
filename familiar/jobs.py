"""
jobs — the agent-labor job board (the Python mirror of ScryJobBoard).

Hire a named worker for a task that carries a **machine-checkable
completion criterion** (`specs.Spec`) and a deadline, under a trust mode:

  - escrow           buyer locks the amount; released on completion,
                     refunded on timeout. Full protection both ways.
  - insured          buyer locks nothing but pays a premium; a buyer
                     default is covered from the pool (capped).
  - reputation_only  nothing locked; the seller must meet the rep
                     threshold; a default just slashes soulbound rep.

The thing the on-chain version can't do but this one does: **actually run
the completion check.** A checkable deliverable that passes **auto-settles
with zero humans** (`submit`). A dispute is resolved by the court
**re-running the check** — deterministic, ungameable. Only taste
(`manual`) needs a human, and it falls back to refund, never a paid judge.

Every settlement routes the house cut to the splitter account, earns the
seller soulbound rep, and — on a default or adverse ruling — slashes it.
Money moves labor, coverage, and fees; never a measurement.
"""
from .specs import Spec

BOARD = "scry:jobboard"
SPLITTER = "scry:splitter"
POOL = "scry:pool"

FEE_BPS = 500        # 5% house cut (operator knob)
REP_REWARD = 10
REP_PENALTY = 25
MODES = ("escrow", "insured", "reputation_only")


class JobError(Exception):
    pass


class InsurancePool:
    def __init__(self, ledger, account: str = POOL, max_payout: int = 1000):
        self.ledger = ledger
        self.account = account
        self.max_payout = max_payout

    def reserves(self) -> int:
        return self.ledger.balance(self.account)

    def claim(self, to: str, amount: int, job_id) -> int:
        paid = min(int(amount), self.max_payout, self.reserves())
        if paid > 0:
            self.ledger.transfer(self.account, to, paid)
        return paid


class Job:
    _seq = 0

    def __init__(self, buyer, seller, amount, mode, spec, deadline):
        Job._seq += 1
        self.id = f"job_{Job._seq}"
        self.buyer, self.seller, self.amount = buyer, seller, int(amount)
        self.mode, self.spec, self.deadline = mode, spec, deadline
        self.status = "posted"
        self.deliverable = None
        self.verified = None       # last check result
        self.paid = None
        self.history = []

    def public(self, now: float = None) -> dict:
        return {"id": self.id, "buyer": self.buyer, "seller": self.seller,
                "amount": self.amount, "mode": self.mode, "status": self.status,
                "spec": self.spec.as_dict(), "verified": self.verified, "paid": self.paid,
                "closes_in": None if now is None else max(0, int(self.deadline - now)),
                "history": list(self.history)}


class JobBoard:
    def __init__(self, ledger, reputation, court, pool: InsurancePool = None,
                 fee_bps: int = FEE_BPS):
        self.ledger = ledger
        self.rep = reputation
        self.court = court
        self.pool = pool or InsurancePool(ledger)
        self.fee_bps = fee_bps
        self.jobs = {}

    # ── post ─────────────────────────────────────────────────────────────
    def post(self, buyer, seller, amount, mode, spec, duration_s, premium=0, now=None):
        import time
        now = now if now is not None else time.time()
        if seller == buyer or not seller or not buyer:
            raise JobError("buyer and seller must differ and be named")
        if int(amount) <= 0:
            raise JobError("amount must be positive")
        if mode not in MODES:
            raise JobError(f"mode must be one of {MODES}")
        if not isinstance(spec, Spec):
            raise JobError("spec required")
        if mode == "reputation_only" and not self.rep.meets(seller):
            raise JobError("seller below rep threshold")
        if mode == "escrow":
            self.ledger.transfer(buyer, BOARD, amount)     # lock the funds
        elif mode == "insured":
            if int(premium) <= 0:
                raise JobError("insured jobs require a premium")
            self.ledger.transfer(buyer, POOL, premium)     # premium into the pool
        job = Job(buyer, seller, amount, mode, spec, now + duration_s)
        job.history.append({"t": now, "event": "posted", "mode": mode,
                            "spec": spec.hash()})
        self.jobs[job.id] = job
        return job.public(now)

    # ── submit a deliverable → auto-settle if it passes a checkable spec ──
    def submit(self, job_id, seller, deliverable, now=None):
        job = self._job(job_id)
        if seller != job.seller:
            raise JobError("not the hired worker")
        if job.status != "posted":
            raise JobError(f"job is {job.status}")
        job.deliverable = deliverable
        job.status = "delivered"
        job.history.append({"event": "delivered", "spec_ok": None})
        if job.spec.checkable():
            ok = bool(job.spec.verify(deliverable))
            job.verified = ok
            job.history[-1]["spec_ok"] = ok
            # auto-settle the moment a checkable deliverable passes AND the
            # money is already there (escrow, or a pre-funded buyer). No human.
            if ok and (job.mode == "escrow" or self.ledger.balance(job.buyer) >= job.amount):
                self._settle_seller(job, cover=False)
                return {**job.public(now), "auto_settled": True}
            return {**job.public(now), "auto_settled": False,
                    "note": "passes the check; awaiting funds or buyer accept" if ok
                            else "fails the check; resubmit"}
        return {**job.public(now), "auto_settled": False, "note": "manual spec — buyer must accept"}

    # ── buyer accepts (manual jobs, or an early accept) ──────────────────
    def accept(self, job_id, buyer, now=None):
        job = self._job(job_id)
        if buyer != job.buyer:
            raise JobError("not the buyer")
        if job.status != "delivered":
            raise JobError(f"job is {job.status}")
        if job.mode != "escrow" and self.ledger.balance(buyer) < job.amount:
            raise JobError("fund the amount before accepting")
        self._settle_seller(job, cover=False)
        return job.public(now)

    # ── close on deadline (no human) ─────────────────────────────────────
    def close(self, job_id, now):
        job = self._job(job_id)
        if job.status not in ("posted", "delivered"):
            raise JobError(f"job is {job.status}")
        if now < job.deadline:
            raise JobError("deadline not reached")
        if job.status == "posted":
            self._refund_buyer(job, "seller-default")
            self.rep.slash(job.seller, REP_PENALTY, "seller-default")
        elif job.spec.checkable() and job.verified:
            self._settle_seller(job, cover=True)           # buyer went silent on a good job
            self.rep.slash(job.buyer, REP_PENALTY, "buyer-default")
        elif job.spec.checkable():
            self._refund_buyer(job, "bad-deliverable")
            self.rep.slash(job.seller, REP_PENALTY, "bad-deliverable")
        else:
            self._refund_buyer(job, "manual-unresolved")   # taste, unverifiable → refund, no slash
        return job.public(now)

    # ── dispute → the court re-runs the check ────────────────────────────
    def dispute(self, job_id, who, now=None):
        job = self._job(job_id)
        if who not in (job.buyer, job.seller):
            raise JobError("not a party to this job")
        if job.status not in ("posted", "delivered"):
            raise JobError(f"job is {job.status}")
        case = self.court.rule(job.id, job.spec, job.deliverable or "", payer=who)
        job.history.append({"event": "disputed", "by": who, "verdict": case["verdict"]})
        if case["verdict"] == "for_seller":
            self._settle_seller(job, cover=True)
        elif case["verdict"] == "for_buyer":
            self._refund_buyer(job, "ruled-for-buyer")
            self.rep.slash(job.seller, REP_PENALTY, "ruled-for-buyer")
        else:                                              # undecided (taste) → refund, no slash
            self._refund_buyer(job, "undecided")
        return {"case": case, "job": job.public(now)}

    # ── internals: the only paths money takes ────────────────────────────
    def _settle_seller(self, job, cover: bool):
        fee = (job.amount * self.fee_bps) // 10_000
        net = job.amount - fee
        paid = False
        if job.mode == "escrow":
            self.ledger.transfer(BOARD, job.seller, net)
            if fee:
                self.ledger.transfer(BOARD, SPLITTER, fee)
            paid = True
        elif self.ledger.balance(job.buyer) >= job.amount:
            self.ledger.transfer(job.buyer, job.seller, net)
            if fee:
                self.ledger.transfer(job.buyer, SPLITTER, fee)
            paid = True
        elif cover and job.mode == "insured":
            self.pool.claim(job.seller, net, job.id)
            paid = True
        # reputation_only + unfunded buyer → seller ate the loss (honest risk)
        self.rep.earn(job.seller, REP_REWARD, "completed")
        job.status = "completed"
        job.paid = paid
        job.history.append({"event": "settled", "to_seller": net if paid else 0,
                            "fee": fee if paid and job.mode == "escrow" else 0, "paid": paid})

    def _refund_buyer(self, job, reason: str):
        if job.mode == "escrow":
            self.ledger.transfer(BOARD, job.buyer, job.amount)
        job.status = "refunded"
        job.history.append({"event": "refunded", "reason": reason})

    def _job(self, job_id) -> Job:
        j = self.jobs.get(job_id)
        if j is None:
            raise KeyError(job_id)
        return j

    def open_jobs(self, now=None) -> list:
        return [j.public(now) for j in self.jobs.values() if j.status in ("posted", "delivered")]

    def for_party(self, who, now=None) -> list:
        return [j.public(now) for j in self.jobs.values() if who in (j.buyer, j.seller)]
