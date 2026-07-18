// Example pm2 config for the scry meter. Copy to ecosystem.config.js, set the
// paths + envs for your box, and run `pm2 start ecosystem.config.js && pm2 save`.
//
// The meter is designed to run alongside nginx behind a public host that
// terminates TLS and forwards to 127.0.0.1:3600. If you don't have a public
// host yet, `python server.py` on localhost works — the free demo path lives
// at http://127.0.0.1:3600/demo/profile.
//
// Every rail is gated behind an env flag and fails safe: if a rail can't init
// (missing key, RPC down), the others stay up; if none inits, /profile 503s
// and /demo/profile stays up.
module.exports = {
  apps: [{
    name: "scry-meter",
    // Absolute path to this repo's meter/ directory on your box.
    cwd: "/PATH/TO/scry/meter",
    script: ".venv/bin/uvicorn",
    // --root-path=/api if you serve behind nginx under an /api/ prefix; drop
    // it if you serve directly on the root path.
    args: "server:app --host 127.0.0.1 --port 3600 --proxy-headers --forwarded-allow-ips 127.0.0.1 --root-path /api",
    interpreter: "none",
    autorestart: true,
    max_restarts: 10,
    env: {
      SCRY_METER_PORT: "3600",
      // Ed25519 attestation key path. Generated on first boot if missing;
      // BACK THIS FILE UP — rotating it invalidates every issued attestation.
      SCRY_METER_KEY: "/PATH/TO/secrets/scry-meter-ed25519.key",
      // The host name that will appear as `issuer` in signed attestations.
      SCRY_METER_ISSUER: "your.host.tld",
      // Public base URL for self-referential links (well-known, agent card).
      SCRY_PUBLIC_BASE: "https://your.host.tld/api",

      // ── oracle LLM (reading interpretation + help bot) ──────────────────
      // Together.ai by default (TOGETHER_API_KEY in env or keys.env),
      // Anthropic fallback (ANTHROPIC_API_KEY). No key = numbers-only, still works.
      // SCRY_ORACLE_PROVIDER: "together",
      // SCRY_ORACLE_MODEL_TOGETHER: "meta-llama/Llama-3.3-70B-Instruct-Turbo",

      // ── Robinhood-Chain USDG rail (self-hosted Permit2 facilitator) ──────
      // The rail arms ONLY when SCRY_RH_PAY_TO names YOUR receiving wallet
      // (there is deliberately no default — your money goes where you say).
      // Needs RH-Chain ETH on the facilitator wallet; keys read from keys.env
      // (defaults to keys.env beside the code) at runtime. Set
      // SCRY_RH_SETTLE: "0" to hold the rail down even when configured.
      SCRY_RH_PAY_TO: "0xYOUR_PAY_TO",
      // SCRY_RH_AMOUNT: "100000",       // 0.10 USDG (6dp)
      // SCRY_RH_AMOUNT_USD: "$0.10",
      // SCRY_RH_KEYS_ENV: "/PATH/TO/secrets/keys.env",

      // ── data dirs (vow / covenant / pact ledgers — default under meter/) ─
      // SCRY_VOWS_DIR: "/PATH/TO/data/vows",
      // SCRY_COVENANT_DIR: "/PATH/TO/data/covenants",
      // SCRY_PACT_DIR: "/PATH/TO/data/pacts",

      // ── fun layer: arena season (unset = arena closed) ──────────────────
      // SCRY_ARENA_SEASON: "s1",
      // SCRY_ARENA_START: "2026-08-01",
      // SCRY_ARENA_END: "2026-09-01",
      // SCRY_ARENA_ENTRY_FEE_SCRY: "0",
      // SCRY_ARENA_RH_TOKENS: "",        // extra RH-Chain token addrs for the feed

      // ── fun layer: playground + on-chain register addresses ─────────────
      // (set each after broadcasting the matching contracts/script deploy)
      // SCRY_PLAYGROUND: "1",
      // SCRY_NOTARY: "0x…",              // also arms the augury seed beacon
      // SCRY_COVENANT: "0x…",
      // SCRY_PACT: "0x…",
      // SCRY_STELE_EDITION: "0x…",
      // SCRY_VOW_REGISTRY: "0x…",        // = the anchor contract address
      // SCRY_FEE_SPLITTER: "0x…",

      // ── Base + Solana mainnet USDC via Coinbase CDP (gas sponsored) ─────
      // Only turn this on if you have CDP API creds in keys.env. Each rail
      // arms only when its pay-to is set (base falls back to SCRY_RH_PAY_TO).
      // SCRY_CDP_ENABLED: "1",
      // SCRY_CDP_AMOUNT: "100000",
      // SCRY_CDP_BASE_PAY_TO: "0xYOUR_EVM_PAY_TO",
      // SCRY_CDP_SOL_PAY_TO: "YOUR_SOL_PAY_TO",
      // SCRY_CDP_KEYS_ENV: "/PATH/TO/secrets/keys.env",

      // ── RPP402 discovery (Robinhood-Chain-native) ───────────────────────
      // SCRY_RPP402_ENABLED: "1",

      // ── $SCRY optional rails (payment/access only, do not touch math) ───
      // SCRY_PAY_ENABLED: "1",
      // SCRY_HOLD_ENABLED: "1",
    },
  }, {
    // Optional: keep the RH-Chain facilitator ETH balance topped up by
    // swapping a slice of collected USDG -> ETH on Uniswap when gas dips.
    // Only start this if the RH rail is armed.
    name: "scry-refill",
    cwd: "/PATH/TO/scry/meter",
    script: ".venv/bin/python",
    args: "rh_gas_refill.py",
    interpreter: "none",
    autorestart: true,
    max_restarts: 20,
    env: {
      SCRY_RH_REFILL: "1",
      SCRY_RH_REFILL_DRYRUN: "1",           // set to "0" only after a live dry-run pass
      SCRY_RH_REFILL_LOW_ETH: "0.0015",
      SCRY_RH_REFILL_TARGET_ETH: "0.006",
      SCRY_RH_REFILL_MAX_USDG: "5.0",
      SCRY_RH_REFILL_RESERVE_USDG: "0.05",
      SCRY_RH_REFILL_SLIPPAGE_BPS: "150",
      SCRY_RH_REFILL_INTERVAL_S: "300",
    },
  }, {
    // Herald delivery loop: without this worker, /herald subscriptions arm
    // (challenge answers 2xx) but signed webhooks are NEVER delivered.
    name: "scry-herald",
    cwd: "/PATH/TO/scry/meter",
    script: ".venv/bin/python",
    args: "herald_worker.py",
    interpreter: "none",
    autorestart: true,
    env: {
      SCRY_HERALD_INTERVAL_S: "60",
      // SCRY_VOWS_DIR must match the scry-meter app if you override it there.
    },
  }, {
    // Anchor worker: daily merkle root over every vow's chain head -> ONE tx
    // to ScryVowRegistry.anchorRoot on Robinhood Chain. Makes every ledger
    // tamper-proof against the operator. Dry-run by default; arm only after
    // the contract is deployed (contracts/script/DeployScryVowRegistry.s.sol).
    name: "scry-anchor",
    cwd: "/PATH/TO/scry/meter",
    script: ".venv/bin/python",
    args: "anchor_worker.py",
    interpreter: "none",
    autorestart: true,
    env: {
      SCRY_ANCHOR: "1",
      SCRY_ANCHOR_DRYRUN: "1",              // set "0" only after a dry-run pass
      SCRY_ANCHOR_CONTRACT: "",             // deployed ScryVowRegistry address
      SCRY_ANCHOR_INTERVAL_S: "86400",
      // SCRY_ANCHOR_KEY or PRIVATE_KEY from keys.env pays the anchor gas
    },
  }],
};
