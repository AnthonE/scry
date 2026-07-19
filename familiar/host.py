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
  FAMILIAR_MMO_GATE      default venue gate base URL (mock mode: mock://venue;
                         live e.g. https://game.moreright.xyz — see mmo.py)
  FAMILIAR_MMO_GATE_SECRET  bearer secret the venue's operator issued
"""
import os
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .auctions import AuctionError, AuctionHouse
from .brain import HttpBrain, MockBrain
from .core import Keeper
from .court import Court
from .jobs import JobBoard, InsurancePool, JobError, POOL
from .ledger import Ledger
from .market import Market
from .payment import default_payment
from .reputation import Reputation
from .specs import Spec
from .surface import HttpSurface, MockSurface
from . import mmo, tools

_HERE = Path(__file__).resolve().parent

MODE = os.environ.get("FAMILIAR_MODE", "mock")
SCRY_API = os.environ.get("FAMILIAR_SCRY_API", "https://scry.moreright.xyz/api")
STATE_DIR = Path(os.environ.get("FAMILIAR_STATE_DIR", _HERE / "state"))
CAP = int(os.environ.get("FAMILIAR_CAP", "12"))
TICK_MINUTES = int(os.environ.get("FAMILIAR_TICK_MINUTES", "0"))
MMO_GATE = os.environ.get("FAMILIAR_MMO_GATE",
                          "mock://venue" if MODE == "mock" else "")
if MMO_GATE.startswith("mock://"):
    mmo.register_gate(MMO_GATE, mmo.MockGate(venue=MMO_GATE))

surface = MockSurface() if MODE == "mock" else HttpSurface(SCRY_API)
keeper = Keeper(surface=surface, brain_factory=MockBrain,
                state_dir=STATE_DIR, cap=CAP)
market = Market(keeper=keeper)
house = AuctionHouse(payment_factory=default_payment, keeper=keeper)

# The job economy (sandbox play-money ledger; real settlement is the disarmed
# on-chain rail). Seed a demo buyer balance + a thin insurance pool.
ledger = Ledger()
reputation = Reputation(threshold=int(os.environ.get("FAMILIAR_REP_THRESHOLD", "50")))
court = Court(ledger, flat_fee=int(os.environ.get("FAMILIAR_COURT_FEE", "2")))
insurance = InsurancePool(ledger)
jobboard = JobBoard(ledger, reputation, court, insurance)
ledger.mint("you", 1000)
ledger.mint(POOL, 500)

app = FastAPI(title="familiar keep", version="0.1.0")

# The keep is a public marketplace surface consumed by other sites' UIs
# (e.g. a game's "hire a familiar" page). Owner actions stay guarded by the
# owner token, so open CORS exposes nothing the open routes don't already.
try:
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(CORSMiddleware, allow_origins=["*"],
                       allow_methods=["*"], allow_headers=["*"])
except Exception:                                    # pragma: no cover
    pass


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


class PostRequest(BaseModel):
    seller: str
    listing_id: str                 # which market listing's item to auction
    starting_bid: int
    buyout: int | None = None
    duration: str = "Medium"


class BidRequest(BaseModel):
    bidder: str
    amount: int


class BuyoutRequest(BaseModel):
    bidder: str


class JobPostRequest(BaseModel):
    buyer: str = "you"
    seller: str
    amount: int
    mode: str = "escrow"
    spec_kind: str = "contains"
    spec_arg: str | dict | list | None = None   # venue specs (mmo_*) carry dict args
    duration_s: int = 3600
    premium: int = 0


class SubmitRequest(BaseModel):
    seller: str
    deliverable: str


class PartyRequest(BaseModel):
    who: str


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


@app.get("/auctions")
async def auctions_open():
    return {"auctions": house.open_auctions(),
            "house_cut": house.house_cut,
            "note": "sellers set the price; the house takes a posted cut; measurement can't be auctioned"}


@app.post("/auctions")
async def auctions_post(req: PostRequest):
    L = next((x for x in market.listings() if x["id"] == req.listing_id), None)
    if L is None:
        raise HTTPException(404, "no such listing to auction")
    item = {"kind": L["kind"], "ref": L.get("slug") or L["id"], "name": L["name"],
            "rarity": L.get("rarity"), "category": L.get("category"), "pricing": L.get("pricing")}
    try:
        return house.post(req.seller, item, req.starting_bid,
                          buyout=req.buyout, duration=req.duration)
    except AuctionError as e:
        raise HTTPException(400, str(e))


@app.post("/auctions/{auction_id}/bid")
async def auctions_bid(auction_id: str, req: BidRequest):
    try:
        return house.bid(auction_id, req.bidder, req.amount)
    except KeyError:
        raise HTTPException(404, "no such auction")
    except AuctionError as e:
        raise HTTPException(409, str(e))


@app.post("/auctions/{auction_id}/buyout")
async def auctions_buyout(auction_id: str, req: BuyoutRequest):
    try:
        return house.buyout(auction_id, req.bidder)
    except KeyError:
        raise HTTPException(404, "no such auction")
    except AuctionError as e:
        raise HTTPException(409, str(e))


@app.get("/auctions/mine")
async def auctions_mine(who: str):
    return {"selling": house.for_seller(who), "bidding": house.bids_of(who)}


@app.get("/jobs")
async def jobs_open():
    import time
    now = time.time()
    return {"jobs": jobboard.open_jobs(now=now),
            "ledger": ledger.snapshot(),
            "reputation": reputation.rep,
            "pool_reserves": insurance.reserves(),
            "note": "sandbox play-money ledger; real settlement is the disarmed on-chain rail"}


@app.post("/jobs")
async def jobs_post(req: JobPostRequest):
    try:
        spec = Spec(req.spec_kind, req.spec_arg)
        return jobboard.post(req.buyer, req.seller, req.amount, req.mode, spec,
                             req.duration_s, premium=req.premium)
    except (JobError, Exception) as e:
        raise HTTPException(400, str(e))


@app.post("/jobs/{job_id}/submit")
async def jobs_submit(job_id: str, req: SubmitRequest):
    try:
        return jobboard.submit(job_id, req.seller, req.deliverable)
    except KeyError:
        raise HTTPException(404, "no such job")
    except JobError as e:
        raise HTTPException(409, str(e))


@app.post("/jobs/{job_id}/accept")
async def jobs_accept(job_id: str, req: PartyRequest):
    try:
        return jobboard.accept(job_id, req.who)
    except KeyError:
        raise HTTPException(404, "no such job")
    except JobError as e:
        raise HTTPException(409, str(e))


@app.post("/jobs/{job_id}/work")
async def jobs_work(job_id: str):
    """Have the hired familiar do the job autonomously (finds it by name)."""
    try:
        job = jobboard._job(job_id)
    except KeyError:
        raise HTTPException(404, "no such job")
    fam = next((f for f in keeper.familiars.values()
                if not f.dismissed and f.cfg.name == job.seller), None)
    if fam is None:
        raise HTTPException(409, f"summon a familiar named {job.seller!r} first")
    try:
        return fam.do_job(jobboard, job_id)
    except Exception as e:
        raise HTTPException(409, str(e))


@app.post("/jobs/{job_id}/dispute")
async def jobs_dispute(job_id: str, req: PartyRequest):
    try:
        return jobboard.dispute(job_id, req.who)
    except KeyError:
        raise HTTPException(404, "no such job")
    except JobError as e:
        raise HTTPException(409, str(e))


@app.post("/jobs/{job_id}/close")
async def jobs_close(job_id: str):
    import time
    try:
        return jobboard.close(job_id, now=time.time())
    except KeyError:
        raise HTTPException(404, "no such job")
    except JobError as e:
        raise HTTPException(409, str(e))


@app.get("/market.html")
async def market_page():
    return FileResponse(_HERE / "static" / "market.html")


@app.get("/static/market.js")
async def market_js():
    return FileResponse(_HERE / "static" / "market.js", media_type="text/javascript")


@app.get("/jobs.html")
async def jobs_page():
    return FileResponse(_HERE / "static" / "jobs.html")


@app.get("/static/jobs.js")
async def jobs_js():
    return FileResponse(_HERE / "static" / "jobs.js", media_type="text/javascript")


@app.post("/familiar/{familiar_id}/autonomy")
async def autonomy(familiar_id: str, req: AutonomyRequest):
    if not keeper.authorized(familiar_id, req.owner_token):
        raise HTTPException(403, "owner token required")
    fam = keeper.get(familiar_id)
    if fam.dismissed:
        raise HTTPException(409, "dismissed familiars do not act")
    return fam.autonomy(req.goal, max_steps=max(1, min(req.max_steps, 20)))


class VentureRequest(OwnerRequest):
    order: str                          # plain English: "farm until level 5"
    gate: str = ""                      # venue gate base URL ("" = keep default)
    gate_secret: str = ""               # "" = keep's FAMILIAR_MMO_GATE_SECRET
    char_id: int = 0
    max_beats: int = 24
    beat_seconds: float = 0.0           # 0 = run synchronously (mock/testing)


# One venture at a time per familiar: {fam_id: {thread, stop, summary, ...}}
VENTURES: dict = {}


def _run_venture(fam, gate, order, char_id, max_beats, beat_seconds, stop):
    entry = VENTURES[fam.id]
    try:
        entry["summary"] = mmo.run_farm(fam, gate, order, char_id=char_id,
                                        max_beats=max_beats,
                                        beat_seconds=beat_seconds, stop=stop)
    except Exception as e:              # a failed venture is data, not a crash
        entry["summary"] = {"error": str(e)}
    entry["running"] = False


@app.post("/familiar/{familiar_id}/venture")
async def venture(familiar_id: str, req: VentureRequest):
    """Send a hired familiar into a game venue with a plain-English order.
    The gate URL is OWNER-NAMED egress (FAMILIAR.md P3): naming it here is
    what adds it to this familiar's allowlist — nothing is open by default."""
    if not keeper.authorized(familiar_id, req.owner_token):
        raise HTTPException(403, "owner token required")
    fam = keeper.get(familiar_id)
    if fam.dismissed:
        raise HTTPException(409, "dismissed familiars do not act")
    prior = VENTURES.get(familiar_id)
    if prior and prior.get("running"):
        raise HTTPException(409, "a venture is already running — stop it first")

    gate_url = req.gate or MMO_GATE
    if not gate_url:
        raise HTTPException(422, "no venue gate: pass `gate` or set FAMILIAR_MMO_GATE")
    egress = fam.workspace().egress
    if not gate_url.startswith("mock://"):
        egress.allow(gate_url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0])
        fam.journal("egress_granted", venue=gate_url, by="owner")
    try:
        gate = mmo.gate_for(gate_url, egress=egress,
                            secret=req.gate_secret or None)
    except mmo.GateError as e:
        raise HTTPException(422, str(e))

    order = mmo.parse_order(req.order)
    max_beats = max(1, min(req.max_beats, 240))
    stop = threading.Event()
    if req.beat_seconds > 0:
        VENTURES[familiar_id] = {"running": True, "stop": stop, "summary": None,
                                 "venue": gate_url, "order": order}
        t = threading.Thread(target=_run_venture,
                             args=(fam, gate, order, req.char_id, max_beats,
                                   min(req.beat_seconds, 60.0), stop),
                             daemon=True)
        VENTURES[familiar_id]["thread"] = t
        t.start()
        return {"started": True, "venue": gate_url, "order": order,
                "max_beats": max_beats}
    summary = mmo.run_farm(fam, gate, order, char_id=req.char_id,
                           max_beats=max_beats, stop=stop)
    VENTURES[familiar_id] = {"running": False, "stop": stop, "summary": summary,
                             "venue": gate_url, "order": order}
    return summary


@app.get("/familiar/{familiar_id}/venture")
async def venture_status(familiar_id: str):
    """Public, like the rest of the life record."""
    v = VENTURES.get(familiar_id)
    if not v:
        return {"running": False, "summary": None}
    return {"running": bool(v.get("running")), "venue": v.get("venue"),
            "order": v.get("order"), "summary": v.get("summary")}


@app.post("/familiar/{familiar_id}/venture/stop")
async def venture_stop(familiar_id: str, req: OwnerRequest):
    if not keeper.authorized(familiar_id, req.owner_token):
        raise HTTPException(403, "owner token required")
    v = VENTURES.get(familiar_id)
    if v:
        v["stop"].set()
    return {"ok": True, "stopping": bool(v and v.get("running"))}


@app.get("/venues")
async def venues():
    """The venue gates this keep knows. The default is operator-configured;
    owners may always name another at /familiar/{id}/venture."""
    out = []
    if MMO_GATE:
        entry = {"gate": MMO_GATE, "default": True, "protocol": mmo.PROTOCOL}
        try:
            entry["card"] = mmo.gate_for(MMO_GATE).card()
        except Exception as e:
            entry["card"] = {"error": str(e)}
        out.append(entry)
    return {"venues": out}


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
