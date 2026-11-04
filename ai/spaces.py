"""Standardized Observation and Action Transformations for Q-SAT AI Controllers.

Ensures exact mathematical parity between training (QSATEnvironment) and inference (PPOController).
All normalization constants and clipping limits are centralized.
"""

from typing import Tuple
import numpy as np

from backend.app.config import settings
from backend.app.models.environment import EnvironmentData
from backend.app.models.qkd import OpticalChannelState, QKDMetrics
from backend.app.models.satellite import SatelliteState

OBSERVATION_DIM = 15
ACTION_DIM = 3


def build_normalized_observation(
    satellite: SatelliteState,
    environment: EnvironmentData,
    channel: OpticalChannelState,
    qkd: QKDMetrics,
    current_power_pct: float,
    current_photon_rate_norm: float,
    current_beam_divergence_norm: float
) -> np.ndarray:
    """Build canonical 15-dimensional observation vector in [0.0, 1.0].
    
    Shared identically between gym environment and controller inference.
    """
    elev_norm = max(0.0, min(1.0, (satellite.elevation_deg + 10.0) / 100.0))
    range_norm = max(0.0, min(1.0, satellite.slant_range_km / 2000.0))
    temp_norm = max(0.0, min(1.0, (environment.temperature + 20.0) / 70.0))
    hum_norm = max(0.0, min(1.0, environment.humidity / 100.0))
    light_norm = max(0.0, min(1.0, environment.ambient_light / 100000.0))
    vib_norm = max(0.0, min(1.0, environment.vibration / 2.0))
    cloud_norm = max(0.0, min(1.0, environment.cloud_factor))
    turb_norm = max(0.0, min(1.0, environment.turbulence))
    loss_norm = max(0.0, min(1.0, channel.total_loss_db / 60.0))
    qber_norm = max(0.0, min(1.0, qkd.qber / 0.50))
    skr_norm = max(0.0, min(1.0, qkd.secret_key_rate / 30000.0))
    rx_norm = max(0.0, min(1.0, channel.received_photon_rate / 500000.0))
    pwr_norm = max(0.0, min(1.0, current_power_pct / 100.0))
    rate_norm = max(0.0, min(1.0, current_photon_rate_norm))
    div_norm = max(0.0, min(1.0, current_beam_divergence_norm))

    return np.array([
        elev_norm, range_norm, temp_norm, hum_norm, light_norm,
        vib_norm, cloud_norm, turb_norm, loss_norm, qber_norm,
        skr_norm, rx_norm, pwr_norm, rate_norm, div_norm
    ], dtype=np.float32)


def apply_action_deltas(
    action: np.ndarray,
    current_power_pct: float,
    current_photon_rate_norm: float,
    current_beam_divergence_norm: float,
    rate_limit: float = settings.MAX_RATE_OF_CHANGE
) -> Tuple[float, float, float, float, float, float]:
    """Map continuous action [-1, 1]^3 to physical actuator setpoints and deltas.
    
    Returns:
        (new_power_pct, new_photon_rate, new_beam_div, delta_p, delta_r, delta_d)
    """
    clipped_action = np.clip(action, -1.0, 1.0)

    delta_p = float(clipped_action[0] * (rate_limit * 100.0))
    delta_r = float(clipped_action[1] * rate_limit)
    delta_d = float(clipped_action[2] * rate_limit)

    new_p = float(np.clip(
        current_power_pct + delta_p,
        settings.MIN_TRANSMISSION_POWER, settings.MAX_TRANSMISSION_POWER
    ))
    new_r = float(np.clip(
        current_photon_rate_norm + delta_r,
        settings.MIN_PHOTON_RATE, settings.MAX_PHOTON_RATE
    ))
    new_d = float(np.clip(
        current_beam_divergence_norm + delta_d,
        settings.MIN_BEAM_DIVERGENCE, settings.MAX_BEAM_DIVERGENCE
    ))

    return new_p, new_r, new_d, delta_p, delta_r, delta_d

