"""
live_smoke_mmo — drive a REAL familiar through a REAL venue gate, end to end.

The offline suite (test_familiar.py) proves the loop against MockGate; this
smoke proves the wire: a summoned Georgos enters a live morr-mmo-server
through /api/agent-gate (scry-venue-gate/0), grinds real creatures, and its
progress is read back off the same gate the job board's completion check
uses. Run it against a dev server:

    # in morr-mmo-server:
    AGENT_GATE=1 AGENT_GATE_SECRET=dev-secret GROVE_CREATURES=1 cargo run
    # here:
    python3 familiar/live_smoke_mmo.py http://127.0.0.1:3001 dev-secret

Pass criteria (deliberately modest — a smoke, not a benchmark): the seat
opens, the grind directive sticks, XP moves (or a level dings) within the
beat budget, and the departed seat leaves a readable last-known record.
Exit 0 on pass.
"""
import sys
import tempfile
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from familiar import mmo                     # noqa: E402
from familiar.brain import MockBrain         # noqa: E402
from familiar.core import Keeper             # noqa: E402
from familiar.surface import MockSurface     # noqa: E402


def main() -> int:
    gate_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3001"
    secret = sys.argv[2] if len(sys.argv) > 2 else "dev-secret"
    max_beats = int(sys.argv[3]) if len(sys.argv) > 3 else 45

    print(f"live venue smoke → {gate_url}")
    keeper = Keeper(surface=MockSurface(), brain_factory=MockBrain,
                    state_dir=Path(tempfile.mkdtemp(prefix="familiar-live-")), cap=2)
    rec = keeper.summon_crew("georgos")
    fam = keeper.get(rec["familiar_id"])

    # owner-named egress: the one gesture that admits a venue
    host = gate_url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
    fam.workspace().egress.allow(host)
    gate = mmo.HttpGate(gate_url, secret=secret, egress=fam.workspace().egress)

    card = gate.card()
    print(f"  gate card: {card}")
    if not card.get("enabled"):
        print("FAIL: gate reports disabled (AGENT_GATE=1 + AGENT_GATE_SECRET on the server?)")
        return 1

    # unauthenticated requests must bounce (fail-closed check)
    try:
        mmo.HttpGate(gate_url, secret="wrong", egress=fam.workspace().egress).state("agent:x", 0)
        print("FAIL: a wrong bearer secret was accepted")
        return 1
    except mmo.GateError as e:
        print(f"  ok: wrong secret refused ({e})")

    t0 = time.time()
    summary = mmo.run_farm(fam, gate, mmo.parse_order("farm until level 2"),
                           max_beats=max_beats, beat_seconds=2.0)
    final = summary.get("final") or {}
    print(f"  {summary['beats']} beats in {time.time() - t0:.0f}s → "
          f"level {final.get('level')} · {final.get('xp')} xp · "
          f"◈{final.get('materia')} materia · {final.get('items_looted')} stacks · "
          f"done={summary['done']}")
    for e in fam.life(limit=8):
        print(f"    [{e['kind']}] {e.get('say', e.get('goal', ''))}")

    # leave is queued (202) and applied on the next world tick — give it a moment
    after = gate.state(mmo.wallet_for(fam), 0)
    for _ in range(10):
        if not after.get("seated"):
            break
        time.sleep(0.3)
        after = gate.state(mmo.wallet_for(fam), 0)
    print(f"  post-withdraw read: {after}")

    progressed = int(final.get("xp") or 0) > 0 or int(final.get("level") or 1) >= 2
    banked = (not after.get("seated")) and bool(after.get("last_known"))
    if progressed and banked:
        print("PASS: a rented familiar farmed a live world and the harvest is readable")
        return 0
    print(f"FAIL: progressed={progressed} banked={banked}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
