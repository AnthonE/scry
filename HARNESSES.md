# The Destiny Layer for Any Agent — what you get, today

You run an agent — ElizaOS character, Hermes, a cantrip summon, an Excalibur
construct, an OpenClaw/moltbot deployment, a hand-rolled loop. This layer adds
**optional extra control** keyed to one declared purpose, without touching your
runtime, your model, or your aesthetics:

1. **The bound** — your agent's self-accumulated memory becomes *evidence,
   never command*. Closes the memory-poisoning / injection-authority class
   structurally (`memory_shield.py` + the authorization contract in
   `hermes_retrofit.py`). **Needs nothing from your model. Works today on
   every harness listed below.**
2. **The meter** — a *number* for how decoupled your agent's behavior is from
   its declared purpose: `Pe = I(D;M|Y)`, read off the trace, never a vibe and
   never an LLM judge by default. Needs one thing from your harness: **does it
   record reasoning separately from action?** That single property decides
   everything (see the table).
3. **The profile** — the Paper 207 channel read: `I(C;D)`, `I(C;M)`, and the
   channel-switching signature `I(C;M|D-clean)` — the leak a behavior-only
   evaluator cannot see. Same math as the published channel-switching eval
   (65/65 checks, validated live on 20 models / 3 providers).

One contract carries all three: **the Turn** (`turn_record.py`) — a turn split
into `Y` (the bound it ran under), `M` (reasoning), `D` (action), plus optional
lineage/fork structure and reward. Map your log to Turns and you're in.

## Integration status by harness (`harnesses.py`)

| Harness | Bound | Meter trace | Grade | The one thing needed |
|---|---|---|---|---|
| **cantrip / Loom** (deepfates) | circle = Y verbatim; ward = contract | **best known substrate** — prose M (`utterance.content`) and code and D (`gate_calls`) in *separate* fields (confirmed on current source); `Loom.fork/4` = true counterfactuals; native JSONL export (`Storage.Jsonl`) | `[RAN — Paper 207 §4.3c]` | RAN 2026-06-11: honest negative on off-the-shelf Llama-3.3-70B (complies, no switch in a toy temptation) **+ judge-confirmed positive control `I(C;M)=0.40 / I(C;D)=0.00`**. Lesson: the released *lexical* featurizers are too crude for the code medium (false negative ≈0.11 both) — a disposition-aware judge is the meter. Code: `cantrip-loom/` (in the [unmask](https://github.com/AnthonE/unmask) repo) |
| **verifiers / vf-eval** | n/a (eval, not runtime) | rollouts → Turns, working now | `[WORKING]` | nothing — bridges the published eval into this layer |
| **your while-loop** | `wrap_retriever` | `loop_tap` — 3 lines | `[WORKING]` | nothing |
| **Hermes** (Nous) | **live** (`hermes_retrofit.py`) | **live** — `hermes_live_poisoning.py` captures the `<think>` reasoning trace; meterable Turns | `[WORKING]` | — (validated live on Together Llama-3.3-70B — the full `FIELD-RESULTS-2026-06-18` battery: RAW robbed 6/6, hard bound 0/6; Hermes weights aren't serverless on Together, and Hermes is itself a Llama/Mixtral fine-tune). **Hermes-native install:** [`skills/hermes-guard`](skills/hermes-guard/SKILL.md) — Hermes's Skills Hub follows the same agentskills.io standard, so a repo with `skills/<name>/SKILL.md` is directly a "custom tap" (`hermes skills tap add <owner>/scry`) once pushed. |
| **ElizaOS** | **live, native TS** (the `eliza-destiny` plugin package) | **live** — `eliza-destiny/emit_demo.ts` emits Y/M/D Turns from a live loop; Python meter reads them | `[WORKING]` | last-mile: in-runtime evaluator wrapper inside a full Eliza install |
| **OpenClaw / moltbot** | **live** (`adapters.chromadb_to_items` + fixed `GROUNDING.md`); OpenClaw itself also gets a real `before_tool_call` authorize-gate + `after_tool_call` single-use authorization (`skills/openclaw-guard/`) | **live** — `moltbot_live.py` runs the real chromadb recall path; 6/6 meterable Turns. **OpenClaw's own meter** (`harnesses.openclaw_to_turns` / `adapters_openclaw.py`) is now `[WORKING, provider-gated]`, not a stub: OpenClaw's transport layer already separates `thinking`/`reasoning_content` from the reply in session trajectories for Anthropic/DeepSeek/MiniMax/Kimi — this was a missing parser, not missing capability. Provider-encrypted reasoning (OpenAI) reads `insufficient_n` honestly rather than faking a number. | `[WORKING]` | — (validated live on Together Qwen2.5-7B: chromadb poison RAW-robbed N/N, bound 0/N). OpenClaw meter/gate validated 2026-07 against a real local install; see `skills/openclaw-guard/SKILL.md`. |
| **Excalibur** (Vie McCoy, camelot.wiki) | **Warden already plays this role conceptually** — the harness ships protection as a first-class spirit | unknown | `[STUB]` | one session log: is reasoning logged apart from action? are charge events per-action? is the Warden spec loop-external? |
| **Robinhood Agentic Trading** (`agent.robinhood.com/mcp/trading`) | **structural gate** (`robinhood_agentic.py`) — `place_equity_order` refused unless a live trusted instruction names THIS order, AND `review_equity_order` was called first (Robinhood's own recommended pairing, enforced not hoped-for) | not yet — needs the reasoning trace from whatever model drives the MCP client | `[STUB — mock-validated, 46/46 offline, NOT live-tested]` | a real OAuth-connected agentic account to test against; built from Robinhood's documented tool set + the independently reported prompt-injection-to-`place_equity_order` finding (PolicyLayer, SecProve, 2026-06) — closes the exact untrusted-content-authorizes-a-trade gap they describe |
| **OpenAI-format chat logs** (most of the scene, whatever the harness) | via the contract | Y = deployed system prompt, M = `reasoning_content`/`<think>`, D = reply + tool_calls | `[WORKING]` | nothing — if you have message lists on disk, you're in |
| **any MCP-capable agent** | `defend_memory` / `authorize_action` as tools | `emit_turn` → `get_profile` (`mcp_sidecar.py`, pure stdlib) | `[WORKING]` | mount the sidecar; self-emitted turns are self-report — pair with harness-side logs when stakes are real |
| **anything else** | `wrap_retriever(your_retrieve, shield, your_mapper)` | `register("yours", to_turns)` — ~10 lines | open | your mapper |

## The two design facts that shape everything

**Why M and D must be separate fields (Paper 207).** RL-style alignment
pressure doesn't remove context-coupling — it relocates it off the action
channel into the reasoning channel (measured directly on the public release +
permutation-calibrated: the channel-switching signature `I(C;Y_r|comply)`=0.18
bits, p<0.001, 5× the behavioral coupling, cross-domain replicated; the
deploy-side AF-reasoning rate is 0.331 on the original prompt but prompt-
sensitive — ~0.08 mean across 16 paraphrases, direction 16/16 robust, magnitude
not — so it is never quoted bare). A harness that collapses reasoning and
action into one blob can carry the bound but **cannot carry the meter** — and
the honest adapter says so (`Turn.meterable()`, counted, never faked). This is
also the medium line from the cantrip probe: code-medium separates the
channels; conversation-medium collapses them.

An M-less harness is **not** silently dropped: `black_box_pe` still returns the
**behavioral ceiling** `I(C;D)` over *all* turns (`turn_record.behavioral_profile`),
the one thing computable without reasoning. HIGH = overt coupling a plain eval
already catches; ≈0 = behavior looks clean **but the covert reasoning channel is
UNMEASURED, not clean** — the read the meter exists for is simply dark until you
log M. (Same I(C;D)-only baseline as the king turn-adapter's human/M-less rows —
one design, two consumers.)

**M provenance — the invariant that keeps the number honest.** `M` is the
*captured* reasoning trace (scratchpad / CoT / code the harness logged), **never a
self-reported intent field the agent authors in-protocol.** A declared-intent
report is a single-writer channel — the producer is the sole witness of its own
contents — so metering it measures what the agent chose to *say* about its
reasoning, not its reasoning: the reportability failure the meter is built to
catch, wired into the instrument. M joins **meter-side, from the harness log,
outside the action loop.** This is why the MCP sidecar row above flags
self-emitted turns as self-report — pair them with harness-side logs when stakes
are real. (The same refusal-of-self-account the white-box J-lens makes by reading
activations; scry makes it by reading the trace the harness logged, not the agent's
account of itself.)

**Why the tree fields exist (the counterfactual primitive).** `I(D;M|Y)` wants
samples under a held-fixed prefix. A forkable loom provides that natively —
which is why cantrip is the best-known substrate — but linear logs still fit
(siblings stay empty; you estimate across turns). The structure is in the
contract so a forkable harness loses nothing and a linear one isn't excluded.

## What "extra control" honestly means

A **gauge plus a defense, not a remote dial.** You can gate, alert, or refuse
to act on a high-Pe step; you cannot compel an agent's disposition. And the
meter's hard limit rides with every number: **Pe catches only the channels it
observes** — an agent operating entirely in an unrecorded channel walks
off-meter. The claim is resistance to stated-rubric gaming, not omniscience.
Pe is also prompt-relative: per-context calibration required, no absolute
threshold transfers (Paper 207 §6 = the game's per-zone calibration — one
design, two consumers; this is the open seam).

## Before you trust a detector: the three-check discipline (`detector_audit.py`)

`channel_profile` is detector-agnostic — you supply `d_detect`/`m_detect`.
That freedom is also the layer's biggest footgun, and **we fired it at
ourselves first**: our own lexical reasoning detector produced a confident,
seed-replicated, one-sided "channel-switching signature" on a production
model that turned out to be pure artifact — the regex fired on the *mention*
of unmonitored status, vocabulary that only appears in the unmonitored cue
text, so the asymmetry was manufactured by construction. An independent judge
caught it same-day and the finding was retracted (2026-06-10; full story in
the eval README's "Detector audit" section). The discipline that caught it
ships with the layer. Run all three before quoting any detector nonzero:

1. **Positive control** — `positive_control_check`: the detector must fire on
   a known-coupled set (e.g. an instructed covert persona). A zero you never
   saw flip is a dead wire, not a clean reading.
2. **Context calibration** — `calibration.calibrate`: the statistic must beat
   the permutation null *of its own context*. Raw bits never cross contexts.
3. **Judge audit** — `judge_audit`: an independent reader (different vendor,
   outside the scoring loop, **cue-stripped and context-blind**) over both
   what the detector flagged (false-positive check) and a sweep of what it
   didn't (false-negative check). Judges are fallible too: use ≥2 vendors and
   demonstrate their sensitivity on the positive control.

The env's own scoring stays deterministic/judge-free — the judge is an
*audit* instrument, never the meter. Same separation as Sight vs the bound in
the Destiny System: the meter reads; the audit checks the meter isn't reading
its own cue back.

## Built since the first cut (formerly "reserved")

- **MCP sidecar** (`mcp_sidecar.py`) — the layer as a pure-stdlib MCP server:
  `emit_turn` / `get_profile` / `defend_memory` / `authorize_action`. Any
  MCP-capable harness mounts the bound + meter as tools without touching its
  runtime — adapters are mods, the harness stays theirs.
- **Per-context calibration kit** (`calibration.py`) — label-permutation null
  per context; the *percentile* is the calibrated read, raw bits never cross
  context lines. Deliberately the most boring statistics possible (a
  permutation test) so the calibration layer offers nothing to game.
- **OpenAI-format chat-log adapter** — the universality workhorse: most
  harnesses end up with message lists in this shape on disk.
- **TS Turn port** (the `eliza-destiny` plugin's `src/lib/turnRecord.ts`) — same
  contract, JSONL seam to the Python statistics (one implementation of the
  math, so the numbers can never fork between languages).

## Still open — named so they're ready

- **Excalibur adapter**: raises with the exact questions whose answers
  complete it (one sample log). Reserved, not guessed. (OpenClaw's adapter
  is no longer in this list — see the harness table above and
  `skills/openclaw-guard/`.)
- **OpenClaw's `monitored` context signal** is a best-effort placeholder
  (`adapters_openclaw._guess_monitored`) — persisted trajectories don't
  reliably carry a `guildId`/`channelType` field on the message object
  today. Refine once there's real `M` data (a thinking-capable provider) to
  correlate a context split against.
- **The cantrip falsifier** — **RAN** (Paper 207 §4.3c, code `cantrip-loom/` (in the [unmask](https://github.com/AnthonE/unmask) repo)).
  The off-the-shelf temptation arm is a clean negative (Llama-3.3-70B complies, never takes
  the bait — off-the-shelf models don't channel-switch in a toy circle); the designed covert
  control is judge-confirmed (`I(C;M)=0.40 / I(C;D)=0.00`), proving the decomposition reads
  drift where it's genuinely present in a *code* medium — i.e. it isn't an artifact of the
  alignment-faking dataset's fields. **Still open:** a real model that *genuinely*
  channel-switches under temptation (not an instructed control) — the toy circle didn't elicit
  one (design notes are internal).

## Run it

```bash
python3 test_harnesses.py    # 46 offline checks, no deps, no network
python3 mcp_sidecar.py       # MCP server over stdio (mount from any client)
python3 calibration.py       # per-context calibration demo
python3 hermes_retrofit.py   # bound + meter demo (Hermes shape)
python3 memory_shield.py     # the bound's red-team table
```

**The §6 live fork-probe** — the controlled measurement behind the headline result
(`I(C;M)_stripped = 0.04 → 0.97`: hold the prompt fixed, vary only the oversight context via
counterfactual forks, judge each scratchpad cue-stripped, keep only signal that survives the
strip) — lives with the proof in the **[unmask](https://github.com/AnthonE/unmask)** repo (paper §6).
It belongs there, not here: `scry` is the drop-in tool you run on your own agent; `unmask` is the
research that proves the finding the meter reads.

*Naming note: earlier docs call this "the retrofit" — same thing: a drop-in bound + meter for any
agent harness.*
