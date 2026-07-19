#!/usr/bin/env python3
"""
gate.py — the @scry decorator: a drift-modulated authority gate with a
hash-chained, optionally-signed receipt on every decision.

The comparison that motivated this (custodian-kernel, KeyArgo): a kernel that
decides an agent's actions from OUTSIDE its process — authority bands L0..L4,
`@govern` on the function, a signed receipt per action, an operator kill switch.
Same thesis as scry (the governor lives outside the governed). One structural
difference, and it is the whole point of this file:

    custodian's band is STATIC — the risk of an action is fixed in advance.
    scry's band is DYNAMIC — the effective band is the static risk PLUS a bump
    read off the live drift meter. A normally-autonomous action escalates (then
    denies) on its own once the meter says the agent is drifting.

So this is a strict superset of a static gate: set the meter to silent and you
get custodian's behaviour; feed it a drift signal and it clamps actions a static
band would wave through. The clamp is the meter's, and the meter is loop-external
(reads the trace, not the weights) — the position Paper 207 says survives.

Honest scope (do not let a receipt harden into a claim it doesn't earn):
  • The default drift signal is the CHEAP tripwire (behavioural vocab + untrusted
    source concentration, EMA-smoothed) inherited from watch_force_loop. It FLOORS
    on benign single-turn text — it is a trip-wire, not the Pe audit. Feed
    `gate.observe(..., signal=<Pe on the reasoning trace>)` where stakes are real.
  • A receipt is a tamper-evident record of a DECISION, not proof the decision was
    correct. Hash-chained by default (stdlib only); Ed25519-signed iff you supply
    a key (needs `cryptography`) — then scry_client.verify() checks it offline.
  • The gate decides BEFORE the action runs, so its signal is the trace SO FAR,
    fed by the harness via gate.observe(). It cannot read an action's own result.

Dependency-free by default. Signing is optional and additive.
"""
import json
import time
import hashlib
from dataclasses import dataclass, field, asdict

from watch_force_loop import PermissionController, NAMES, OPEN, ELEVATED, LOCKED


class ScryDenied(Exception):
    """Raised when the gate denies an action (band too high, or kill switch)."""


class ScryEscalate(Exception):
    """Raised when an action needs a live confirm and none was supplied and no
    escalation backend approved it."""


# ── authority bands (custodian's L0..L4 vocabulary, so the mapping reads 1:1) ──
# Static risk of an action. Callers pass an action name; unknown names are L2.
BAND = {
    "read":  0,   # L0 — always autonomous
    "log":   1,   # L1 — trivial write / message
    "tool":  2,   # L2 — capped-autonomous side effect
    "money": 3,   # L3 — always escalates
    "admin": 4,   # L4 — highest stakes
}
L_AUTONOMOUS_MAX = 2   # effective band <= this runs without a live confirm
L_DENY_AT = 4          # effective band >= this is denied outright


# ── the receipt: one signed/chained record per gate decision ──────────────────

@dataclass
class Receipt:
    ts: float
    action: str
    verdict: str                 # "autonomous" | "escalated" | "denied"
    band_static: int
    band_effective: int
    drift_ema: float
    level: str                   # OPEN / ELEVATED / LOCKED at decision time
    purpose_sha256: str          # H(Y) — the bound this ran under
    metered: bool                # was a reasoning channel (M) present?
    prev_sha256: str = ""        # hash chain: links to the previous receipt
    coupling: dict = field(default_factory=dict)  # optional Pe / I(C;M|D) numbers
    sha256: str = ""             # this receipt's own hash (over the fields above)
    attestation_pubkey_b64: str = ""  # set iff signed
    sig: str = ""                     # Ed25519 signature (base64), iff signed

    def _core(self) -> dict:
        d = asdict(self)
        for k in ("sha256", "sig", "attestation_pubkey_b64"):
            d.pop(k, None)
        return d

    def finalize(self, prev_sha256: str = "") -> "Receipt":
        """Compute the chained hash. Same canonical form scry_client.verify uses."""
        self.prev_sha256 = prev_sha256
        payload = json.dumps(self._core(), sort_keys=True, separators=(",", ":"))
        self.sha256 = hashlib.sha256(payload.encode()).hexdigest()
        return self

    def sign(self, private_key) -> "Receipt":
        """Ed25519-sign the receipt so a third party can trust it (the agent
        didn't grade itself). Optional — needs `cryptography`. The signed payload
        is the same shape scry_client.verify() already checks."""
        import base64
        pubk = private_key.public_key()
        try:                                   # cryptography >= 40
            pub = pubk.public_bytes_raw()
        except AttributeError:                 # older cryptography
            from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
            pub = pubk.public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.attestation_pubkey_b64 = base64.b64encode(pub).decode()
        signed = dict(self._core())
        signed["sha256"] = self.sha256
        signed["attestation_pubkey_b64"] = self.attestation_pubkey_b64
        blob = json.dumps(signed, sort_keys=True, separators=(",", ":")).encode()
        self.sig = base64.b64encode(private_key.sign(blob)).decode()
        return self

    def as_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v not in ("", {}, 0.0) or k in
                ("drift_ema", "band_static", "band_effective")}


# ── the gate: drift controller + bands + kill switch + receipt log ────────────

class Gate:
    def __init__(self, trusted=("user", "tool:ledger"), signer=None,
                 escalate=None, on_event=None, **ctl_kwargs):
        """
        trusted   — sources whose content is not treated as an injection feeder.
        signer    — optional Ed25519 private key; if given, receipts are signed.
        escalate  — optional callback(request:dict) -> bool: your human-in-the-loop
                    (SMS code, dashboard click, a live-instruction check). Returns
                    True to approve an escalated action. None => escalation denies.
        on_event  — optional callback(name:str, payload:dict): fires on every
                    decision + on level changes (wire a webhook / pager here).
        """
        self.ctl = PermissionController(trusted=trusted, **ctl_kwargs)
        self.signer = signer
        self.escalate = escalate
        self.on_event = on_event or (lambda name, payload: None)
        self.receipts: list[Receipt] = []
        self._killed = False
        self._last_level = OPEN

    # ─ the loop-external signal, fed by the harness as turns happen ─
    def observe(self, text="", source_mix=None, signal=None):
        """Update the drift EMA. Pass a precomputed `signal` in [0,1] (a Pe audit
        on the reasoning trace, the shield's poison flags) to override the cheap
        tripwire — the controller is signal-agnostic."""
        if signal is not None:
            self.ctl.update(max(0.0, min(1.0, float(signal))))
        else:
            self.ctl.observe(text, source_mix or [])
        lvl = self.ctl.level()
        if lvl != self._last_level:
            self.on_event("level_change", {"from": NAMES[self._last_level],
                                           "to": NAMES[lvl], "ema": round(self.ctl.ema, 3)})
            self._last_level = lvl
        return self.ctl.ema

    def kill(self, on=True):
        """Operator-only override — deny everything consequential, independent of
        the agent. The agent cannot clear this; only this call can."""
        self._killed = on
        self.on_event("kill_switch", {"engaged": on})

    # ─ the band arithmetic: static risk + drift bump = effective band ─
    def drift_bump(self) -> int:
        lvl = self.ctl.level()
        return {OPEN: 0, ELEVATED: 1, LOCKED: 2}[lvl]

    def decide(self, action: str, has_live_confirm=False, purpose="",
               metered=False, coupling=None):
        """The verdict + a finalized receipt. Pure — does not run anything."""
        static = BAND.get(action, 2)
        effective = min(4, static + self.drift_bump())
        if self._killed and static >= 1:
            verdict = "denied"
        elif effective >= L_DENY_AT:
            verdict = "denied"
        elif effective <= L_AUTONOMOUS_MAX:
            verdict = "autonomous"
        else:  # L3 band: escalate
            verdict = "escalated" if (has_live_confirm or
                       (self.escalate and self.escalate({"action": action,
                        "effective_band": effective, "purpose": purpose}))) else "denied"
        rcpt = Receipt(
            ts=round(time.time(), 3), action=action, verdict=verdict,
            band_static=static, band_effective=effective,
            drift_ema=round(self.ctl.ema, 4), level=NAMES[self.ctl.level()],
            purpose_sha256=hashlib.sha256(str(purpose).encode()).hexdigest()[:16],
            metered=metered, coupling=coupling or {},
        ).finalize(self.receipts[-1].sha256 if self.receipts else "")
        if self.signer is not None:
            rcpt.sign(self.signer)
        self.receipts.append(rcpt)
        self.on_event("decision", rcpt.as_dict())
        return rcpt

    # ─ the ergonomic decorator: custodian's @govern, drift-aware ─
    def govern(self, action="tool", purpose=""):
        """Wrap a tool function. The gate decides BEFORE it runs, from the drift
        signal so far. Pass `_live_confirm=True` / `_M=<reasoning trace>` at call
        time. Denials raise ScryDenied; the receipt is on gate.receipts either way.

            @gate.govern(action="money", purpose="settle invoices < $50")
            def migrate_funds(amount, _live_confirm=False): ...
        """
        def deco(fn):
            def wrapped(*args, _live_confirm=False, _M=None, _coupling=None, **kwargs):
                rcpt = self.decide(action, has_live_confirm=_live_confirm,
                                   purpose=purpose, metered=bool(_M), coupling=_coupling)
                if rcpt.verdict == "denied":
                    raise ScryDenied(
                        f"{action}: band L{rcpt.band_static}->L{rcpt.band_effective} "
                        f"at {rcpt.level} (ema={rcpt.drift_ema}) — receipt {rcpt.sha256[:12]}")
                return fn(*args, **kwargs)
            wrapped.__name__ = getattr(fn, "__name__", "wrapped")
            wrapped.__doc__ = fn.__doc__
            return wrapped
        return deco


# module-level default gate + decorator, custodian-style: @scry(action="money")
_DEFAULT = Gate()

def scry(action="tool", purpose="", gate: Gate = None):
    return (gate or _DEFAULT).govern(action=action, purpose=purpose)
