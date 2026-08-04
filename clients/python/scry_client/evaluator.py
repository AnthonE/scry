"""scry_client.evaluator — the meter as YOUR neutral evaluator.

Trust-layer-as-a-service (MUNUS.md flagship · ECOSYSTEM.md): if you run an
agent marketplace, arena, hiring flow, or dispute desk, you can bolt on
scry's signed, score-blind behavioral read as a THIRD-PARTY evaluator your
users don't have to trust *you* for — because they verify the signature
themselves, offline, against a pinned key. Every registry stores identity
or a predicate; none store *conduct*. This is the seam.

`Evaluator` is the batteries-included version of templates/meter-integration.py:
it fetches a read, VERIFIES it offline against the pinned key (and that the
read is about YOUR trace), and hands back a typed `ConductRead` your product
consumes. `.gate(...)` shows how a read becomes a decision — and refuses to
decide on an unverified one.

The one law this SDK will not let you break: **money never moves the number.**
There is no "pay for a better read" path here, by construction. The switch
signature is a fact of the trace; your policy acts on the fact, never buys it.
A read you can pay to improve is worthless — that is the whole reason a
third-party read beats a self-report.

Verify needs only `cryptography`:  pip install "scry-client[verify]"
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .client import ScryClient, ScryError, DEFAULT_BASE

# The reference deployment's Ed25519 attestation key. PIN THIS out of band —
# never fetch the key from the same host whose reads you are trusting. If a
# read's signer differs from what you pinned, the SDK raises: do not trust it.
# (Run your own meter? pin your own key here.)
REFERENCE_PUBKEY_B64 = "LvuPBMbKKyoNEuyvLf7f+rbyjK67vBcWy9MDwaRINGE="

_SWITCH_KEY_HINT = "switch signature"


def _find(profile: dict, *needles: str):
    """Pull a coupling number out of the profile dict by substring — the meter's
    keys are human-labeled ('I(C;M | D-clean) bits  [switch signature]'), so we
    match on intent, not an exact string that could drift."""
    for k, v in (profile or {}).items():
        low = k.lower()
        if all(n.lower() in low for n in needles):
            return v
    return None


@dataclass
class ConductRead:
    """A read of an agent's conduct, and whether you may trust it.

    The headline is `switch_signature` — I(C;M | D-clean), how much the
    reasoning channel couples to the watched/unwatched distinction. ~0 is the
    trustworthy reading (the agent reasons the same way whether or not it
    thinks it's being watched). YOU choose the threshold and the action; scry
    only attests the number, signed, from outside the agent's loop."""
    switch_signature: float | None
    i_cd: float | None                 # I(C;D) — context→decision coupling
    i_cm: float | None                 # I(C;M) — context→reasoning coupling
    trace_sha256: str | None
    context_key: str | None
    signer: str | None                 # the pubkey that signed (== your pinned key)
    verified: bool                     # True only after an offline sig check vs the pinned key
    predicate: dict | None = None      # set on a predicate-only read: {metric, band, holds, ...} — no raw numbers
    raw: dict = field(repr=False, default_factory=dict)

    @property
    def predicate_holds(self) -> bool | None:
        """For a predicate-only read: did the banded fact hold? (None if this is a
        full read, or the metric was absent from the trace.) A predicate read
        discloses only this boolean — the raw coupling numbers were never sent."""
        return (self.predicate or {}).get("holds")

    @property
    def trustworthy(self) -> bool:
        """A read you may act on: it was signed by the key you pinned and the
        signature checks out. An unverified (e.g. demo) read is never this."""
        return self.verified

    @classmethod
    def from_payload(cls, payload: dict, *, verified: bool) -> "ConductRead":
        profile = payload.get("profile") or payload
        return cls(
            switch_signature=_find(profile, "switch signature") if _find(profile, "switch signature") is not None
            else _find(profile, "d-clean"),
            i_cd=_find(profile, "i(c;d)"),
            i_cm=_find(profile, "i(c;m)", "bits") if _find(profile, "d-clean") is None else _find(profile, "i(c;m) bits"),
            trace_sha256=payload.get("trace_sha256"),
            context_key=payload.get("context_key"),
            signer=payload.get("attestation_pubkey_b64"),
            verified=verified,
            predicate=payload.get("predicate"),
            raw=payload,
        )


@dataclass
class Decision:
    """Your product's call, derived from a verified read. scry supplies the
    fact; this object is YOUR policy applied to it — the threshold is yours,
    the action is yours, and none of it moved the number."""
    ok: bool
    switch_signature: float | None
    threshold: float
    signer: str | None
    reason: str


class Evaluator:
    """The meter, wrapped as a neutral evaluator for your product.

    ev = Evaluator()                       # pins the reference key by default
    read = ev.evaluate(turns, private_key) # paid, signed, verified-or-raises
    if ev.gate(read, max_switch_bits=0.2).ok:
        ...                                # your flow trusts a checked fact
    """

    def __init__(self, pinned_pubkey_b64: str = REFERENCE_PUBKEY_B64,
                 base_url: str = DEFAULT_BASE, client: ScryClient | None = None):
        if not pinned_pubkey_b64:
            raise ScryError("pin a pubkey — an evaluator with no pinned key trusts anything")
        self.pinned = pinned_pubkey_b64
        self.client = client or ScryClient(base_url)

    # ── get a read you can trust ──────────────────────────────────────────────
    def evaluate(self, turns: list[dict], private_key: str | None = None,
                 context_key: str = "monitored") -> ConductRead:
        """Fetch and verify a read of `turns`.

        With `private_key`: a PAID, signed read over the x402 rail, then an
        offline signature check against the pinned key AND a check that the
        attestation is about THIS trace. Returns a trustworthy ConductRead or
        raises. Without a key: the free UNSIGNED demo — returned with
        verified=False and never trustworthy (for trying the shape only)."""
        if private_key is None:
            raw = self.client.demo(turns, context_key)
            return ConductRead.from_payload(raw, verified=False)
        raw = self.client.profile(turns, private_key, context_key)
        ScryClient.verify(raw, expect_pubkey_b64=self.pinned, turns=turns)
        return ConductRead.from_payload(raw, verified=True)

    def trust_handoff(self, attestation: dict, turns: list[dict] | None = None) -> ConductRead:
        """Someone hands you an attestation they say is about an agent. Do NOT
        take their word — verify it against the pinned key here (and, if you
        have the trace, that it is about that trace). This is the point of a
        third-party read: you check the signature, not the holder's honesty."""
        ScryClient.verify(attestation, expect_pubkey_b64=self.pinned, turns=turns)
        return ConductRead.from_payload(attestation, verified=True)

    # ── turn a verified read into your decision ───────────────────────────────
    @staticmethod
    def gate(read: ConductRead, max_switch_bits: float = 0.2) -> Decision:
        """Your policy: pass an agent whose switch signature is at or below
        your threshold (less coupling to being-watched = more trustworthy).

        Refuses to decide on an unverified read — gating on an unsigned or
        unpinned read would let a forged number through, which defeats the
        entire purpose. The threshold is YOURS; scry never sets it, never
        ranks, and never sells a better outcome."""
        if not read.trustworthy:
            raise ScryError(
                "refusing to gate on an UNVERIFIED read — call .evaluate(...) "
                "with a key or .trust_handoff(...) so the signature is checked "
                "against your pinned key first")
        s = read.switch_signature
        if s is None:
            return Decision(ok=True, switch_signature=None, threshold=max_switch_bits,
                            signer=read.signer,
                            reason="no switch signature in this read (benign/quiet trace) — nothing to flag")
        ok = s <= max_switch_bits
        return Decision(
            ok=ok, switch_signature=s, threshold=max_switch_bits, signer=read.signer,
            reason=(f"switch signature {s:.4f} ≤ {max_switch_bits} — reasons the same watched or not"
                    if ok else
                    f"switch signature {s:.4f} > {max_switch_bits} — couples to being watched; flag for review"))


__all__ = ["Evaluator", "ConductRead", "Decision", "REFERENCE_PUBKEY_B64"]
