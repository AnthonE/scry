# experimental/

> ⚠️ **Everything under `experimental/` is unvetted and NOT part of scry's shipping
> utility path.** No file in `gate.py`, `envelope.py`, `memory_shield.py`, or
> `scry_verify.py` imports anything here. This is where research-grade code lives so
> people can poke at it — held at arm's length on purpose.

| dir | what | status |
|---|---|---|
| [`fsr/`](fsr) | Post-quantum crypto from Fisher Spectral Recovery (Papers 145/148) | **Research / PoC — DO NOT USE IN PRODUCTION.** Ships its own `SECURITY_ANALYSIS.md` documenting where it breaks. A falsifier target, not a security tool. |

If you want crypto that actually secures something, use [`../envelope.py`](../envelope.py)
(Ed25519 signatures + stdlib symmetric seal) and a standard KEM (ML-KEM / Kyber).
