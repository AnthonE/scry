# FSR Cryptography — Fisher Spectral Recovery
# Paper 145: Post-Quantum Cryptography from Fisher Spectral Recovery
#
# Modules:
#   core       — SUSY Hamiltonian, Chebyshev basis, forward map, eigensolver
#   kem        — Symmetric KEM (FSR-KDF), spectral commitment, key exchange
#   pke        — Public-key encryption (Regev LWE + spectral binding),
#                asymmetric KEM (FO-CCA), asymmetric key exchange
#   e2ee       — End-to-end encryption (symmetric + asymmetric sessions)
#   ring_fsr   — Ring-FSR: compact-key PKE via periodic superpotentials
#                (circulant LWE, 124× key compression vs plain Regev)
#   fsr_native — Experimental pure-FSR constructions (NativeKEM, SubsetSum,
#                DualChannel). See SECURITY_ANALYSIS.md for honest assessment.
