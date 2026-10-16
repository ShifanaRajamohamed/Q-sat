"""Optical Channel Model: Link budget, diffraction, pointing jitter, and noise calculation.

Calculates free-space geometric diffraction, atmospheric extinction, pointing errors,
scintillation fading, received photon rates, and optical signal-to-noise ratio.
"""

import math
from typing import Optional
import numpy as np

from backend.app.config import settings
from backend.app.models.environment import EnvironmentData
from backend.app.models.qkd import OpticalChannelState
from backend.app.models.satellite import SatelliteState
from digital_twin.atmospheric_model import AtmosphericModel


class OpticalChannelModel:
    """Calculates optical link budget and received optical states."""

    def __init__(
        self,
        receiver_aperture_m: float = 1.0,       # Ground station telescope mirror diameter (1.0 meter)
        min_divergence_urad: float = 10.0,      # Minimum diffraction-limited divergence half-angle (10 microradians)
        max_divergence_urad: float = 100.0,     # Maximum expanded divergence half-angle (100 microradians)
        optical_efficiency_rx: float = 0.65,    # Telescope optics and coupling transmission efficiency
        vibration_jitter_coeff: float = 25.0,   # Micro-radians of pointing jitter per 1.0 g of vibration
        stray_light_coeff: float = 0.15         # Noise counts per sec per lux (with sub-nanometer spectral bandpass filter)
    ):
        self.receiver_aperture_radius_m = receiver_aperture_m / 2.0
        self.min_divergence_urad = min_divergence_urad
        self.max_divergence_urad = max_divergence_urad
        self.optical_efficiency_rx = optical_efficiency_rx
        self.vibration_jitter_coeff = vibration_jitter_coeff
        self.stray_light_coeff = stray_light_coeff

        self.atmospheric_model = AtmosphericModel(wavelength_nm=settings.OPTICAL_WAVELENGTH_NM)

    def calculate_link_state(
        self,
        satellite: SatelliteState,
        environment: EnvironmentData,
        transmission_power_pct: float = 100.0,  # [0, 100%]
        photon_rate_norm: float = 1.0,          # [0, 1] normalized to MAX_PHOTON_RATE (e.g. 100 MHz base)
        beam_divergence_norm: float = 0.20      # [0, 1] normalized between min & max divergence
    ) -> OpticalChannelState:
        """Compute comprehensive optical channel link budget and return OpticalChannelState."""
        # 1. Base Transmitter Quantities
        base_rate_hz = 50e6  # 50 MHz base single-photon pulse repetition frequency
        tx_photon_rate = base_rate_hz * max(0.01, photon_rate_norm) * (max(1.0, transmission_power_pct) / 100.0)

        # If satellite is below line-of-sight threshold, link is physically blocked
        if not satellite.is_visible or satellite.elevation_deg < settings.MIN_ELEVATION:
            return OpticalChannelState(
                total_loss_db=100.0,
                transmittance=0.0,
                fspl_loss_db=60.0,
                atmospheric_loss_db=40.0,
                pointing_loss_db=0.0,
                scintillation_loss_db=0.0,
                received_photon_rate=0.0,
                background_noise_rate=round(environment.ambient_light * self.stray_light_coeff + 100.0, 1),
                snr_db=-99.0,
                beam_spot_radius_m=1000.0
            )

        # 2. Free Space Geometric Loss (Diffraction Beam Divergence)
        # Map normalized divergence [0, 1] to microradians
        divergence_urad = self.min_divergence_urad + beam_divergence_norm * (self.max_divergence_urad - self.min_divergence_urad)
        divergence_rad = divergence_urad * 1e-6

        slant_range_m = satellite.slant_range_km * 1000.0
        beam_spot_radius_m = max(0.1, divergence_rad * slant_range_m)

        # Geometric collection efficiency (Gaussian beam intercepted by circular telescope aperture)
        ratio_sq = (self.receiver_aperture_radius_m / beam_spot_radius_m) ** 2
        eta_geom = 1.0 - math.exp(-2.0 * ratio_sq)
        eta_geom = float(np.clip(eta_geom * self.optical_efficiency_rx, 1e-8, 1.0))
        fspl_loss_db = -10.0 * math.log10(eta_geom)

        # 3. Atmospheric Loss (Extinction + Clouds + Turbulence Scintillation)
        eta_atm, atm_loss_db, scint_var = self.atmospheric_model.calculate_atmospheric_transmission(
            elevation_deg=satellite.elevation_deg,
            humidity_percent=environment.humidity,
            cloud_factor=environment.cloud_factor,
            turbulence_index=environment.turbulence
        )

        # 4. Pointing Error & Vibration Jitter Loss
        # Vibration causes angular jitter (micro-radians)
        pointing_jitter_urad = max(0.5, environment.vibration * self.vibration_jitter_coeff)
        pointing_jitter_rad = pointing_jitter_urad * 1e-6
        displacement_m = pointing_jitter_rad * slant_range_m

        # If beam spot is narrow, displacement causes severe clipping.
        # If beam spot is wide, beam clipping is less severe (control trade-off).
        pointing_penalty = math.exp(-2.0 * ((displacement_m / beam_spot_radius_m) ** 2))
        eta_pointing = float(np.clip(pointing_penalty, 1e-6, 1.0))
        pointing_loss_db = -10.0 * math.log10(eta_pointing)

        # 5. Combined Channel Transmittance and Path Loss
        total_transmittance = float(np.clip(eta_geom * eta_atm * eta_pointing, 1e-12, 1.0))
        total_loss_db = -10.0 * math.log10(max(1e-12, total_transmittance))

        # 6. Received Signal and Ambient Noise Counts
        rx_photon_rate = tx_photon_rate * total_transmittance
        bg_noise_rate = (environment.ambient_light * self.stray_light_coeff) + 200.0  # ambient stray light + dark counts

        # Signal-to-Noise Ratio (dB)
        if bg_noise_rate > 0.0 and rx_photon_rate > 0.0:
            snr_db = 10.0 * math.log10(rx_photon_rate / bg_noise_rate)
        else:
            snr_db = -99.0

        return OpticalChannelState(
            total_loss_db=round(float(total_loss_db), 2),
            transmittance=round(float(total_transmittance), 8),
            fspl_loss_db=round(float(fspl_loss_db), 2),
            atmospheric_loss_db=round(float(atm_loss_db), 2),
            pointing_loss_db=round(float(pointing_loss_db), 2),
            scintillation_loss_db=round(float(scint_var * 4.34), 2),
            received_photon_rate=round(float(rx_photon_rate), 2),
            background_noise_rate=round(float(bg_noise_rate), 1),
            snr_db=round(float(snr_db), 2),
            beam_spot_radius_m=round(float(beam_spot_radius_m), 2)
        )
