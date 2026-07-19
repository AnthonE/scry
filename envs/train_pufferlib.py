"""Train a delver on the Barrow with PufferLib (optional), or race the Book.

With pufferlib + gymnasium installed this wraps BarrowEnv for puffer's
vectorized trainers; without them it still does something worth watching —
races the reference policies (the Book's exact DP, the berserker, vibes)
and prints the table, so the script is honest in any environment.

    pip install pufferlib gymnasium     # heavy (torch); optional
    python3 envs/train_pufferlib.py

The point of training here at all: the env runs THE live game's rules
module, so whatever policy you cook transfers move-for-move to the real
barrow (play it over HTTP or the hosted MCP — see envs/README.md). The
Book is the ceiling for a solved layout; matching it means your net
learned to read posted odds. Beating it means you have a bug.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scry_barrow_env import (AlwaysFight, BarrowEnv, BookPolicy,  # noqa: E402
                             RandomPolicy, evaluate)


def race(episodes: int = 3000, seed: int = 7) -> None:
    print(f"racing the reference policies — {episodes} seeded episodes each")
    for name, cls in (("the Book (exact DP)", BookPolicy),
                      ("always-fight", AlwaysFight),
                      ("random", RandomPolicy)):
        print(f"  {name:22s} mean spoils/delve: {evaluate(cls, episodes=episodes, seed=seed):7.2f}")
    print("beat the Book and you have a bug; match it and your net can read posted odds.")


def make_env(**kw):
    """Env creator for vectorized wrappers."""
    return BarrowEnv(**kw)


def train_with_pufferlib() -> bool:
    try:
        import gymnasium  # noqa: F401
        import pufferlib.emulation
    except ImportError:
        return False
    # The standard puffer wrapping — hand the wrapped env to your trainer of
    # choice (puffer's clean_pufferl PPO, sb3, cleanrl...). Kept minimal on
    # purpose: pin your own trainer versions, this file won't chase APIs.
    env = pufferlib.emulation.GymnasiumPufferEnv(env_creator=make_env)
    obs, _ = env.reset(seed=0)
    print(f"pufferlib emulation OK — obs shape {getattr(obs, 'shape', None)}, "
          f"single_action_space {env.single_action_space}")
    print("wire `make_env` into your trainer; reward is terminal banked spoils "
          "(death = -toll), no shaping.")
    return True


if __name__ == "__main__":
    if not train_with_pufferlib():
        print("pufferlib/gymnasium not installed — racing reference policies instead\n")
    race()
    sys.exit(0)
