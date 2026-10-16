"""Unit and integration tests for Phase 3: Satellite Digital Twin and Orbital Mechanics."""

import math
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.satellite import GroundStationConfig
from digital_twin.orbital_model import OrbitalModel
from digital_twin.satellite_model import SatelliteModel

client = TestClient(app)


def test_orbital_dynamics_constants():
    """Verify Keplerian orbital velocity and period for a 500 km LEO satellite."""
    model = OrbitalModel(altitude_km=500.0)
    # Expected speed ~7.61 km/s, period ~94.6 minutes (5677 seconds)
    assert 7.5 < model.orbital_velocity_km_s < 7.7
    assert 5600.0 < model.orbital_period_s < 5800.0


def test_slant_range_geometry():
    """Verify slant range increases monotonically as elevation decreases towards the horizon."""
    model = OrbitalModel(altitude_km=500.0)

    # Zenith: slant range equals satellite altitude
    range_zenith = model.calculate_slant_range(90.0)
    assert range_zenith == pytest.approx(500.0, rel=1e-2)

    # 45 deg elevation: slant range should be roughly ~680 km
    range_45 = model.calculate_slant_range(45.0)
    assert range_45 > range_zenith

    # Horizon (10 deg cutoff): slant range is longest (~1695 km for 500 km LEO)
    range_10 = model.calculate_slant_range(10.0)
    assert range_10 > range_45
    assert 1300.0 < range_10 < 1800.0


def test_pass_visibility_and_cutoff():
    """Verify visibility and link status follow the minimum elevation threshold."""
    sat_model = SatelliteModel()

    # Peak of pass (progress = 0.5)
    sat_peak = sat_model.orbital_model.force_pass_progress(0.5)
    assert sat_peak.is_visible is True
    assert sat_peak.elevation_deg > 50.0
    assert sat_peak.link_status == "TRACKING"

    # Out of pass (below horizon)
    sat_below = sat_model.orbital_model.propagate(sat_model.orbital_model.orbital_period_s * 0.5)
    assert sat_below.is_visible is False
    assert sat_below.elevation_deg < sat_model.ground_station.min_elevation_deg
    assert sat_below.link_status == "UNAVAILABLE"


def test_api_satellite_state():
    """Verify GET /api/satellite/state returns full telemetry vector."""
    response = client.get("/api/satellite/state")
    assert response.status_code == 200
    data = response.json()

    assert "altitude_km" in data
    assert "elevation_deg" in data
    assert "azimuth_deg" in data
    assert "slant_range_km" in data
    assert "orbital_velocity_km_s" in data
    assert "is_visible" in data
    assert data["link_status"] in ["ACQUIRED", "TRACKING", "UNAVAILABLE"]


def test_api_ground_station_update():
    """Verify ground station coordinate updates via API."""
    new_gs = {
        "name": "Equatorial Ground Station",
        "latitude": 1.3521,
        "longitude": 103.8198,
        "altitude_m": 15.0,
        "min_elevation_deg": 12.0
    }
    response = client.post("/api/satellite/ground_station", json=new_gs)
    assert response.status_code == 200
    data = response.json()
    assert data["latitude"] == 1.3521
    assert data["min_elevation_deg"] == 12.0
