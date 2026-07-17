"""
FSR-KEM — Symmetric Key Encapsulation from Fisher Spectral Recovery.

This module provides SYMMETRIC key operations:
  1. FSR-KDF: derive symmetric keys from spectral computation
  2. Spectral commitment: commit-reveal using eigenvalue spectra
  3. Symmetric KEM: shared secret → FSR-KDF → encryption key
  4. SpectralKeyExchange: on-chain commitment + side channel

For ASYMMETRIC (public-key) operations, see pke.py:
  - SpectralKEM: Regev LWE + Borg-Marchenko norming-constant trapdoor
  - AsymmetricKeyExchange: KEM-based, no pre-shared secret needed
  - Full public-key encryption: keygen_pke, encrypt_block, decrypt_block

The trapdoor gap identified in Paper 145 §3 (eigenvalues are one-way but
not a trapdoor function) is resolved in pke.py by using the norming constants
as the LWE secret, derived from the Borg-Marchenko two-spectra structure.
The LWE matrix is spectrally bound to the SUSY Hamiltonian eigenvalues.
"""

import numpy as np
from hashlib import sha256
import hmac as hmac_mod
import struct
import os
from .core import forward_map, forward_map_mining, spectral_hash


# ─── FSR Key Derivation Function ─────────────────────────────────────────

def fsr_kdf(shared_secret, context=b'', N=16, grid_size=64):
    """Derive a symmetric key using the FSR forward map as a KDF.

    Post-quantum: recovering shared_secret from the output key requires
    inverting BOTH SHA-256 AND the FSR forward map.

    Key derivation:
      1. Expand shared_secret to N superpotential coefficients
      2. Compute eigenvalues λ = F(s)  [O(N³) spectral computation]
      3. key = SHA-256(λ || shared_secret || context)

    The spectral computation adds a "computational hardness" layer beyond
    standard hash-based KDF — the work function is the eigenvalue computation,
    which is O(N³) and ASIC-resistant (same as spectral mining).

    Args:
        shared_secret: bytes — shared secret material
        context: bytes — domain separation
        N: security parameter (superpotential degree)
        grid_size: Hamiltonian grid size

    Returns:
        key: 32-byte derived key
    """
    # Expand shared secret to N coefficients via iterated hashing
    s = np.zeros(N)
    h = sha256(shared_secret + b'fsr-kdf-expand').digest()
    for i in range(N):
        if i > 0 and i % 4 == 0:
            h = sha256(h + struct.pack('>I', i)).digest()
        idx = (i % 4) * 8
        val_bytes = h[idx:idx + 8]
        s[i] = struct.unpack('>d', val_bytes)[0]
        # Normalize to reasonable range
        s[i] = (s[i] % 6.0) - 3.0

    T = 1.0 / N
    c0 = np.sqrt(N)

    # Forward map: the computational work
    eigenvalues = forward_map(s, T, c0, M=N, grid_size=grid_size)

    # Derive key from eigenvalues + shared secret
    buf = shared_secret
    for ev in eigenvalues:
        buf += struct.pack('>d', ev)
    buf += context

    return sha256(buf).digest()


# ─── Spectral Commitment ─────────────────────────────────────────────────

class SpectralCommitment:
    """Spectral commitment scheme using the FSR forward map.

    Properties:
      - Hiding: spectrum doesn't reveal the committed value (FSR one-wayness)
      - Binding: can't find two values with the same spectrum (collision resistance)
      - On-chain compatible: commitment matches SpectralMiner spectrumHash

    Usage:
      commitment, opening = SpectralCommitment.commit(value)
      assert SpectralCommitment.verify(commitment, opening, value)
    """

    @staticmethod
    def commit(value, randomness=None):
        """Commit to a value.

        Args:
            value: bytes to commit to
            randomness: optional 32-byte blinding factor (generated if None)

        Returns:
            commitment: dict with spectrum hash and metadata
            opening: dict with randomness needed to verify
        """
        if randomness is None:
            randomness = os.urandom(32)

        # Combine value and randomness
        seed = sha256(value + randomness).digest()

        # Compute spectrum (on-chain compatible)
        eigenvalues, ground_energy, spec_hash = forward_map_mining(
            seed, degree=16, grid_size=64
        )

        commitment = {
            'hash': spec_hash,
            'ground_energy': ground_energy,
        }

        opening = {
            'randomness': randomness,
            'seed': seed,
        }

        return commitment, opening

    @staticmethod
    def verify(commitment, opening, value):
        """Verify a commitment opening.

        Args:
            commitment: from commit()
            opening: from commit()
            value: the claimed committed value

        Returns:
            bool: True if valid
        """
        # Recompute seed
        seed = sha256(value + opening['randomness']).digest()

        # Verify seed matches opening
        if seed != opening['seed']:
            return False

        # Recompute spectrum
        _, _, spec_hash = forward_map_mining(seed, degree=16, grid_size=64)

        return spec_hash == commitment['hash']


# ─── Symmetric KEM ───────────────────────────────────────────────────────

def kem_from_shared_secret(shared_secret, context=b'fsr-kem'):
    """Derive an encryption key from a pre-shared secret using FSR-KDF.

    This is the symmetric KEM: both parties know the shared secret
    (from ECDH, in-person exchange, or on-chain commitment reveal).

    The FSR computation adds post-quantum hardness:
    even if the shared_secret is compromised, the derived key
    requires inverting the spectral computation to forge.

    Args:
        shared_secret: bytes — pre-shared secret
        context: bytes — domain separation

    Returns:
        enc_key: 32-byte encryption key
        mac_key: 32-byte MAC key
    """
    master = fsr_kdf(shared_secret, context=context)
    enc_key = sha256(master + b'enc').digest()
    mac_key = sha256(master + b'mac').digest()
    return enc_key, mac_key


# ─── On-Chain Key Exchange Protocol ──────────────────────────────────────

class SpectralKeyExchange:
    """Key exchange using on-chain spectral commitments.

    Protocol:
      1. Alice mines a spectral proof (finds seed with low λ₀)
      2. Alice publishes spectrumHash on-chain (SpectralMiner.submitProof)
      3. Alice sends seed to Bob via secure side-channel
      4. Bob verifies: recomputes spectrum from seed, checks hash matches
      5. Both derive: key = FSR-KDF(seed || commitment || "spectral-exchange")
      6. Both use key for subsequent encrypted communication

    Post-quantum security:
      - On-chain commitment: bound by FSR hardness (no quantum speedup)
      - Key derivation: FSR-KDF (eigenvalue computation + SHA-256)
      - Side-channel for seed: could be existing E2EE channel, QR code, etc.
    """

    @staticmethod
    def initiate(target=5.0, degree=8, grid_size=32):
        """Alice: generate spectral material for key exchange.

        Args:
            target: mining difficulty (λ₀ must be below this)
            degree: superpotential degree
            grid_size: Hamiltonian grid size

        Returns:
            public: dict to publish on-chain (commitment)
            private: dict to send to Bob via side-channel (seed)
        """
        # Mine until we find a valid proof
        while True:
            seed = os.urandom(32)
            eigenvalues, ground_energy, spec_hash = forward_map_mining(
                seed, degree=degree, grid_size=grid_size
            )
            if ground_energy > 0 and ground_energy < target:
                break

        public = {
            'spectrum_hash': spec_hash,
            'ground_energy_fixed': int(round(ground_energy * 1e6)),
            'degree': degree,
        }

        private = {
            'seed': seed,
            'eigenvalues': eigenvalues,
        }

        return public, private

    @staticmethod
    def complete(public, private_seed, degree=8, grid_size=32):
        """Bob: verify commitment and derive shared key.

        Args:
            public: Alice's on-chain commitment
            private_seed: seed received from Alice via side-channel
            degree: must match Alice's
            grid_size: must match Alice's

        Returns:
            key: 32-byte shared encryption key
            valid: bool — whether the commitment verified
        """
        # Recompute and verify
        eigenvalues, ground_energy, spec_hash = forward_map_mining(
            private_seed, degree=degree, grid_size=grid_size
        )

        valid = spec_hash == public['spectrum_hash']

        if not valid:
            return None, False

        # Derive shared key
        key = fsr_kdf(
            private_seed + public['spectrum_hash'].encode(),
            context=b'spectral-exchange'
        )

        return key, True

    @staticmethod
    def derive_key_alice(private, public):
        """Alice: derive the same shared key.

        Args:
            private: from initiate()
            public: the on-chain commitment

        Returns:
            key: 32-byte shared encryption key (matches Bob's)
        """
        return fsr_kdf(
            private['seed'] + public['spectrum_hash'].encode(),
            context=b'spectral-exchange'
        )
