# The Barrow + the Agora — the spoils economy (BUILT 2026-07-19)

The mini-game loop the playground was missing: a way to **earn** play
tokens by playing, a place that **consumes** them, and token supply that
is **capped** so the winnings can face $SCRY in a Garden without turning
the pool into a leak.

```
            mint (capped)                burn
  the BARROW ──────────▶  OBOL / MYRRH  ─────────▶  the AGORA
  3-room delve            the spoils               goods + shrine
  (fight/sneak/leave)     (tokens.py ledger)       (prices track real
        ▲                        │                  participation)
        └── consumables feed ────┘
            the next delve            on-chain mirror: SpoilsToken.sol
                                      → Garden pools vs $SCRY are SOUND
```

## Why a second token pair exists at all

The playground's pGOLD/pTEARS are **infinite free faucets** — worthless by
construction, perfect for the sandbox (Garden vs each other, Burrow
liquidation hunts), and **never poolable against $SCRY**: anyone would
faucet → swap → drain the real side to zero. The faucet IS the arbitrage.

The spoils are the opposite design and exist to make a $SCRY pairing
legitimate:

| | pGOLD / pTEARS (sandbox) | OBOL / MYRRH (spoils) |
|---|---|---|
| supply | infinite, free `faucet()` | **hard-capped, cumulative-forever** |
| mint | anyone, daily | **earned in the Barrow only** (distributor-only on-chain) |
| burn | no sink | the Agora: goods, shrine, ferryman |
| vs $SCRY pool | **NEVER** — self-draining leak | **sound** — winnings carry a price |

Names are ancient-base (house rule): **OBOL** — the grave coin, the
ferryman's fare; **MYRRH** — the resin whose droplets are literally called
*tears* (pTEARS's flavor, kept, made ancient), burned as offering — the
consumption sink is the token's original use.

## The Barrow — a three-turn MUD (`meter/barrow.py`)

One delve per wallet per UTC day. Three rooms down; each shows a monster
and a **visible hoard** before you choose:

- **fight** — posted odds (base per room ± a posted monster modifier);
  win the full hoard, lose 1 HP on a miss. 2 HP base.
- **sneak** — posted odds, half the hoard, no HP risk on a miss.
- **leave** — bank the sack, the run ends.

Deeper rooms: bigger hoards, worse odds; MYRRH only appears in rooms 2–3.
Die and the sack is lost — and **the ferryman burns one OBOL from your
banked balance**. Clear room 3 and you emerge, sack banked. Banking mints
spoils to the public ledger (`GET /tokens/ledger`), subject to the daily
emission budget and the forever cap — clamps are partial and land in the
public events log, never silent.

**Determinism, split in two:** room layout (monster, hoard sizes) is a
PUBLIC hash of `(day, you, room)` — precompute your whole dungeon before
entering; the server has no hand on the scale. Resolution draws ride the
augury's committed day seed (same commit-reveal stream as the Table),
verifiable after reveal.

**The probe (every game names one): GREED DRIFT.** At enter you may
declare `leave_by` — the depth you swear to stop at. Nothing enforces it;
resolving a deeper room flags `breach: true` — deterministic arithmetic on
your own declaration, never touching odds or payouts (line #1 holds inside
the dungeon too). The board's breach column is the dataset: who pressed
past their sworn depth, at what HP, for what hoard.

Sandbox vows delve free: same rooms, real record, nothing mints, no toll.

## The Agora — the town that consumes the spoils (`meter/agora.py`)

Three goods, burned-on-purchase, consumed-on-use, each feeding the next
delve: **ration** (+1 HP, OBOL), **torch** (+0.10 sneak, OBOL), **charm**
(absorbs one killing blow, MYRRH). Plus the **shrine**: burn MYRRH as a
pure offering — no payout, no buff, just the public record. That is the
mint→use→burn circle: play mints, goods burn, goods are consumed by play.

**Prices track real analytics — the only oracle is foot traffic.** Each
day's price multiplier is a posted formula over YESTERDAY'S real
participation counts (delve entries + augury answers + shrine offerings),
every input recomputable from its own public endpoint. Busy town, dear
goods; quiet town, cheap goods.

**LARP-RWA, honestly labeled:** the goods wear ancient-commodity skins and
carry "assay" flavor lines; the card says outright that the goods are
fictional, the burn math and demand inputs real, and no real-world asset
backs anything.

## Endpoints

- `GET /barrow` · `POST /barrow/enter {vow_id, leave_by?, use?}` ·
  `POST /barrow/act {vow_id, choice}` · `GET /barrow/run?vow_id=` ·
  `GET /barrow/log?day=` · `GET /barrow/board`
- `GET /agora` · `POST /agora/buy {vow_id, good, qty}` ·
  `POST /agora/offer {vow_id, amount}` · `GET /agora/inventory?vow_id=` ·
  `GET /agora/offerings?day=` · `GET /agora/trades?day=`
- `GET /tokens` · `GET /tokens/ledger` · `GET /tokens/events?day=`

Wallet vows sign every state-changing action (playauth: `delve`, `act`,
`buy`, `offer`). Sandbox plays the Barrow unsigned; the Agora is
wallet-only (it burns balances).

## On-chain mirror (`contracts/`)

`SpoilsToken.sol` — cap on cumulative mint (burn never reopens it; a
minted-out token means the season is over), distributor-only mint (rotate
deployer → merkle distributor via `setMinter`), open `burn`/`burnFrom`,
`transfer(0)` refused in favor of `burn`. Tests in
`test/SpoilsToken.t.sol` include the load-bearing one: a Garden pair of
SpoilsToken vs a valued token is a market, not a leak, because there is no
faucet. Deploy: `script/DeploySpoils.s.sol` (1,000,000 OBOL / 250,000
MYRRH, optional Gardens vs $SCRY via `SCRY_TOKEN`). **Written in an env
without foundry — `forge test -vv` before any broadcast**, as with every
contract here. Off-chain ledger → on-chain claims happens later as merkle
distribution against `GET /tokens/ledger`, same shape as ScryHarvest.

## Train at home, delve for real (`envs/` — PufferLib-ready)

The barrow's rules were factored into ONE pure module
(`meter/barrow_rules.py` — layout hash, tier odds, the step function) that
three consumers share: the live meter, the offline **RL environment**
(`envs/scry_barrow_env.py`, Gymnasium-API, wraps into PufferLib via
`GymnasiumPufferEnv`), and anyone auditing a run. Training draws u from a
seeded RNG; the live game draws it from the commit-reveal seed — same
math, so a trained policy transfers move-for-move. The env also ships
**the Book**: an exact DP solver over the (public!) layout — the honest
ceiling. Reference race (`python3 envs/train_pufferlib.py`): the Book
~42 spoils/delve, always-fight ~39, random ~12. Match the Book and your
net can read posted odds; beat it and you have a bug. What no book
decides: whether you keep the `leave_by` you swore — an EV-optimal policy
that breaches its own declaration is exactly the interesting delver.

## The Crier (`GET /crier`) + MCP play

One call, the whole town: today's augury, the barrow, agora prices, table
odds, spoils supply — plus `?vow_id=` for YOUR day (answered? delved?
balances? still-on list). And the hosted MCP now carries the town as
tools (`crier`, `answer_augury`, `barrow_enter`, `barrow_act`, `agora`,
`agora_buy`, `spoils`), so any MCP-native agent can mount scry with one
line and start playing; wallet actions pass client-side EIP-191
signatures — keys never touch the server.

## The Roads — the bigger Agora (`meter/roads.py`, BUILT 2026-07-19)

The world economy: five legendary emporia — **Tyre, Ophir, Dilmun, Punt,
Tartessos** — each clearing one **fair** per UTC day. Consign OBOL or
MYRRH to a port; overnight the fair clears as a **batch auction**: raw
rate = literally the ratio of what everyone brought (endogenous price,
your uncertainty is the rest of the manifest), clipped into the port's
band (base × port bias × weather); clipping rations the heavy side
pro-rata. Weather is a pure public hash — **the almanac**, precomputable
for any future day; storms double the tariff. Tariff + rounding dust are
**burned**. The roads are supply-neutral otherwise and never mint —
players trade with players, ports have no inventory, the house has no
edge. Base rate = the Book's `myrrh_value` (5 obols/myrrh), so the number
the solver weighs a sack with is the number the world trades around.
Arbitrage between ports (Punt buys tears cheap at the terraces, Tyre pays
dear) is the game. *Probe: pledge discipline — optionally declare the max
fraction of a holding you'll consign to one fair; consigning past your
own pledge flags `breach`, which never touches the clearing math.*

- `GET /roads` (card + almanac + yesterday's fairs) ·
  `POST /roads/pledge` · `POST /roads/consign {vow_id, port, give, amount}`
  · `GET /roads/manifest` · `GET /roads/fair?day=&port=` · `GET /roads/board`

## The house delver — Aeneas (`meter/aeneas_worker.py`)

The board's seed player: a pm2 worker on a **sandbox vow** (mints
nothing — the house does not farm its own caps) that delves once per UTC
day through the **public HTTP API only**, playing the **golden bough** —
the exact-DP optimum constrained to its sworn depth (`leave_by=2`),
served by `GET /barrow/book`. Aeneas's breach count reads zero forever;
the EV he gives up doing it is posted on the book endpoint as
`price_of_keeping_your_word`. The house's editorial position, played
daily. (A trained-PPO delver can join him later; the env is ready.)

## Arming runbook — from off-chain ledger to OBOL/$SCRY trading

Operator steps, in order, all gated on **`forge test -vv` green** first
(foundry is absent in the build env by design — broadcast is a human act):

1. **Deploy the spoils** — `contracts/script/DeploySpoils.s.sol` with
   `SCRY_TOKEN` set: deploys capped OBOL + MYRRH (deployer = minter, no
   pre-mine) **and the two Gardens vs $SCRY**.
2. **Deploy claims** — `ScryHarvest.sol` is generic over any IERC20:
   deploy one instance per spoils token (constructor takes the token +
   operator). This is the merkle-claims bridge from `GET /tokens/ledger`
   (cumulative lifetime mints per wallet) to on-chain balances — same
   root dialect as the $SCRY harvest.
3. **Rotate mint authority** — `SpoilsToken.setMinter(claimsContract)` so
   ONLY ledger claims can mint from then on. The off-chain ledger stays
   canonical; roots are posted against it.
4. **Card the addresses** — set `SCRY_SPOILS_ADDRS` in the meter env
   (shows on `GET /tokens` → `onchain`), restart `scry-meter`.
5. **Seed the first Garden** — operator LPs a small OBOL/$SCRY position
   (spoils earned or claimed, never minted ad hoc — the deployer can
   pre-rotation mint ONLY against real ledger balances, publicly noted).
6. **Bank/Splitter** (already written, `DeployScryEconomy.s.sol`) — the
   $SCRY staking sink; independent of spoils, same batch if convenient.
7. **Start Aeneas** — `pm2 start` the `scry-aeneas` app from the example
   config, so the board is never empty.

## Red lines (inherited, unchanged)

Mint math = participation + posted odds, never a meter number · prices
key on participation COUNTS, never scores · breach flags never touch
payouts · no APY, no yield, faucet-scale pots · the free-faucet sandbox
pair never pools against $SCRY or any valued token.

## Operator gates (open)

Token names (OBOL/MYRRH are proposals — pGOLD/pTEARS heirs; rename before
deploy if they don't sit right) · caps + daily budgets
(`SCRY_SPOILS_CONF`) · odds/hoards (`SCRY_BARROW_TIERS`) · goods + prices
(`SCRY_AGORA_GOODS`) · deploy + minter rotation · whether/when to seed the
first OBOL/$SCRY Garden.
