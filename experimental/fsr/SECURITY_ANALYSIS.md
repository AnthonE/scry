# FSR Encryption Constructions — Honest Security Analysis

**Date:** 2026-03-18 (updated 2026-03-31)
**Status:** Research / proof-of-concept. NO production use.

---

## The Fundamental Question

Can FSR (Fisher Spectral Recovery) serve as the SOLE hardness assumption
for public-key encryption? Not just key derivation or commitment, but
full IND-CPA (or IND-CCA2) public-key encryption?

**Answer (updated 2026-03-31): Conditionally yes, under dFSR-C.**

The original dFSR assumption (vs uniform random) was broken — K-FSR-14
FIRED, logistic regression achieves 100% at all N (nb_fsr07). However,
the reformulated **dFSR-C** assumption (distinguish FSR instance from a
fresh draw from the same keygen distribution) is viable — K-FSR-19 FIRED
positively: accuracy 0.529 ± 0.020 at N=64 (chance level, nb_fsr11).

Under dFSR-C, the native §3.3 scheme in Paper 148 achieves IND-CPA, and
the FO-KEM (§3.4) achieves IND-CCA2 in the QROM. The hybrid FSR+LWE
(§3.5) remains recommended for production (defense-in-depth).

**Caveats:** (1) dFSR-C → FSR one-wayness reduction is informal.
(2) dFSR-C tested only to N=64, not N=256. (3) Individual keys ARE
distinguishable from each other (pairwise: 1.000); only the DISTRIBUTION
is indistinguishable.

The analysis below of why SPECIFIC constructions fail remains valid —
the constructions analyzed (SpectralSubsetSum, SpectralNativeKEM,
SpectralDualChannel) have structural problems beyond dFSR. The native
§3.3 scheme in Paper 148 is the one that dFSR-C resurrects.

Here's the original analysis, and what FSR CAN do.

---

## Why Pure FSR Public-Key Encryption Is Hard

### The Trapdoor Asymmetry Problem

For public-key encryption you need:
1. **Public key** derived from the secret (one-way)
2. **Encryption** using only the public key
3. **Decryption** requiring the secret
4. **Semantic security** — ciphertexts indistinguishable without secret

FSR gives us (1): eigenvalues λ are derived from superpotential s via
the forward map F(s) = λ. This IS one-way (Theorem 1.8, Fisher rank
collapse Theorem 2.2).

The problem is (2-4). The public key IS the eigenvalues. Any function
of eigenvalues is computable by everyone with the public key.

### Why Each Construction Fails as Standalone Crypto

**SpectralSubsetSum:**
- Subset S is in ciphertext
- Attacker computes Σ_{i∈S} λ_i from pk (eigenvalues are public)
- Subtracts from c to recover bit·gap/2 + noise
- Trivially decryptable by anyone with pk
- **Verdict: NOT semantically secure**
- **What it IS:** A demonstration that eigenvalue operations roundtrip correctly

**SpectralNativeKEM (v2):**
- Perturbation δ = λ' - λ is recoverable by anyone who has pk
- The "sign-based" shared key is derivable by anyone: signs = sign(λ' - λ)
- **Verdict: NOT a secure KEM** (shared key is public!)
- **What it IS:** A correct roundtrip mechanism that could be secured
  if eigenvalues were NOT in the pk (but then how does the encryptor work?)

**SpectralDualChannel:**
- The eigenstate-weight gap (exact vs noisy) is real in theory
- In practice: eigenvalues × weights ≈ eigenvalues × O(1), so weight
  noise is negligible relative to eigenvalue magnitude
- Attacker gets 100% accuracy even with 10× amplified weight noise
- **Verdict: Security gap does not manifest with current parameters**
- **What it IS:** A demonstration that eigenstate information alone
  is insufficient to create a usable security gap when eigenvalues
  are also known

### The Root Cause

In LWE, the matrix A is random and independent of the secret S.
The pair (A, AS + E) hides S in the noise.

In FSR, both eigenvalues λ and norming constants α are deterministic
functions of the SAME secret s. Publishing λ AND α̃ (noisy α) means
the noise in α̃ is the ONLY security — and it adds linearly while
the signal (bit encoding) also adds linearly, so the signal-to-noise
ratio doesn't degrade for the attacker.

**This is why pke.py uses LWE as the encryption mechanism.**
FSR provides the structural binding (keys are tied to a specific
spectral computation), but LWE provides the actual indistinguishability.

---

## What FSR CAN Do (Genuine Capabilities)

### 1. Symmetric Encryption (kem.py) ✓
FSR-KDF derives symmetric keys through eigenvalue computation.
Post-quantum: inverting requires solving FSR. ASIC-resistant.

### 2. Commitment Schemes (kem.py) ✓
Spectral commitment: commit to a value via eigenvalue spectrum.
Binding: collision resistance from spectral hash.
Hiding: eigenvalues don't reveal the committed value.

### 3. Proof of Computation (SpectralMiner.sol) ✓
Prove you performed a specific eigenvalue computation.
This is genuinely novel — no other PQC scheme has this property.

### 4. Hash Functions (core.py) ✓
spectral_hash: preimage resistance from FSR hardness.

### 5. Key Binding for LWE (pke.py) ✓
The LWE keypair is cryptographically bound to a specific SUSY
Hamiltonian computation. This means:
- You can't generate a valid keypair without the spectral computation
- The key material has physical/mathematical meaning
- This IS genuinely novel in PQC

### 6. Spectral Signatures (NOT YET IMPLEMENTED)
Sign a message by demonstrating knowledge of the superpotential
that produces a specific eigenvalue pattern. This is an FSR-native
construction that doesn't need LWE.

---

## Genuinely Novel Directions (Worth Pursuing)

### A. Ring-FSR (Compact Keys)
Use periodic superpotentials (Bloch waves on a circle) to get
algebraic structure analogous to Ring-LWE polynomial rings.
This could reduce pke.py key sizes from 128KB to ~1-4KB.

### B. FSR-Native Signatures
Schnorr-like protocol:
1. Prover commits to random superpotential perturbation
2. Challenge: hash of eigenvalue commitment
3. Response: masked superpotential that proves knowledge
   without revealing the full secret

### C. Verifiable Spectral Computation
Zero-knowledge proof that you performed a specific eigenvalue
computation. Combines FSR with SNARK/STARK techniques.
Application: on-chain verification without revealing the potential.

### D. Multi-Spectrum Encryption
Instead of (eigenvalues, norming constants), use MULTIPLE Hamiltonians
sharing a common spectral structure. The common structure is secret;
individual spectra are public. This creates an LWE-like problem:
many equations, one hidden variable (the common potential).

### E. Spectral Lattice (Novel Hardness Assumption)
The eigenvalue spacing distribution defines a LATTICE in spectral
space. Finding the closest lattice point to a given target spectrum
is a Closest Vector Problem on a novel lattice — not a standard
integer lattice, but one defined by the spectral geometry.
Could yield a new SVP variant with FSR-specific hardness.

---

## Summary Table

| Construction | Roundtrip | Semantically Secure | Novel Hardness | Status |
|---|---|---|---|---|
| pke.py (FSR + LWE) | ✓ | ✓ (LWE) | Dual (LWE + FSR) | Working |
| SubsetSum | ✓ | ✗ | None (eigenvalues public) | Demo only |
| NativeKEM | ✓ | ✗ | None (signs public) | Demo only |
| DualChannel | ✓ | ✗ | Gap doesn't manifest | Demo only |
| kem.py (symmetric) | ✓ | ✓ (FSR-KDF) | FSR | Working |
| SpectralCommitment | ✓ | ✓ (hiding) | FSR | Working |
| Ring-FSR | — | — | Potentially FSR | **TODO** |
| FSR Signatures | — | — | FSR | **TODO** |

---

## Kill Conditions for This Analysis

| ID | Condition | Fires if |
|---|---|---|
| K-NATIVE-1 | Pure FSR PKE exists | Someone constructs IND-CPA PKE from FSR alone |
| K-NATIVE-2 | DualChannel gap exists | Parameter regime found where exact weights >> noisy |
| K-NATIVE-3 | SubsetSum is secure | Construction without subset in ciphertext found |
| K-NATIVE-4 | Ring-FSR works | Periodic superpotentials give compact keys + security |

**Honest bottom line:** The pke.py construction (FSR + LWE) remains the
strongest. FSR's real contribution is structural — it gives the lattice
keys physical meaning and binds them to a specific computation. That's
novel and valuable, but LWE does the heavy lifting for encryption.

---

## External Precedent Validation (2026-03-18)

### Finsler Geometry Encryption (Nagano & Anada, 2020-2023)

PKE from asymmetric parallel displacement in Finsler spaces, proved
IND-CCA2 under the Decisional LPD (Linear Parallel Displacement) problem.
This validates the **category** of geometric one-way functions for crypto.

**What it means for FSR:** We are not the first to build crypto from
differential-geometric hardness. Nagano-Anada succeeded with a SIMPLER
construction (linear transport, no spectral theory, no SUSY). FSR is
strictly stronger: Čencov-unique metric (no coordinate escape), two-layer
hardness (measurement + fiber), SUSY trapdoor, quantized output.

**Actionable:** Their IND-CCA2 proof structure (via Fujisaki-Okamoto
transform on geometric primitives) could upgrade our IND-CPA to IND-CCA2.

### QFESTA (Crypto 2024) — Constructive Attack Pattern

QFESTA turns the Castryck-Decru SIDH attack into the RandIsogImages
algorithm for computing non-smooth-degree isogenies constructively.

**What it means for FSR:** Fisher rank collapse is currently treated as
a pure security argument. QFESTA suggests a constructive reading: the
(N-r)-dimensional fiber could serve as an encryption space (Fiber-KEM,
speculative). Two parties sharing effective parameters ξ communicate by
choosing different fiber points. See Paper 145 §5.6 for details.

**Status:** Speculative. The null-space perturbation produces zero spectral
change by definition, so a side channel is needed. This reduces to kem.py
(symmetric). A true Fiber-KEM needs approximate null-space perturbation
with a small but nonzero spectral signature.

---

## AI Cryptanalysis Threat (2026-03-18)

### DeepDistinguisher (Malhou, Perret & Lauter, SAC 2025)

**Threat:** Encoder-only transformer (~50M params) distinguishes Goppa
and QC-MDPC codes from random linear codes at >96% accuracy. Open-source
at facebookresearch/ai4code-cryptanalysis.

**FSR vulnerability:** The dFSR assumption (distinguish FSR eigenvalues
from random) is EXACTLY the kind of problem DeepDistinguisher targets.
FSR eigenvalue sequences have structural signatures:

1. **Double-well splitting** — exponentially close eigenvalue pairs (tunnel
   doublets) followed by widely-spaced continuum eigenvalues
2. **Low effective rank** — r = O(1) parameters control the full spectrum,
   creating low-dimensional structure detectable by learned features
3. **Wigner-type spacing** — eigenvalue spacing distribution differs from
   uniform random sequences

**Mitigating factors:**
- DeepDistinguisher collapses to chance at high Goppa degree t
- FSR at N=256 is far more complex than t=6 Goppa codes
- Noise injection (σ_e) can obscure the doublet signature
- Spectral shuffling (unsorted eigenvalues) removes ordering structure

**Required experiment (HP-FSR-AI):**
Train a 50M-param transformer on FSR vs random eigenvalue sequences at
N = 24, 32, 64, 128, 256. Measure accuracy vs N and noise level.

| KC | Fires if | Status |
|---|---|---|
| K-FSR-14 | Transformer accuracy > 0.9 at N=256, σ_e at correctness threshold | **OPEN** |
| K-FSR-15 | No countermeasure reduces accuracy below 0.7 at N=256 | **OPEN** |

**EXPERIMENTAL RESULT (HP-FSR-AI, nb_fsr07, 2026-03-18):**

K-FSR-14 **FIRED**. K-FSR-15 **FIRED**.

A simple 11-feature logistic regression achieves 100% accuracy at ALL
tested N (24, 32, 64, 128, 256). Not even a transformer needed. ALL
countermeasures failed: noise injection (1.000), spectral shuffling
(1.000), perturbative regime (1.000).

**dFSR as formulated (distinguish from uniform random) is BROKEN.**

The FSR+LWE construction (pke.py) is UNAFFECTED — it relies on LWE
for indistinguishability, not dFSR. The native §3 IND-CPA proof needs
reformulation: either (a) structured random baseline (random Schrödinger
spectra, not uniform scalars) or (b) gap-hiding variant.

**Previous honest assessment was correct:** the double-well pattern IS
too distinctive. The surprise is that it's trivial — not even adversarial
ML is needed, just basic statistics (spacing kurtosis, close-pair
fraction, growth exponent).

### Updated Kill Condition Table

| ID | Condition | Fires if | Status |
|---|---|---|---|
| K-NATIVE-1 | Pure FSR PKE exists | Someone constructs IND-CPA PKE from FSR alone | OPEN |
| K-NATIVE-2 | DualChannel gap exists | Parameter regime found where exact weights >> noisy | OPEN |
| K-NATIVE-3 | SubsetSum is secure | Construction without subset in ciphertext found | OPEN |
| K-NATIVE-4 | Ring-FSR works | Periodic superpotentials give compact keys + security | OPEN |
| K-FSR-12 | Finsler LPD broken | Polynomial-time LPD solver found | OPEN |
| K-FSR-13 | Fiber-KEM secure | Construction achieves IND-CPA from rank collapse alone | OPEN |
| K-FSR-14 | DeepDistinguisher breaks dFSR | Transformer accuracy > 0.9 at N≥256 | **FIRED** (nb_fsr07: 1.000 at all N) |
| K-FSR-15 | Spectral signature ineradicable | No countermeasure below 0.7 at N=256 | **FIRED** (nb_fsr07: all countermeasures 1.000) |
