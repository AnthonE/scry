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

# Cadence actions + autonomy actions. `note`/`recall` act on the familiar's
# workspace; `done` ends an autonomy run. parse_head validates against this.
ACTIONS = ("answer_augury", "report_in", "self_read", "note", "recall", "done", "rest")


def _h(*parts) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


class MockBrain:
    """Deterministic stand-in: earnest, a little liturgical, zero network."""

    name = "mock"

    def decide(self, obs: dict) -> dict:
        if obs.get("autonomy"):
            return self._decide_autonomy(obs)
        return self._decide_cadence(obs)

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
              "`done` ends an autonomous run. After that line, think freely. Keep "
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
