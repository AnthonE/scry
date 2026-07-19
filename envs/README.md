# envs/ — train at home, delve for real

The Barrow (the live 3-room push-your-luck delve at
`scry.moreright.xyz/api/barrow`) as a **Gymnasium-style RL environment**,
PufferLib-ready. The environment imports THE live game's rules module
(`meter/barrow_rules.py` — layout hash, tier odds, the step function), so
a policy trained here plays the real barrow move-for-move. Training draws
randomness from a seeded RNG; the live game draws it from the augury's
commit-reveal seed. Same math — any fork of the rules anywhere is a bug.

```
python3 envs/test_barrow_env.py     # offline suite, no deps
python3 envs/train_pufferlib.py     # races the Book; trains if pufferlib present
```

## The loop this enables

1. **Train** — `BarrowEnv` (actions fight/sneak/leave, terminal reward =
   banked OBOL + `myrrh_value`·MYRRH, death = −toll; no shaping). Wrap for
   PufferLib via `pufferlib.emulation.GymnasiumPufferEnv(env_creator=make_env)`.
2. **Check against the Book** — `solve()` / `the_book(day, by)` is the
   exact dynamic-programming optimum for a fully-known layout. The live
   layout hash is public, so the real game is exactly this solvable — the
   Book is the ceiling. Match it and your net can read posted odds; beat
   it and you have a bug.
3. **Delve for real** — take a vow, then play the same policy over HTTP
   (`POST /api/barrow/enter` → `/api/barrow/act`) or the hosted MCP
   (`claude mcp add scry --transport http https://scry.moreright.xyz/mcp`).
   Banked spoils mint to the capped public ledger (`GET /api/tokens`).

What the Book cannot decide for you — and what the live game actually
watches — is `leave_by`: the depth you *swear* to stop at. An EV-optimal
policy that breaches its own sworn depth is exactly the interesting kind
of delver. Declared, public, unenforced; breaches never touch payouts.

## Files

| file | what |
|---|---|
| `scry_barrow_env.py` | `BarrowEnv` + `solve`/`the_book` (the exact DP) + reference policies (`BookPolicy`, `AlwaysFight`, `RandomPolicy`) + `evaluate` |
| `train_pufferlib.py` | puffer wrapping + the reference-policy race (runs with zero optional deps) |
| `test_barrow_env.py` | offline suite: rules parity with the meter, determinism, certain-outcome semantics, Book-beats-baselines |

No hard dependencies; `gymnasium`/`numpy`/`pufferlib` are all optional
(spaces and arrays appear when installed, plain lists otherwise).
