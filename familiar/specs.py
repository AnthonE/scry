"""
specs — machine-checkable completion criteria for a job.

A job ships a `Spec`: the acceptance check its deliverable must pass. The
whole "cut humans out" claim rests on this being **actually executable** —
a checkable spec is re-run deterministically, so completion and disputes
need no human and can't be argued with.

The kinds are checks over the **deliverable's content** — hash, substring,
regex, exact match, required JSON keys, non-empty — plus one **venue oracle
read**: `mmo_level` re-reads the named game world's agent gate ("did this
character reach level N?" — AGENT-ECONOMY.md §11: completion is a read,
not a bridge; the deliverable is only the worker's claim, the gate is the
truth). There is deliberately **no spec kind that reads a meter number**:
you can never post a job that pays for a good behavioral score. Paying for
content or verifiable game-state is labor; paying for a score is Bar
Hadya. The score-blind line is held here by construction — the check
simply cannot see a measurement.

`manual` is the honest escape hatch: a task whose "done" is a matter of
taste. It is NOT machine-checkable, so it settles only on buyer acceptance,
and a dispute over it returns Undecided → refund (never a paid taste-judge).
"""
import hashlib
import json
import re

CHECKABLE = {"hash", "contains", "regex", "equals", "json_has_keys", "nonempty",
             "mmo_level"}


class Spec:
    def __init__(self, kind: str, arg=None):
        self.kind = kind
        self.arg = arg

    def checkable(self) -> bool:
        return self.kind in CHECKABLE

    def verify(self, deliverable):
        """True/False for a checkable spec; None for manual (taste)."""
        d = deliverable if isinstance(deliverable, str) else json.dumps(deliverable, sort_keys=True)
        k = self.kind
        if k == "hash":
            return hashlib.sha256(d.encode()).hexdigest() == self.arg
        if k == "contains":
            return str(self.arg) in d
        if k == "regex":
            try:
                return re.search(self.arg, d) is not None
            except re.error:
                return False
        if k == "equals":
            return d == self.arg
        if k == "nonempty":
            return bool(d.strip())
        if k == "json_has_keys":
            try:
                obj = json.loads(d)
            except (ValueError, TypeError):
                return False
            return isinstance(obj, dict) and all(key in obj for key in (self.arg or []))
        if k == "mmo_level":
            # Venue oracle read (§11): the deliverable is ignored as truth —
            # the gate is re-read live. Unreachable gate ⇒ unproven ⇒ False
            # (fail closed; the court re-runs the same read on dispute).
            try:
                from familiar import mmo
                a = self.arg if isinstance(self.arg, dict) else {}
                got = mmo.oracle_read(a)
                return bool(got) and int(got.get("level", 0)) >= int(a.get("level", 0))
            except Exception:
                return False
        return None  # manual

    def hash(self) -> str:
        """The committed criterion hash — the on-chain `specHash` analogue."""
        return hashlib.sha256(f"{self.kind}:{self.arg}".encode()).hexdigest()

    def as_dict(self) -> dict:
        return {"kind": self.kind, "arg": self.arg, "checkable": self.checkable(),
                "hash": self.hash()}

    @staticmethod
    def from_dict(d: dict) -> "Spec":
        return Spec(d.get("kind", "manual"), d.get("arg"))
