"""Unit tests for SGP4 and Skyfield-based orbital tracking and pass prediction."""

from datetime import datetime, timezone
import pytest

from backend.app.models.satellite import GroundStationConfig
from digital_twin.tle_orbital_provider import DOCUMENTED_REFERENCE_TLES, TLEOrbitalProvider


def test_tle_provider_initialization():
    """Verify provider loads reference satellite with Tiruchirappalli coordinates."""
    gs = GroundStationConfig()
    assert "Tiruchirappalli" in gs.name

    provider = TLEOrbitalProvider.from_reference_satellite("MICIUS", ground_station=gs)
    assert "MICIUS" in provider.satellite_name
    assert provider.epoch_iso == "2024-03-01T12:00:00Z"
    assert provider.source == "Documented Reference GP/TLE (CelesTrak / Space-Track Archive)"
    assert provider.assumed_payload["is_payload_verified"] is False


def test_tle_propagation_coordinates():
    """Verify topocentric propagation produces valid angles and prediction flags."""
    provider = TLEOrbitalProvider.from_reference_satellite("MICIUS")
    
    # Propagate at exact epoch
    state = provider.propagate_at_datetime(datetime(2024, 3, 1, 12, 0, 0, tzinfo=timezone.utc))
    
    assert state.is_orbital_prediction is True
    assert state.orbital_source == "SGP4_TLE_PREDICTION"
    assert state.orbital_epoch == "2024-03-01T12:00:00Z"
    assert state.retrieval_timestamp is not None
    assert state.epoch_warning is None  # Exact epoch, no warning
    assert 400.0 <= state.altitude_km <= 600.0
    assert 7.0 <= state.orbital_velocity_km_s <= 8.5
    assert 0.0 <= state.azimuth_deg <= 360.0
    assert -90.0 <= state.elevation_deg <= 90.0
    assert state.slant_range_km >= state.altitude_km


def test_tle_epoch_age_warning():
    """Verify that propagating far from epoch triggers an explicit warning."""
    provider = TLEOrbitalProvider.from_reference_satellite("MICIUS")
    
    # Propagate 45 days after epoch
    state_future = provider.propagate_at_datetime(datetime(2024, 4, 15, 12, 0, 0, tzinfo=timezone.utc))
    assert state_future.epoch_age_days > 40.0
    assert state_future.epoch_warning is not None
    assert "Do not treat as accurate historical tracking" in state_future.epoch_warning

    # Propagate 45 days before epoch
    state_past = provider.propagate_at_datetime(datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc))
    assert state_past.epoch_age_days < -40.0
    assert state_past.epoch_warning is not None


def test_tle_assumed_payload_parameters():
    """Verify optical payload parameters are marked as research assumptions."""
    provider = TLEOrbitalProvider.from_reference_satellite("MICIUS")
    state = provider.propagate_at_datetime(datetime(2024, 3, 1, 12, 0, 0, tzinfo=timezone.utc))
    
    payload = state.assumed_payload_parameters
    assert payload is not None
    assert payload["wavelength_nm"] == 850.0
    assert payload["transmitter_telescope_diameter_m"] == 0.30
    assert payload["is_payload_verified"] is False
    assert "Assumed research payload configuration" in payload["provenance_note"]


def test_upcoming_passes_prediction():
    """Verify pass predictor calculates AOS, TCA, LOS, and pass duration."""
    provider = TLEOrbitalProvider.from_reference_satellite("MICIUS")
    
    # Predict passes over 48 hours starting at epoch
    start_dt = datetime(2024, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
    passes = provider.predict_upcoming_passes(start_dt, duration_hours=48.0, step_seconds=30.0)
    
    assert len(passes) >= 1, "Should detect at least 1 pass over 48 hours for LEO orbit"
    first_pass = passes[0]
    assert "aos_time_utc" in first_pass
    assert "tca_time_utc" in first_pass
    assert "los_time_utc" in first_pass
    assert first_pass["duration_seconds"] > 0
    assert first_pass["max_elevation_deg"] >= 10.0
    assert first_pass["is_orbital_prediction"] is True

