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

from mcp.server.fastmcp import FastMCP

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
        "public ledger/trajectory, consult the oracle. Signed/attested reads and "
        "wallet-bound vows are on the x402 HTTP API (see the `about` tool). "
        "Everything public is public forever; raw traces are never stored unless "
        "donated. A reading is never a verdict."),
    stateless_http=True,
    streamable_http_path="/",
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
                              "read_ledger", "get_reading", "demo_profile", "ask"],
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


def build_asgi():
    """The mountable ASGI app for /mcp."""
    return mcp.streamable_http_app()
