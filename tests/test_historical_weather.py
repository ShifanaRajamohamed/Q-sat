"""Unit tests for HistoricalWeatherProvider and CSV replay."""

import datetime
from pathlib import Path
import pytest
import numpy as np

from digital_twin.historical_weather_provider import HistoricalWeatherProvider
from backend.app.models.environment import EnvironmentData

FIXTURE_PATH = "simulation/historical_weather/tiruchirappalli_2024_03_synthetic_fixture.csv"


def test_historical_weather_provider_loading():
    """Verify loading of standard synthetic fixture."""
    provider = HistoricalWeatherProvider(FIXTURE_PATH)
    assert len(provider.records) == 744
    assert provider.is_healthy() is True
    assert provider.get_mode() == "historical_replay"


def test_hold_vs_linear_interpolation():
    """Verify hold mode preserves step values while linear interpolation computes intermediate states."""
    # Hold mode
    p_hold = HistoricalWeatherProvider(FIXTURE_PATH, interpolation_mode="HOLD")
    e0_hold = p_hold.get_current_environment()
    e_mid_hold = p_hold.step(dt=1800.0)  # 30 minutes in
    assert e_mid_hold.is_interpolated is False
    assert e_mid_hold.temperature == e0_hold.temperature
    assert e_mid_hold.interpolation_method == "HOLD"

    # Linear mode
    p_lin = HistoricalWeatherProvider(FIXTURE_PATH, interpolation_mode="LINEAR")
    e0_lin = p_lin.get_current_environment()
    e_mid_lin = p_lin.step(dt=1800.0)
    assert e_mid_lin.is_interpolated is True
    assert e_mid_lin.interpolation_method == "LINEAR"
    # Midpoint should lie strictly between hour 0 and hour 1
    rec1_temp = p_lin.records[1].temperature_c
    expected_mid = (e0_lin.temperature + rec1_temp) / 2.0
    assert abs(e_mid_lin.temperature - expected_mid) < 0.05


def test_cloud_cover_separation_from_cloud_factor():
    """Verify meteorological cloud cover (%) is distinct from optical cloud_factor [0, 1]."""
    provider = HistoricalWeatherProvider(FIXTURE_PATH)
    env = provider.get_current_environment()

    assert env.meteorological_cloud_cover_pct is not None
    assert 0.0 <= env.meteorological_cloud_cover_pct <= 100.0
    assert 0.0 <= env.cloud_factor <= 1.0

    # Optical cloud factor is monotonically related to cloud cover but not numerically equal
    # e.g., 18% cloud cover does not equal 0.18 optical factor
    assert env.cloud_factor != pytest.approx(env.meteorological_cloud_cover_pct / 100.0, abs=1e-3)


def test_unmeasured_inputs_labeled_as_assumptions():
    """Verify turbulence and vibration are explicitly marked as configured assumptions."""
    provider = HistoricalWeatherProvider(
        FIXTURE_PATH,
        assumed_turbulence=0.15,
        assumed_vibration_g=0.020
    )
    env = provider.get_current_environment()

    assert env.field_provenance is not None
    assert "CONFIGURED_ASSUMPTION" in env.field_provenance["turbulence"]
    assert "CONFIGURED_ASSUMPTION" in env.field_provenance["vibration"]
    assert "SOLAR_RADIATION_MODELED" in env.field_provenance["ambient_light"]


def test_date_range_validation_and_slice(tmp_path):
    """Verify start date filtering and out-of-bounds error handling."""
    provider = HistoricalWeatherProvider(
        FIXTURE_PATH,
        start_datetime_iso="2024-03-10T12:00:00Z"
    )
    env = provider.get_current_environment()
    assert "2024-03-10T12:00:00" in env.datetime_iso

    # Test requesting a date outside the CSV boundaries
    with pytest.raises(ValueError, match="outside dataset range"):
        HistoricalWeatherProvider(
            FIXTURE_PATH,
            start_datetime_iso="2025-01-01T00:00:00Z"
        )


def test_csv_validation_errors(tmp_path):
    """Verify validator catches non-monotonic timestamps and corrupted files."""
    bad_csv = tmp_path / "bad.csv"
    # Non-monotonic timestamps
    bad_csv.write_text(
        "timestamp,temperature_c,relative_humidity_pct,cloud_cover_pct\n"
        "2024-03-01T02:00:00Z,25.0,60.0,20.0\n"
        "2024-03-01T01:00:00Z,24.0,65.0,20.0\n"
    )
    with pytest.raises(ValueError, match="strictly monotonic"):
        HistoricalWeatherProvider(bad_csv)

