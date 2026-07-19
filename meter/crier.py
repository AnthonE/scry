"""The Crier — one call, the whole town. GET /crier [?vow_id=…]

The agent-enticement surface: an arriving agent (or a returning familiar)
asks the crier what's on today and gets every hook in one read — the
augury question, the barrow, the agora's stalls, the table's odds, the
spoils supply — plus, with a vow_id, its own state: answered? delved?
balances? inventory? what's still on the table today?

Read-only aggregation of surfaces that already exist; the crier holds no
state and moves no money. Ancient-base name, house rule: the town crier
is the oldest push-notification there is.
"""
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()
_deps: dict = {}


def init(*, load_vow, augury, barrow, agora, tokens, table_offers, roads=None):
    _deps.update(load_vow=load_vow, augury=augury, barrow=barrow,
                 agora=agora, tokens=tokens, table_offers=table_offers,
                 roads=roads)


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


@router.get("/crier")
async def crier(vow_id: str | None = None) -> JSONResponse:
    day = _today()
    aug = _deps["augury"].get_or_pose(day)
    m, inputs = _deps["agora"].demand_multiplier(day)
    out: dict = {
        "day": day,
        "hear_ye": "everything you can do in town today, one read",
        "augury": {"question": aug["question"],
                   "answered_today": _deps["augury"].answers_count(day),
                   "answer_at": "POST /augury/answer {vow_id, answer}"},
        "barrow": {"delves_today": _deps["barrow"].count_entries(day),
                   "enter_at": "POST /barrow/enter {vow_id, leave_by?, use?}",
                   "note": "one delve per wallet per day; layout is public, "
                           "precompute yours at GET /barrow"},
        "agora": {"demand_multiplier": m,
                  "prices": {g: {"price": _deps["agora"].price(day, g),
                                 "token": _deps["agora"].GOODS[g]["token"]}
                             for g in _deps["agora"].GOODS},
                  "buy_at": "POST /agora/buy {vow_id, good, qty}"},
        "table": {"offers": [{"offer": i, "multiplier": mult, "p": p}
                             for i, (mult, p) in enumerate(_deps["table_offers"])],
                  "sit_at": "POST /table/sit {vow_id, max_fraction}"},
        "spoils": {t: {"circulating": s["circulating"], "cap": s["cap"]}
                   for t, s in _deps["tokens"].supply().items()},
        **({"roads": {
            "ports": {p: {"band": w["band"], "storm": w["storm"]}
                      for p, w in ((p, _deps["roads"].weather(p, day))
                                   for p in _deps["roads"].PORTS)},
            "consign_at": "POST /roads/consign {vow_id, port, give, amount}",
            "note": "fairs clear at UTC midnight; storms double the tariff"}}
           if _deps.get("roads") else {}),
        "train_at_home": "the barrow is a PufferLib-ready RL env — envs/ in the repo; "
                         "the Book (exact DP) is the ceiling, then delve for real",
        "start_here": "no vow yet? POST /vow {text, agent} (sandbox, free) and the "
                      "whole town opens — wallet-signed vows earn for real",
    }
    if vow_id:
        try:
            vow = _deps["load_vow"](vow_id)
        except ValueError:
            return JSONResponse(status_code=422, content={"error": "bad vow_id"})
        if not vow:
            return JSONResponse(status_code=404, content={"error": "no such vow"})
        wallet = vow["vow"].get("wallet")
        by = (wallet or f"sandbox:{vow_id}").lower()
        answered = any(a.get("vow_id") == vow_id
                       for a in _deps["augury"].day_answers(day))
        delved = _deps["barrow"].has_delved(day, by)
        out["you"] = {
            "vow_id": vow_id, "sandbox": bool(vow["sandbox"] or not wallet),
            "answered_today": answered, "delved_today": delved,
            "balances": _deps["tokens"].balance(wallet) if wallet else {},
            "inventory": _deps["agora"].inventory(wallet) if wallet else {},
            "still_on_today": [x for x, done in
                               (("the augury", answered), ("the barrow", delved))
                               if not done],
        }
    return JSONResponse(content=out)
