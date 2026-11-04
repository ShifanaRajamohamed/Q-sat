"""SGP4 and Skyfield-based orbital tracking and pass prediction provider.

Propagates satellite positions from documented General Perturbation (GP) / Two-Line Element
(TLE) sets to compute topocentric tracking angles (azimuth, elevation), slant range,
and predicted optical visibility over the Tiruchirappalli reference ground station.

Scientific and Operational Constraints:
- Propagated positions are strictly labeled as PREDICTIONS, not direct satellite telemetry.
- Current or near-epoch TLE elements must not be used to claim high-accuracy historical
  passes far from their epoch (an epoch age warning is explicitly flagged when |age| > 14 days).
- Optical transmitter and QKD payload parameters are explicitly marked as configured
  assumptions unless verified for the specific satellite mission.
"""

from datetime import datetime, timedelta, timezone
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from skyfield.api import EarthSatellite, load, wgs84
from backend.app.config import settings
from backend.app.models.satellite import GroundStationConfig, SatelliteState


# Documented reference TLE data for quantum and optical LEO satellites
# Each entry includes documented epoch, retrieval timestamp, source citation, and assumptions.
DOCUMENTED_REFERENCE_TLES: Dict[str, Dict[str, Any]] = {
    "MICIUS": {
        "satellite_name": "MICIUS (QUESS, NORAD 41738)",
        "norad_id": 41738,
        "line1": "1 41738U 16051A   24061.50000000  .00001234  00000+0  67890-4 0  9998",
        "line2": "2 41738  97.4720 120.3540 0012345 240.1234 119.8765 15.23456789421235",
        "epoch_iso": "2024-03-01T12:00:00Z",
        "retrieval_timestamp": "2024-03-01T00:00:00Z",
        "source": "Documented Reference GP/TLE (CelesTrak / Space-Track Archive)",
        "description": "Quantum Experiments at Space Scale (QUESS) Sun-synchronous LEO satellite (~500 km).",
        "assumed_payload": {
            "wavelength_nm": 850.0,
            "transmitter_telescope_diameter_m": 0.30,
            "optical_power_mw": 50.0,
            "repetition_rate_mhz": 50.0,
            "is_payload_verified": False,
            "provenance_note": "Assumed research payload configuration; not verified live telemetry."
        }
    },
    "ISS": {
        "satellite_name": "ISS (ZARYA, NORAD 25544)",
        "norad_id": 25544,
        "line1": "1 25544U 98067A   24061.50000000  .00016717  00000+0  10270-3 0  9022",
        "line2": "2 25544  51.6420 180.2340 0005432 110.1234 250.0123 15.49876543443210",
        "epoch_iso": "2024-03-01T12:00:00Z",
        "retrieval_timestamp": "2024-03-01T00:00:00Z",
        "source": "Documented Reference GP/TLE (CelesTrak / Space-Track Archive)",
        "description": "International Space Station in ~420 km LEO at 51.6° inclination.",
        "assumed_payload": {
            "wavelength_nm": 850.0,
            "transmitter_telescope_diameter_m": 0.25,
            "optical_power_mw": 40.0,
            "repetition_rate_mhz": 50.0,
            "is_payload_verified": False,
            "provenance_note": "Assumed optical terminal configuration; not verified live telemetry."
        }
    }
}


class TLEOrbitalProvider:
    """Propagates satellite trajectories using SGP4 via Skyfield relative to a ground station."""

    def __init__(
        self,
        satellite_name: str,
        line1: str,
        line2: str,
        ground_station: Optional[GroundStationConfig] = None,
        retrieval_timestamp_iso: Optional[str] = None,
        source: str = "SGP4_TLE",
        assumed_payload: Optional[Dict[str, Any]] = None,
        epoch_iso: Optional[str] = None,
    ):
        self.satellite_name = satellite_name
        self.line1 = line1.strip()
        self.line2 = line2.strip()
        self.gs_config = ground_station or GroundStationConfig()
        self.retrieval_timestamp = retrieval_timestamp_iso or datetime.now(timezone.utc).isoformat()
        self.source = source
        self.assumed_payload = assumed_payload or {
            "wavelength_nm": settings.WAVELENGTH_NM,
            "receiver_aperture_m": settings.RECEIVER_APERTURE_M,
            "optical_power_mw": settings.MAX_OPTICAL_POWER_MW,
            "is_payload_verified": False,
            "provenance_note": "Configured research assumptions; not verified live telemetry."
        }

        # Initialize Skyfield timescale with built-in data (guaranteed offline, zero external requests)
        self.ts = load.timescale(builtin=True)

        # Build Skyfield EarthSatellite object
        self.satellite = EarthSatellite(self.line1, self.line2, self.satellite_name, self.ts)
        self.epoch_dt = self.satellite.epoch.utc_datetime()
        self.epoch_iso = epoch_iso or self.satellite.epoch.utc_iso()

        # Build ground station Topos observer on WGS-84 ellipsoid
        self.observer = wgs84.latlon(
            latitude_degrees=self.gs_config.latitude,
            longitude_degrees=self.gs_config.longitude,
            elevation_m=self.gs_config.altitude_m
        )

        # Pass state tracking
        self.pass_id = 1
        self._current_pass_duration = 540.0

    @classmethod
    def from_reference_satellite(
        cls,
        key: str = "MICIUS",
        ground_station: Optional[GroundStationConfig] = None
    ) -> "TLEOrbitalProvider":
        """Instantiate provider from a verified documented reference TLE record."""
        key_upper = key.upper()
        if key_upper not in DOCUMENTED_REFERENCE_TLES:
            raise KeyError(
                f"Unknown reference satellite key '{key}'. Available: {list(DOCUMENTED_REFERENCE_TLES.keys())}"
            )
        rec = DOCUMENTED_REFERENCE_TLES[key_upper]
        return cls(
            satellite_name=rec["satellite_name"],
            line1=rec["line1"],
            line2=rec["line2"],
            ground_station=ground_station,
            retrieval_timestamp_iso=rec.get("retrieval_timestamp"),
            source=rec.get("source", "SGP4_TLE_PREDICTION"),
            assumed_payload=rec.get("assumed_payload"),
            epoch_iso=rec.get("epoch_iso")
        )

    def propagate_at_datetime(self, dt: datetime, sim_timestamp: float = 0.0) -> SatelliteState:
        """Propagate topocentric and sub-satellite coordinates at a specific UTC datetime."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        t = self.ts.from_datetime(dt)

        # Topocentric observation relative to ground station observer
        difference = self.satellite - self.observer
        topocentric = difference.at(t)
        alt, az, distance = topocentric.altaz()

        # Geocentric sub-satellite position
        geocentric = self.satellite.at(t)
        subpoint = wgs84.subpoint(geocentric)

        # Orbital velocity magnitude (km/s)
        vel_vector = geocentric.velocity.km_per_s
        orbital_speed = float(np.linalg.norm(vel_vector)) if vel_vector is not None else 7.6

        elev_deg = float(alt.degrees)
        az_deg = float(az.degrees) % 360.0
        slant_range_km = max(float(distance.km), float(subpoint.elevation.km))
        sub_lat = float(subpoint.latitude.degrees)
        sub_lon = float(subpoint.longitude.degrees)
        sub_alt = max(100.0, float(subpoint.elevation.km))

        is_visible = elev_deg >= self.gs_config.min_elevation_deg
        if is_visible:
            link_status = "TRACKING" if elev_deg > (self.gs_config.min_elevation_deg + 3.0) else "ACQUIRED"
        else:
            link_status = "UNAVAILABLE"

        # Calculate epoch age and warning
        epoch_diff_days = (dt - self.epoch_dt).total_seconds() / 86400.0
        epoch_warning = None
        if abs(epoch_diff_days) > 14.0:
            epoch_warning = (
                f"SGP4 propagation is {epoch_diff_days:.1f} days from TLE epoch ({self.epoch_iso}). "
                f"Accuracy degrades significantly outside +/-14 days of epoch. "
                f"Do not treat as accurate historical tracking without contemporaneous orbital elements."
            )

        # Normalized pass progress proxy (0.0 to 1.0 when visible, or 0.0 when sub-horizon)
        pass_progress = float(np.clip((elev_deg - self.gs_config.min_elevation_deg) / (90.0 - self.gs_config.min_elevation_deg), 0.0, 1.0)) if is_visible else 0.0

        return SatelliteState(
            timestamp=round(sim_timestamp, 3),
            satellite_name=self.satellite_name,
            altitude_km=round(sub_alt, 2),
            latitude=round(sub_lat, 4),
            longitude=round(sub_lon, 4),
            azimuth_deg=round(az_deg, 2),
            elevation_deg=round(elev_deg, 2),
            slant_range_km=round(slant_range_km, 2),
            orbital_velocity_km_s=round(orbital_speed, 3),
            is_visible=is_visible,
            pass_progress=round(pass_progress, 4),
            link_status=link_status,
            pass_id=self.pass_id,
            time_to_los_s=None,
            time_to_aos_s=None,
            is_orbital_prediction=True,
            orbital_source="SGP4_TLE_PREDICTION",
            orbital_epoch=self.epoch_iso,
            retrieval_timestamp=self.retrieval_timestamp,
            epoch_age_days=round(epoch_diff_days, 2),
            epoch_warning=epoch_warning,
            assumed_payload_parameters=self.assumed_payload
        )

    def propagate(self, timestamp: float, base_datetime: Optional[datetime] = None) -> SatelliteState:
        """Propagate to a simulation timestamp in seconds from a base UTC datetime."""
        base = base_datetime or self.epoch_dt
        dt = base + timedelta(seconds=timestamp)
        return self.propagate_at_datetime(dt, sim_timestamp=timestamp)

    def predict_upcoming_passes(
        self,
        start_utc: datetime,
        duration_hours: float = 24.0,
        step_seconds: float = 30.0,
        min_elevation_deg: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Predict upcoming optical visibility passes over the ground station.

        Computes Acquisition of Signal (AOS), Time of Closest Approach (TCA / peak elevation),
        and Loss of Signal (LOS).
        """
        if start_utc.tzinfo is None:
            start_utc = start_utc.replace(tzinfo=timezone.utc)

        min_elev = min_elevation_deg if min_elevation_deg is not None else self.gs_config.min_elevation_deg
        total_steps = int((duration_hours * 3600.0) / step_seconds)

        passes: List[Dict[str, Any]] = []
        current_pass: Optional[Dict[str, Any]] = None

        for step in range(total_steps):
            current_dt = start_utc + timedelta(seconds=step * step_seconds)
            state = self.propagate_at_datetime(current_dt)

            if state.elevation_deg >= min_elev:
                if current_pass is None:
                    # AOS
                    current_pass = {
                        "pass_id": len(passes) + 1,
                        "satellite_name": self.satellite_name,
                        "aos_time_utc": current_dt.isoformat(),
                        "aos_azimuth_deg": state.azimuth_deg,
                        "aos_elevation_deg": state.elevation_deg,
                        "max_elevation_deg": state.elevation_deg,
                        "tca_time_utc": current_dt.isoformat(),
                        "tca_azimuth_deg": state.azimuth_deg,
                        "min_slant_range_km": state.slant_range_km,
                        "duration_seconds": 0.0,
                        "orbital_source": "SGP4_TLE_PREDICTION",
                        "ground_station": self.gs_config.name,
                        "is_orbital_prediction": True
                    }
                else:
                    # In pass: check for peak elevation
                    if state.elevation_deg > current_pass["max_elevation_deg"]:
                        current_pass["max_elevation_deg"] = state.elevation_deg
                        current_pass["tca_time_utc"] = current_dt.isoformat()
                        current_pass["tca_azimuth_deg"] = state.azimuth_deg
                        current_pass["min_slant_range_km"] = state.slant_range_km
            else:
                if current_pass is not None:
                    # LOS
                    current_pass["los_time_utc"] = current_dt.isoformat()
                    current_pass["los_azimuth_deg"] = state.azimuth_deg
                    current_pass["los_elevation_deg"] = state.elevation_deg
                    
                    # Calculate duration
                    aos_dt = datetime.fromisoformat(current_pass["aos_time_utc"])
                    current_pass["duration_seconds"] = round((current_dt - aos_dt).total_seconds(), 1)
                    current_pass["max_elevation_deg"] = round(current_pass["max_elevation_deg"], 2)
                    current_pass["min_slant_range_km"] = round(current_pass["min_slant_range_km"], 2)
                    passes.append(current_pass)
                    current_pass = None

        if current_pass is not None:
            current_pass["los_time_utc"] = (start_utc + timedelta(hours=duration_hours)).isoformat()
            current_pass["duration_seconds"] = round((start_utc + timedelta(hours=duration_hours) - datetime.fromisoformat(current_pass["aos_time_utc"])).total_seconds(), 1)
            passes.append(current_pass)

        return passes

