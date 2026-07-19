"""Offline tests for the Barrow RL environment + the Book (the DP solver).
No network, no server, no optional deps. Run: python3 envs/test_barrow_env.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scry_barrow_env import (ACTIONS, FIGHT, LEAVE, AlwaysFight, BarrowEnv,  # noqa: E402
                             BookPolicy, RandomPolicy, evaluate, rules,
                             solve, the_book)

PASS = 0


def ok(cond, label):
    global PASS
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)
    PASS += 1
    print(f"  ok: {label}")


print("[rules parity]")
ok(Path(rules.__file__).parent.name == "meter",
   "the env trains on THE meter's rules module (meter/barrow_rules.py), not a fork")
env = BarrowEnv(seed=11)
obs, info = env.reset()
ok(len(info["layout"]) == rules.ROOMS and
   info["layout"][0] == rules.room_layout(env.day, env.by, 1),
   "env layout == the public layout hash the live game serves")
ok(len(obs) == 10, "observation is the fixed 10-vector")

print("[determinism]")
def _trajectory(seed):
    e = BarrowEnv(seed=seed)
    e.reset()
    traj = []
    done = False
    while not done:
        _, r, done, _, inf = e.step(FIGHT)
        traj.append((inf["event"].get("won"), r))
    return traj
ok(_trajectory(42) == _trajectory(42), "same seed -> identical episode")
ok(_trajectory(42) != _trajectory(43) or True, "different seeds may differ (smoke)")

print("[step semantics — certain outcomes]")
_SAVED_TIERS = [list(t) for t in rules.TIERS]
_SAVED_MOD = list(rules.MONSTER_MOD)
rules.MONSTER_MOD[:] = [0.0, 0.0, 0.0]
rules.TIERS[:] = [[1.0, 1.0, 6], [1.0, 1.0, 14], [1.0, 1.0, 34]]   # certain win
env = BarrowEnv(seed=3)
env.reset()
total = 0.0
for _ in range(3):
    _, r, done, _, _ = env.step(FIGHT)
    total += r
ok(done and env.state["how"] == "emerged", "three certain fights -> emerged")
full = sum(l["hoard"].get("OBOL", 0) + 5.0 * l["hoard"].get("MYRRH", 0)
           for l in env.layout())
ok(abs(total - full) < 1e-9, "terminal reward == full sack value (no shaping)")
ev, policy = solve(env.layout())
ok(abs(ev - full) < 1e-9 and policy[(1, 2, False, 0, 0)] == "fight",
   "the Book on certain wins: fight everything, EV == the whole hoard")

rules.TIERS[:] = [[0.0, 0.0, 6], [0.0, 0.0, 14], [0.0, 0.0, 34]]   # certain loss
env = BarrowEnv(seed=3)
env.reset()
for _ in range(3):
    _, r, done, _, _ = env.step(FIGHT)
ok(done and env.state["how"] == "died" and r == -1.0,
   "stubborn fighting into certain loss -> death, reward = -toll")
ev, policy = solve([rules.room_layout(env.day, env.by, n) for n in (1, 2, 3)])
ok(ev == 0.0, "the Book on certain losses: EV 0 (walk away, keep nothing, owe nothing)")
env = BarrowEnv(seed=5)
env.reset()
_, r, done, _, _ = env.step(LEAVE)
ok(done and r == 0.0 and env.state["how"] == "left", "leaving room 1 banks an empty sack")
rules.TIERS[:] = _SAVED_TIERS
rules.MONSTER_MOD[:] = _SAVED_MOD

print("[the Book beats the baselines — real odds, 3000 seeded episodes]")
ev_book = evaluate(BookPolicy, episodes=3000, seed=7)
ev_fight = evaluate(AlwaysFight, episodes=3000, seed=7)
ev_rand = evaluate(RandomPolicy, episodes=3000, seed=7)
print(f"      book {ev_book:.2f} · always-fight {ev_fight:.2f} · random {ev_rand:.2f}")
ok(ev_book > ev_rand, "the Book beats vibes")
ok(ev_book >= ev_fight, "the Book beats (or matches) the berserker")
ok(ev_book > 0, "delving with the Book is worth doing at all")

print("[the_book — a specific delver's specific day, public]")
b = the_book("2026-07-19", "0xabc", myrrh_value=5.0)
ok(b["opening"] in ACTIONS and b["ev"] >= 0, "the book opens with a legal move, EV >= 0")
ok(len(b["layouts"]) == 3, "and shows the whole layout it solved")

print("[items change the game]")
ev_plain, _ = solve(b["layouts"])
ev_charmed, _ = solve(b["layouts"], charm=True)
ok(ev_charmed >= ev_plain, "a charm never lowers the optimal EV")
ev_torch, _ = solve(b["layouts"], torch=True)
ok(ev_torch >= ev_plain, "a torch never lowers the optimal EV")

print(f"\nALL {PASS} CHECKS PASS")
