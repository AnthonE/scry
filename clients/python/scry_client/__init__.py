"""scry-client — call the hosted scry meter (signed channel-coupling attestation)."""
from .client import ScryClient, ScryError

__version__ = "0.1.0"
__all__ = ["ScryClient", "ScryError"]
