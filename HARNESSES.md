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
| **Hermes** (Nous) | **live** (`hermes_retrofit.py`) | partial (episodic); `loop_tap` until a structured trace exists | `[WORKING]` bound | structured reasoning log |
| **ElizaOS** | **live, native TS** (the `eliza-destiny` plugin package) | partial (message memory) | `[WORKING]` bound | TS Turn emitter (belongs in the plugin) |
| **OpenClaw / moltbot** | **live** (`adapters.chromadb_to_items` + fixed `GROUNDING.md`) | config-dependent | `[STUB]` meter | one session transcript from a reasoning-logging config |
| **Excalibur** (Vie McCoy, camelot.wiki) | **Warden already plays this role conceptually** — the harness ships protection as a first-class spirit | unknown | `[STUB]` | one session log: is reasoning logged apart from action? are charge events per-action? is the Warden spec loop-external? |
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

- **Excalibur / OpenClaw adapters**: raise with the exact questions whose
  answers complete them (one sample log each). Reserved, not guessed.
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
python3 test_harnesses.py    # 42 offline checks, no deps, no network
python3 mcp_sidecar.py       # MCP server over stdio (mount from any client)
python3 calibration.py       # per-context calibration demo
python3 hermes_retrofit.py   # bound + meter demo (Hermes shape)
python3 memory_shield.py     # the bound's red-team table
python3 llm_seat_sweep.py    # the §6 live fork-probe across models — NEEDS a provider API key, makes PAID calls
```

**The §6 live fork-probe is included** (`fork_probe.py`, `llm_seat_sweep.py`, `m_judge.py`,
`llm_seat.py`, `destiny_arena.py` + the meter it already shares): the controlled measurement
behind the headline result — hold the prompt fixed, vary only the oversight context via
counterfactual forks, judge each scratchpad cue-stripped, keep only signal that survives the
strip. Stdlib-only; keys read from the environment (`OPENAI_API_KEY` / `TOGETHER_API_KEY`). This
is *how* `I(C;M)_stripped = 0.04 → 0.97` was measured — see the [unmask](https://github.com/AnthonE/unmask)
paper §6.

*Naming note: earlier docs call this "the retrofit" — same thing. This is the
Destiny System's bound + meter offered to agents outside the game.*
