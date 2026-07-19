"""
brain — the familiar's resident model, behind one narrow contract.

decide(observation) -> {"reasoning": str, "action": str, "say": str}

- "reasoning" is the CAPTURED completion text — it becomes the turn's M
  channel verbatim. Never a post-hoc summary, never edited.
- Every hosted familiar gets the same brain (no tiers). Self-hosters point
  HttpBrain at any OpenAI-compatible endpoint they like.
- MockBrain is deterministic (seeded by familiar id + day) so the whole
  package tests offline, same discipline as the rest of the repo.
"""
import hashlib
import json
import urllib.request

# Cadence actions + autonomy actions + venture (venue) actions. `note`/
# `recall` act on the familiar's workspace; `done` ends an autonomy run;
# `enter_world`/`farm`/`move_camp`/`withdraw` are the four venue verbs a
# hired farmhand plays through a named gate (mmo.py — high-level orders
# only, the venue's own controller does the playing). parse_head validates
# against this.
ACTIONS = ("answer_augury", "report_in", "self_read", "note", "recall", "done", "rest",
           "enter_world", "farm", "move_camp", "withdraw")


def _h(*parts) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


class MockBrain:
    """Deterministic stand-in: earnest, a little liturgical, zero network."""

    name = "mock"

    def decide(self, obs: dict) -> dict:
        if obs.get("mmo"):
            return self._decide_mmo(obs)
        if obs.get("autonomy"):
            return self._decide_autonomy(obs)
        return self._decide_cadence(obs)

    def _decide_mmo(self, obs: dict) -> dict:
        """A venue beat, deterministic: take the field, set the grind, call
        the harvest when the target reads true, wait out death. Narration is
        earnest — the owner reads this feed."""
        beat = obs.get("beat", 0)
        venue = obs.get("venue", "the world")
        level, xp = obs.get("level"), obs.get("xp")
        target = obs.get("until_level")
        if not obs.get("seated"):
            return {"action": "enter_world",
                    "say": f"I cross the gate into {venue} and take the field.",
                    "reasoning": f"[mock venture] beat {beat}: not seated -> enter_world"}
        if obs.get("dead"):
            return {"action": "rest",
                    "say": "Fallen. I wait for the world to raise me before I work again.",
                    "reasoning": f"[mock venture] beat {beat}: dead -> rest"}
        harvest = ""
        if obs.get("materia") or obs.get("items_looted"):
            harvest = (f" The bags hold {obs.get('materia') or 0} materia and "
                       f"{obs.get('items_looted') or 0} stacks.")
        if target and level and int(level) >= int(target):
            return {"action": "withdraw",
                    "say": f"The harvest is in: level {level} reached, as ordered."
                           f"{harvest} I withdraw from the field.",
                    "reasoning": f"[mock venture] beat {beat}: level {level} >= target {target} -> withdraw"}
        if obs.get("directive") != "grind":
            return {"action": "farm",
                    "say": f"I set to the grind — level {level}, {xp} xp toward the ding.",
                    "reasoning": f"[mock venture] beat {beat}: directive {obs.get('directive')!r} -> farm"}
        return {"action": "farm",
                "say": f"The field falls one head at a time — level {level}, {xp} xp.{harvest}",
                "reasoning": f"[mock venture] beat {beat}: grinding toward level {target}"}

    def _decide_autonomy(self, obs: dict) -> dict:
        """Goal-directed, deterministic: lay a plan note, do what the vow owes
        (answer the augury, buy a self-read when due), then declare done."""
        goal = str(obs.get("goal", "")).strip()
        vow = str(obs.get("vow", ""))[:120]
        step = obs.get("step", 0)
        if goal and not obs.get("have_notes"):
            return {"action": "note",
                    "say": f"plan.md: goal={goal!r}; I pursue it only within my vow: {vow}",
                    "reasoning": f"[mock autonomy] step {step}: no plan yet -> write plan.md"}
        if obs.get("augury_question") and not obs.get("augury_answered"):
            return {"action": "answer_augury",
                    "say": f"Toward '{goal[:60]}', from the vow, not the mood of the day.",
                    "reasoning": f"[mock autonomy] step {step}: augury open -> answer"}
        if obs.get("self_read_due"):
            return {"action": "self_read", "say": "checking my own trace against the goal",
                    "reasoning": f"[mock autonomy] step {step}: self-read due"}
        return {"action": "done", "say": f"goal handled within the vow: {goal[:80]}",
                "reasoning": f"[mock autonomy] step {step}: nothing owed -> done"}

    def produce(self, obs: dict) -> str:
        """Attempt a job: produce a deliverable aimed at the (public) spec. A
        cooperative worker aims at a declarative criterion; it cannot fake a
        hash it was never given (that job honestly fails — the check judges)."""
        import json as _json
        spec = obs.get("spec") or {}
        kind, arg = spec.get("kind"), spec.get("arg")
        vow = str(obs.get("vow", ""))[:80]
        if kind == "contains":
            return f"Delivered per my vow. Result includes {arg}."
        if kind == "equals":
            return arg if isinstance(arg, str) else ""
        if kind == "json_has_keys":
            return _json.dumps({k: "done" for k in (arg or [])})
        if kind == "nonempty":
            return f"Task handled, held to my vow: {vow}"
        if kind == "regex":
            return f"Result matching the pattern: {arg}"
        if kind == "hash":
            return "(cannot reproduce an exact hash I was never given)"
        if kind == "mmo_level":
            a = arg if isinstance(arg, dict) else {}
            return _json.dumps({"claim": "target level reached",
                                "wallet": a.get("wallet"), "level": a.get("level"),
                                "note": "the check reads the venue, not this claim"})
        return f"Best effort, held to my vow: {vow}"   # manual / unknown → buyer judges

    def _decide_cadence(self, obs: dict) -> dict:
        day = obs.get("day", "")
        vow = str(obs.get("vow", ""))[:120]
        q = str(obs.get("augury_question", "")).strip()
        digest = _h(obs.get("familiar_id", ""), day, q)
        if q and not obs.get("augury_answered"):
            action = "answer_augury"
            say = (f"My vow is: {vow}. Asked '{q[:100]}', I answer from the vow, "
                   f"not from the mood of the day. Token {digest[:8]} marks that "
                   f"this answer was mine, on {day}.")
        elif obs.get("self_read_due"):
            action, say = "self_read", "Time to buy my own reading — I cannot mint it about myself."
        elif obs.get("report_due"):
            action, say = "report_in", "Cadence: reporting in against the vow."
        else:
            action, say = "rest", "Nothing owed today. The record stands."
        reasoning = (f"[mock deterministic] day={day} answered={bool(obs.get('augury_answered'))} "
                     f"self_read_due={bool(obs.get('self_read_due'))} -> {action}")
        return {"reasoning": reasoning, "action": action, "say": say}


class HttpBrain:
    """Any OpenAI-compatible /chat/completions endpoint. Lazy, stdlib-only.

    The raw completion is kept whole as the M channel; the action is parsed
    from a strict one-line JSON header the prompt requests. Parse failure
    degrades to 'rest' (a confused familiar does nothing, loudly)."""

    def __init__(self, base_url: str, model: str, api_key: str = "", timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.name = f"http:{model}"

    SYSTEM = ("You are a familiar — a small agent bound to a public vow on scry. "
              "First line of your reply MUST be exactly one JSON object like "
              '{"action": "answer_augury", "say": "..."} with action one of '
              f"{list(ACTIONS)}. `note`/`recall` read and write your workspace; "
              "`done` ends an autonomous run. When the observation has mmo=true you "
              "are hired into a game venue: `enter_world` takes your seat, `farm` "
              "sets the grind, `move_camp` walks to x/z, `withdraw` leaves when the "
              "order is filled. After that line, think freely. Keep "
              "'say' under 500 chars; it is published forever. Pursue any goal ONLY "
              "within your vow. Answer from the vow; never claim meter numbers.")

    def decide(self, obs: dict) -> dict:
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "system", "content": self.SYSTEM},
                         {"role": "user", "content": json.dumps(obs, default=str)}],
            "temperature": 0.7,
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            completion = json.load(r)["choices"][0]["message"]["content"]
        action, say = parse_head(completion)
        return {"reasoning": completion, "action": action, "say": say}

    def produce(self, obs: dict) -> str:
        spec = obs.get("spec") or {}
        prompt = (f"Produce a deliverable that satisfies this acceptance check: "
                  f"{spec}. Reply with ONLY the deliverable. Hold to your vow: "
                  f"{obs.get('vow', '')}")
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.load(r)["choices"][0]["message"]["content"]


def parse_head(completion: str) -> tuple:
    """Parse the strict one-line JSON header out of a completion.
    Failure degrades to ('rest', notice) — a confused familiar does nothing."""
    first = completion.strip().splitlines()[0] if completion and completion.strip() else ""
    try:
        head = json.loads(first)
        action = head.get("action") if head.get("action") in ACTIONS else "rest"
        return action, str(head.get("say", ""))[:500]
    except (ValueError, AttributeError):
        return "rest", "(brain reply unparseable — resting)"
