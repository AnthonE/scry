"""
Tests for Ring-FSR compact-key encryption.
"""

import numpy as np
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fsr.ring_fsr import (
    RingFSR,
    build_periodic_hamiltonian,
    periodic_forward_map,
    circulant_multiply,
    circulant_multiply_mod,
    circulant_from_first_col,
)


def test_periodic_hamiltonian():
    """Test that periodic Hamiltonian has correct structure."""
    print("=" * 60)
    print("  Test 1: Periodic Hamiltonian Structure")
    print("=" * 60)

    N = 8
    s = np.random.normal(0, 1, size=N)
    T = 1.0 / N
    grid_size = 32

    H, theta, W = build_periodic_hamiltonian(s, T, L=1.0, grid_size=grid_size)

    # Check symmetry
    sym_error = np.max(np.abs(H - H.T))
    print(f"  Symmetry error: {sym_error:.2e}")

    # Check periodic BCs: H[0, G-1] and H[G-1, 0] should be nonzero
    has_periodic = H[0, grid_size - 1] != 0 and H[grid_size - 1, 0] != 0
    print(f"  Periodic BCs: {has_periodic}")

    # Eigenvalues should be real
    eigenvalues = np.linalg.eigvalsh(H)
    print(f"  Eigenvalues (first 5): {eigenvalues[:5]}")

    passed = sym_error < 1e-12 and has_periodic
    print(f"  {'PASS' if passed else 'FAIL'}")
    return passed


def test_periodic_forward_map():
    """Test periodic forward map roundtrip."""
    print("\n" + "=" * 60)
    print("  Test 2: Periodic Forward Map")
    print("=" * 60)

    N = 16
    s = np.random.normal(0, np.sqrt(N), size=N)
    T = 1.0 / N

    eigenvalues = periodic_forward_map(s, T, M=N, grid_size=64)
    print(f"  N={N}, M={N}")
    print(f"  Eigenvalues range: [{eigenvalues[0]:.2f}, {eigenvalues[-1]:.2f}]")
    print(f"  Spectral gap: {eigenvalues[1] - eigenvalues[0]:.4f}")

    # Verify determinism
    eigenvalues2 = periodic_forward_map(s, T, M=N, grid_size=64)
    deterministic = np.allclose(eigenvalues, eigenvalues2)
    print(f"  Deterministic: {deterministic}")

    passed = deterministic and len(eigenvalues) == N
    print(f"  {'PASS' if passed else 'FAIL'}")
    return passed


def test_circulant_multiply():
    """Test cyclic convolution (polynomial multiplication)."""
    print("\n" + "=" * 60)
    print("  Test 3: Cyclic Convolution (Polynomial Multiply)")
    print("=" * 60)

    n = 8
    a = np.random.randint(0, 100, size=n).astype(np.float64)
    b = np.random.randint(0, 100, size=n).astype(np.float64)

    # Our function
    result = circulant_multiply(a, b)

    # Matrix form: C[i,j] = a[(i-j) mod n], then C @ b
    C = circulant_from_first_col(a)
    result_matrix = C @ b

    error = np.max(np.abs(result - result_matrix))
    print(f"  Function vs matrix error: {error:.2e}")

    # Commutativity check
    result_ba = circulant_multiply(b, a)
    comm_error = np.max(np.abs(result - result_ba))
    print(f"  Commutativity error (a*b vs b*a): {comm_error:.2e}")

    passed = error < 1e-8 and comm_error < 1e-8
    print(f"  {'PASS' if passed else 'FAIL'}")
    return passed


def test_circulant_multiply_mod():
    """Test modular cyclic convolution."""
    print("\n" + "=" * 60)
    print("  Test 4: Cyclic Convolution Mod q")
    print("=" * 60)

    n = 8
    q = 12289
    a = np.random.randint(0, q, size=n, dtype=np.int64)
    b = np.random.randint(0, q, size=n, dtype=np.int64)

    result = circulant_multiply_mod(a, b, q)

    # Verify mod q
    all_in_range = np.all((result >= 0) & (result < q))
    print(f"  All results in [0, q): {all_in_range}")

    # Commutativity
    result_ba = circulant_multiply_mod(b, a, q)
    commutative = np.array_equal(result, result_ba)
    print(f"  Commutative (a*b == b*a): {commutative}")

    # Direct matrix verification
    C = circulant_from_first_col(a.astype(np.float64)).astype(np.int64)
    expected = np.zeros(n, dtype=np.int64)
    for i in range(n):
        s = 0
        for j in range(n):
            s += int(C[i, j]) * int(b[j])
        expected[i] = s % q
    match = np.array_equal(result, expected)
    print(f"  Matches matrix form: {match}")

    passed = all_in_range and commutative and match
    print(f"  {'PASS' if passed else 'FAIL'}")
    return passed


def test_ring_fsr_keygen():
    """Test Ring-FSR key generation."""
    print("\n" + "=" * 60)
    print("  Test 5: Ring-FSR KeyGen")
    print("=" * 60)

    t0 = time.time()
    pk, sk = RingFSR.keygen(N_fsr=16, n_ring=64)
    t_keygen = time.time() - t0
    print(f"  KeyGen: {t_keygen:.3f}s (N_fsr=16, n_ring=64)")

    # Check key structure
    print(f"  pk keys: {list(pk.keys())}")
    print(f"  A_row shape: {pk['A_row'].shape}")
    print(f"  B_row shape: {pk['B_row'].shape}")
    print(f"  q = {pk['q']}")

    # Key sizes
    sizes = RingFSR.key_sizes(n_ring=64)
    print(f"  pk size: {sizes['pk_bytes']} bytes")
    print(f"  ct size: {sizes['ct_bytes']} bytes")

    passed = pk['A_row'].shape == (64,) and pk['B_row'].shape == (64,)
    print(f"  {'PASS' if passed else 'FAIL'}")
    return passed


def test_ring_fsr_encrypt_decrypt():
    """Test Ring-FSR single-block encrypt/decrypt."""
    print("\n" + "=" * 60)
    print("  Test 6: Ring-FSR Encrypt/Decrypt")
    print("=" * 60)

    pk, sk = RingFSR.keygen(N_fsr=16, n_ring=64)

    # Encrypt a block of bits
    n = pk['n_ring']
    msg = np.random.randint(0, 2, size=n, dtype=np.uint8)

    t0 = time.time()
    c1, c2 = RingFSR.encrypt_block(pk, msg)
    t_enc = time.time() - t0

    t0 = time.time()
    recovered = RingFSR.decrypt_block(sk, c1, c2)
    t_dec = time.time() - t0

    n_correct = np.sum(recovered[:n] == msg)
    accuracy = n_correct / n
    print(f"  Encrypt: {t_enc * 1000:.2f}ms")
    print(f"  Decrypt: {t_dec * 1000:.2f}ms")
    print(f"  Bit accuracy: {n_correct}/{n} ({accuracy:.1%})")

    passed = accuracy >= 0.99
    print(f"  {'PASS' if passed else 'FAIL'}")
    return passed


def test_ring_fsr_kem_roundtrip():
    """Test Ring-FSR KEM encaps/decaps."""
    print("\n" + "=" * 60)
    print("  Test 7: Ring-FSR KEM Roundtrip")
    print("=" * 60)

    t0 = time.time()
    pk, sk = RingFSR.keygen(N_fsr=16, n_ring=64)
    t_keygen = time.time() - t0

    t0 = time.time()
    ct, key_alice = RingFSR.encaps(pk)
    t_encaps = time.time() - t0

    t0 = time.time()
    key_bob = RingFSR.decaps(sk, ct)
    t_decaps = time.time() - t0

    match = key_alice == key_bob
    print(f"  KeyGen: {t_keygen:.3f}s")
    print(f"  Encaps: {t_encaps:.3f}s")
    print(f"  Decaps: {t_decaps:.3f}s")
    print(f"  Keys match: {match}")

    if not match:
        print(f"    Alice: {key_alice[:8].hex()}")
        print(f"    Bob:   {key_bob[:8].hex()}")

    print(f"  {'PASS' if match else 'FAIL'}")
    return match


def test_ring_fsr_kem_distinct():
    """Test that different KEM encapsulations produce different keys."""
    print("\n" + "=" * 60)
    print("  Test 8: Ring-FSR KEM Distinct Keys")
    print("=" * 60)

    pk, sk = RingFSR.keygen(N_fsr=16, n_ring=64)

    ct1, key1 = RingFSR.encaps(pk)
    ct2, key2 = RingFSR.encaps(pk)

    distinct = key1 != key2
    print(f"  Keys distinct: {distinct}")
    print(f"  {'PASS' if distinct else 'FAIL'}")
    return distinct


def test_ring_fsr_key_sizes():
    """Report key size comparison."""
    print("\n" + "=" * 60)
    print("  Test 9: Key Size Comparison")
    print("=" * 60)

    sizes = RingFSR.key_sizes(n_ring=256)

    print(f"  Ring-FSR (n=256):")
    print(f"    pk: {sizes['pk_bytes']} bytes ({sizes['pk_bytes']/1024:.1f} KB)")
    print(f"    ct: {sizes['ct_bytes']} bytes ({sizes['ct_bytes']/1024:.1f} KB)")
    print(f"  Comparison:")
    print(f"    Plain Regev pk: {sizes['comparison']['plain_regev_pk']} bytes "
          f"({sizes['comparison']['plain_regev_pk']/1024:.0f} KB)")
    print(f"    Ring-FSR pk: {sizes['comparison']['ring_fsr_pk']} bytes")
    print(f"    Kyber-512 pk: {sizes['comparison']['kyber512_pk']} bytes")
    print(f"    Compression: {sizes['comparison']['compression_ratio']:.0f}×")

    passed = sizes['comparison']['compression_ratio'] > 50
    print(f"  {'PASS' if passed else 'FAIL'}")
    return passed


def test_all():
    """Run all Ring-FSR tests."""
    print("\n" + "=" * 60)
    print("  RING-FSR COMPACT KEY ENCRYPTION TEST SUITE")
    print("  Novel: periodic superpotentials for compact keys")
    print("=" * 60)

    results = {}
    tests = [
        ("Periodic Hamiltonian", test_periodic_hamiltonian),
        ("Periodic Forward Map", test_periodic_forward_map),
        ("Circulant Multiply", test_circulant_multiply),
        ("Circulant Multiply Mod", test_circulant_multiply_mod),
        ("Ring-FSR KeyGen", test_ring_fsr_keygen),
        ("Ring-FSR Encrypt/Decrypt", test_ring_fsr_encrypt_decrypt),
        ("Ring-FSR KEM Roundtrip", test_ring_fsr_kem_roundtrip),
        ("Ring-FSR KEM Distinct", test_ring_fsr_kem_distinct),
        ("Key Size Comparison", test_ring_fsr_key_sizes),
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
