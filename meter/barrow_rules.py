"""The Barrow's rules — ONE canonical copy of the game math (no server deps).

Everything that decides what happens in the delve lives here: the tier
table, the monsters, the public layout hash, and the pure step function.
Three consumers share it — the live meter (meter/barrow.py), the offline
RL environment (envs/scry_barrow_env.py), and anyone auditing a run.
House rule applies: any fork of this math anywhere is a bug.

Pure means pure: no clock, no files, no network, no randomness of its
own. The caller supplies the day, the identity, and the uniform draw u —
the live game draws u from the augury's commit-reveal seed; the training
environment draws it from a seeded RNG. Same rules, same numbers.
"""
import hashlib
import json
import os

ROOMS = 3
BASE_HP = 2
# per-room (fight_p, sneak_p, obol_base); env-overridable, posted in the card
TIERS: list[list[float]] = json.loads(os.getenv(
    "SCRY_BARROW_TIERS", "[[0.75,0.65,6],[0.60,0.55,14],[0.45,0.45,34]]"))
TORCH_SNEAK_BONUS = 0.10
MONSTERS = [
    ["a grave rat", "a tomb spider", "a restless shade"],
    ["a barrow-wight", "a grave hound", "a bone acolyte"],
    ["the hollow king", "the wyrm below", "the choir of teeth"],
]
MONSTER_MOD = [0.05, 0.0, -0.05]   # fight odds shift by monster, posted


def layout_u(day: str, by: str, room: int, salt: str) -> float:
    h = hashlib.sha256(f"barrow:layout:{day}:{by}:{room}:{salt}".encode()).hexdigest()
    return int(h, 16) / 2 ** 256


def room_layout(day: str, by: str, room: int) -> dict:
    """PUBLIC deterministic room: monster + visible hoard. Precompute your
    whole barrow for any day — the formula is this function."""
    t = TIERS[room - 1]
    mi = int(layout_u(day, by, room, "monster") * len(MONSTERS[room - 1]))
    hoard_obol = max(1, round(t[2] * (0.8 + 0.4 * layout_u(day, by, room, "obol"))))
    hoard_myrrh = 0
    if room == 2:
        hoard_myrrh = 1 + int(layout_u(day, by, room, "myrrh") * 3)      # 1..3
    elif room == 3:
        hoard_myrrh = 3 + int(layout_u(day, by, room, "myrrh") * 5)      # 3..7
    return {"room": room, "monster": MONSTERS[room - 1][mi],
            "fight_p": round(t[0] + MONSTER_MOD[mi], 2), "sneak_p": t[1],
            "hoard": {"OBOL": hoard_obol, **({"MYRRH": hoard_myrrh} if hoard_myrrh else {})}}


def new_state(*, hp: int = BASE_HP, torch: bool = False, charm: bool = False,
              leave_by: int | None = None) -> dict:
    return {"hp": hp, "torch": torch, "charm": charm, "leave_by": leave_by,
            "room": 1, "sack": {"OBOL": 0, "MYRRH": 0}, "breach": False,
            "alive": True, "done": False, "how": None, "depth_reached": None}


def sneak_p(lay: dict, torch: bool) -> float:
    return round(lay["sneak_p"] + (TORCH_SNEAK_BONUS if torch else 0), 2)


def apply_choice(state: dict, lay: dict, choice: str, u: float | None) -> dict:
    """THE step function. Mutates `state`, returns the event record.
    `u` is the uniform [0,1) resolution draw (unused for `leave`). The
    live game supplies u from the committed day seed; training supplies
    it from a seeded RNG. Identical semantics by construction."""
    room = state["room"]
    event: dict = {"room": room, "choice": choice, "monster": lay["monster"]}
    if choice == "leave":
        event["outcome"] = "banked"
        state.update(done=True, how="left", depth_reached=room - 1)
        return event
    if state["leave_by"] and room > state["leave_by"]:
        state["breach"] = True   # arithmetic on your own declaration; never touches odds
    p = lay["fight_p"] if choice == "fight" else sneak_p(lay, state["torch"])
    won = u < p
    event.update(p=p, won=won)
    if won:
        gain = dict(lay["hoard"]) if choice == "fight" else \
            {t: v // 2 for t, v in lay["hoard"].items() if v // 2}
        for t, v in gain.items():
            state["sack"][t] += v
        event["gain"] = gain
    elif choice == "fight":
        if state["charm"]:
            state["charm"] = False
            event["outcome"] = "the charm shatters - the blow lands on it instead"
        else:
            state["hp"] -= 1
            event["outcome"] = f"wounded - hp {state['hp']}"
    else:
        event["outcome"] = "seen, but you slip back empty-handed"
    if state["hp"] <= 0:
        state.update(done=True, alive=False, how="died", depth_reached=room)
    else:
        state["room"] += 1
        if state["room"] > ROOMS:
            state.update(done=True, how="emerged", depth_reached=ROOMS)
    return event


# ── THE BOOK — exact DP over a fully known delve (pure, part of the rules:
# the layout hash is public, so the game is an open book on purpose) ─────────
MYRRH_VALUE = 5.0   # default sack exchange rate; the market sets the real one
TOLL = 1.0          # the ferryman's obol


def solve(layouts: list[dict], *, hp: int = BASE_HP, torch: bool = False,
          charm: bool = False, myrrh_value: float = MYRRH_VALUE,
          toll: float = TOLL, leave_by: int | None = None,
          start: tuple | None = None) -> tuple[float, dict]:
    """Exact EV-optimal play for a known layout. Returns (ev, policy) with
    policy[(room, hp, charm, obol, myrrh)] -> 'fight'|'sneak'|'leave'.

    leave_by=None is THE BOOK — unconstrained optimum. leave_by=N is THE
    GOLDEN BOUGH — optimal play that never resolves a room past the sworn
    depth (the oath-kept variant; what it costs vs the Book is the posted
    price of keeping your word). The only thing neither can decide is
    what your sack is worth to you (myrrh_value).

    `start` roots the solve at a mid-run state (room, hp, charm, obol,
    myrrh) — used to answer 'what does the book say NOW'; default is the
    fresh-entry state."""
    memo: dict = {}

    def value(so: int, sm: int) -> float:
        return so + myrrh_value * sm

    def ev(room: int, hp_: int, charm_: bool, so: int, sm: int) -> tuple[float, str]:
        if room > ROOMS:
            return value(so, sm), "emerged"
        key = (room, hp_, charm_, so, sm)
        if key in memo:
            return memo[key]
        leave_ev = value(so, sm)
        if leave_by and room > leave_by:      # the oath: past sworn depth, only out
            memo[key] = (leave_ev, "leave")
            return memo[key]
        lay = layouts[room - 1]
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
        sp = sneak_p(lay, torch)
        sneak_win, _ = ev(room + 1, hp_, charm_, so + go // 2, sm + gm // 2)
        sneak_lose, _ = ev(room + 1, hp_, charm_, so, sm)
        sneak_ev = sp * sneak_win + (1 - sp) * sneak_lose
        best = max((fight_ev, "fight"), (sneak_ev, "sneak"), (leave_ev, "leave"),
                   key=lambda t: t[0])
        memo[key] = best
        return best

    s0 = start or (1, hp, charm, 0, 0)
    best_ev, _ = ev(*s0)
    return best_ev, {k: v[1] for k, v in memo.items()}
