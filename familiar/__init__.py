"""
familiar — summon a hosted player (P1: local-first).

Design of record: ../FAMILIAR.md. The familiar is a PLAYER of scry, never
part of the instrument: the ward runs inside its own loop (this package),
the meter stays loop-external (it pays /profile like any stranger, or uses
the free /demo path). Every turn names Y (§220) or it doesn't happen.
"""
from .core import Familiar, FamiliarConfig, Keeper
from .brain import MockBrain, HttpBrain
from .surface import MockSurface, HttpSurface

__version__ = "0.1.0"
__all__ = ["Familiar", "FamiliarConfig", "Keeper",
           "MockBrain", "HttpBrain", "MockSurface", "HttpSurface"]
