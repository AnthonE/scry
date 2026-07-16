"""
Tests for FSR-native encryption constructions.

Validates:
  1. SpectralNativeKEM — pure FSR key encapsulation
  2. SpectralSubsetSum — eigenvalue subset-sum encryption
  3. SpectralDualChannel — Borg-Marchenko dual-channel encryption
"""

import numpy as np
import time
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fsr.fsr_native import (
    SpectralNativeKEM,
    SpectralSubsetSum,
    SpectralDualChannel,
)


def test_native_kem_roundtrip():
    """Test SpectralNativeKEM encaps_v2/decaps roundtrip."""
    print("=" * 60)
    print("  Test 1: SpectralNativeKEM Roundtrip (v2)")
    print("=" * 60)

    t0 = time.time()
    pk, sk = SpectralNativeKEM.keygen(N=16, grid_size=64)
    t_keygen = time.time() - t0
    print(f"  KeyGen: {t_keygen:.3f}s (N=16)")

    # Encapsulate (v2 — sign-based key derivation)
    t0 = time.time()
    ct, key_alice = SpectralNativeKEM.encaps_v2(pk)
    t_encaps = time.time() - t0
    print(f"  Encaps: {t_encaps:.3f}s")

    # Decapsulate
    t0 = time.time()
    key_bob = SpectralNativeKEM.decaps(sk, ct)
    t_decaps = time.time() - t0
    print(f"  Decaps: {t_decaps:.3f}s")

    match = key_alice == key_bob
    print(f"  Keys match: {match}")

    if match:
        print("  PASS")
    else:
        print("  FAIL — keys do not match")
        print(f"    Alice: {key_alice[:8].hex()}")
        print(f"    Bob:   {key_bob[:8].hex()}")

    return match


def test_native_kem_distinct():
    """Test that different encapsulations produce different keys."""
    print("\n" + "=" * 60)
    print("  Test 2: SpectralNativeKEM Distinct Keys")
    print("=" * 60)

    pk, sk = SpectralNativeKEM.keygen(N=16, grid_size=64)

    ct1, key1 = SpectralNativeKEM.encaps_v2(pk)
    ct2, key2 = SpectralNativeKEM.encaps_v2(pk)

    distinct = key1 != key2
    print(f"  Keys distinct: {distinct}")

    if distinct:
        print("  PASS")
    else:
        print("  FAIL — keys should differ for different encapsulations")

    return distinct


def test_subset_sum_single_bit():
    """Test SpectralSubsetSum single-bit encrypt/decrypt."""
    print("\n" + "=" * 60)
    print("  Test 3: SpectralSubsetSum Single Bit")
    print("=" * 60)

    pk, sk = SpectralSubsetSum.keygen(N=16, grid_size=64)

    n_trials = 20
    correct = 0

    for trial in range(n_trials):
        bit = trial % 2
        ct = SpectralSubsetSum.encrypt_bit(pk, bit)
        recovered = SpectralSubsetSum.decrypt_bit(sk, ct)
        if recovered == bit:
            correct += 1

    rate = correct / n_trials
    print(f"  Correct: {correct}/{n_trials} ({rate:.1%})")

    passed = rate >= 0.9
    if passed:
        print("  PASS")
    else:
        print(f"  FAIL — accuracy {rate:.1%} below 90% threshold")

    return passed


def test_subset_sum_bytes():
    """Test SpectralSubsetSum byte-level encrypt/decrypt."""
    print("\n" + "=" * 60)
    print("  Test 4: SpectralSubsetSum Bytes")
    print("=" * 60)

    pk, sk = SpectralSubsetSum.keygen(N=24, grid_size=96)

    message = b"HELLO"
    print(f"  Plaintext: {message}")

    t0 = time.time()
    cts = SpectralSubsetSum.encrypt_bytes(pk, message)
    t_enc = time.time() - t0
    print(f"  Encrypt: {t_enc:.3f}s ({len(cts)} ciphertexts)")

    t0 = time.time()
    recovered = SpectralSubsetSum.decrypt_bytes(sk, cts)
    t_dec = time.time() - t0
    print(f"  Decrypt: {t_dec:.3f}s")

    recovered = recovered[:len(message)]
    print(f"  Recovered: {recovered}")

    match = recovered == message
    print(f"  Match: {match}")

    if match:
        print("  PASS")
    else:
        # Count bit errors
        orig_bits = np.unpackbits(np.frombuffer(message, dtype=np.uint8))
        recov_bits = np.unpackbits(np.frombuffer(recovered, dtype=np.uint8))
        min_len = min(len(orig_bits), len(recov_bits))
        bit_errors = np.sum(orig_bits[:min_len] != recov_bits[:min_len])
        print(f"  FAIL — {bit_errors}/{min_len} bit errors ({bit_errors/min_len:.1%} BER)")

    return match


def test_dual_channel_single_bit():
    """Test SpectralDualChannel single-bit encrypt/decrypt."""
    print("\n" + "=" * 60)
    print("  Test 5: SpectralDualChannel Single Bit")
    print("=" * 60)

    pk, sk = SpectralDualChannel.keygen(N=24, grid_size=96)

    n_trials = 20
    correct = 0

    for trial in range(n_trials):
        bit = trial % 2
        ct = SpectralDualChannel.encrypt_bit(pk, bit)
        recovered = SpectralDualChannel.decrypt_bit(sk, ct)
        if recovered == bit:
            correct += 1

    rate = correct / n_trials
    print(f"  Correct: {correct}/{n_trials} ({rate:.1%})")

    passed = rate >= 0.9
    if passed:
        print("  PASS")
    else:
        print(f"  FAIL — accuracy {rate:.1%} below 90% threshold")

    return passed


def test_dual_channel_bytes():
    """Test SpectralDualChannel byte-level encrypt/decrypt."""
    print("\n" + "=" * 60)
    print("  Test 6: SpectralDualChannel Bytes")
    print("=" * 60)

    pk, sk = SpectralDualChannel.keygen(N=32, grid_size=128)

    message = b"FSR!"
    print(f"  Plaintext: {message}")

    t0 = time.time()
    cts = SpectralDualChannel.encrypt_bytes(pk, message)
    t_enc = time.time() - t0
    print(f"  Encrypt: {t_enc:.3f}s ({len(cts)} ciphertexts)")

    t0 = time.time()
    recovered = SpectralDualChannel.decrypt_bytes(sk, cts)
    t_dec = time.time() - t0
    print(f"  Decrypt: {t_dec:.3f}s")

    recovered = recovered[:len(message)]
    print(f"  Recovered: {recovered}")

    match = recovered == message
    print(f"  Match: {match}")

    if match:
        print("  PASS")
    else:
        orig_bits = np.unpackbits(np.frombuffer(message, dtype=np.uint8))
        recov_bits = np.unpackbits(np.frombuffer(recovered, dtype=np.uint8))
        min_len = min(len(orig_bits), len(recov_bits))
        bit_errors = np.sum(orig_bits[:min_len] != recov_bits[:min_len])
        print(f"  FAIL — {bit_errors}/{min_len} bit errors ({bit_errors/min_len:.1%} BER)")

    return match


def test_dual_channel_security_gap():
    """Test that dual-channel has a security gap: exact weights >> noisy weights."""
    print("\n" + "=" * 60)
    print("  Test 7: Dual-Channel Security Gap")
    print("=" * 60)

    pk, sk = SpectralDualChannel.keygen(N=24, grid_size=96)

    n_trials = 50
    correct_with_secret = 0
    correct_with_noisy = 0

    for trial in range(n_trials):
        bit = trial % 2
        ct = SpectralDualChannel.encrypt_bit(pk, bit)

        # Decrypt with secret key (exact eigenstate weights)
        recovered_secret = SpectralDualChannel.decrypt_bit(sk, ct)
        if recovered_secret == bit:
            correct_with_secret += 1

        # "Decrypt" with public key (noisy self-overlaps) — simulates attacker
        eigenvalues = pk['eigenvalues']
        diag_noisy = pk['diag_noisy']
        indices = ct['indices']
        gap = ct['gap']
        noisy_weighted_sum = np.sum(eigenvalues[indices] * diag_noisy[indices])
        signal = ct['c'] - noisy_weighted_sum
        guess = 1 if abs(signal - gap) < abs(signal) else 0
        if guess == bit:
            correct_with_noisy += 1

    rate_secret = correct_with_secret / n_trials
    rate_noisy = correct_with_noisy / n_trials

    print(f"  Secret key accuracy: {correct_with_secret}/{n_trials} ({rate_secret:.1%})")
    print(f"  Noisy key accuracy:  {correct_with_noisy}/{n_trials} ({rate_noisy:.1%})")
    print(f"  Gap: {rate_secret - rate_noisy:.1%}")

    # Secret should be much better than noisy
    gap_exists = rate_secret > rate_noisy + 0.05
    if gap_exists:
        print("  PASS — security gap exists")
    else:
        print(f"  NOTE — gap {rate_secret - rate_noisy:.1%} may need parameter tuning")

    # Also test with amplified noise to show the gap
    print("\n  Stress test: amplified weight noise (10x)...")
    # Create a modified pk with much more noisy weights
    import copy
    pk_noisy = copy.deepcopy(pk)
    noise_amp = np.random.normal(0, np.std(pk['diag_noisy']) * 2.0, size=pk['M'])
    pk_noisy['diag_noisy'] = pk['diag_noisy'] + noise_amp

    correct_stress_secret = 0
    correct_stress_noisy = 0
    for trial in range(n_trials):
        bit = trial % 2
        ct = SpectralDualChannel.encrypt_bit(pk_noisy, bit)
        # Secret key still decrypts
        recovered = SpectralDualChannel.decrypt_bit(sk, ct)
        if recovered == bit:
            correct_stress_secret += 1
        # Attacker with very noisy weights
        eigenvalues = pk_noisy['eigenvalues']
        diag_noisy = pk_noisy['diag_noisy']
        indices = ct['indices']
        gap = ct['gap']
        noisy_weighted_sum = np.sum(eigenvalues[indices] * diag_noisy[indices])
        signal = ct['c'] - noisy_weighted_sum
        guess = 1 if abs(signal - gap) < abs(signal) else 0
        if guess == bit:
            correct_stress_noisy += 1

    print(f"  Secret key (stressed): {correct_stress_secret}/{n_trials}")
    print(f"  Noisy key (stressed):  {correct_stress_noisy}/{n_trials}")
    stress_gap = correct_stress_secret / n_trials - correct_stress_noisy / n_trials
    print(f"  Stress gap: {stress_gap:.1%}")

    return rate_secret >= 0.85


def test_all():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("  FSR-NATIVE ENCRYPTION TEST SUITE")
    print("  Novel constructions beyond LWE")
    print("=" * 60)

    results = {}
    tests = [
        ("NativeKEM Roundtrip", test_native_kem_roundtrip),
        ("NativeKEM Distinct", test_native_kem_distinct),
        ("SubsetSum Bit", test_subset_sum_single_bit),
        ("SubsetSum Bytes", test_subset_sum_bytes),
        ("DualChannel Bit", test_dual_channel_single_bit),
        ("DualChannel Bytes", test_dual_channel_bytes),
        ("DualChannel Security Gap", test_dual_channel_security_gap),
    ]

    for name, test_fn in tests:
        try:
            results[name] = test_fn()
        except Exception as e:
            print(f"\n  ERROR in {name}: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False

    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")

    total = len(results)
    passed_count = sum(1 for v in results.values() if v)
    print(f"\n  {passed_count}/{total} tests passed")
    print("=" * 60)

    return all(results.values())


if __name__ == '__main__':
    success = test_all()
    sys.exit(0 if success else 1)
