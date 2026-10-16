"""Unit and integration tests for Phase 2: Environment Simulator and Abstraction Layer."""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.environment import EnvironmentData, ScenarioType
from backend.app.services.environment_service import environment_service
from digital_twin.environment_provider import EnvironmentProvider
from digital_twin.mqtt_environment_provider import MQTTEnvironmentProvider
from digital_twin.simulation_environment_provider import SimulationEnvironmentProvider

client = TestClient(app)


def test_provider_abstraction_compliance():
    """Verify that both simulation and MQTT providers implement the EnvironmentProvider interface."""
    sim_provider = SimulationEnvironmentProvider(seed=42)
    assert isinstance(sim_provider, EnvironmentProvider)
    assert sim_provider.get_mode() == "simulation"
    assert sim_provider.is_healthy() is True

    mqtt_provider = MQTTEnvironmentProvider()
    assert isinstance(mqtt_provider, EnvironmentProvider)
    assert mqtt_provider.get_mode() == "mqtt"
    # Gracefully closes without exception
    mqtt_provider.close()


def test_deterministic_reproducibility():
    """Verify that identical random seeds yield identical environmental time-series traces."""
    provider_1 = SimulationEnvironmentProvider(scenario=ScenarioType.CLEAR_SKY, seed=12345)
    provider_2 = SimulationEnvironmentProvider(scenario=ScenarioType.CLEAR_SKY, seed=12345)

    trace_1 = [provider_1.step(dt=1.0).model_dump() for _ in range(50)]
    trace_2 = [provider_2.step(dt=1.0).model_dump() for _ in range(50)]

    assert trace_1 == trace_2, "Simulators with identical seeds must produce identical output"


def test_different_seeds_produce_different_traces():
    """Verify that distinct seeds produce divergent stochastic traces."""
    provider_a = SimulationEnvironmentProvider(scenario=ScenarioType.CLEAR_SKY, seed=111)
    provider_b = SimulationEnvironmentProvider(scenario=ScenarioType.CLEAR_SKY, seed=999)

    trace_a = [provider_a.step(dt=1.0).temperature for _ in range(20)]
    trace_b = [provider_b.step(dt=1.0).temperature for _ in range(20)]

    assert trace_a != trace_b


@pytest.mark.parametrize("scenario, checks", [
    (ScenarioType.CLEAR_SKY, {
        "cloud_max": 0.15,
        "turbulence_max": 0.20,
        "vibration_max": 0.08,
        "ambient_light_max": 1000.0,
    }),
    (ScenarioType.HUMID, {
        "humidity_min": 75.0,
    }),
    (ScenarioType.CLOUDY, {
        "cloud_min": 0.55,
    }),
    (ScenarioType.HIGH_AMBIENT_LIGHT, {
        "ambient_light_min": 50000.0,
    }),
    (ScenarioType.VIBRATION, {
        "vibration_min": 0.40,
    }),
    (ScenarioType.COMBINED_DEGRADATION, {
        "humidity_min": 70.0,
        "cloud_min": 0.50,
        "turbulence_min": 0.50,
        "vibration_min": 0.40,
    }),
])
def test_scenario_characteristics(scenario, checks):
    """Verify that each scenario adheres to its expected physical boundary conditions."""
    provider = SimulationEnvironmentProvider(scenario=scenario, seed=42)
    samples = [provider.step(dt=1.0) for _ in range(30)]

    for sample in samples:
        # Check physical ranges
        assert 0.0 <= sample.cloud_factor <= 1.0
        assert 0.0 <= sample.turbulence <= 1.0
        assert 0.0 <= sample.humidity <= 100.0
        assert sample.ambient_light >= 0.0
        assert sample.vibration >= 0.0
        assert sample.data_source == "SIMULATION"
        assert sample.scenario_name == scenario.value

        # Check scenario-specific profile constraints
        if "cloud_max" in checks:
            assert sample.cloud_factor <= checks["cloud_max"]
        if "cloud_min" in checks:
            assert sample.cloud_factor >= checks["cloud_min"]
        if "turbulence_max" in checks:
            assert sample.turbulence <= checks["turbulence_max"]
        if "turbulence_min" in checks:
            assert sample.turbulence >= checks["turbulence_min"]
        if "vibration_max" in checks:
            assert sample.vibration <= checks["vibration_max"]
        if "vibration_min" in checks:
            assert sample.vibration >= checks["vibration_min"]
        if "humidity_min" in checks:
            assert sample.humidity >= checks["humidity_min"]
        if "ambient_light_max" in checks:
            assert sample.ambient_light <= checks["ambient_light_max"]
        if "ambient_light_min" in checks:
            assert sample.ambient_light >= checks["ambient_light_min"]


def test_dynamic_scenario_switching():
    """Verify smooth switching between scenarios at runtime."""
    provider = SimulationEnvironmentProvider(scenario=ScenarioType.CLEAR_SKY, seed=42)
    s1 = provider.step(dt=1.0)
    assert s1.cloud_factor < 0.15

    # Switch to heavy cloud
    provider.set_scenario(ScenarioType.CLOUDY)
    # Step forward several times for OU process to evolve
    for _ in range(50):
        s2 = provider.step(dt=1.0)

    assert s2.scenario_name == ScenarioType.CLOUDY.value
    assert s2.cloud_factor > 0.50


def test_api_environment_current():
    """Verify GET /api/environment/current returns valid telemetry."""
    response = client.get("/api/environment/current")
    assert response.status_code == 200
    data = response.json()

    assert "temperature" in data
    assert "humidity" in data
    assert "ambient_light" in data
    assert "vibration" in data
    assert "cloud_factor" in data
    assert "turbulence" in data
    assert data["data_source"] in ["SIMULATION", "HARDWARE"]


def test_api_simulation_scenarios_list():
    """Verify GET /api/simulation/scenarios lists all 6 benchmark scenarios."""
    response = client.get("/api/simulation/scenarios")
    assert response.status_code == 200
    scenarios = response.json()

    assert len(scenarios) == 6
    scenario_ids = [s["id"] for s in scenarios]
    for expected in ["CLEAR_SKY", "HUMID", "CLOUDY", "HIGH_AMBIENT_LIGHT", "VIBRATION", "COMBINED_DEGRADATION"]:
        assert expected in scenario_ids


def test_api_simulation_control_flow():
    """Verify scenario switching, stepping, and resetting via API."""
    # 1. Reset simulation
    res_reset = client.post("/api/simulation/reset?seed=999")
    assert res_reset.status_code == 200
    assert res_reset.json()["timestamp"] == 0.0

    # 2. Step forward
    res_step = client.post("/api/simulation/step", json={"dt": 2.5})
    assert res_step.status_code == 200
    assert res_step.json()["timestamp"] == 2.5

    # 3. Switch scenario to VIBRATION
    res_switch = client.post("/api/simulation/scenario", json={"scenario": "VIBRATION", "seed": 42})
    assert res_switch.status_code == 200
    assert res_switch.json()["scenario_name"] == "VIBRATION"
