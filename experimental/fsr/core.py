"""
FSR Core — Fisher Spectral Recovery forward map.

Implements the SUSY Hamiltonian construction and eigenvalue computation
from Paper 145 §1-§3. Uses Chebyshev basis on the Bernoulli manifold (0,1)
as specified in Definition 1.1.

The forward map F: R^N -> R^M computes:
  s (superpotential coefficients) -> lambda (eigenvalue sequence)

This is the "easy direction" — O(N^3) via tridiagonal eigensolver.
The inverse (FSR problem) is the hard direction — exponentially ill-conditioned.

On-chain compatibility note:
  The SpectralMiner contract and spectral-miner.mjs use a simpler polynomial
  basis on [-L, L]. This module uses the Paper 145 Chebyshev basis on (0,1).
  Use `forward_map_mining()` for on-chain compatible computation.
"""

import numpy as np
from hashlib import sha256
import struct
import os


# ─── Chebyshev Basis on (0,1) ─────────────────────────────────────────────

def chebyshev_T(n, x):
    """Chebyshev polynomial T_n evaluated at x.
    Paper 145 Def 1.1: phi_i(theta) = T_i(2*theta - 1)
    """
    # Use recurrence: T_0=1, T_1=x, T_{n+1}=2x*T_n - T_{n-1}
    if n == 0:
        return np.ones_like(x, dtype=np.float64)
    if n == 1:
        return x.copy()
    T_prev2 = np.ones_like(x, dtype=np.float64)
    T_prev1 = x.copy()
    for _ in range(2, n + 1):
        T_curr = 2.0 * x * T_prev1 - T_prev2
        T_prev2 = T_prev1
        T_prev1 = T_curr
    return T_prev1


def chebyshev_T_deriv(n, x):
    """First derivative of T_n at x.
    T_n'(x) = n * U_{n-1}(x) where U is Chebyshev of 2nd kind.
    Using: U_0=1, U_1=2x, U_{n+1}=2x*U_n - U_{n-1}
    """
    if n == 0:
        return np.zeros_like(x, dtype=np.float64)
    if n == 1:
        return np.ones_like(x, dtype=np.float64)
    U_prev2 = np.ones_like(x, dtype=np.float64)
    U_prev1 = 2.0 * x
    for _ in range(2, n):
        U_curr = 2.0 * x * U_prev1 - U_prev2
        U_prev2 = U_prev1
        U_prev1 = U_curr
    return float(n) * U_prev1


# ─── Superpotential Construction ──────────────────────────────────────────

def build_superpotential(s, T, c0, theta):
    """Construct superpotential W(theta) on the Bernoulli manifold.

    Paper 145 Algorithm 3.3 step 3:
      W(theta) = W_0(theta) + sum_i s_i * T_i(2*theta - 1)
      W_0(theta) = -c0 * theta*(1-theta) / sqrt(T)

    Args:
        s: array of N superpotential coefficients
        T: temperature parameter
        c0: reference potential strength (typically sqrt(N))
        theta: array of grid points in (0, 1)

    Returns:
        W: superpotential values at theta
        Wp: W'(theta) first derivative
        Wpp: W''(theta) second derivative
    """
    N = len(s)
    u = 2.0 * theta - 1.0  # Map (0,1) -> (-1,1)

    # Reference superpotential
    W0 = -c0 * theta * (1.0 - theta) / np.sqrt(T)
    W0p = -c0 * (1.0 - 2.0 * theta) / np.sqrt(T)
    W0pp = 2.0 * c0 / np.sqrt(T) * np.ones_like(theta)

    # Chebyshev expansion
    W = W0.copy()
    Wp = W0p.copy()
    Wpp = W0pp.copy()

    for i in range(N):
        Ti = chebyshev_T(i + 1, u)  # T_{i+1}(2θ-1), 1-indexed
        Ti_p = chebyshev_T_deriv(i + 1, u) * 2.0  # Chain rule: d/dθ = 2 * d/du

        # Second derivative of T_{i+1}(2θ-1) w.r.t. θ
        # d²/dθ² T_n(2θ-1) = 4 * T_n''(u)
        # Use: T_n''(x) = n * ((n+1)*T_n(x) - U_n(x)) / (x² - 1) for |x| < 1
        # Numerically stable: use finite difference for second deriv
        eps = 1e-7
        u_p = u + eps
        u_m = u - eps
        Ti_p_plus = chebyshev_T_deriv(i + 1, u_p) * 2.0
        Ti_p_minus = chebyshev_T_deriv(i + 1, u_m) * 2.0
        Ti_pp = (Ti_p_plus - Ti_p_minus) / (2.0 * eps)

        W += s[i] * Ti
        Wp += s[i] * Ti_p
        Wpp += s[i] * Ti_pp

    return W, Wp, Wpp


# ─── SUSY Hamiltonian ─────────────────────────────────────────────────────

def build_hamiltonian(s, T, c0, grid_size=256, domain=(0.001, 0.999)):
    """Build the SUSY Schrödinger Hamiltonian H_S = A†A on a discrete grid.

    Paper 145 Definition 1.2:
      V_S(theta) = W(theta)²/T - W'(theta)
      H_S = -T * d²/dθ² + V_S(theta)

    Uses Dirichlet boundary conditions on [0,1] (Paper 145 §1.2).

    Args:
        s: superpotential coefficients (length N = security parameter)
        T: temperature
        c0: reference potential strength
        grid_size: number of interior grid points
        domain: (theta_min, theta_max) to avoid boundary singularities

    Returns:
        H: grid_size × grid_size symmetric tridiagonal matrix
        theta: grid points
        W_vals: superpotential at grid points
    """
    theta = np.linspace(domain[0], domain[1], grid_size)
    dx = theta[1] - theta[0]

    W, Wp, Wpp = build_superpotential(s, T, c0, theta)

    # Schrödinger potential: V_S = W²/T - W'
    V_S = W * W / T - Wp

    # Build tridiagonal Hamiltonian
    # H = -T * d²/dθ² + V_S(θ)
    # Finite difference: -T * (ψ_{i-1} - 2ψ_i + ψ_{i+1}) / dx²
    G = grid_size
    H = np.zeros((G, G), dtype=np.float64)

    kinetic = T / (dx * dx)

    for i in range(G):
        H[i, i] = 2.0 * kinetic + V_S[i]
        if i > 0:
            H[i, i - 1] = -kinetic
        if i < G - 1:
            H[i, i + 1] = -kinetic

    return H, theta, W


def build_partner_hamiltonian(s, T, c0, grid_size=256, domain=(0.001, 0.999)):
    """Build the SUSY partner Hamiltonian H̃_S = AA†.

    Ṽ_S(theta) = W(theta)²/T + W'(theta)

    By Proposition 1.3: spec(H̃_S) = {λ_{n+1}} (shifted spectrum).
    """
    theta = np.linspace(domain[0], domain[1], grid_size)
    dx = theta[1] - theta[0]

    W, Wp, Wpp = build_superpotential(s, T, c0, theta)

    # Partner potential: Ṽ_S = W²/T + W'
    V_tilde = W * W / T + Wp

    G = grid_size
    H = np.zeros((G, G), dtype=np.float64)
    kinetic = T / (dx * dx)

    for i in range(G):
        H[i, i] = 2.0 * kinetic + V_tilde[i]
        if i > 0:
            H[i, i - 1] = -kinetic
        if i < G - 1:
            H[i, i + 1] = -kinetic

    return H, theta, W


# ─── Forward Map ──────────────────────────────────────────────────────────

def forward_map(s, T, c0, M=None, grid_size=256, return_states=False):
    """Compute the FSR forward map: s -> eigenvalues.

    Paper 145 Definition 1.4:
      F(s) = (λ_1(s), ..., λ_M(s))

    Complexity: O(grid_size^2) for tridiagonal eigensolver (not O(N^3) general).

    Args:
        s: superpotential coefficients (length N)
        T: temperature
        c0: reference potential strength
        M: number of eigenvalues to return (default: N)
        grid_size: Hamiltonian grid size
        return_states: if True, also return eigenstates

    Returns:
        eigenvalues: sorted array of M lowest eigenvalues
        eigenstates: (only if return_states=True) M × grid_size matrix
    """
    N = len(s)
    if M is None:
        M = N

    H, theta, W = build_hamiltonian(s, T, c0, grid_size)

    if return_states:
        eigenvalues, eigenstates = np.linalg.eigh(H)
        idx = np.argsort(eigenvalues)[:M]
        return eigenvalues[idx], eigenstates[:, idx], theta
    else:
        eigenvalues = np.linalg.eigvalsh(H)
        eigenvalues.sort()
        return eigenvalues[:M]


def norming_constants(eigenstates, grid_size):
    """Compute norming constants (left-half localization).

    α_n = ∫_0^{1/2} |ψ_n(θ)|² dθ ≈ Σ_{j < G/2} |ψ_n[j]|² * dx

    These are the "second spectrum" in inverse spectral theory.
    By Borg-Marchenko, (eigenvalues, norming_constants) uniquely determine
    the potential. The norming constants serve as the trapdoor data:
    - With secret key (W): efficiently computable from eigenstates
    - Without secret key: requires solving the inverse spectral problem

    Args:
        eigenstates: M × grid_size matrix from forward_map(return_states=True)
        grid_size: number of grid points

    Returns:
        alpha: array of M norming constants, each in [0, 1]
    """
    half = grid_size // 2
    # Each column is an eigenstate; compute left-half probability
    alpha = np.sum(eigenstates[:half, :] ** 2, axis=0)
    # Normalize (eigenstates may not be perfectly normalized on partial domain)
    total = np.sum(eigenstates ** 2, axis=0)
    alpha = alpha / np.maximum(total, 1e-15)
    return alpha


# ─── Key Generation ───────────────────────────────────────────────────────

def keygen(N=24, grid_size=None):
    """Generate FSR key pair.

    Paper 145 Algorithm 3.3, corrected to include norming constants
    in the public key (required for working encryption).

    Security levels (from Paper 145 Table, Corollary 2.7):
      N=24  → AES-128 equivalent
      N=32  → AES-192 equivalent
      N=256 → NIST PQC Level 1

    Args:
        N: security parameter (superpotential degree)
        grid_size: Hamiltonian discretization (default: max(4*N, 64))

    Returns:
        pk: dict with eigenvalues, noisy norming constants, parameters
        sk: dict with secret coefficients, exact norming constants
    """
    if grid_size is None:
        grid_size = max(4 * N, 64)

    # Step 1: Sample secret (discrete Gaussian, σ = √N)
    sigma_s = np.sqrt(N)
    s = np.random.normal(0, sigma_s, size=N)

    # Step 2: Temperature
    T = 1.0 / N

    # Step 3: Reference potential strength
    c0 = np.sqrt(N)

    # Step 4: Forward map — eigenvalues AND eigenstates
    M = N  # Square system
    eigenvalues, eigenstates, theta = forward_map(
        s, T, c0, M=M, grid_size=grid_size, return_states=True
    )

    # Step 5: Norming constants (trapdoor data)
    alpha = norming_constants(eigenstates, grid_size)

    # Step 6: Add noise to norming constants for public key
    # Noise must be small enough for decryption but large enough for security
    # σ_α = 1/(8√M) gives correct decryption with prob ≥ 1 - negl(N)
    sigma_alpha = 1.0 / (8.0 * np.sqrt(M))
    alpha_noise = np.random.normal(0, sigma_alpha, size=M)
    alpha_noisy = alpha + alpha_noise

    # Public key
    pk = {
        'eigenvalues': eigenvalues,       # λ_1,...,λ_M
        'norming_noisy': alpha_noisy,      # α̃_1,...,α̃_M (noisy)
        'T': T,
        'c0': c0,
        'N': N,
        'M': M,
        'grid_size': grid_size,
    }

    # Secret key
    sk = {
        's': s,                            # Superpotential coefficients
        'T': T,
        'c0': c0,
        'N': N,
        'M': M,
        'grid_size': grid_size,
        'norming_exact': alpha,            # Exact norming constants (trapdoor)
        'eigenvalues': eigenvalues,        # Exact eigenvalues (for convenience)
    }

    return pk, sk


# ─── Mining-Compatible Forward Map ────────────────────────────────────────

def forward_map_mining(seed_bytes, degree=8, grid_size=32, L=3.0):
    """Forward map matching spectral-miner.mjs / SpectralMiner.sol.

    Uses polynomial basis on [-L, L] (not Chebyshev on (0,1)).
    This is the on-chain compatible version for spectral mining.

    Args:
        seed_bytes: 32-byte seed
        degree: polynomial degree
        grid_size: Hamiltonian grid size
        L: grid half-width

    Returns:
        eigenvalues: sorted array of all eigenvalues
        ground_energy: λ₀ (ground state)
        spectrum_hash: SHA-256 hash of eigenvalue encoding
    """
    # seed -> SHA-256 -> coefficients (matches spectral-miner.mjs)
    h = sha256(seed_bytes).digest()
    coeffs = []
    for i in range(degree + 1):
        idx = (i * 2) % len(h)
        raw = struct.unpack('>H', h[idx:idx + 2])[0]
        coeffs.append(raw / 65535.0 - 0.5)

    # Confining superpotential constraints (match spectral-miner.mjs)
    coeffs[0] = 0.0
    coeffs[1] = abs(coeffs[1]) + 0.5
    if degree >= 2:
        coeffs[degree] = abs(coeffs[degree]) + 0.1

    # Build Hamiltonian on [-L, L]
    dx = (2.0 * L) / (grid_size - 1)
    H = np.zeros((grid_size, grid_size))

    for i in range(grid_size):
        x = -L + i * dx

        # W'(x)
        Wp = sum(k * coeffs[k] * x ** (k - 1) for k in range(1, len(coeffs)))
        # W''(x)
        Wpp = sum(k * (k - 1) * coeffs[k] * x ** (k - 2)
                  for k in range(2, len(coeffs)))

        V = Wp * Wp - Wpp
        H[i, i] = 2.0 / (dx * dx) + V
        if i > 0:
            H[i, i - 1] = -1.0 / (dx * dx)
        if i < grid_size - 1:
            H[i, i + 1] = -1.0 / (dx * dx)

    eigenvalues = np.linalg.eigvalsh(H)
    eigenvalues.sort()

    # Spectrum hash (matches spectral-miner.mjs)
    buf = b''
    for ev in eigenvalues:
        fixed = int(np.clip(round(ev * 1e6), -2**62, 2**62))
        buf += struct.pack('>q', fixed)
    spec_hash = '0x' + sha256(buf).hexdigest()

    return eigenvalues, eigenvalues[0], spec_hash


# ─── Spectral Hash ────────────────────────────────────────────────────────

def spectral_hash(data, N=16, grid_size=64):
    """Hash function based on FSR forward map.

    Uses the data as a seed to generate superpotential coefficients,
    then returns the eigenvalue spectrum as the hash.

    Preimage resistance: finding data' with spectral_hash(data') = h
    requires solving FSR (exponentially hard for N ≥ 24).

    Args:
        data: bytes to hash
        N: security parameter
        grid_size: Hamiltonian grid size

    Returns:
        hash_bytes: 32-byte hash derived from eigenvalues
    """
    # Expand data to N coefficients via iterated hashing
    s = np.zeros(N)
    h = sha256(data).digest()
    for i in range(N):
        if i > 0 and i % 4 == 0:
            h = sha256(h).digest()
        idx = (i % 4) * 8
        s[i] = struct.unpack('>d', h[idx:idx + 8])[0]
        # Normalize to reasonable range
        s[i] = (s[i] % 10.0) - 5.0

    T = 1.0 / N
    c0 = np.sqrt(N)

    eigenvalues = forward_map(s, T, c0, M=N, grid_size=grid_size)

    # Compress eigenvalues to 32-byte hash
    buf = b''
    for ev in eigenvalues:
        buf += struct.pack('>d', ev)
    return sha256(buf).digest()
