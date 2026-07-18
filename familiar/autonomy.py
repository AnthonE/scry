"""
autonomy — a familiar pursues a goal on its own, bounded and on the record.

The loop is the "somewhat autonomous" ask: give a familiar a goal and it
plans its own next action, acts through its workspace + the scry surfaces,
observes, and repeats — until it declares the goal done or it spends its
step budget. Three hard rails:

  - **Y on every turn.** Every step records a turn whose Y is the vow. A
    goal is pursued only WITHIN the vow (§220); the goal never replaces it.
  - **Bounded.** `max_steps` is a hard budget — an autonomous familiar
    cannot run away. No step, no unbounded recursion, no surprise spend.
  - **Sandboxed side effects.** File actions go through the jailed
    Workspace; code execution is refused unless the host wired a real
    sandbox backend (workspace.py). Everything the familiar does is
    journaled as it happens.
"""
import time


def run_autonomy(fam, goal_text: str, max_steps: int = 6, day: str = None) -> dict:
    """Drive `fam` toward `goal_text` for at most `max_steps`. Returns a
    summary; every step is also on the familiar's public record."""
    if fam.dismissed:
        raise RuntimeError("dismissed familiars do not act")
    if not fam.vow_id:
        raise RuntimeError("unborn: call be_born() first")

    # Resolve the day ONCE so the augury-answered check and the journal entry
    # agree — otherwise obs sees today while the record says None and the loop
    # re-answers forever (caught by live smoke; the test that passed had
    # over-specified day and masked it).
    day = day or time.strftime("%Y-%m-%d", time.gmtime())
    ws = fam.workspace()
    fam.journal("autonomy_start", goal=goal_text, budget=max_steps)
    steps = []

    for i in range(max_steps):
        obs = fam._autonomy_obs(goal_text, step=i, day=day)  # noqa: SLF001 (same package)
        decision = fam.brain.decide(obs)
        action = decision.get("action", "rest")

        fam._record_turn(decision, day=day, kind="autonomy")  # Y = vow, always

        outcome = _act_autonomy(fam, ws, action, decision, day=day)
        fam.journal("autonomy_step", n=i, goal=goal_text, action=action,
                    say=decision.get("say", ""), outcome=outcome)
        steps.append({"action": action, "outcome": outcome})

        if action == "done" or (isinstance(outcome, dict) and outcome.get("stop")):
            break

    done = bool(steps) and steps[-1]["action"] == "done"
    fam.journal("autonomy_end", goal=goal_text, steps=len(steps), done=done)
    return {"goal": goal_text, "steps": steps, "done": done,
            "budget": max_steps, "spent": len(steps),
            "workspace": ws.list()}


def _act_autonomy(fam, ws, action: str, decision: dict, day: str = None) -> dict:
    """Workspace actions here; surface actions delegate to the familiar's
    own actor so there is one place that talks to scry."""
    try:
        if action == "note":
            body = decision.get("say", "")
            name = decision.get("file", "plan.md")
            return {"ok": True, **ws.write(name, body)}
        if action == "recall":
            files = ws.list()
            return {"ok": True, "files": files,
                    "head": (ws.read(files[0])[:200] if files else "")}
        if action == "done":
            return {"ok": True, "stop": True, "did": "done"}
        if action == "rest":
            return {"ok": True, "did": "rest"}
        # answer_augury / self_read / report_in — the surface actions
        return fam._act(decision, day=day)                     # noqa: SLF001
    except Exception as e:                                     # a bad step is data, not a crash
        fam.journal("error", where=f"autonomy:{action}", detail=str(e))
        return {"ok": False, "action": action, "error": str(e)}
