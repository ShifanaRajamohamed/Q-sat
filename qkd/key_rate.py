"""Raw and sifted key rate calculations for BB84 QKD protocol."""

from backend.app.config import settings


def calculate_raw_key_rate(
    received_photon_rate: float,
    detector_efficiency: float = 0.10
) -> float:
    """Calculate raw key rate in bits per second (bps) after single-photon detector detection.
    
    R_raw = R_rx * eta_det
    """
    if received_photon_rate <= 0.0 or detector_efficiency <= 0.0:
        return 0.0
    return float(received_photon_rate * detector_efficiency)


def calculate_sifted_key_rate(
    raw_key_rate: float,
    basis_matching_probability: float = 0.50
) -> float:
    """Calculate sifted key rate in bits per second (bps) after basis reconciliation.
    
    R_sifted = R_raw * P_basis
    """
    if raw_key_rate <= 0.0:
        return 0.0
    return float(raw_key_rate * basis_matching_probability)
