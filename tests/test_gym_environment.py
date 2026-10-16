"""Unit tests for Phase 7: Gymnasium Environment & Reward Function."""

import numpy as np
import pytest
from ai.environment import QSATEnvironment
from ai.reward import calculate_reward
from backend.app.models.environment import ScenarioType


def test_reward_function_properties():
    """Verify reward penalizes QBER, rewards SKR, and penalizes excessive instability."""
    # Good link (High SKR, Low QBER)
    r_good = calculate_reward(
        secret_key_rate=15000.0,
        qber=0.02,
        transmission_power_pct=50.0,
        delta_power=0.0,
        delta_photon_rate=0.0,
        delta_divergence=0.0,
        is_link_visible=True
    )
    assert r_good.total_reward > 0.0
    assert r_good.qber_penalty < 0.5
    assert r_good.security_breach_penalty == 0.0

    # Critical error link (QBER >= 11% cutoff)
    r_bad = calculate_reward(
        secret_key_rate=0.0,
        qber=0.12,
        transmission_power_pct=100.0,
        delta_power=20.0,
        delta_photon_rate=0.2,
        delta_divergence=0.2,
        is_link_visible=True
    )
    assert r_bad.total_reward < 0.0
    assert r_bad.security_breach_penalty > 0.0


def test_gym_environment_lifecycle():
    """Verify QSATEnvironment follows standard Gymnasium API."""
    env = QSATEnvironment(scenario=ScenarioType.CLEAR_SKY, max_steps=20, seed=42)

    # 1. Reset
    obs, info = env.reset(seed=42)
    assert isinstance(obs, np.ndarray)
    assert obs.shape == (15,)
    assert np.all(obs >= 0.0) and np.all(obs <= 1.0)
    assert "qber" in info

    # 2. Step
    action = np.array([0.5, 0.0, -0.2], dtype=np.float32)
    obs, reward, terminated, truncated, step_info = env.step(action)

    assert obs.shape == (15,)
    assert isinstance(reward, float)
    assert terminated is False
    assert truncated is False
    assert "qber" in step_info
    assert "skr" in step_info

    # 3. Step to termination
    for _ in range(25):
        obs, reward, terminated, truncated, step_info = env.step(np.zeros(3, dtype=np.float32))
        if terminated:
            break

    assert terminated is True
