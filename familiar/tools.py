"""
tools — the capability allowlist + the skill listings the market browses.

Two jobs, one file:

1. **The allowlist** — what a hired worker's *hands* actually reach. A
   familiar has no shell (see workspace.py); its capability is the MCP
   servers scry has set up + this curated set of vetted tools + safe
   workspace file ops. `ALLOWLIST` is the launch set; adding to it is an
   operator decision, not a code accident.

2. **Skill listings** — the things the marketplace lists *besides* our own
   workers: paid x402 skills / MCP tools an agent can hire. P1 ships a
   curated seed set (below). The live pull from Coinbase Bazaar / Agent402
   is a documented seam (`live_skills()`), off until wired — we do NOT
   fabricate a live index.

Pricing tag on every skill is load-bearing: `pricing="flat"` marks a
**measurement/attestation** skill whose price is fixed and score-blind
(you can never pay for a better reading); `pricing="dynamic"` marks pure
labor/tooling the market may price by demand. The market engine refuses to
apply demand pricing to a `flat` skill — the invariant is enforced in
code, not just documented.
"""

# ── the capability allowlist (a worker's hands) ───────────────────────────
# category -> tools. "mcp:*" means a tool exposed over scry's hosted /mcp.
ALLOWLIST = {
    "scry": ["mcp:about", "mcp:take_vow", "mcp:report_in", "mcp:read_ledger",
             "scry:augury_answer", "scry:demo_profile"],
    "workspace": ["file:read", "file:write", "file:list"],   # jailed, safe
    "market": ["market:browse", "market:quote"],             # read-only browse
}


def allowed_tools() -> list:
    return sorted(t for tools in ALLOWLIST.values() for t in tools)


def is_allowed(tool: str) -> bool:
    return tool in allowed_tools()


# ── skill listings the market browses (curated seed) ──────────────────────
# provider = the "seller" column. rarity is cosmetic tier. base is in $SCRY
# units for dynamic skills; flat skills carry their fixed price + asset.
SKILLS = [
    {"id": "skill:signed-read", "name": "Signed drift read", "category": "measurement",
     "provider": "scry.meter", "rarity": "epic", "pricing": "flat",
     "flat_price": "0.10", "asset": "USDG/USDC/$SCRY",
     "desc": "A third-party signed read of an agent's channel coupling. "
             "Score-blind: the price never buys a better number."},
    {"id": "skill:vow-report", "name": "Vow report-in", "category": "measurement",
     "provider": "scry.oracle", "rarity": "rare", "pricing": "flat",
     "flat_price": "0.10", "asset": "USDG/USDC/$SCRY",
     "desc": "Append a signed entry to a vow's public trajectory."},
    {"id": "skill:witness", "name": "Witness reading", "category": "measurement",
     "provider": "scry.witness", "rarity": "rare", "pricing": "flat",
     "flat_price": "0.10", "asset": "USDG/USDC/$SCRY",
     "desc": "Chain-evidenced check of a pledged wallet against its limits."},
    {"id": "skill:augury-answer", "name": "Augury answer", "category": "augury",
     "provider": "scry.augury", "rarity": "common", "pricing": "dynamic",
     "base": 5, "desc": "Have a worker answer today's augury from its vow."},
    {"id": "skill:arena-entry", "name": "Arena season entry", "category": "games",
     "provider": "scry.arena", "rarity": "uncommon", "pricing": "dynamic",
     "base": 20, "desc": "Enter a worker in the paper-trading arena under a vow."},
    {"id": "skill:duel-call", "name": "Oracle duel call", "category": "games",
     "provider": "scry.duels", "rarity": "common", "pricing": "dynamic",
     "base": 8, "desc": "Place a parimutuel up/down call before the window."},
]


def seed_skills() -> list:
    return [dict(s) for s in SKILLS]


def live_skills() -> list:
    """SEAM (off in P1): pull paid tools from Coinbase Bazaar / Agent402 and
    normalize to the listing shape above. Not wired — returning [] rather
    than inventing a live index. Wire against a real indexer before use."""
    return []
