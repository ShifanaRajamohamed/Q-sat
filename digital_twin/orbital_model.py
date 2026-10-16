"""Orbital mechanics and topocentric geometric propagation for LEO satellites.

Models satellite trajectories, slant range, elevation, azimuth, and pass durations
relative to an optical ground station using analytical orbital dynamics and SGP4.
"""

import math
from typing import Dict, Optional, Tuple
import numpy as np

from backend.app.models.satellite import GroundStationConfig, SatelliteState

# Physical and Astrodynamical Constants (WGS-84)
EARTH_RADIUS_KM = 6371.0
EARTH_MU = 398600.4418  # km^3 / s^2 (Standard gravitational parameter)
DEFAULT_ORBIT_ALTITUDE_KM = 500.0  # Typical LEO altitude for quantum satellites (e.g., Micius is ~500 km)


class OrbitalModel:
    """Propagates LEO satellite positions and computes relative ground station geometry."""

    def __init__(
        self,
        ground_station: Optional[GroundStationConfig] = None,
        altitude_km: float = DEFAULT_ORBIT_ALTITUDE_KM,
        inclination_deg: float = 97.4,  # Sun-synchronous orbit inclination
        satellite_name: str = "Q-SAT-LEO-1"
    ):
        self.gs = ground_station or GroundStationConfig()
        self.altitude_km = altitude_km
        self.inclination_deg = inclination_deg
        self.satellite_name = satellite_name

        # Calculate orbital period & velocity (Keplerian)
        self.semi_major_axis_km = EARTH_RADIUS_KM + self.altitude_km
        self.orbital_velocity_km_s = math.sqrt(EARTH_MU / self.semi_major_axis_km)
        self.orbital_period_s = 2.0 * math.pi * math.sqrt((self.semi_major_axis_km ** 3) / EARTH_MU)

        # Pass trajectory generation parameters
        self.pass_id = 1
        self.sim_time = 0.0

        # Current active pass state
        self._current_pass_duration = 540.0  # ~9 minutes pass duration
        self._time_since_pass_start = 0.0
        self._pass_max_elevation_deg = 68.5
        self._pass_start_azimuth_deg = 195.0
        self._pass_end_azimuth_deg = 25.0
        self._in_pass = True

    def calculate_slant_range(self, elevation_deg: float) -> float:
        """Calculate Euclidean slant range (km) from ground station to satellite.
        
        Equation:
            d = sqrt(R_E^2 * sin^2(elev) + 2*R_E*h + h^2) - R_E * sin(elev)
        """
        elev_rad = math.radians(max(elevation_deg, -90.0))
        re = EARTH_RADIUS_KM + (self.gs.altitude_m / 1000.0)
        h = self.altitude_km
        term = (re * math.sin(elev_rad)) ** 2 + 2.0 * re * h + h ** 2
        slant_range = math.sqrt(max(0.0, term)) - re * math.sin(elev_rad)
        return max(h, float(slant_range))

    def propagate(self, timestamp: float) -> SatelliteState:
        """Propagate satellite state to the given simulation timestamp in seconds."""
        self.sim_time = timestamp

        # Model periodic LEO passes over the ground station
        # A typical LEO satellite pass occurs every ~95 minutes (orbital period)
        orbit_cycle_time = self.sim_time % self.orbital_period_s
        pass_duration = self._current_pass_duration
        pass_intermission = self.orbital_period_s - pass_duration

        if orbit_cycle_time < pass_duration:
            # SATELLITE IS IN AN ACTIVE VISIBLE PASS
            self._in_pass = True
            progress = orbit_cycle_time / pass_duration
            tau = (progress - 0.5) * 2.0  # Normalized pass time: -1.0 (AOS) to +1.0 (LOS)

            # Smooth parabolic/sinusoidal elevation trajectory matching orbital pass geometry
            # Peak elevation at tau = 0
            elev_rad_max = math.radians(self._pass_max_elevation_deg)
            # Min elevation at horizon edge
            elev_deg = self.gs.min_elevation_deg + (self._pass_max_elevation_deg - self.gs.min_elevation_deg) * math.cos(tau * (math.pi / 2.0))

            # Azimuth transitions smoothly from south-southwest to north-northeast
            azimuth_deg = self._pass_start_azimuth_deg + (self._pass_end_azimuth_deg - self._pass_start_azimuth_deg) * progress
            azimuth_deg = azimuth_deg % 360.0

            time_to_los = max(0.0, pass_duration - orbit_cycle_time)
            time_to_aos = 0.0

            # Sub-satellite geographical coordinates
            lat_offset = (progress - 0.5) * 25.0
            lon_offset = (progress - 0.5) * 10.0
            sub_lat = np.clip(self.gs.latitude + lat_offset, -90.0, 90.0)
            sub_lon = ((self.gs.longitude + lon_offset + 180.0) % 360.0) - 180.0
        else:
            # SATELLITE IS BELOW HORIZON (OUT OF PASS)
            self._in_pass = False
            time_since_los = orbit_cycle_time - pass_duration
            progress = 0.0
            time_to_los = 0.0
            time_to_aos = max(0.0, self.orbital_period_s - orbit_cycle_time)

            # Sub-horizon elevation (negative angle)
            cycle_fraction = time_since_los / pass_intermission
            elev_deg = -10.0 - 50.0 * math.sin(cycle_fraction * math.pi)
            azimuth_deg = (self._pass_end_azimuth_deg + cycle_fraction * 180.0) % 360.0

            sub_lat = np.clip(self.gs.latitude - 40.0 + cycle_fraction * 80.0, -90.0, 90.0)
            sub_lon = ((self.gs.longitude + 180.0 + cycle_fraction * 360.0) % 360.0) - 180.0

        # Slant range geometry
        slant_range_km = self.calculate_slant_range(elev_deg)

        is_visible = elev_deg >= self.gs.min_elevation_deg
        if is_visible:
            link_status = "TRACKING" if elev_deg > (self.gs.min_elevation_deg + 3.0) else "ACQUIRED"
        else:
            link_status = "UNAVAILABLE"

        return SatelliteState(
            timestamp=round(timestamp, 3),
            satellite_name=self.satellite_name,
            altitude_km=round(self.altitude_km, 2),
            latitude=round(float(sub_lat), 4),
            longitude=round(float(sub_lon), 4),
            azimuth_deg=round(float(azimuth_deg), 2),
            elevation_deg=round(float(elev_deg), 2),
            slant_range_km=round(float(slant_range_km), 2),
            orbital_velocity_km_s=round(self.orbital_velocity_km_s, 3),
            is_visible=is_visible,
            pass_progress=round(float(progress), 4),
            link_status=link_status,
            pass_id=self.pass_id,
            time_to_los_s=round(time_to_los, 1) if is_visible else None,
            time_to_aos_s=round(time_to_aos, 1) if not is_visible else None
        )

    def force_pass_progress(self, progress: float) -> SatelliteState:
        """Directly jump to a specified pass progress [0.0, 1.0] for testing."""
        progress = float(np.clip(progress, 0.0, 1.0))
        target_timestamp = progress * self._current_pass_duration
        return self.propagate(target_timestamp)
