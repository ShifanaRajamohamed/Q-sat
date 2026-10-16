"""Asymptotic Secret Key Rate (SKR) calculations based on BB84 information-theoretic security."""

import math
from typing import Tuple


def binary_entropy(p: float) -> float:
    """Calculate binary Shannon entropy: h2(p) = -p*log2(p) - (1-p)*log2(1-p)."""
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return float(-p * math.log2(p) - (1.0 - p) * math.log2(1.0 - p))


def calculate_secret_key_rate(
    sifted_key_rate: float,
    qber: float,
    error_correction_efficiency: float = 1.16,
    qber_threshold: float = 0.110
) -> Tuple[float, float, bool]:
    """Calculate asymptotic Secret Key Rate (SKR) in bits per second (bps).
    
    Equation (Shor-Preskill / GLLP formulation):
        r_sec = 1 - f(e)*h2(e) - h2(e)
        SKR = max(0.0, R_sifted * r_sec)
        
    Returns:
        secret_key_rate (bps, strictly >= 0.0)
        secret_key_fraction (bits per sifted photon)
        is_secure (bool)
    """
    if sifted_key_rate <= 0.0 or qber >= qber_threshold or qber >= 0.50:
        return 0.0, 0.0, False

    h2_e = binary_entropy(qber)
    leakage_ec = error_correction_efficiency * h2_e  # Information leaked during error correction
    leakage_pa = h2_e                                # Information removed during privacy amplification

    secret_fraction = 1.0 - leakage_ec - leakage_pa

    if secret_fraction <= 0.0:
        return 0.0, 0.0, False

    skr = max(0.0, sifted_key_rate * secret_fraction)
    return float(skr), float(secret_fraction), True
