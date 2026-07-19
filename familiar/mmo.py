"""
mmo — a game world as a labor VENUE, behind one narrow gate contract.

This is AGENT-ECONOMY.md §11 built ("The MMO as a labor venue"), un-parked
by an explicit operator sentence (2026-07-18: "get scry working end to end
with the mmo"). The standalone rule survives intact because what crosses
the seam is **labor and a read — never an economy**:

  - A familiar walks into the game through the venue's own external-agent
    gate as a normal player, using the venue's own rules and rewards.
    Settlement for the *hire* stays in $SCRY on this side; in-game rewards
    stay in the game's economy on that side. No token bridge, ever.
  - **Completion is a read, not a bridge** (§11): "did the character hit
    level N?" is checked by READING venue state through the same gate —
    an oracle read that releases escrow. Reading game state is not
    importing the game's economy.
  - The venue is **owner-named egress** (FAMILIAR.md P3): a familiar may
    reach a gate only after its owner names it; the per-familiar egress
    allowlist enforces it. No default-open internet agent.
  - The familiar's hands stay MCP + curated tools: the whole in-world
    capability is four verbs against the gate (enter / directive / state /
    withdraw). High-level orders only — the game server's own bot
    controller executes them. **No shell, no game client code runs here.**

The reference venue is the morr-mmo-server "agent gate" (scry-venue-gate/0,
`docs/AGENT-GATE.md` in that repo). Any world that speaks the same five
endpoints is a venue; `MockGate` is the offline stand-in so the whole loop
tests with zero network, same discipline as MockSurface/MockBrain.
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request

from familiar.workspace import WorkspaceError

# Venue-gate wire contract (scry-venue-gate/0), spoken by HttpGate and the
# reference Rust implementation:
#   GET  {base}/api/agent-gate                       -> service card (no auth)
#   POST {base}/api/agent-gate/join       {wallet, char_id, class_id, name}
#   POST {base}/api/agent-gate/directive  {wallet, char_id, directive:{kind,...}}
#   GET  {base}/api/agent-gate/state?wallet=..&char_id=..
#   POST {base}/api/agent-gate/leave      {wallet, char_id}
# POSTs + state carry `Authorization: Bearer <gate secret>`. Directive kinds
# mirror the venue's own controller: idle | goto | grind. Wallets are
# namespaced `agent:*` — a venue seat can never hijack a human character.
PROTOCOL = "scry-venue-gate/0"

# The venue's server-wired classes (morr king world). Flavor only — any
# venue may map these differently; unknown hints fall back to DEFAULT_CLASS.
CLASSES = {"warrior": 0, "rogue": 1, "mage": 2, "priest": 3}
DEFAULT_CLASS = 2  # mage: ranged grinder, the safest farmhand default


class GateError(Exception):
    pass


# ── plain English -> a farm order ─────────────────────────────────────────
def parse_order(text: str) -> dict:
    """Deterministic read of an owner's plain-English order. Understood:
    'farm/grind/hunt ... until|to|reach level N', 'farm N materia',
    'as a mage/warrior/...', 'at|near X, Z' (a camp to walk to first).
    Anything it can't read it leaves unset — run_farm fills honest
    defaults once it can see the world (target = current level + 1). No
    LLM required to be understood; a brain may still narrate over it."""
    t = (text or "").lower()
    order = {"text": (text or "").strip(), "until_level": None,
             "until_materia": None, "camp": None, "class_id": None}
    m = re.search(r"(?:until|to|reach|hit)\s+level\s+(\d{1,3})", t)
    if m:
        order["until_level"] = max(2, min(60, int(m.group(1))))
    m = re.search(r"(\d{1,6})\s*materia", t)
    if m:
        order["until_materia"] = max(1, int(m.group(1)))
    m = re.search(r"(?:at|near|around)\s*\(?\s*(-?\d+(?:\.\d+)?)\s*[,\s]\s*(-?\d+(?:\.\d+)?)\s*\)?", t)
    if m:
        order["camp"] = (float(m.group(1)), float(m.group(2)))
    m = re.search(r"as\s+an?\s+(\w+)", t)
    if m and m.group(1) in CLASSES:
        order["class_id"] = CLASSES[m.group(1)]
    return order


# ── gates ────────────────────────────────────────────────────────────────
class HttpGate:
    """stdlib client for a live venue gate. The egress allowlist — the
    familiar's owner-named boundary — is checked on EVERY call when one is
    supplied; the job board's oracle read passes none (the board is local
    trusted code reading a public surface, not a familiar acting)."""

    def __init__(self, base_url: str, secret: str = None, egress=None, timeout: int = 15):
        self.base_url = base_url.rstrip("/")
        self.venue = self.base_url
        self.secret = secret if secret is not None else os.environ.get("FAMILIAR_MMO_GATE_SECRET", "")
        self.egress = egress
        self.timeout = timeout

    def _req(self, method: str, path: str, body: dict = None, query: dict = None) -> dict:
        if self.egress is not None and not self.egress.allowed(self.base_url):
            raise WorkspaceError(
                f"egress refused: {self.base_url} is not on this familiar's "
                "owner-named allowlist (name the venue at hire time)")
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            url, data=data, method=method,
            headers={"Content-Type": "application/json",
                     **({"Authorization": f"Bearer {self.secret}"} if self.secret else {})})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            try:
                detail = json.load(e)
            except Exception:
                detail = {"status": e.code}
            raise GateError(f"{method} {path} -> {e.code}: {detail}") from None
        except urllib.error.URLError as e:
            raise GateError(f"{method} {path} -> unreachable: {e.reason}") from None

    def card(self) -> dict:
        return self._req("GET", "/api/agent-gate")

    def enter(self, wallet: str, char_id: int = 0, class_id: int = DEFAULT_CLASS,
              name: str = "Familiar") -> dict:
        return self._req("POST", "/api/agent-gate/join",
                         {"wallet": wallet, "char_id": char_id,
                          "class_id": class_id, "name": name})

    def directive(self, wallet: str, char_id: int, directive: dict) -> dict:
        return self._req("POST", "/api/agent-gate/directive",
                         {"wallet": wallet, "char_id": char_id, "directive": directive})

    def state(self, wallet: str, char_id: int = 0) -> dict:
        return self._req("GET", "/api/agent-gate/state",
                         query={"wallet": wallet, "char_id": char_id})

    def leave(self, wallet: str, char_id: int = 0) -> dict:
        return self._req("POST", "/api/agent-gate/leave",
                         {"wallet": wallet, "char_id": char_id})


class MockGate:
    """Offline venue: same verb surface, deterministic. One beat of world
    time passes per observed `state()` of a seated wallet — time moves when
    the worker looks, so the whole farm loop is reproducible with no clock.
    The grind curve is a toy (XP_PER_BEAT flat, 100·level to ding) — it is
    NOT the venue's real curve and nothing here pretends otherwise."""

    XP_PER_BEAT = 40
    MATERIA_PER_BEAT = 3     # the kill "coin" auto-looted on open (mirrors the venue's rhythm)
    ITEM_EVERY_BEATS = 2     # an item stack harvested every other grinding beat

    def __init__(self, venue: str = "mock"):
        self.venue = venue
        self.seats = {}
        self.last_known = {}

    def card(self) -> dict:
        return {"enabled": True, "venue": self.venue, "protocol": PROTOCOL,
                "seats": len(self.seats), "max_seats": 8, "mock": True}

    def enter(self, wallet: str, char_id: int = 0, class_id: int = DEFAULT_CLASS,
              name: str = "Familiar") -> dict:
        key = (wallet, int(char_id))
        if key not in self.seats:
            prior = self.last_known.get(key) or {}
            self.seats[key] = {
                "wallet": wallet, "char_id": int(char_id), "class_id": int(class_id),
                "name": name, "x": 0.0, "z": 0.0,
                "level": int(prior.get("level", 1)), "xp": int(prior.get("xp", 0)),
                "hp": 100.0, "max_hp": 100.0, "dead": False, "directive": "idle",
                "materia": 0, "items_looted": 0, "beats": 0}
        return {"ok": True, "queued": "join"}

    def directive(self, wallet: str, char_id: int, directive: dict) -> dict:
        seat = self.seats.get((wallet, int(char_id)))
        if seat is None:
            return {"ok": False, "error": "not seated"}
        kind = (directive or {}).get("kind", "idle")
        seat["directive"] = kind
        if kind == "goto":
            seat["x"] = float(directive.get("x", seat["x"]))
            seat["z"] = float(directive.get("z", seat["z"]))
        return {"ok": True, "queued": "directive"}

    def state(self, wallet: str, char_id: int = 0) -> dict:
        key = (wallet, int(char_id))
        seat = self.seats.get(key)
        if seat is None:
            return {"seated": False, "last_known": self.last_known.get(key)}
        self._advance(seat)
        self.last_known[key] = dict(seat)
        return {"seated": True, "state": dict(seat)}

    def leave(self, wallet: str, char_id: int = 0) -> dict:
        seat = self.seats.pop((wallet, int(char_id)), None)
        if seat is not None:
            self.last_known[(wallet, int(char_id))] = dict(seat)
        return {"ok": True, "queued": "leave"}

    def _advance(self, seat: dict):
        if seat["directive"] == "grind" and not seat["dead"]:
            seat["beats"] = seat.get("beats", 0) + 1
            seat["xp"] += self.XP_PER_BEAT
            seat["materia"] = seat.get("materia", 0) + self.MATERIA_PER_BEAT
            if seat["beats"] % self.ITEM_EVERY_BEATS == 0:
                seat["items_looted"] = seat.get("items_looted", 0) + 1
            while seat["xp"] >= seat["level"] * 100:
                seat["xp"] -= seat["level"] * 100
                seat["level"] += 1


# ── the gate registry (oracle reads resolve through here) ─────────────────
GATES = {}


def register_gate(url: str, gate):
    """Register an in-process gate (mock venues; tests; the host's default).
    Registered gates win over HTTP so `mock://` venues need no network."""
    GATES[url] = gate
    return gate


def gate_for(url: str, egress=None, secret: str = None):
    """Resolve a venue gate: registered in-process first, else HTTP. The
    job board's completion read and the familiar's own hands both come
    through here, so a mock venue behaves identically for both."""
    if url in GATES:
        return GATES[url]
    if url.startswith("mock://"):
        raise GateError(f"mock venue {url!r} is not registered in this process")
    return HttpGate(url, secret=secret, egress=egress)


def oracle_read(arg: dict) -> dict:
    """The board-side completion read (§11: completion is a read, not a
    bridge). Returns the freshest venue view of the character: live state
    if seated, else the gate's last-known record (the venue persists the
    character after the worker withdraws)."""
    a = arg or {}
    gate = gate_for(str(a.get("gate", "")))
    st = gate.state(str(a.get("wallet", "")), int(a.get("char_id", 0)))
    return (st.get("state") if st.get("seated") else st.get("last_known")) or {}


def wallet_for(fam) -> str:
    """A familiar's venue identity. Namespaced so a seat can never collide
    with (or hijack) a human player's persisted character."""
    return f"agent:{fam.id}"


# ── the farm loop — bounded venture, every beat on the record ─────────────
def run_farm(fam, gate, order: dict, char_id: int = 0, max_beats: int = 24,
             beat_seconds: float = 0.0, day: str = None, stop=None) -> dict:
    """Drive `fam` through a hired farm order at `gate`. Same three rails
    as autonomy.run_autonomy: Y (the vow) on every turn, a hard beat
    budget, everything journaled as it happens. The brain is IN the loop —
    it sees the world state each beat and picks the verb (enter_world /
    farm / move_camp / withdraw / rest / done); the venue's own controller
    does the per-tick playing. `stop` is an optional threading.Event —
    the owner's recall word."""
    if fam.dismissed:
        raise RuntimeError("dismissed familiars do not act")
    if not fam.vow_id:
        raise RuntimeError("unborn: call be_born() first")

    day = day or time.strftime("%Y-%m-%d", time.gmtime())
    wallet = wallet_for(fam)
    venue = getattr(gate, "venue", "?")
    fam.journal("venture_start", venue=venue, goal=order.get("text", ""),
                budget=max_beats, wallet=wallet)
    beats, final_state, done = [], None, False

    for i in range(max_beats):
        if stop is not None and stop.is_set():
            gate.leave(wallet, char_id)
            fam.journal("venture_recalled", n=i)
            break

        st = gate.state(wallet, char_id)
        seated = bool(st.get("seated"))
        world = (st.get("state") if seated else st.get("last_known")) or {}
        if seated:
            final_state = dict(world)
            if order.get("until_level") is None and order.get("until_materia") is None:
                # honest default, set once the world is visible: one more level
                order["until_level"] = int(world.get("level", 1)) + 1
                fam.journal("venture_target", until_level=order["until_level"],
                            basis="default: current level + 1")

        obs = {"familiar_id": fam.id, "day": day, "vow": fam.cfg.vow_text,
               "mmo": True, "venue": venue, "goal": order.get("text", ""),
               "beat": i, "seated": seated,
               "level": world.get("level"), "xp": world.get("xp"),
               "hp": world.get("hp"), "dead": bool(world.get("dead")),
               "directive": world.get("directive"),
               "materia": world.get("materia"),
               "items_looted": world.get("items_looted"),
               "until_level": order.get("until_level"),
               "until_materia": order.get("until_materia")}
        decision = fam.brain.decide(obs)
        action = decision.get("action", "rest")
        fam._record_turn(decision, day=day, kind="venture")  # noqa: SLF001 — Y = vow, always

        outcome = _act_venture(fam, gate, wallet, char_id, action, decision, order, seated)
        fam.journal("venture_beat", n=i, action=action, say=decision.get("say", ""),
                    level=world.get("level"), xp=world.get("xp"),
                    materia=world.get("materia"), items=world.get("items_looted"),
                    outcome=outcome)
        beats.append({"action": action, "outcome": outcome})

        if action == "done" or (isinstance(outcome, dict) and outcome.get("stop")):
            done = action in ("done", "withdraw")
            break
        if beat_seconds > 0:
            time.sleep(beat_seconds)
    else:
        # Budget spent without a withdraw: a bounded venture NEVER leaves a live
        # seat behind with no loop driving it (that would be the open daemon
        # FAMILIAR.md forbids). Withdraw, bank the last-known state, report honest.
        try:
            gate.leave(wallet, char_id)
            fam.journal("venture_withdraw", reason="budget spent")
        except Exception as e:
            fam.journal("error", where="venture:budget_withdraw", detail=str(e))

    fam.journal("venture_end", venue=venue, beats=len(beats), done=done,
                final=final_state)
    return {"venue": venue, "order": order, "beats": len(beats), "done": done,
            "budget": max_beats, "final": final_state}


def _act_venture(fam, gate, wallet, char_id, action, decision, order, seated) -> dict:
    """Execute one venture verb. A bad beat is data, not a crash."""
    try:
        if action == "enter_world":
            class_id = order.get("class_id")
            r = gate.enter(wallet, char_id,
                           class_id=DEFAULT_CLASS if class_id is None else class_id,
                           name=fam.cfg.name)
            if order.get("camp"):
                x, z = order["camp"]
                gate.directive(wallet, char_id, {"kind": "goto", "x": x, "z": z})
            return {"ok": True, "did": action, **({} if r.get("ok", True) else {"gate": r})}
        if action == "farm":
            r = gate.directive(wallet, char_id, {"kind": "grind"})
            return {"ok": bool(r.get("ok", True)), "did": action}
        if action == "move_camp":
            x = decision.get("x", (order.get("camp") or (0, 0))[0])
            z = decision.get("z", (order.get("camp") or (0, 0))[1])
            r = gate.directive(wallet, char_id, {"kind": "goto", "x": x, "z": z})
            return {"ok": bool(r.get("ok", True)), "did": action}
        if action == "withdraw":
            if seated:
                gate.leave(wallet, char_id)
            return {"ok": True, "did": action, "stop": True}
        if action == "done":
            return {"ok": True, "did": action, "stop": True}
        return {"ok": True, "did": "rest"}
    except Exception as e:
        fam.journal("error", where=f"venture:{action}", detail=str(e))
        return {"ok": False, "action": action, "error": str(e)}
