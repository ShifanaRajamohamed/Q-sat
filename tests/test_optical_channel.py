"""Unit tests for Phase 4: Optical Channel Model."""

import pytest
from backend.app.models.environment import EnvironmentData
from backend.app.models.satellite import SatelliteState
from digital_twin.atmospheric_model import AtmosphericModel
from digital_twin.optical_channel import OpticalChannelModel


@pytest.fixture
def base_satellite():
    return SatelliteState(
        timestamp=0.0,
        satellite_name="Q-SAT-LEO-1",
        altitude_km=500.0,
        latitude=10.79,
        longitude=78.70,
        azimuth_deg=180.0,
        elevation_deg=45.0,
        slant_range_km=680.0,
        orbital_velocity_km_s=7.61,
        is_visible=True,
        pass_progress=0.5,
        link_status="TRACKING",
        pass_id=1
    )


@pytest.fixture
def clear_environment():
    return EnvironmentData(
        timestamp=0.0,
        temperature=24.0,
        humidity=45.0,
        ambient_light=300.0,
        vibration=0.02,
        cloud_factor=0.02,
        turbulence=0.08,
        data_source="SIMULATION",
        scenario_name="CLEAR_SKY"
    )


def test_atmospheric_airmass():
    """Verify Rozenberg airmass calculation (1.0 at zenith, ~5.8 at 10 deg)."""
    atm = AtmosphericModel()
    assert atm.calculate_airmass(90.0) == pytest.approx(1.0, rel=1e-2)
    assert 5.0 < atm.calculate_airmass(10.0) < 6.5


def test_cloud_extinction():
    """Verify cloud cover drastically degrades atmospheric transmittance."""
    atm = AtmosphericModel()
    t_clear, loss_clear, _ = atm.calculate_atmospheric_transmission(45.0, 50.0, 0.05, 0.1)
    t_cloudy, loss_cloudy, _ = atm.calculate_atmospheric_transmission(45.0, 50.0, 0.85, 0.1)

    assert t_cloudy < t_clear
    assert loss_cloudy > loss_clear + 10.0  # More than 10 dB additional cloud loss


def test_optical_link_budget(base_satellite, clear_environment):
    """Verify complete link budget calculation."""
    channel = OpticalChannelModel()
    state = channel.calculate_link_state(
        satellite=base_satellite,
        environment=clear_environment,
        transmission_power_pct=100.0,
        photon_rate_norm=1.0,
        beam_divergence_norm=0.20
    )

    assert state.total_loss_db > 0.0
    assert 0.0 < state.transmittance < 1.0
    assert state.received_photon_rate > 0.0
    assert state.snr_db > 0.0


def test_beam_divergence_tradeoff(base_satellite):
    """Verify control trade-off: widening beam divergence mitigates pointing error in high vibration."""
    channel = OpticalChannelModel()

    # Severe vibration environment
    vib_env = EnvironmentData(
        timestamp=0.0, temperature=25.0, humidity=50.0, ambient_light=500.0,
        vibration=1.50, cloud_factor=0.05, turbulence=0.15, data_source="SIMULATION"
    )

    # Narrow beam divergence (0.05) vs expanded beam divergence (0.80)
    narrow = channel.calculate_link_state(base_satellite, vib_env, beam_divergence_norm=0.05)
    wide = channel.calculate_link_state(base_satellite, vib_env, beam_divergence_norm=0.80)

    # In high vibration, narrow beam suffers severe pointing loss (displacement / spot_radius is large)
    assert narrow.pointing_loss_db > wide.pointing_loss_db
