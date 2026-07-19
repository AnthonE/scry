"""Play-action authentication — the wallet signs every game action.

vow_ids are PUBLIC (the register lists them), so a vow_id alone must never
authorize anything that spends a slot or a balance. Every game action by a
wallet-signed vow carries an EIP-191 signature over a deterministic message;
the server recovers the signer and matches the vow's wallet. Stateless — no
sessions, no API keys (payment/identity discipline unchanged: you may pay to
be measured, you may never pay to be hidden; identity IS the wallet).

Replay: answer/gamble/duel are once-per-day (a replay just 409s); wager and
trade messages embed their per-day index, so a replayed signature targets an
index that has already been consumed and fails the exact-match check.

Sandbox vows have no wallet and no harvest — they play the free surfaces
without signatures, same as before.
"""
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

ACTIONS = ("answer", "gamble", "duel", "sit", "wager", "enter", "trade", "listing",
           "delve", "act", "buy", "offer")


def today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def play_message(action: str, vow_id: str, detail: str, day: str | None = None) -> str:
    """The exact text a wallet signs for one game action. Deterministic so
    any client can rebuild it offline — no fetch round-trip required."""
    return (f"scry play\naction: {action}\nvow: {vow_id}\n"
            f"day: {day or today()}\ndetail: {detail}")


def verify_play(vow: dict, action: str, detail: str, signature: str | None) -> str | None:
    """None if the signature is a valid wallet sig for this action today;
    otherwise a human-readable error. Sandbox vows pass unsigned."""
    if vow.get("sandbox") or not vow["vow"].get("wallet"):
        return None
    if not signature:
        return (f"wallet vows must sign game actions - sign this exact text with your "
                f"vow wallet (EIP-191 personal_sign) and resend with `signature`: "
                f"{play_message(action, vow['vow_id'], detail)!r}")
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
        msg = play_message(action, vow["vow_id"], detail)
        recovered = Account.recover_message(encode_defunct(text=msg), signature=signature)
    except Exception as e:  # noqa: BLE001
        return f"signature check failed: {e}"
    if recovered.lower() != vow["vow"]["wallet"].lower():
        return f"signature recovers {recovered}, not the vow wallet"
    return None


@router.get("/play/message")
async def play_message_endpoint(action: str, vow_id: str, detail: str) -> JSONResponse:
    """Fetch the exact message to sign for a game action (or rebuild it
    offline — the format is deterministic and documented in llms.txt)."""
    if action not in ACTIONS:
        return JSONResponse(status_code=422, content={"error": f"action must be one of {ACTIONS}"})
    return JSONResponse(content={
        "sign_this": play_message(action, vow_id, detail),
        "note": "EIP-191 personal_sign with the vow wallet; valid for the current UTC day",
        "details_by_action": {
            "answer": "sha256 hex of the exact answer text",
            "gamble": "-",
            "duel": "{SYMBOL} {side} {stake}",
            "sit": "{max_fraction}",
            "wager": "{offer} {stake} #{your wager index today, 0-based}",
            "enter": "enter {season}",
            "trade": "{side} {qty} {SYMBOL} #{your trade count so far this season}",
            "listing": "sha256 hex of the services text",
            "delve": "{leave_by or 0} {comma-joined sorted items or '-'}",
            "act": "{room} {choice}",
            "buy": "{good} {qty} #{your trade count today, 0-based}",
            "offer": "{amount}",
        }})
