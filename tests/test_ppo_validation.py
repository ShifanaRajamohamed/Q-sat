"""Unit tests for PPO Model Archive Validation and Controller Execution."""

from pathlib import Path
import pytest
import numpy as np

from ai.model_validator import validate_ppo_archive, repair_nested_archive
from ai.ppo_controller import PPOController
from ai.spaces import build_normalized_observation, apply_action_deltas
from backend.app.models.environment import EnvironmentData
from backend.app.models.qkd import OpticalChannelState, QKDMetrics
from backend.app.models.satellite import SatelliteState


def test_repaired_archive_validation():
    """Verify that models/ppo_qsat.zip passes validation and has root-level files."""
    report = validate_ppo_archive("models/ppo_qsat.zip")
    assert report.is_valid_zip is True
    assert report.is_loadable is True
    assert report.required_at_root is True
    assert not report.missing_files
    assert report.sb3_version == "2.9.0"
    assert report.observation_space_info["shape"] == [15]
    assert report.action_space_info["shape"] == [3]


def test_original_nested_archive_detection():
    """Verify that original nested archive is identified as nested and not directly loadable."""
    orig_path = Path("models/ppo_qsat_original_nested.zip")
    if orig_path.exists():
        report = validate_ppo_archive(orig_path)
        assert report.is_valid_zip is True
        assert report.is_loadable is False
        assert report.is_nested is True
        assert report.nested_prefix == "ppo_qsat/"


def test_evaluation_mode_fails_on_missing_model(tmp_path):
    """In evaluation mode, PPO must fail explicitly if model cannot load."""
    missing_path = tmp_path / "non_existent_ppo.zip"
    with pytest.raises(FileNotFoundError):
        PPOController(model_path=str(missing_path), evaluation_mode=True)


def test_requested_vs_actual_controller_reporting():
    """Verify requested_controller, actual_controller, and model_loaded tracking."""
    # Loaded model
    ctrl = PPOController(model_path="models/ppo_qsat.zip", evaluation_mode=False)
    assert ctrl.model_loaded is True

    sat = SatelliteState(
        timestamp=60.0, satellite_name="Q-SAT-1", altitude_km=500.0,
        latitude=10.8, longitude=78.7, azimuth_deg=180.0, elevation_deg=45.0,
        slant_range_km=700.0, orbital_velocity_km_s=7.6, is_visible=True
    )
    env = EnvironmentData(
        timestamp=60.0, temperature=25.0, humidity=50.0, ambient_light=500.0,
        vibration=0.015, cloud_factor=0.05, turbulence=0.10, data_source="SIMULATION"
    )
    chan = OpticalChannelState(
        total_loss_db=25.0, transmittance=0.003, fspl_loss_db=18.0, atmospheric_loss_db=5.0,
        pointing_loss_db=1.0, scintillation_loss_db=1.0, received_photon_rate=20000.0,
        background_noise_rate=250.0, snr_db=19.0, beam_spot_radius_m=10.0
    )
    qkd = QKDMetrics(
        timestamp=60.0, transmitted_photon_rate=50e6, received_photon_rate=20000.0,
        raw_key_rate=2000.0, sifted_key_rate=1000.0, qber=0.035, secret_key_rate=500.0,
        qber_decomposition={
            "base_error": 0.01, "atmospheric_noise": 0.005, "background_light_noise": 0.005,
            "pointing_error": 0.005, "detector_noise": 0.01, "security_anomaly_component": 0.0,
            "total_qber": 0.035
        },
        channel_loss_db=25.0, channel_transmittance=0.003, is_key_distillation_possible=True
    )

    action = ctrl.decide(sat, env, chan, qkd)
    assert action.requested_controller == "PPO"
    assert action.actual_controller == "PPO"
    assert action.model_loaded is True
    assert action.fallback_reason is None


def test_shared_observation_and_action_spaces():
    """Verify shared spaces module consistency."""
    sat = SatelliteState(
        timestamp=60.0, satellite_name="Q-SAT-1", altitude_km=500.0,
        latitude=10.8, longitude=78.7, azimuth_deg=180.0, elevation_deg=45.0,
        slant_range_km=700.0, orbital_velocity_km_s=7.6, is_visible=True
    )
    env = EnvironmentData(
        timestamp=60.0, temperature=25.0, humidity=50.0, ambient_light=500.0,
        vibration=0.015, cloud_factor=0.05, turbulence=0.10, data_source="SIMULATION"
    )
    chan = OpticalChannelState(
        total_loss_db=25.0, transmittance=0.003, fspl_loss_db=18.0, atmospheric_loss_db=5.0,
        pointing_loss_db=1.0, scintillation_loss_db=1.0, received_photon_rate=20000.0,
        background_noise_rate=250.0, snr_db=19.0, beam_spot_radius_m=10.0
    )
    qkd = QKDMetrics(
        timestamp=60.0, transmitted_photon_rate=50e6, received_photon_rate=20000.0,
        raw_key_rate=2000.0, sifted_key_rate=1000.0, qber=0.035, secret_key_rate=500.0,
        qber_decomposition={
            "base_error": 0.01, "atmospheric_noise": 0.005, "background_light_noise": 0.005,
            "pointing_error": 0.005, "detector_noise": 0.01, "security_anomaly_component": 0.0,
            "total_qber": 0.035
        },
        channel_loss_db=25.0, channel_transmittance=0.003, is_key_distillation_possible=True
    )

    obs = build_normalized_observation(sat, env, chan, qkd, 50.0, 0.70, 0.25)
    assert obs.shape == (15,)
    assert np.all(obs >= 0.0)
    assert np.all(obs <= 1.0)

    # Test action mapping
    action_raw = np.array([1.0, -1.0, 0.0], dtype=np.float32)
    p, r, d, dp, dr, dd = apply_action_deltas(action_raw, 50.0, 0.70, 0.25, rate_limit=0.20)
    assert p == pytest.approx(70.0)
    assert r == pytest.approx(0.50)
    assert d == pytest.approx(0.25)

