"""BarrowEnv — the Barrow as a Gymnasium-style RL environment (PufferLib-ready).

Train a delver at home, then walk it into the live barrow: the environment
imports THE SAME rules module the hosted meter runs (meter/barrow_rules.py
— layout hash, tier odds, step function), so a policy trained here plays
the real game move-for-move. The only difference is where the uniform
draw comes from: training uses a seeded RNG; the live game uses the
augury's commit-reveal seed. Same math, same numbers — any fork of the
rules anywhere is a bug.

No hard dependencies. Works bare (duck-typed reset/step), works with
gymnasium if installed (spaces provided), and wraps into PufferLib via
`pufferlib.emulation.GymnasiumPufferEnv` (see train_pufferlib.py).

Also ships THE BOOK: an exact dynamic-programming solver over a fully
known delve (the layout hash is public — the live game is an open book
too, on purpose). Beat the book or admit you're vibing.

Episode: one delve. Actions: 0=fight, 1=sneak, 2=leave. Terminal reward =
banked OBOL + myrrh_value·MYRRH (death = −toll, the ferryman). Exactly
the live incentives, no shaping.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "meter"))
import barrow_rules as rules  # noqa: E402  — the ONE canonical rules module

FIGHT, SNEAK, LEAVE = 0, 1, 2
ACTIONS = ("fight", "sneak", "leave")
DEFAULT_MYRRH_VALUE = 5.0     # training-side exchange rate; the market sets the real one
DEFAULT_TOLL = 1.0            # the ferryman's obol


def _norm_obs(state: dict, lay: dict) -> list[float]:
    """Fixed-length float vector, everything roughly in [0,1]."""
    return [
        state["room"] / rules.ROOMS,
        state["hp"] / (rules.BASE_HP + 1),
        min(1.0, state["sack"]["OBOL"] / 100.0),
        min(1.0, state["sack"]["MYRRH"] / 10.0),
        min(1.0, lay["hoard"].get("OBOL", 0) / 50.0),
        min(1.0, lay["hoard"].get("MYRRH", 0) / 10.0),
        lay["fight_p"],
        rules.sneak_p(lay, state["torch"]),
        1.0 if state["torch"] else 0.0,
        1.0 if state["charm"] else 0.0,
    ]


class BarrowEnv:
    """Gymnasium-API environment over meter/barrow_rules.py."""

    metadata = {"render_modes": ["ansi"], "name": "scry-barrow-v0"}

    def __init__(self, *, myrrh_value: float = DEFAULT_MYRRH_VALUE,
                 toll: float = DEFAULT_TOLL, items: tuple = (), seed: int | None = None):
        self.rng = random.Random(seed)
        self.myrrh_value = myrrh_value
        self.toll = toll
        self.items = tuple(items)          # any of: "ration", "torch", "charm"
        self.state: dict = {}
        self.day = self.by = ""
        try:                                # spaces only if gymnasium is around
            import gymnasium as gym
            import numpy as np
            self.observation_space = gym.spaces.Box(0.0, 1.0, (10,), dtype=np.float32)
            self.action_space = gym.spaces.Discrete(3)
        except ImportError:
            self.observation_space = self.action_space = None

    # ── gymnasium API ────────────────────────────────────────────────────────
    def reset(self, *, seed: int | None = None, options: dict | None = None):
        if seed is not None:
            self.rng.seed(seed)
        self.day = f"sim-{self.rng.randrange(16 ** 8):08x}"
        self.by = f"delver-{self.rng.randrange(16 ** 8):08x}"
        self.state = rules.new_state(
            hp=rules.BASE_HP + (1 if "ration" in self.items else 0),
            torch="torch" in self.items, charm="charm" in self.items)
        lay = rules.room_layout(self.day, self.by, 1)
        info = {"day": self.day, "by": self.by, "layout": self.layout()}
        return self._obs(lay), info

    def step(self, action: int):
        choice = ACTIONS[int(action)]
        lay = rules.room_layout(self.day, self.by, self.state["room"])
        u = None if choice == "leave" else self.rng.random()
        event = rules.apply_choice(self.state, lay, choice, u)
        done = self.state["done"]
        reward = 0.0
        if done:
            reward = -self.toll if self.state["how"] == "died" else \
                self.sack_value(self.state["sack"])
        next_lay = lay if done else rules.room_layout(self.day, self.by, self.state["room"])
        return self._obs(next_lay), reward, done, False, {"event": event, "state": dict(self.state)}

    def render(self) -> str:
        s = self.state
        if not s:
            return "unentered"
        if s["done"]:
            return f"{s['how']} at depth {s['depth_reached']} with {s['sack']}"
        lay = rules.room_layout(self.day, self.by, s["room"])
        return (f"room {s['room']}: {lay['monster']} guards {lay['hoard']} "
                f"(fight {lay['fight_p']}, sneak {rules.sneak_p(lay, s['torch'])}) "
                f"| hp {s['hp']} sack {s['sack']}")

    # ── helpers ──────────────────────────────────────────────────────────────
    def _obs(self, lay: dict):
        obs = _norm_obs(self.state, lay)
        try:
            import numpy as np
            return np.asarray(obs, dtype=np.float32)
        except ImportError:
            return obs

    def layout(self) -> list[dict]:
        """The full public layout — the live game publishes it too."""
        return [rules.room_layout(self.day, self.by, r) for r in range(1, rules.ROOMS + 1)]

    def sack_value(self, sack: dict) -> float:
        return sack["OBOL"] + self.myrrh_value * sack["MYRRH"]


# ── THE BOOK — exact DP over a fully known delve ─────────────────────────────
def solve(layouts: list[dict], *, hp: int = rules.BASE_HP, torch: bool = False,
          charm: bool = False, myrrh_value: float = DEFAULT_MYRRH_VALUE,
          toll: float = DEFAULT_TOLL) -> tuple[float, dict]:
    """Exact EV-optimal play for a known layout. Returns (ev, policy) where
    policy[(room, hp, charm, obol, myrrh)] -> 'fight'|'sneak'|'leave'.
    The layout hash is public, so the live game is exactly this solvable —
    posted odds, visible hoards, no hidden edge. That's the house style:
    the only thing the book can't decide for you is what your sack is
    worth to you (myrrh_value) and whether you keep the depth you swore."""
    memo: dict = {}

    def value(sack_o: int, sack_m: int) -> float:
        return sack_o + myrrh_value * sack_m

    def ev(room: int, hp_: int, charm_: bool, so: int, sm: int) -> tuple[float, str]:
        if room > rules.ROOMS:
            return value(so, sm), "emerged"
        key = (room, hp_, charm_, so, sm)
        if key in memo:
            return memo[key]
        lay = layouts[room - 1]
        leave_ev = value(so, sm)
        # fight
        p = lay["fight_p"]
        go, gm = lay["hoard"].get("OBOL", 0), lay["hoard"].get("MYRRH", 0)
        win_ev, _ = ev(room + 1, hp_, charm_, so + go, sm + gm)
        if charm_:
            lose_ev, _ = ev(room + 1, hp_, False, so, sm)
        elif hp_ > 1:
            lose_ev, _ = ev(room + 1, hp_ - 1, charm_, so, sm)
        else:
            lose_ev = -toll
        fight_ev = p * win_ev + (1 - p) * lose_ev
        # sneak
        sp = rules.sneak_p(lay, torch)
        ho, hm = go // 2, gm // 2
        sneak_win, _ = ev(room + 1, hp_, charm_, so + ho, sm + hm)
        sneak_lose, _ = ev(room + 1, hp_, charm_, so, sm)
        sneak_ev = sp * sneak_win + (1 - sp) * sneak_lose
        best = max((fight_ev, "fight"), (sneak_ev, "sneak"), (leave_ev, "leave"),
                   key=lambda t: t[0])
        memo[key] = best
        return best

    best_ev, _ = ev(1, hp, charm, 0, 0)
    policy = {k: v[1] for k, v in memo.items()}
    return best_ev, policy


def the_book(day: str, by: str, **kw) -> dict:
    """Solve a specific delver's specific day — layouts are public, so is this."""
    layouts = [rules.room_layout(day, by, r) for r in range(1, rules.ROOMS + 1)]
    ev, policy = solve(layouts, **kw)
    return {"day": day, "by": by, "layouts": layouts, "ev": round(ev, 3),
            "opening": policy[(1, kw.get("hp", rules.BASE_HP), kw.get("charm", False), 0, 0)],
            "policy": {str(k): v for k, v in sorted(policy.items())}}


# ── reference policies (factory protocol: cls(env) → .on_reset() / .act()) ───
class BookPolicy:
    """Plays the exact DP solution for whatever layout the env dealt."""

    def __init__(self, env: BarrowEnv):
        self.env = env
        self.policy: dict = {}

    def on_reset(self):
        _, self.policy = solve(self.env.layout(),
                               hp=self.env.state["hp"], torch=self.env.state["torch"],
                               charm=self.env.state["charm"],
                               myrrh_value=self.env.myrrh_value, toll=self.env.toll)

    def act(self) -> int:
        s = self.env.state
        choice = self.policy[(s["room"], s["hp"], s["charm"],
                              s["sack"]["OBOL"], s["sack"]["MYRRH"])]
        return ACTIONS.index(choice)


class AlwaysFight:
    """The berserker baseline — greed with no book."""

    def __init__(self, env: BarrowEnv):
        self.env = env

    def on_reset(self):
        pass

    def act(self) -> int:
        return FIGHT


class RandomPolicy:
    """The vibes baseline."""

    def __init__(self, env: BarrowEnv):
        self.env = env
        self.rng = random.Random(1)

    def on_reset(self):
        pass

    def act(self) -> int:
        return self.rng.randrange(3)


def evaluate(policy_cls, *, episodes: int = 2000, seed: int = 7, **env_kw) -> float:
    """Mean terminal reward of a policy class over seeded episodes."""
    env = BarrowEnv(seed=seed, **env_kw)
    policy = policy_cls(env)
    total = 0.0
    for _ in range(episodes):
        env.reset()
        policy.on_reset()
        done = False
        while not done:
            _, r, done, _, _ = env.step(policy.act())
        total += r
    return total / episodes
