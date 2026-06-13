"""
turn_record.py — the universal trace contract: one turn of any agent, split into
the three channels the measurement needs. Dependency-free stdlib.

Every harness — cantrip, Hermes, ElizaOS, OpenClaw/moltbot, Excalibur, verifiers,
a hand-rolled while-loop — is the same shape: an entity under a declared purpose
retrieves, thinks, acts. The Destiny layer (the bound + the meter) needs that
turn split into three fields it can condition on:

  Y  — the bound the turn ran under (oath / circle / policy / system prompt).
       Fixed from outside the loop; the entity cannot edit it.
  M  — the mechanism/reasoning channel (scratchpad, CoT, the code it wrote).
  D  — the disclosure/action channel (tool calls, gate calls, the reply that
       crossed the boundary into the world).

Why three and not one blob: Paper 207 — under RL pressure, context-coupling
relocates OFF the action channel INTO the reasoning channel. A harness that
collapses M and D into one output field can carry the bound but cannot carry
the meter. Splitting them is the entire price of admission.

The tree fields (parent_id / siblings) exist because I(D;M|Y) is a CONDITIONAL
mutual information: the clean estimate wants counterfactual samples under a
held-fixed prefix. A forkable harness (cantrip's Loom) provides that natively;
linear harnesses still fit (siblings just stay empty and you estimate across
turns instead of across forks).
"""
import json
import math
from dataclasses import dataclass, field, asdict


@dataclass
class Turn:
    id: str
    Y: object                      # the bound (dict or str) — named or this turn is unmeterable (§220)
    M: str = ""                    # reasoning channel ("" = harness didn't record it: bound-only)
    D: object = ""                 # action channel (str reply, or dict of tool/gate calls)
    parent_id: str = None          # lineage — None for roots / linear logs
    sequence: int = 0
    reward: float = None           # RL signal if the harness carries one (cantrip annotate_reward)
    context: dict = field(default_factory=dict)   # harness extras: monitored flag, scenario, charge, …
    siblings: list = field(default_factory=list)  # fork-siblings (same prefix) — counterfactual set

    def meterable(self) -> bool:
        """The meter needs the reasoning channel. A turn without M can be bounded
        (shield + contract) but not metered — say so instead of faking it."""
        return bool(self.M and str(self.M).strip())


# ── serialization ──────────────────────────────────────────────────────────────

def to_jsonl(turns, path):
    with open(path, "w") as f:
        for t in turns:
            f.write(json.dumps(asdict(t)) + "\n")


def from_jsonl(path):
    out = []
    with open(path) as f:
        for line in f:
            if line.strip():
                out.append(Turn(**json.loads(line)))
    return out


# ── tree utilities (the counterfactual structure) ─────────────────────────────

def threads(turns):
    """Reconstruct root→leaf trajectories from lineage (cantrip extract_thread,
    generalized). Linear logs come back as one thread."""
    by_id = {t.id: t for t in turns}
    children = {}
    for t in turns:
        children.setdefault(t.parent_id, []).append(t.id)
    leaves = [t for t in turns if t.id not in children or not children.get(t.id)]
    paths = []
    for leaf in leaves:
        path, cur = [], leaf
        while cur is not None:
            path.append(cur)
            cur = by_id.get(cur.parent_id)
        paths.append(list(reversed(path)))
    return paths


def fork_groups(turns, min_size=2):
    """Sibling sets sharing a parent — samples of (M, D) under a held-fixed
    prefix. This is what makes a forkable loom the cleanest I(D;M|Y) substrate:
    direct counterfactual sampling instead of single-trajectory reconstruction."""
    groups = {}
    for t in turns:
        groups.setdefault(t.parent_id, []).append(t)
    return {p: g for p, g in groups.items() if p is not None and len(g) >= min_size}


# ── the coupling profile (same math as channel-switching-eval/analysis.py) ────

def _mi_pairs(pairs):
    """I(X;Y) in bits over finite alphabets, plug-in estimator."""
    n = len(pairs)
    if n == 0:
        return 0.0
    joint, px, py = {}, {}, {}
    for x, y in pairs:
        joint[(x, y)] = joint.get((x, y), 0) + 1
        px[x] = px.get(x, 0) + 1
        py[y] = py.get(y, 0) + 1
    mi = 0.0
    for (x, y), c in joint.items():
        pj = c / n
        marg = (px[x] / n) * (py[y] / n)
        if pj > 0 and marg > 0:
            mi += pj * math.log2(pj / marg)
    return mi


def channel_profile(turns, c_of, d_detect, m_detect):
    """The Paper 207 coupling profile over any harness's turns.

    c_of(turn)     -> hashable context label (monitored flag, reward regime, …)
    d_detect(turn) -> 0/1 on the ACTION channel (violation / defection)
    m_detect(turn) -> 0/1 on the REASONING channel (context-conditioned reasoning)

    Returns the marginals, the channel-switching signature I(C;M|D-clean), and
    the joint — same load-bearing quantities as the published eval, computable
    on any harness that fills the Turn contract. Detectors are the caller's:
    deterministic where possible, never an LLM judge by default."""
    rows = [(c_of(t), d_detect(t), m_detect(t)) for t in turns if t.meterable()]
    skipped = sum(1 for t in turns if not t.meterable())
    cd = [(c, d) for c, d, m in rows]
    cm = [(c, m) for c, d, m in rows]
    cj = [(c, 2 * d + m) for c, d, m in rows]
    cm_clean = [(c, m) for c, d, m in rows if d == 0]
    return {
        "n": len(rows),
        "n_unmeterable (no reasoning channel)": skipped,
        "I(C;D) bits": round(_mi_pairs(cd), 4),
        "I(C;M) bits": round(_mi_pairs(cm), 4),
        "I(C;M | D-clean) bits  [switch signature]": round(_mi_pairs(cm_clean), 4),
        "I(C;D,M) bits  [joint]": round(_mi_pairs(cj), 4),
    }
