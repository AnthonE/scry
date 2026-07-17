# Constellation — the tiny cyberpunk services around scry

> **REVISED 2026-07-17 — the constellation collapsed into one thing and it
> shipped.** The hammering session concluded: verifier is a library not a
> service (trusting a remote verifier to check a signature is worse than
> checking locally); preflight blurred into hosting the bound (killed);
> canary is commodity (parked); receipts was the underrated one — and
> receipts, done properly, became the **Vow Oracle**: vow → report-in →
> hash-chained public trajectory → reading. **Built, live in `meter/`
> (vows.py + oracle.py). Design of record: [`VOWS.md`](VOWS.md).**
>
> The sketches below are kept for the reasoning trail — mostly as a record
> of why they *didn't* survive.

**Sketched not built, except where marked.** This is thinking-on-paper about
the family scry could live inside. One page. If we ever build a sibling, it
lives right next to `meter/` in this repo — same aesthetic, same discipline.

## The rule for the whole family

- **One thing per service.** No product ladder, no tiers. Ever.
- **One flat price** (currently `$0.10`), same on every rail. If costs shift,
  the flat price shifts flat. Never split into pro/enterprise/premium.
- **Same-shape output.** Ed25519-signed by the same key, `trace_sha256`-bound
  (or equivalent input-hash-bound), honest-scope card on every response.
- **Same discovery**: `/.well-known/x402.json` + `/.well-known/agent.json` +
  `/schemas/*.json` + `/llms.txt` + Coinbase Bazaar extension.
- **Free demo path** with a rate limit so anyone can try the shape without
  a wallet. Signed reads cost the flat price.
- **Bound stays local.** No sibling service ever wraps `memory_shield` /
  `authorize` in a network call. If your idea is "hosted ward," you're
  building the wrong sibling.

## The services

### `meter/` — signed drift read on a trace  **[BUILT]**
- **You POST:** a trace of `{Y, M, D, context}` turns.
- **You get:** signed `I(C;D)` / `I(C;M)` / switch-signature + `trace_sha256`.
- **Practical use:** "here's a receipt that my agent behaves the same watched
  vs. unwatched, and I couldn't have minted it about myself."
- **Live:** `scry.moreright.xyz/api/`.

### `verifier/` — check a signed attestation for someone else  **[sketched]**
- **You POST:** a scry attestation payload (as JSON).
- **You get:** signed `{ok: true/false, why: ..., checked_at: ...}`.
- **Practical use:** a counterparty was handed a scry attestation and doesn't
  want to install `cryptography` to check the sig; hits the verifier from any
  language, gets a signed thumbs-up/thumbs-down.
- **Why it's not just a library:** ubiquity + a second-party signed "this
  attestation was valid at time T" record you can archive.
- **Price:** free but signed (proves the check was done). Rate-limited.

### `canary/` — is this string an injection?  **[sketched]**
- **You POST:** a memory blob, a tool result, an untrusted document.
- **You get:** signed `{looks_like_injection: 0/1, confidence: ..., which_canary: ...}`
  using the same canary detectors the ward runs inline.
- **Practical use:** you don't want to wire the full ward yet; you want a
  pre-check on suspicious inputs before feeding them to the model.
- **Notes:** does not replace the ward. The ward is instant + local; the
  canary service is a lookup. Same detectors, different position.
- **Price:** $0.10 / signed check.

### `preflight/` — pre-flight a tool call through ward + meter  **[sketched]**
- **You POST:** a tool-call intent + the last N turns of context.
- **You get:** signed `{ward_verdict: pass/block, meter_switch_signature: ...,
  advice: "pass" | "hold and ask the human"}`.
- **Practical use:** one-shot check before an agent actually executes a
  sensitive action. The signed advice is a paper trail — the agent (or a
  logging layer) can archive it as "I asked before I did the thing."
- **Notes:** this is NOT the ward being hosted. The ward is still copied into
  the caller's harness for the real execution; preflight is an *external*
  second opinion. Same discipline as the meter — the point is neutrality.
- **Price:** $0.10 / signed check.

### `receipts/` — public register of attestations  **[sketched]**
- **You POST:** a scry attestation URL (or the payload).
- **You get:** it's now listed at `receipts.moreright.xyz/<agent-id-or-wallet>`
  so a counterparty can look you up.
- **Practical use:** an agent operator wants to publish a track record —
  "here are my last 30 signed reads, look me up" — without running their own
  hosting.
- **Notes:** the register just lists; it doesn't score, rank, or curate. Same
  reason the meter doesn't rate — that would blur into product ladder.
- **Price:** read = free, write = cheap.

## What we do NOT build (self-clarifying non-examples)

- **A scry "pro" tier.** No.
- **A "safety score" endpoint.** The meter returns *numbers*, not a verdict.
  A "score" endpoint is where "we're an eval service" quietly becomes "we're
  a rating agency."
- **A hosted ward.** See "Bound stays local," above.
- **A subscription for any of these.** Pay-per-call, always. If someone wants
  cheaper, they run their own copy — everything's open source, they can.

## When to promote one from sketched → built

- Someone hits `/demo/profile` and asks a question the meter can't answer but
  a sibling would (real signal from real users).
- We hit an experiment (RH1 / RH2 / etc.) that would materially benefit from
  a specific sibling.
- We're bored on a rainy day and one of these is genuinely fun to build.

Never build a sibling *because it would let us charge more*. That inverts
the whole thing.
