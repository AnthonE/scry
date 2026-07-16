#!/usr/bin/env python3
"""
FSR Benchmark — Performance characterization at various security parameters.
"""

import time
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fsr.core import keygen, forward_map, forward_map_mining
from fsr.kem import fsr_kdf, SpectralCommitment, SpectralKeyExchange
from fsr.e2ee import create_session, symmetric_encrypt, symmetric_decrypt


def benchmark_forward_map(N_values, grid_multiplier=4, repeats=5):
    """Benchmark the forward map at various N."""
    print("\n─── Forward Map Benchmark ───────────────────────────────")
    print(f"{'N':>6} {'Grid':>6} {'Time (ms)':>12} {'Evals/s':>10} {'λ₀':>12}")
    print("-" * 54)

    for N in N_values:
        grid = max(N * grid_multiplier, 64)
        T = 1.0 / N
        c0 = np.sqrt(N)
        s = np.random.normal(0, np.sqrt(N), size=N)

        times = []
        lam0 = None
        for _ in range(repeats):
            t0 = time.perf_counter()
            eigenvalues = forward_map(s, T, c0, M=N, grid_size=grid)
            elapsed = time.perf_counter() - t0
            times.append(elapsed)
            lam0 = eigenvalues[0]

        avg_ms = np.mean(times) * 1000
        rate = 1.0 / np.mean(times)
        print(f"{N:>6} {grid:>6} {avg_ms:>12.2f} {rate:>10.1f} {lam0:>12.4f}")


def benchmark_keygen(N_values, repeats=3):
    """Benchmark key generation."""
    print("\n─── KeyGen Benchmark ───────────────────────────────────")
    print(f"{'N':>6} {'Time (ms)':>12} {'PK size (est)':>14} {'SK size (est)':>14}")
    print("-" * 52)

    for N in N_values:
        times = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            pk, sk = keygen(N=N)
            elapsed = time.perf_counter() - t0
            times.append(elapsed)

        avg_ms = np.mean(times) * 1000
        pk_bytes = N * 8 * 2 + 32
        sk_bytes = N * 8 + 32
        print(f"{N:>6} {avg_ms:>12.1f} {pk_bytes:>11d} B {sk_bytes:>11d} B")


def benchmark_kdf(N_values, repeats=5):
    """Benchmark FSR-KDF."""
    print("\n─── FSR-KDF Benchmark ──────────────────────────────────")
    print(f"{'N':>6} {'Time (ms)':>12} {'KDF/s':>10}")
    print("-" * 32)

    secret = b"benchmark-shared-secret"
    for N in N_values:
        times = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            fsr_kdf(secret, context=b'bench', N=N)
            elapsed = time.perf_counter() - t0
            times.append(elapsed)

        avg_ms = np.mean(times) * 1000
        rate = 1.0 / np.mean(times)
        print(f"{N:>6} {avg_ms:>12.2f} {rate:>10.1f}")


def benchmark_e2ee(repeats=20):
    """Benchmark E2EE session message throughput."""
    print("\n─── E2EE Session Benchmark ─────────────────────────────")

    shared_secret = os.urandom(32)
    t0 = time.perf_counter()
    alice = create_session(shared_secret, kdf_N=16)
    bob = create_session(shared_secret, kdf_N=16)
    session_ms = (time.perf_counter() - t0) * 1000
    print(f"  Session setup: {session_ms:.1f}ms (includes FSR-KDF)")

    msg = b"Hello! This is a benchmark message for E2EE throughput."

    enc_times = []
    dec_times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        ct = alice.encrypt(msg)
        enc_times.append(time.perf_counter() - t0)

        t0 = time.perf_counter()
        pt = bob.decrypt(ct)
        dec_times.append(time.perf_counter() - t0)
        assert pt == msg

    enc_ms = np.mean(enc_times) * 1000
    dec_ms = np.mean(dec_times) * 1000
    total_ms = enc_ms + dec_ms
    msgs_per_sec = 1000.0 / total_ms if total_ms > 0 else float('inf')
    print(f"  Encrypt: {enc_ms:.3f}ms/msg")
    print(f"  Decrypt: {dec_ms:.3f}ms/msg")
    print(f"  Throughput: {msgs_per_sec:.0f} msgs/s")


def benchmark_commitment(repeats=5):
    """Benchmark spectral commitment."""
    print("\n─── Spectral Commitment Benchmark ──────────────────────")

    value = b"benchmark-value"
    times_commit = []
    times_verify = []

    for _ in range(repeats):
        t0 = time.perf_counter()
        c, o = SpectralCommitment.commit(value)
        times_commit.append(time.perf_counter() - t0)

        t0 = time.perf_counter()
        SpectralCommitment.verify(c, o, value)
        times_verify.append(time.perf_counter() - t0)

    print(f"  Commit: {np.mean(times_commit)*1000:.2f}ms")
    print(f"  Verify: {np.mean(times_verify)*1000:.2f}ms")


def benchmark_key_exchange(repeats=3):
    """Benchmark spectral key exchange."""
    print("\n─── Spectral Key Exchange Benchmark ────────────────────")

    from fsr.e2ee import spectral_key_exchange
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        ak, bk, pub, valid = spectral_key_exchange()
        elapsed = time.perf_counter() - t0
        times.append(elapsed)
        assert ak == bk and valid

    print(f"  Full exchange: {np.mean(times)*1000:.1f}ms (avg of {repeats})")


def benchmark_mining(degrees, grid_size=32, repeats=20):
    """Benchmark on-chain compatible forward map."""
    print("\n─── Mining Forward Map Benchmark ────────────────────────")
    print(f"{'Degree':>8} {'Grid':>6} {'Time (ms)':>12} {'Spectra/s':>10}")
    print("-" * 40)

    for degree in degrees:
        times = []
        for _ in range(repeats):
            seed = os.urandom(32)
            t0 = time.perf_counter()
            forward_map_mining(seed, degree=degree, grid_size=grid_size)
            elapsed = time.perf_counter() - t0
            times.append(elapsed)

        avg_ms = np.mean(times) * 1000
        rate = 1.0 / np.mean(times)
        print(f"{degree:>8} {grid_size:>6} {avg_ms:>12.3f} {rate:>10.1f}")


def main():
    print("=" * 60)
    print("  FSR Cryptosystem Performance Benchmark")
    print("  Paper 145: Post-Quantum Spectral Cryptography")
    print("=" * 60)

    N_values = [8, 16, 24, 32, 64]
    mining_degrees = [4, 8, 16, 32]

    benchmark_forward_map(N_values)
    benchmark_keygen([8, 16, 24, 32])
    benchmark_kdf([8, 16, 24, 32])
    benchmark_e2ee()
    benchmark_commitment()
    benchmark_key_exchange()
    benchmark_mining(mining_degrees)

    if '--large' in sys.argv:
        print("\n─── Large N ────────────────────────────────────────────")
        benchmark_forward_map([128, 256], repeats=2)
        benchmark_keygen([128, 256], repeats=1)

    print(f"\n{'=' * 60}")
    print("  Benchmark complete.")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
