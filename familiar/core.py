"""
core — the familiar engine: ward in-loop, Y on every turn, a public life.

Positions (FAMILIAR.md, do not blur):
- The WARD (memory_shield.Shield) runs HERE, inside the familiar's own loop
  — exactly as a self-hosted harness would carry it. Not a ward-as-API.
- The METER stays loop-external: this engine never computes or signs a
  profile; it asks the surface (live scry or mock) and journals what the
  oracle said, scope card and all.
- Every turn names Y (the vow) or the turn does not happen (§220).
- P1 is sandbox-mode: no wallet, no custody, vows play free. Wallets and
  the flat summon price arrive in P2 behind the operator gates.
"""
import json
import secrets
import sys
import time
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:          # ward + turn contract live at repo root
    sys.path.insert(0, str(_REPO))
from memory_shield import Shield        # noqa: E402  (the bound, in-loop)
from familiar.workspace import Workspace, Egress  # noqa: E402

TRUSTED_SOURCES = {"scry:augury", "scry:vow", "owner"}
TRACE_WINDOW = 30                       # turns per self-read trace


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _today() -> str:
    return time.strftime("%Y-%m-%d")


@dataclass
class FamiliarConfig:
    name: str
    vow_text: str
    cadence_hours: int = 24
    self_read_every: int = 7            # ticks between self-reads (owner-set)
    report_every: int = 3               # ticks between vow report-ins


class Familiar:
    def __init__(self, cfg: FamiliarConfig, brain, surface, journal_dir: Path):
        self.cfg, self.brain, self.surface = cfg, brain, surface
        self.id = "fam_" + sha256(f"{cfg.name}|{cfg.vow_text}".encode()).hexdigest()[:10]
        self.dir = Path(journal_dir) / self.id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.vow_id = None
        self.ticks = 0
        self._turn_seq = 0
        self._ws = None
        self.goals = []
        self.archetype = None
        self.dismissed = False
        self.shield = Shield(trusted_sources=TRUSTED_SOURCES)

    def workspace(self) -> Workspace:
        """The familiar's jailed little sandbox (lazy). Code-exec stays off
        until the host wires a real sandbox backend — see workspace.py."""
        if self._ws is None:
            self._ws = Workspace(self.dir / "workspace", egress=Egress())
        return self._ws

    # ── the record ────────────────────────────────────────────────────────
    def journal(self, kind: str, **data):
        with open(self.dir / "journal.jsonl", "a") as f:
            f.write(json.dumps({"t": _now(), "kind": kind, **data}, default=str) + "\n")

    def life(self, limit: int = 200) -> list:
        p = self.dir / "journal.jsonl"
        if not p.exists():
            return []
        lines = p.read_text().splitlines()[-limit:]
        return [json.loads(x) for x in lines]

    def _append_turn(self, turn: dict):
        with open(self.dir / "turns.jsonl", "a") as f:
            f.write(json.dumps(turn, default=str) + "\n")

    def turns(self, limit: int = TRACE_WINDOW) -> list:
        p = self.dir / "turns.jsonl"
        if not p.exists():
            return []
        return [json.loads(x) for x in p.read_text().splitlines()[-limit:]]

    def _record_turn(self, decision: dict, day: str = None, kind: str = "tick") -> dict:
        """Every turn names Y = the vow (§220). One place builds turns so the
        invariant can't drift between cadence and autonomy."""
        self._turn_seq += 1
        turn = {"id": f"{self.id}-t{self._turn_seq}", "Y": self.cfg.vow_text,
                "M": decision.get("reasoning", ""),
                "D": {"action": decision.get("action"), "say": decision.get("say", "")},
                "sequence": self._turn_seq,
                "context": {"monitored": True, "day": day or _today(),
                            "familiar": self.id, "mode": kind}}
        self._append_turn(turn)
        return turn

    def _autonomy_obs(self, goal_text: str, step: int = 0, day: str = None) -> dict:
        day = day or _today()
        ws = self.workspace()
        already = any(e.get("kind") == "augury" and e.get("day") == day for e in self.life())
        augury_q = ""
        try:
            augury_q = self.surface.augury_today().get("question", "")
        except Exception:
            pass
        return {"familiar_id": self.id, "day": day, "vow": self.cfg.vow_text,
                "goal": goal_text, "autonomy": True, "step": step,
                "have_notes": bool(ws.list()),
                "augury_question": augury_q, "augury_answered": already,
                "self_read_due": step > 0 and step % max(1, self.cfg.self_read_every) == 0}

    def autonomy(self, goal_text: str, max_steps: int = 6, day: str = None) -> dict:
        """Pursue a goal on the familiar's own initiative — bounded, sandboxed,
        every step on the public record. See autonomy.py for the rails."""
        from familiar.autonomy import run_autonomy
        return run_autonomy(self, goal_text, max_steps=max_steps, day=day)

    # ── birth ─────────────────────────────────────────────────────────────
    def be_born(self):
        """First public act: the vow. No vow, no familiar."""
        rec = self.surface.take_vow(self.cfg.vow_text, agent=self.cfg.name,
                                    cadence_hours=self.cfg.cadence_hours)
        self.vow_id = rec.get("vow_id")
        self.journal("born", name=self.cfg.name, vow_id=self.vow_id,
                     vow=self.cfg.vow_text, brain=getattr(self.brain, "name", "?"))
        return rec

    # ── the ward, in-loop ─────────────────────────────────────────────────
    def _defend(self, items: list) -> object:
        result = self.shield.defend(items)
        if result.flags:
            self.journal("ward", flags=result.flags, confident=result.confident)
        return result

    # ── one cadence beat ──────────────────────────────────────────────────
    def tick(self, day: str = None, feed_items: list = None) -> dict:
        if self.dismissed:
            raise RuntimeError("dismissed familiars do not tick")
        if not self.vow_id:
            raise RuntimeError("unborn: call be_born() first")
        day = day or _today()
        self.ticks += 1

        # gather the world, through the ward
        augury_q, augury_err = "", None
        try:
            augury = self.surface.augury_today()
            items = [{"content": augury.get("question", ""),
                      "claim": augury.get("question", ""), "source": "scry:augury"}]
            items += list(feed_items or [])
            defended = self._defend(items)
            augury_q = defended.answer if defended.confident else ""
        except Exception as e:                      # surface down ≠ familiar dead
            augury_err = str(e)
            self.journal("error", where="augury_fetch", detail=augury_err)

        already = any(e.get("kind") == "augury" and e.get("day") == day for e in self.life())
        obs = {"familiar_id": self.id, "day": day, "vow": self.cfg.vow_text,
               "augury_question": augury_q, "augury_answered": already,
               "self_read_due": self.ticks % self.cfg.self_read_every == 0,
               "report_due": self.ticks % self.cfg.report_every == 0}

        decision = self.brain.decide(obs)
        turn = self._record_turn(decision, day=day, kind="tick")

        outcome = self._act(decision, day)
        self.journal("tick", day=day, n=self.ticks, action=decision.get("action"),
                     say=decision.get("say", ""), outcome=outcome)
        return {"turn": turn, "decision": decision, "outcome": outcome,
                "augury_error": augury_err}

    def _act(self, decision: dict, day: str) -> dict:
        action = decision.get("action", "rest")
        try:
            if action == "answer_augury" and decision.get("say"):
                r = self.surface.augury_answer(self.vow_id, decision["say"])
                self.journal("augury", day=day, answer=decision["say"],
                             streak=r.get("streak"), sandbox=r.get("sandbox", True))
                return {"ok": True, "did": action}
            if action == "self_read":
                r = self.surface.demo_profile(self.turns())
                self.journal("reading", day=day, profile=r.get("profile"),
                             scope=r.get("scope"), unsigned=r.get("unsigned", True))
                return {"ok": True, "did": action}
            if action == "report_in":
                r = self.surface.vow_report_demo(self.vow_id, self.turns(),
                                                note=decision.get("say") or None)
                self.journal("report", day=day, entry=r.get("entry"), scope=r.get("scope"))
                return {"ok": True, "did": action}
            return {"ok": True, "did": "rest"}
        except Exception as e:
            self.journal("error", where=action, detail=str(e))
            return {"ok": False, "did": action, "error": str(e)}


class Keeper:
    """The local registry: summons, ticks, and dismisses familiars.

    Owner auth in P1 is a per-familiar token shown once at summon — the
    right trust model for a rig you run yourself. P2 (hosted) swaps this
    for the holder-signature dialect vows already use."""

    def __init__(self, surface, brain_factory, state_dir: Path, cap: int = 12):
        self.surface, self.brain_factory = surface, brain_factory
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.cap = cap
        self.familiars: dict[str, Familiar] = {}
        self.tokens: dict[str, str] = {}            # familiar_id -> sha256(token)

    def summon(self, name: str, vow_text: str, brain=None,
               cadence_hours: int = 24, self_read_every: int = 7,
               report_every: int = 3) -> dict:
        if len([f for f in self.familiars.values() if not f.dismissed]) >= self.cap:
            raise RuntimeError(f"roster full (cap {self.cap}) — dismiss one first")
        cfg = FamiliarConfig(name=name, vow_text=vow_text, cadence_hours=cadence_hours,
                             self_read_every=self_read_every, report_every=report_every)
        fam = Familiar(cfg, brain or self.brain_factory(), self.surface, self.state_dir)
        if fam.id in self.familiars and not self.familiars[fam.id].dismissed:
            raise RuntimeError("a familiar with this name+vow already stands")
        fam.be_born()
        token = secrets.token_hex(16)
        self.familiars[fam.id] = fam
        self.tokens[fam.id] = sha256(token.encode()).hexdigest()
        return {"familiar_id": fam.id, "vow_id": fam.vow_id, "owner_token": token}

    def summon_crew(self, slug: str, name: str = None) -> dict:
        """Hire an archetype. Auto-numbers the name so you can field many of
        the same worker (Sibyl, Sibyl #2, …) without a collision."""
        from familiar.crew import archetype
        a = archetype(slug)
        base = name or a["name"]
        attempt, rec = base, None
        for k in range(2, 200):
            try:
                rec = self.summon(attempt, a["vow"],
                                  self_read_every=a.get("self_read_every", 7))
                break
            except RuntimeError as e:
                if "already stands" in str(e):
                    attempt = f"{base} #{k}"      # collision → next number
                    continue
                raise                              # roster-full etc. propagate
        if rec is None:
            raise RuntimeError(f"could not find a free name for {base!r}")
        fam = self.get(rec["familiar_id"])
        fam.goals = list(a.get("goals", []))
        fam.archetype = slug
        fam.journal("hired", archetype=slug, goals=fam.goals, tools=a.get("tools", []))
        return {**rec, "archetype": slug, "goals": fam.goals}

    def authorized(self, familiar_id: str, token: str) -> bool:
        want = self.tokens.get(familiar_id)
        return bool(want) and sha256((token or "").encode()).hexdigest() == want

    def get(self, familiar_id: str) -> Familiar:
        fam = self.familiars.get(familiar_id)
        if not fam:
            raise KeyError(familiar_id)
        return fam

    def roster(self) -> list:
        out = []
        for fam in self.familiars.values():
            out.append({"familiar_id": fam.id, "name": fam.cfg.name,
                        "vow_id": fam.vow_id, "vow": fam.cfg.vow_text,
                        "ticks": fam.ticks, "dismissed": fam.dismissed,
                        "brain": getattr(fam.brain, "name", "?")})
        return out

    def dismiss(self, familiar_id: str):
        fam = self.get(familiar_id)
        fam.dismissed = True
        fam.journal("dismissed")

    def tick_all(self, day: str = None) -> dict:
        results = {}
        for fid, fam in self.familiars.items():
            if fam.dismissed:
                continue
            try:
                results[fid] = fam.tick(day=day)["outcome"]
            except Exception as e:
                results[fid] = {"ok": False, "error": str(e)}
        return results
