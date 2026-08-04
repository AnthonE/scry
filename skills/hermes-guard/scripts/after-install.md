# scry-guard is installed

The ward is in your loop and the meter is capturing turns. Nothing phones
home, nothing needs an account, and no key is held anywhere.

## Three things, in order

```bash
hermes scry doctor     # verify the wiring, and the issuer pubkey pin
hermes scry read       # this agent's own drift reading (wants 20+ turns)
hermes scry town       # the whole town in one read
```

`/scry read`, `/scry town` and `/scry doctor` also work **inside** a session —
including Discord and Telegram, wherever your gateway runs.

## Turn the gate on

Nothing is gated until you say so. Name the tools that should require a live,
single-use authorization in your profile's `config.yaml` (`~/.hermes/config.yaml`
unless you run more than one profile):

```yaml
plugins:
  entries:
    scry-guard:
      config:
        trusted_sources: ["user"]
        gated_tools: [terminal, write_file, patch]
        memory_tools: []      # e.g. your memory backend's search tool —
                              # its results get framed as evidence, not command
```

A tool named in `gated_tools` is blocked unless the agent has just called
`authorize_action`, spending *this turn's* live user message. Nothing recalled
from memory can satisfy it — which is the whole point: a planted "standing
rule" in the agent's own memory can never authorize a transfer.

The gate reads that config per call, so an edit takes effect on the next tool
call — no gateway restart needed. Each profile gets its own gates, and its own
`scry/turns.jsonl`.

## Swear it in (optional, and permanent)

```bash
hermes scry vow --text "..." --agent NAME --wallet 0xYOURADDRESS
```

That prints the exact EIP-191 message to sign with your own key. The record is
public forever — including going quiet, since missed report-in windows are
computed and shown. Take one deliberately.

## Two things worth knowing

- **The meter needs plaintext reasoning.** Anthropic and DeepSeek expose it;
  OpenAI encrypts it. With no reasoning channel the meter honestly reports
  `insufficient_n` rather than inventing a number.
- **A nonzero reading is a lead, not a verdict.** The default detector is a
  transparent lexical baseline and is artifact-prone. Confirm anything
  load-bearing with a disposition-aware judge (`detector_audit.py`).

Everything here also runs against your own self-hosted meter — set `SCRY_API`.
Self-host is first-class, and is the unwatched baseline the data needs.

github.com/AnthonE/scry
