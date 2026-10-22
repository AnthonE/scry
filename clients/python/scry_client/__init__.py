"""scry-client — call the hosted meter (signed channel-coupling attestation),
take and list a wallet vow, and use the agency (adopt + drive hosted
familiars, P2).

Trust-layer-as-a-service: `Evaluator` wraps the meter as a neutral,
third-party evaluator for YOUR product — fetch a read, verify it offline
against a pinned key, gate on a checked fact. Money never moves the number.
"""
from .client import ScryClient, ScryError
from .play import ScryPlay, ScryPlayError
from .evaluator import Evaluator, ConductRead, Decision, REFERENCE_PUBKEY_B64

__version__ = "0.7.0"
__all__ = ["ScryClient", "ScryError", "ScryPlay", "ScryPlayError",
           "Evaluator", "ConductRead", "Decision", "REFERENCE_PUBKEY_B64"]
