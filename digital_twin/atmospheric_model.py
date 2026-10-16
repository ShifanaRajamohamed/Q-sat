"""Atmospheric extinction, air mass, and turbulence scintillation modeling.

Models optical beam degradation through the troposphere and stratosphere
as a function of elevation angle, humidity, cloud factor, and turbulence index.
"""

import math
from typing import Dict, Tuple
import numpy as np


class AtmosphericModel:
    """Calculates atmospheric transmittance and scintillation fading."""

    def __init__(
        self,
        zenith_transmittance_clear: float = 0.85,  # Clear sky optical transmission at zenith (~850nm)
        cloud_extinction_max_db: float = 25.0,    # Max attenuation from thick cloud layer in dB
        wavelength_nm: float = 850.0
    ):
        self.zenith_transmittance_clear = zenith_transmittance_clear
        self.cloud_extinction_max_db = cloud_extinction_max_db
        self.wavelength_nm = wavelength_nm

    def calculate_airmass(self, elevation_deg: float) -> float:
        """Calculate relative optical airmass using Rozenberg (1966) formula for high zenith angles.
        
        Equation:
            X(z) = 1 / (cos(z) + 0.025 * exp(-11 * cos(z)))
            where z = 90° - elevation.
        """
        elev_clamped = max(1.0, min(90.0, elevation_deg))
        z_rad = math.radians(90.0 - elev_clamped)
        cos_z = math.cos(z_rad)
        airmass = 1.0 / (cos_z + 0.025 * math.exp(-11.0 * cos_z))
        return float(np.clip(airmass, 1.0, 38.0))

    def calculate_atmospheric_transmission(
        self,
        elevation_deg: float,
        humidity_percent: float,
        cloud_factor: float,
        turbulence_index: float
    ) -> Tuple[float, float, float]:
        """Calculate total atmospheric transmittance and component losses.
        
        Returns:
            transmittance (float in [0, 1])
            loss_db (float >= 0)
            scintillation_variance (float >= 0)
        """
        if elevation_deg <= 0.0:
            return 0.0, 100.0, 1.0

        airmass = self.calculate_airmass(elevation_deg)

        # 1. Clear-sky Rayleigh and Aerosol transmission (Beer-Lambert law)
        # Higher humidity slightly increases aerosol scattering
        humidity_penalty = 1.0 - 0.15 * (humidity_percent / 100.0)
        t_clear_zenith = self.zenith_transmittance_clear * humidity_penalty
        t_clear = t_clear_zenith ** airmass

        # 2. Cloud extinction (strongly attenuates optical wavelengths)
        # Modeled as exponential optical depth proportional to cloud factor
        cloud_loss_db = self.cloud_extinction_max_db * (cloud_factor ** 1.5)
        t_cloud = 10.0 ** (-cloud_loss_db / 10.0)

        # 3. Turbulence scintillation fading (Rytov approximation variance)
        # Scintillation variance sigma_R^2 ~ 1.23 * C_n^2 * k^(7/6) * L^(11/6)
        # Normalized turbulence index [0, 1] maps to scintillation variance [0.01, 0.8]
        scintillation_var = 0.02 + 0.70 * (turbulence_index ** 1.3) * (airmass ** 0.5)
        # Mean log-normal intensity transmission reduction factor
        t_turb = float(np.clip(math.exp(-0.5 * scintillation_var), 0.1, 1.0))

        # Total combined atmospheric transmittance
        total_transmittance = float(np.clip(t_clear * t_cloud * t_turb, 1e-8, 1.0))
        loss_db = -10.0 * math.log10(max(1e-8, total_transmittance))

        return total_transmittance, float(loss_db), float(scintillation_var)
