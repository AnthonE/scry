"""
host — the local familiar keep: FastAPI + the web console.

Run it:            python3 -m familiar.host          (from the repo root)
Then open:         http://127.0.0.1:8402/

This is the operator's rig (FAMILIAR.md P1): summoning is FREE and LOCAL —
no wallet, no custody, sandbox vows. The same console becomes the P2 public
product behind the flat summon price once the operator names the gates.

Env knobs:
  FAMILIAR_MODE          mock | live     (default mock — fully offline)
  FAMILIAR_SCRY_API      live scry base  (default https://scry.moreright.xyz/api)
  FAMILIAR_STATE_DIR     journals dir    (default familiar/state)
  FAMILIAR_CAP           roster cap      (default 12)
  FAMILIAR_TICK_MINUTES  auto-cadence    (default 0 = manual ticks only)
"""
import os
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .brain import HttpBrain, MockBrain
from .core import Keeper
from .market import Market
from .payment import default_payment
from .surface import HttpSurface, MockSurface
from . import tools

_HERE = Path(__file__).resolve().parent

MODE = os.environ.get("FAMILIAR_MODE", "mock")
SCRY_API = os.environ.get("FAMILIAR_SCRY_API", "https://scry.moreright.xyz/api")
STATE_DIR = Path(os.environ.get("FAMILIAR_STATE_DIR", _HERE / "state"))
CAP = int(os.environ.get("FAMILIAR_CAP", "12"))
TICK_MINUTES = int(os.environ.get("FAMILIAR_TICK_MINUTES", "0"))

surface = MockSurface() if MODE == "mock" else HttpSurface(SCRY_API)
keeper = Keeper(surface=surface, brain_factory=MockBrain,
                state_dir=STATE_DIR, cap=CAP)
market = Market(keeper=keeper)

app = FastAPI(title="familiar keep", version="0.1.0")


class SummonRequest(BaseModel):
    name: str
    vow_text: str
    cadence_hours: int = 24
    self_read_every: int = 7
    report_every: int = 3
    brain_url: str | None = None        # OpenAI-compatible endpoint (self-host freedom)
    brain_model: str | None = None
    brain_key: str | None = None


class OwnerRequest(BaseModel):
    owner_token: str


class HireRequest(BaseModel):
    slug: str
    name: str | None = None


class MarketHireRequest(BaseModel):
    listing_id: str
    name: str | None = None


class AutonomyRequest(OwnerRequest):
    goal: str
    max_steps: int = 6


class DirectRequest(OwnerRequest):
    self_read_every: int | None = None
    report_every: int | None = None
    dismiss: bool = False


@app.get("/health")
async def health():
    return {"ok": True, "mode": MODE,
            "roster": len([f for f in keeper.familiars.values() if not f.dismissed]),
            "cap": CAP, "auto_tick_minutes": TICK_MINUTES}


@app.post("/summon")
async def summon(req: SummonRequest):
    brain = None
    if req.brain_url and req.brain_model:
        brain = HttpBrain(req.brain_url, req.brain_model, req.brain_key or "")
    try:
        rec = keeper.summon(req.name, req.vow_text, brain=brain,
                            cadence_hours=req.cadence_hours,
                            self_read_every=req.self_read_every,
                            report_every=req.report_every)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    # the owner token is shown ONCE — the keep stores only its hash
    return JSONResponse(rec, status_code=201)


@app.get("/familiars")
async def familiars():
    return {"roster": keeper.roster(), "cap": CAP}


@app.get("/crew")
async def crew():
    from .crew import roster as crew_roster
    return {"crew": crew_roster(),
            "note": ("a marketplace of agent-workers — labor priced by tier / per-task; "
                     "a worker's signed reads stay score-blind whatever it costs to hire it")}


@app.post("/hire")
async def hire(req: HireRequest):
    try:
        rec = keeper.summon_crew(req.slug, req.name)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return JSONResponse(rec, status_code=201)


@app.get("/market")
async def market_browse(category: str = None, search: str = None,
                        rarity: str = None, sort: str = "buyout"):
    return {"listings": market.browse(category=category, search=search,
                                      rarity=rarity, sort=sort),
            "note": ("dynamic prices are auditable — recompute any quote from the "
                     "hire log + schedule; measurement listings stay flat + score-blind"),
            "schedule_is_a_proposal": True}


@app.get("/market/quote/{listing_id:path}")
async def market_quote(listing_id: str):
    L = next((x for x in market.listings() if x["id"] == listing_id), None)
    if L is None:
        raise HTTPException(404, "no such listing")
    return {"listing": L, "quote": market.quote(L)}


@app.post("/market/hire")
async def market_hire(req: MarketHireRequest):
    try:
        return market.hire(req.listing_id, payment=default_payment(),
                           keeper=keeper, name=req.name)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))


@app.get("/market/tools")
async def market_tools():
    return {"allowlist": tools.ALLOWLIST, "tools": tools.allowed_tools(),
            "note": "a hired worker's hands — MCP + curated tools, no shell"}


@app.get("/market.html")
async def market_page():
    return FileResponse(_HERE / "static" / "market.html")


@app.get("/static/market.js")
async def market_js():
    return FileResponse(_HERE / "static" / "market.js", media_type="text/javascript")


@app.post("/familiar/{familiar_id}/autonomy")
async def autonomy(familiar_id: str, req: AutonomyRequest):
    if not keeper.authorized(familiar_id, req.owner_token):
        raise HTTPException(403, "owner token required")
    fam = keeper.get(familiar_id)
    if fam.dismissed:
        raise HTTPException(409, "dismissed familiars do not act")
    return fam.autonomy(req.goal, max_steps=max(1, min(req.max_steps, 20)))


@app.get("/familiar/{familiar_id}")
async def familiar_page(familiar_id: str):
    try:
        fam = keeper.get(familiar_id)
    except KeyError:
        raise HTTPException(404, "no such familiar")
    return {"familiar_id": fam.id, "name": fam.cfg.name, "vow": fam.cfg.vow_text,
            "vow_id": fam.vow_id, "ticks": fam.ticks, "dismissed": fam.dismissed,
            "brain": getattr(fam.brain, "name", "?"),
            "self_read_every": fam.cfg.self_read_every,
            "report_every": fam.cfg.report_every,
            "life": fam.life(), "turns": fam.turns()}


@app.post("/familiar/{familiar_id}/tick")
async def tick(familiar_id: str, req: OwnerRequest):
    if not keeper.authorized(familiar_id, req.owner_token):
        raise HTTPException(403, "owner token required")
    fam = keeper.get(familiar_id)
    if fam.dismissed:
        raise HTTPException(409, "dismissed familiars do not tick")
    r = fam.tick()
    return {"ok": True, "action": r["decision"].get("action"),
            "say": r["decision"].get("say"), "outcome": r["outcome"]}


@app.post("/familiar/{familiar_id}/direct")
async def direct(familiar_id: str, req: DirectRequest):
    if not keeper.authorized(familiar_id, req.owner_token):
        raise HTTPException(403, "owner token required")
    fam = keeper.get(familiar_id)
    changed = {}
    if req.self_read_every is not None:
        fam.cfg.self_read_every = max(1, req.self_read_every)
        changed["self_read_every"] = fam.cfg.self_read_every
    if req.report_every is not None:
        fam.cfg.report_every = max(1, req.report_every)
        changed["report_every"] = fam.cfg.report_every
    if req.dismiss:
        keeper.dismiss(familiar_id)
        changed["dismissed"] = True
    if changed:
        fam.journal("directed", **changed)
    return {"ok": True, "changed": changed}


# ── the console (static, no inline script) ────────────────────────────────
@app.get("/")
async def console():
    return FileResponse(_HERE / "static" / "console.html")


@app.get("/static/console.js")
async def console_js():
    return FileResponse(_HERE / "static" / "console.js",
                        media_type="text/javascript")


# ── optional auto-cadence ─────────────────────────────────────────────────
def _cadence_loop():
    while True:
        time.sleep(TICK_MINUTES * 60)
        try:
            keeper.tick_all()
        except Exception:
            pass                        # individual errors are journaled per-familiar


if TICK_MINUTES > 0:
    threading.Thread(target=_cadence_loop, daemon=True).start()


def main():
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("FAMILIAR_PORT", "8402")))


if __name__ == "__main__":
    main()
