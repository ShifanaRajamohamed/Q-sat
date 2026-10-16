"""Analytical Quantum Bit Error Rate (QBER) calculation and root-cause attribution.

Calculates composite QBER as a function of optical alignment, atmospheric phase jitter,
ambient stray light, mechanical pointing jitter, detector dark counts, and anomaly components.
"""

from typing import Tuple
import numpy as np

from backend.app.config import settings
from backend.app.models.environment import EnvironmentData
from backend.app.models.qkd import OpticalChannelState, QBERDecomposition


def calculate_qber(
    channel_state: OpticalChannelState,
    environment: EnvironmentData,
    anomaly_component: float = 0.0
) -> QBERDecomposition:
    """Calculate multi-factor composite QBER strictly bounded in [0.0, 0.50].
    
    QBER = base_error + atmospheric_noise + background_light_noise + pointing_error + detector_noise + anomaly_component
    """
    rx_signal = max(0.0, channel_state.received_photon_rate)
    bg_noise = max(0.0, channel_state.background_noise_rate)
    dark_noise = settings.DARK_COUNT_RATE * 50e6  # Absolute dark count rate

    # If no signal is received (e.g. satellite below horizon or complete cloud blockage),
    # the detector sees pure noise, yielding theoretical 50% random error
    if rx_signal <= 1e-3 or channel_state.transmittance <= 1e-9:
        return QBERDecomposition(
            base_error=settings.BASE_QBER,
            atmospheric_noise=0.10,
            background_light_noise=0.15,
            pointing_error=0.10,
            detector_noise=0.14,
            security_anomaly_component=anomaly_component,
            total_qber=0.50
        )

    # 1. Base optical error (imperfect polarization beam splitters, waveplate retardance error)
    base_err = settings.BASE_QBER  # Default 0.01 (1.0%)

    # 2. Atmospheric noise (turbulence-induced phase/polarization fluctuation)
    # Higher turbulence and high humidity slightly rotate photon polarization
    atm_err = 0.005 * (environment.turbulence ** 1.2) + 0.003 * (environment.humidity / 100.0)

    # 3. Background optical noise (ambient stray photons entering detector)
    # Stray photons arrive in random polarizations, contributing 50% error to their share of counts
    total_optical_counts = rx_signal + bg_noise
    bg_ratio = bg_noise / total_optical_counts if total_optical_counts > 0 else 1.0
    bg_err = 0.50 * bg_ratio

    # 4. Pointing / Mount vibration error (beam edge clipping and spatial mode distortion)
    vib_g = environment.vibration
    # Higher vibration increases pointing error; widening beam divergence partially mitigates this
    pointing_err = 0.015 * (vib_g ** 1.5)

    # 5. Detector dark count noise
    total_detector_counts = rx_signal + dark_noise
    dark_ratio = dark_noise / total_detector_counts if total_detector_counts > 0 else 1.0
    det_err = 0.50 * dark_ratio

    # 6. Potential security anomaly / eavesdropping disturbance
    sec_err = max(0.0, anomaly_component)

    # Composite sum clamped between base error and 0.50 (random guessing limit)
    raw_sum = base_err + atm_err + bg_err + pointing_err + det_err + sec_err
    total_qber = float(np.clip(raw_sum, 0.0, 0.50))

    return QBERDecomposition(
        base_error=round(float(base_err), 4),
        atmospheric_noise=round(float(atm_err), 4),
        background_light_noise=round(float(bg_err), 4),
        pointing_error=round(float(pointing_err), 4),
        detector_noise=round(float(det_err), 4),
        security_anomaly_component=round(float(sec_err), 4),
        total_qber=round(total_qber, 4)
    )
