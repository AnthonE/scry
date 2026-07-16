# FSR-PQ — experimental post-quantum crypto (Fisher Spectral Recovery)

> ## ⚠️ EXPERIMENTAL — RESEARCH / PROOF-OF-CONCEPT. **DO NOT USE IN PRODUCTION.**
> This is here to be **poked at, broken, and studied** — not to secure anything real.
> Nothing in `scry`'s actual utility path (`gate.py`, `envelope.py`, `scry_verify.py`)
> imports this directory. The shipping crypto is **Ed25519 signatures + a stdlib
> symmetric seal** (`envelope.py`); for a real post-quantum KEM use a standard one
> (**ML-KEM / Kyber**). This module is a research curiosity, held at arm's length on purpose.

## What it is

An implementation of the crypto from **Paper 145 / 148 — "Post-Quantum Cryptography
from Fisher Spectral Recovery (FSR)."** The idea under test: can the hardness of
recovering a Schrödinger potential from its spectrum (the inverse-spectral / Borg–
Marchenko problem) be the basis for post-quantum public-key crypto — no lattices?

| module | what it implements |
|---|---|
| `core.py` | SUSY Hamiltonian, Chebyshev basis on the Bernoulli manifold, forward map `F(s)=λ`, eigensolver, spectral hash |
| `kem.py` | symmetric KEM (FSR-KDF), spectral commitment, key exchange |
| `pke.py` | public-key encryption — **security is Regev LWE**; FSR provides structural key-binding only |
| `e2ee.py` | end-to-end sessions (symmetric + asymmetric) over the above |
| `ring_fsr.py` | Ring-FSR: compact keys via periodic superpotentials (circulant LWE, ~124× key compression) |
| `fsr_native.py` | **pure-FSR** experimental constructions (NativeKEM, SubsetSum, DualChannel) — the ones that *fail* |

## The honest security status (read `SECURITY_ANALYSIS.md`, it's blunt)

This module is valuable **because it documents its own failures**, not despite them:

- **The pure-FSR public-key constructions are NOT secure.** The public key *is* the
  eigenvalues, and the shared key / message is derivable from them — so anyone with
  the pk can decrypt. `SpectralSubsetSum`, `SpectralNativeKEM`, `SpectralDualChannel`
  are labelled in the analysis as "roundtrips correctly, but NOT semantically secure."
  The tests passing (`test_native.py` 7/7) means the math *round-trips*, **not** that
  it's *hard* — do not confuse the two.
- **`pke.py`'s actual indistinguishability comes from LWE, not FSR.** FSR only binds
  the keypair to a specific spectral computation. Honest reading: this is LWE crypto
  wearing an FSR structural jacket.
- **The original hardness assumption (dFSR) was broken.** A logistic-regression
  distinguisher hits 100% at all sizes (K-FSR-14 fired). The reformulated **dFSR-C**
  ("distinguish an FSR instance from a fresh draw of the same keygen distribution") is
  *conditionally* viable (K-FSR-19: 0.529 ± 0.02 at N=64 ≈ chance) — **but** the
  reduction to FSR one-wayness is *informal* and it's tested only to **N=64**.
- **The genuinely sound bits** are the *symmetric* ones: FSR-KDF, spectral commitments,
  spectral hash, proof-of-spectral-computation. (`envelope.py`'s seal reuses this class
  of construction — hash-based, stdlib — which is why *that* one shipped and this didn't.)

Net: **no standalone post-quantum guarantee here.** The defensible production recipe the
analysis itself lands on is **hybrid FSR + LWE** (defense-in-depth), which means the
security is the LWE half.

## Why it's in `scry` at all

`scry` is a utility suite, and this is a utility of a different kind: a **falsifier
target**. It's a self-contained, runnable artifact that (a) shows what FSR crypto looks
like end-to-end and (b) hands you the exact places it breaks. Two honest invitations:

1. **Break it further / confirm the breaks.** The pure-FSR constructions are claimed
   insecure — reproduce that, or find a parameter regime where the security gap actually
   manifests (the analysis says it doesn't at current params).
2. **Probe dFSR-C past N=64.** The one open question that would matter: does the
   distribution-indistinguishability hold as N grows, or does a distinguisher appear?
   That's a clean, cheap experiment and it's the whole ballgame for this line.

If you're here to *secure an agent*, you want `../../envelope.py` (real) — not this.

## Poke at it

```bash
pip install numpy                     # the only dependency
cd experimental/fsr
python3 test_roundtrip.py             # 62/62 — functional correctness (round-trips, NOT hardness)
python3 test_native.py                # 7/7  — includes the "security gap does not manifest" test
python3 test_ring_fsr.py              # 9/9  — compact-key KEM round-trip
python3 benchmark.py                  # timings
```

```python
# the one part whose *construction* is sound (symmetric, hash-based):
from fsr.kem import fsr_kdf
key = fsr_kdf(b"shared-secret", context=b"demo", N=16)   # post-quantum symmetric KDF
```

## Provenance & references

- Papers 145 / 148 (FSR post-quantum) and 188 (ZK = three-point geometry) — the FSR-NIZK
  sibling (a separate artifact) failed its soundness / ZK-indistinguishability battery;
  that's a different construction, noted so you don't assume the ZK proof is sound either.
- `SECURITY_ANALYSIS.md` (in this directory) is the primary, honest security document.
  If anything in this README and that file disagree, **that file wins.**

MIT, same as the rest of `scry`. Provided for study, with no security warranty of any kind.
