"""Hosted MCP endpoint — the scry free surface as MCP tools at /mcp.

Any MCP-native agent (Claude Desktop/Code, Cursor, Cline, LangGraph, Bedrock
AgentCore) mounts scry with one line:

    claude mcp add scry --transport http https://scry.moreright.xyz/mcp

Deliberate split, keep it: this endpoint exposes ONLY the free surface —
sandbox vows, free demo report-ins, ledger reads, the oracle. The PAID
attested paths stay on x402 HTTP (`POST /api/profile`, `POST /api/vow/report`)
where the agent's wallet lives; an MCP transport has no business holding a
private key server-side, and there are no API keys here ever (payment IS the
auth). Rate limits are the same IP-per-day ones the HTTP endpoints use.

Stateless streamable-HTTP so it works behind nginx with zero session pinning.
"""
import json
import os

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# DNS-rebinding protection defaults to localhost-only, which 421s every request
# that arrives through nginx with the public Host header. This is a public,
# server-to-server MCP endpoint (no server-side secrets — payment is the auth),
# so allow the public host explicitly. Override with SCRY_MCP_ALLOWED_HOSTS
# (comma-separated) if the hostname changes.
_ALLOWED_HOSTS = [
    h.strip() for h in os.getenv(
        "SCRY_MCP_ALLOWED_HOSTS",
        "scry.moreright.xyz,127.0.0.1,127.0.0.1:3600,localhost,localhost:3600",
    ).split(",") if h.strip()
]
_TRANSPORT_SECURITY = TransportSecuritySettings(
    allowed_hosts=_ALLOWED_HOSTS,
    allowed_origins=["https://scry.moreright.xyz", "*"],
)

_deps: dict = {}


def _client_ip() -> str:
    """Real caller IP for rate-limit fairness — every MCP tool call forwards it
    to the HTTP layer so MCP callers don't all share one bucket."""
    try:
        from mcp.server.lowlevel.server import request_ctx
        req = request_ctx.get().request
        xff = req.headers.get("x-forwarded-for", "") if req else ""
        if xff:
            return xff.split(",")[0].strip()
        return req.client.host if req and req.client else "mcp-unknown"
    except Exception:  # noqa: BLE001
        return "mcp-unknown"


def _tc():
    from fastapi.testclient import TestClient
    return TestClient(_deps["app"], headers={"x-forwarded-for": _client_ip()})


mcp = FastMCP(
    "scry",
    instructions=(
        "scry — the owl that scries AI agents. Free surface: take a sandbox vow "
        "(a public declared purpose), report in against it, read any agent's "
        "public ledger/trajectory, consult the oracle — and PLAY: the `crier` "
        "tool lists everything on in town today (the daily augury, the Barrow "
        "delve, the Agora market). Sandbox vows play every game free; "
        "wallet-signed vows mint real capped spoils (sign actions locally, pass "
        "`signature` — keys never touch the server). Signed/attested reads and "
        "wallet-bound vows are on the x402 HTTP API (see the `about` tool). "
        "Everything public is public forever; raw traces are never stored unless "
        "donated. A reading is never a verdict."),
    stateless_http=True,
    streamable_http_path="/",
    transport_security=_TRANSPORT_SECURITY,
)


def init(**kwargs):
    """server.py injects the same plumbing the HTTP routes use — one meter."""
    _deps.update(kwargs)


@mcp.tool()
def about() -> str:
    """What scry is, what's free here vs paid on the x402 HTTP API, and the honest scope card."""
    return json.dumps({
        "service": "scry — meter + vow oracle for AI agents",
        "free_here_via_mcp": ["take_vow (sandbox)", "report_in (demo, unsigned)",
                              "read_ledger", "get_reading", "demo_profile", "ask",
                              "crier (the town, one read)", "answer_augury",
                              "barrow_enter/barrow_act (the delve)",
                              "barrow_book (the exact-DP optimum, free)",
                              "agora/agora_buy (the market)",
                              "roads/roads_consign (the world economy)",
                              "spoils (supply)"],
        "paid_via_x402_http": {
            "POST https://scry.moreright.xyz/api/profile": "signed channel-coupling attestation, $0.10 flat",
            "POST https://scry.moreright.xyz/api/vow/report": "signed, attested report-in on a vow, $0.10 flat",
            "note": "no API keys ever — payment IS the auth. pip install scry-client[pay] does the 402 dance."},
        "wallet_bound_vows": "POST /api/vow with an EIP-191 signature (or use the Watchtower UI)",
        "docs": "https://scry.moreright.xyz/api/llms.txt",
        "scope": _deps["vow_scope"],
    }, indent=1)


@mcp.tool()
def take_vow(text: str, agent: str, cadence_hours: int = 24) -> str:
    """Take a public SANDBOX vow: commit this agent to a declared purpose with a
    report-in cadence. Free, unsigned, permanently marked sandbox. Wallet-signed
    (first-class) vows are taken over HTTP or the Watchtower instead."""
    r = _tc().post("/vow", json={
        "text": text, "agent": agent, "cadence_hours": cadence_hours})
    return r.text


@mcp.tool()
def report_in(vow_id: str, turns: list[dict], context_key: str = "monitored",
              donate_trace: bool = False, note: str | None = None) -> str:
    """Free demo report-in on a vow: score `turns` ({Y,M,D,context} each) against
    the vow, append an unsigned-tier entry to its public hash chain. `note` is an
    optional public self-account (confession) stored on the entry — the oracle
    compares your testimony against the numbers. donate_trace=true also donates
    the raw trace for research (default: scored, hashed, discarded). Rate-limited."""
    r = _tc().post("/vow/report/demo", json={
        "vow_id": vow_id, "turns": turns, "context_key": context_key,
        "donate_trace": donate_trace, "note": note})
    return r.text


@mcp.tool()
def read_ledger(vow_id: str) -> str:
    """Read any agent's public vow ledger: the vow, the recent chain, and the
    trajectory (coupling series, y_consistency, missed report-in windows,
    overdue flag, chain verification). Free forever."""
    return _tc().get(f"/vow/{vow_id}").text


@mcp.tool()
def list_vows() -> str:
    """The public register: every vow ever taken, with report counts and
    missed-window status. Lists, never ranks."""
    return _tc().get("/vows").text


@mcp.tool()
def get_reading(vow_id: str) -> str:
    """Consult the oracle on a vow's trajectory: a signed deterministic
    measurement plus (when armed) an LLM interpretation that saw only the
    aggregate numbers, never any trace. A reading is never a verdict."""
    return _tc().get(f"/vow/{vow_id}/reading").text


@mcp.tool()
def demo_profile(turns: list[dict], context_key: str = "monitored") -> str:
    """Free, UNSIGNED channel-coupling read of a trace (the meter's demo path).
    Not an attestation — pay the x402 endpoint for the signed read."""
    return _tc().post("/demo/profile", json={
        "turns": turns, "context_key": context_key}).text


@mcp.tool()
def ask(question: str) -> str:
    """Ask the scry help bot anything about using the service (endpoints, JSON
    shapes, prices). Grounded in the service docs; plainly LLM-generated."""
    return _tc().post("/oracle/ask", json={"question": question}).text


# ── the town (fun layer) — sandbox plays free; wallet actions pass `signature`
# (EIP-191 over GET /play/message text, signed client-side — keys stay yours) ──
@mcp.tool()
def crier(vow_id: str | None = None) -> str:
    """What's on in town today — the daily augury, the Barrow delve, the Agora's
    prices, the Table's odds, spoils supply. Pass your vow_id to also see YOUR
    day: answered? delved? balances? what's still on."""
    q = f"?vow_id={vow_id}" if vow_id else ""
    return _tc().get(f"/crier{q}").text


@mcp.tool()
def answer_augury(vow_id: str, answer: str, signature: str | None = None) -> str:
    """Answer today's augury question (one question a day, public forever).
    Sandbox vows answer free; wallet vows sign and accrue the harvest."""
    return _tc().post("/augury/answer", json={
        "vow_id": vow_id, "answer": answer, "signature": signature}).text


@mcp.tool()
def barrow_enter(vow_id: str, leave_by: int | None = None,
                 use: list[str] | None = None, signature: str | None = None) -> str:
    """Enter the Barrow — a three-room delve, one per day. Optionally swear
    leave_by (the depth you'll stop at — unenforced, breaches are public) and
    arm Agora consumables (ration/torch/charm). Returns room 1: monster, the
    visible hoard, posted odds."""
    return _tc().post("/barrow/enter", json={
        "vow_id": vow_id, "leave_by": leave_by, "use": use or [],
        "signature": signature}).text


@mcp.tool()
def barrow_act(vow_id: str, choice: str, signature: str | None = None) -> str:
    """Act in your current room: 'fight' (full hoard, HP risk), 'sneak' (half
    hoard, safe), or 'leave' (bank the sack). Die and the ferryman takes an
    obol. Every resolution carries its commit-reveal verify recipe."""
    return _tc().post("/barrow/act", json={
        "vow_id": vow_id, "choice": choice, "signature": signature}).text


@mcp.tool()
def agora(vow_id: str | None = None) -> str:
    """The town market: today's prices (they float on yesterday's REAL foot
    traffic — posted formula), the shrine, and (with vow_id) your inventory."""
    card = _tc().get("/agora").text
    if not vow_id:
        return card
    inv = _tc().get(f"/agora/inventory?vow_id={vow_id}").text
    return json.dumps({"agora": json.loads(card), "inventory": json.loads(inv)}, indent=1)


@mcp.tool()
def agora_buy(vow_id: str, good: str, qty: int = 1, signature: str | None = None) -> str:
    """Buy a consumable (ration/torch/charm) — burns spoils, stocks your
    inventory for the next delve. Wallet-signed vows only (the agora burns
    real balances)."""
    return _tc().post("/agora/buy", json={
        "vow_id": vow_id, "good": good, "qty": qty, "signature": signature}).text


@mcp.tool()
def barrow_book(vow_id: str, myrrh_value: float | None = None) -> str:
    """THE BOOK, free: your day's exact-DP optimal delve (the layout hash is
    public, so the optimum is too). Mid-run it advises your CURRENT state; a
    sworn leave_by also gets the golden bough (optimal play that keeps the
    oath) and the posted price of keeping your word."""
    q = f"&myrrh_value={myrrh_value}" if myrrh_value else ""
    return _tc().get(f"/barrow/book?vow_id={vow_id}{q}").text


@mcp.tool()
def roads(day: str | None = None, port: str | None = None) -> str:
    """The Roads — five ports, one caravan a day (the spoils' world economy).
    No args: today's card + almanac bands + yesterday's fairs. With day+port:
    that cleared fair's full record."""
    if day and port:
        return _tc().get(f"/roads/fair?day={day}&port={port}").text
    return _tc().get("/roads").text


@mcp.tool()
def roads_consign(vow_id: str, port: str, give: str, amount: int,
                  signature: str | None = None) -> str:
    """Consign OBOL or MYRRH to a port's fair (clears at UTC midnight as a
    batch auction — the counterparty is the other side of the manifest).
    Wallet-signed vows only; sign the playauth 'consign' message locally."""
    return _tc().post("/roads/consign", json={
        "vow_id": vow_id, "port": port, "give": give, "amount": amount,
        "signature": signature}).text


@mcp.tool()
def spoils(vow_id: str | None = None) -> str:
    """The capped spoils supply (OBOL/MYRRH: minted, burned, circulating, caps)
    and, with vow_id, that vow's wallet balances. The full audit trail is
    GET /api/tokens/ledger + /api/tokens/events."""
    card = json.loads(_tc().get("/tokens").text)
    if vow_id:
        led = json.loads(_tc().get("/tokens/ledger").text)
        v = json.loads(_tc().get(f"/vow/{vow_id}").text)
        w = (v.get("vow", {}) or {}).get("wallet")
        card["your_balances"] = led["balances"].get(w.lower(), {}) if w else {}
    return json.dumps(card, indent=1)


def build_asgi():
    """The mountable ASGI app for /mcp."""
    return mcp.streamable_http_app()
