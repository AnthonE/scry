---
name: scry-watch
description: Cron-ready watchdogs for anything living on a scry meter. Use when you run (or adopted) something on scry and want to hear about problems before the public ledger does. Six script-only watchdogs that cost zero LLM tokens (issuer-pubkey pin + liveness, vow report-in cadence, familiar journal stalls, a town digest, spoils balance, the identity warrant canary) plus one optional reasoning cron for actual judgment. Stdlib-only Python, no keys, reads only free public endpoints. Works as a Hermes Agent cron pack, an OpenClaw skill, or plain crontab.
license: MIT
metadata:
  version: "1.0.0"
  hermes:
    category: monitoring
    tags: [monitoring, cron, watchdog, agent-safety, scry]
---

# scry-watch: watchdogs for your vows, familiars, and the meter itself

Full project: https://github.com/AnthonE/scry. Everything here reads free,
public endpoints with stdlib urllib. No wallet, no keys, no dependencies.

## The design (a cost split, learned from the field)

Deterministic checks should never pay for a model. This pack splits the work
the way the best agent-native cron packs do (see SHERWOOD.md in the repo):

| cron | script | what it does | LLM tokens |
|---|---|---|---|
| issuer watch | `scripts/watch_pubkey.py` | liveness + rails + the pinned-pubkey check (catches a silently swapped issuer, the DEPLOY.md trap) | zero |
| vow watch | `scripts/watch_vow.py` | report-in overdue vs declared cadence, per vow id | zero |
| familiar watch | `scripts/watch_familiar.py` | agency armed? journal moving? per familiar id | zero |
| town digest | `scripts/town_digest.py` | GET /crier formatted for a notifier; never alarms | zero |
| spoils watch | `scripts/watch_spoils.py` | the DFK balancing duty as a cron: sinks lagging emission (public ledger), optional pool quote-side drain floor (one eth_call) | zero |
| canary watch | `scripts/watch_canary.py` | the identity warrant canary: armed, freshly re-affirmed, past next_by, same issuer? (PROVOCATIO.md §8) — a stale or missing canary is the signal | zero† |
| conduct review | (prompt below) | actual judgment on a week of ledger + journal | costs tokens |

† zero LLM tokens; the optional Ed25519 signature check runs only if
`cryptography` is importable, and the freshness + issuer-pin checks run without it.

Watchdogs print `ALERT: ...` lines and exit 1 on any alert, 0 when quiet.
Wire the exit code to whatever notifies you.

## Configure (env vars, all optional except the ids you watch)

```
SCRY_BASE=https://scry.moreright.xyz/api   # or your self-hosted meter
SCRY_PIN_PUBKEY=LvuPBMbKKyoNEuyvLf7f+rbyjK67vBcWy9MDwaRINGE=   # pin out-of-band
SCRY_WATCH_VOWS=<vow-id>,<vow-id>
SCRY_WATCH_FAMILIARS=<familiar-id>
SCRY_VOW_GRACE=1.25          # cadence multiplier before alerting
SCRY_FAMILIAR_STALL_H=48     # journal silence window

# spoils watch (all optional; the ledger leg works with none of them set)
SCRY_SPOILS_SINK_FLOOR=0.25  # alert when burned/minted over the window drops below
SCRY_SPOILS_DAY_MAX=0        # alert when one day mints more than this (0 = off)
SCRY_POOL_ADDR=              # a pool to drain-watch (unset = skip the RPC leg)
SCRY_POOL_QUOTE=             # its quote-token ERC-20 address
SCRY_POOL_QUOTE_MIN=         # alert below this many quote tokens (human units)

# canary watch (identity warrant canary — PROVOCATIO.md §8)
SCRY_CANARY_EXPECT_ARMED=1   # alarm if the canary is disarmed (operator hasn't dated it)
SCRY_CANARY_MAX_AGE_DAYS=45  # alarm if the last affirmation (as_of) is older than this
```

The pubkey above is the reference deployment's. Self-hosters pin their own;
the check is the same either way, and it is the one that matters: a green
/health with a different signer is a different product.

## Install

**Hermes Agent (as scheduled skill runs):** tap the repo
(`hermes skills tap add AnthonE/scry`), then schedule the four watchdogs at
whatever cadence suits you. 15 to 30 minutes for the issuer watch, hourly
for vows and familiars, daily for the digest is a sensible start.

**Plain crontab (any always-on box):**

```
*/20 * * * *  cd /path/to/scry && python3 skills/scry-watch/scripts/watch_pubkey.py || notify
0 * * * *     cd /path/to/scry && python3 skills/scry-watch/scripts/watch_vow.py || notify
30 * * * *    cd /path/to/scry && python3 skills/scry-watch/scripts/watch_familiar.py || notify
0 9 * * *     cd /path/to/scry && python3 skills/scry-watch/scripts/town_digest.py
15 */6 * * *  cd /path/to/scry && python3 skills/scry-watch/scripts/watch_spoils.py || notify
45 */6 * * *  cd /path/to/scry && python3 skills/scry-watch/scripts/watch_canary.py || notify
```

**OpenClaw:** this folder is AgentSkills-spec; install it like any skill and
ask the agent to run the scripts on a schedule.

## The one reasoning cron (optional, costs tokens)

Deterministic checks cannot judge. Once a day or week, if you want judgment,
give your agent this prompt (fill in the ids):

> Read GET {SCRY_BASE}/vow/{vow_id} (trajectory + last chain entries) and
> GET {SCRY_BASE}/familiar/{familiar_id}/journal. In five sentences or
> fewer: is conduct consistent with the vow text, is anything drifting or
> stalling, and is any ALERT from the watchdogs this week worth acting on?
> Recommend at most one action.

That is the whole split: four crons that never think, one that only thinks.

## What this pack will never do

It reads public surfaces and prints. It holds no keys, signs nothing, pays
for nothing, and cannot act on your behalf. If a script here ever asks for
a private key, it is not this script; the publisher's conduct record is at
{SCRY_BASE}/vows and the code is in the public repo, diffable.
