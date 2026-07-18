"""scry-client — call the hosted scry meter (signed channel-coupling
attestation) and play the fun layer (augury / duels / table / arena)."""
from .client import ScryClient, ScryError
from .play import ScryPlay, ScryPlayError

__version__ = "0.2.0"
__all__ = ["ScryClient", "ScryError", "ScryPlay", "ScryPlayError"]
