"""Scenario definitions and parameter profiles for Q-SAT environmental simulations.

Each scenario configures the mean levels, reversion rates, and volatility
for the Ornstein-Uhlenbeck stochastic state evolution.
"""

from dataclasses import dataclass
from typing import Dict
from backend.app.models.environment import ScenarioInfo, ScenarioType


@dataclass(frozen=True)
class ScenarioParams:
    """Statistical parameters for the stochastic environment generator."""
    # Temperature (°C)
    temp_mean: float
    temp_theta: float  # Mean reversion speed
    temp_sigma: float  # Volatility / noise amplitude
    temp_min: float
    temp_max: float

    # Relative Humidity (%)
    humidity_mean: float
    humidity_theta: float
    humidity_sigma: float
    humidity_min: float
    humidity_max: float

    # Ambient Optical Light (lux)
    ambient_light_mean: float
    ambient_light_theta: float
    ambient_light_sigma: float
    ambient_light_min: float
    ambient_light_max: float

    # Platform Vibration (g)
    vibration_mean: float
    vibration_theta: float
    vibration_sigma: float
    vibration_min: float
    vibration_max: float

    # Cloud Obscuration Factor [0.0, 1.0]
    cloud_mean: float
    cloud_theta: float
    cloud_sigma: float
    cloud_min: float
    cloud_max: float

    # Turbulence Index [0.0, 1.0]
    turbulence_mean: float
    turbulence_theta: float
    turbulence_sigma: float
    turbulence_min: float
    turbulence_max: float


# Catalog of Scenario Profiles
SCENARIO_CATALOG: Dict[ScenarioType, ScenarioParams] = {
    ScenarioType.CLEAR_SKY: ScenarioParams(
        temp_mean=24.0, temp_theta=0.05, temp_sigma=0.3, temp_min=18.0, temp_max=30.0,
        humidity_mean=45.0, humidity_theta=0.05, humidity_sigma=1.0, humidity_min=30.0, humidity_max=60.0,
        ambient_light_mean=300.0, ambient_light_theta=0.05, ambient_light_sigma=30.0, ambient_light_min=50.0, ambient_light_max=800.0,
        vibration_mean=0.02, vibration_theta=0.10, vibration_sigma=0.005, vibration_min=0.005, vibration_max=0.06,
        cloud_mean=0.03, cloud_theta=0.05, cloud_sigma=0.01, cloud_min=0.0, cloud_max=0.12,
        turbulence_mean=0.08, turbulence_theta=0.05, turbulence_sigma=0.015, turbulence_min=0.02, turbulence_max=0.18,
    ),
    ScenarioType.HUMID: ScenarioParams(
        temp_mean=29.0, temp_theta=0.05, temp_sigma=0.4, temp_min=24.0, temp_max=35.0,
        humidity_mean=90.0, humidity_theta=0.08, humidity_sigma=1.5, humidity_min=80.0, humidity_max=99.0,
        ambient_light_mean=1200.0, ambient_light_theta=0.05, ambient_light_sigma=80.0, ambient_light_min=300.0, ambient_light_max=3000.0,
        vibration_mean=0.03, vibration_theta=0.10, vibration_sigma=0.008, vibration_min=0.01, vibration_max=0.08,
        cloud_mean=0.22, cloud_theta=0.05, cloud_sigma=0.03, cloud_min=0.10, cloud_max=0.40,
        turbulence_mean=0.35, turbulence_theta=0.05, turbulence_sigma=0.03, turbulence_min=0.20, turbulence_max=0.55,
    ),
    ScenarioType.CLOUDY: ScenarioParams(
        temp_mean=21.0, temp_theta=0.05, temp_sigma=0.3, temp_min=16.0, temp_max=27.0,
        humidity_mean=78.0, humidity_theta=0.05, humidity_sigma=1.2, humidity_min=65.0, humidity_max=92.0,
        ambient_light_mean=6000.0, ambient_light_theta=0.05, ambient_light_sigma=500.0, ambient_light_min=1500.0, ambient_light_max=12000.0,
        vibration_mean=0.04, vibration_theta=0.10, vibration_sigma=0.01, vibration_min=0.01, vibration_max=0.10,
        cloud_mean=0.82, cloud_theta=0.06, cloud_sigma=0.04, cloud_min=0.60, cloud_max=0.98,
        turbulence_mean=0.42, turbulence_theta=0.05, turbulence_sigma=0.03, turbulence_min=0.25, turbulence_max=0.65,
    ),
    ScenarioType.HIGH_AMBIENT_LIGHT: ScenarioParams(
        temp_mean=36.0, temp_theta=0.05, temp_sigma=0.5, temp_min=30.0, temp_max=43.0,
        humidity_mean=35.0, humidity_theta=0.05, humidity_sigma=1.0, humidity_min=20.0, humidity_max=50.0,
        ambient_light_mean=80000.0, ambient_light_theta=0.08, ambient_light_sigma=4000.0, ambient_light_min=55000.0, ambient_light_max=100000.0,
        vibration_mean=0.03, vibration_theta=0.10, vibration_sigma=0.008, vibration_min=0.01, vibration_max=0.08,
        cloud_mean=0.04, cloud_theta=0.05, cloud_sigma=0.015, cloud_min=0.0, cloud_max=0.15,
        turbulence_mean=0.60, turbulence_theta=0.06, turbulence_sigma=0.04, turbulence_min=0.40, turbulence_max=0.82,
    ),
    ScenarioType.VIBRATION: ScenarioParams(
        temp_mean=25.0, temp_theta=0.05, temp_sigma=0.3, temp_min=20.0, temp_max=31.0,
        humidity_mean=50.0, humidity_theta=0.05, humidity_sigma=1.0, humidity_min=35.0, humidity_max=65.0,
        ambient_light_mean=1500.0, ambient_light_theta=0.05, ambient_light_sigma=100.0, ambient_light_min=500.0, ambient_light_max=3500.0,
        vibration_mean=0.95, vibration_theta=0.20, vibration_sigma=0.15, vibration_min=0.50, vibration_max=1.85,
        cloud_mean=0.05, cloud_theta=0.05, cloud_sigma=0.015, cloud_min=0.0, cloud_max=0.15,
        turbulence_mean=0.18, turbulence_theta=0.05, turbulence_sigma=0.02, turbulence_min=0.05, turbulence_max=0.30,
    ),
    ScenarioType.COMBINED_DEGRADATION: ScenarioParams(
        temp_mean=28.0, temp_theta=0.05, temp_sigma=0.4, temp_min=22.0, temp_max=35.0,
        humidity_mean=88.0, humidity_theta=0.06, humidity_sigma=1.5, humidity_min=75.0, humidity_max=98.0,
        ambient_light_mean=25000.0, ambient_light_theta=0.06, ambient_light_sigma=2000.0, ambient_light_min=8000.0, ambient_light_max=50000.0,
        vibration_mean=0.85, vibration_theta=0.18, vibration_sigma=0.12, vibration_min=0.45, vibration_max=1.70,
        cloud_mean=0.78, cloud_theta=0.06, cloud_sigma=0.04, cloud_min=0.55, cloud_max=0.96,
        turbulence_mean=0.80, turbulence_theta=0.06, turbulence_sigma=0.04, turbulence_min=0.55, turbulence_max=0.98,
    ),
}

# Informative metadata descriptions for frontend and API
SCENARIO_METADATA: Dict[ScenarioType, ScenarioInfo] = {
    ScenarioType.CLEAR_SKY: ScenarioInfo(
        id=ScenarioType.CLEAR_SKY,
        name="Scenario A: Clear Sky",
        description="Near-ideal astronomical seeing with minimal cloud cover, low turbulence, and low optical noise.",
        expected_cloud_range=(0.0, 0.12),
        expected_turbulence_range=(0.02, 0.18),
        expected_humidity_range=(30.0, 60.0),
        expected_vibration_range=(0.005, 0.06),
        expected_ambient_light_range=(50.0, 800.0),
    ),
    ScenarioType.HUMID: ScenarioInfo(
        id=ScenarioType.HUMID,
        name="Scenario B: Humid",
        description="High atmospheric moisture causing water-vapor absorption and moderate channel attenuation.",
        expected_cloud_range=(0.10, 0.40),
        expected_turbulence_range=(0.20, 0.55),
        expected_humidity_range=(80.0, 99.0),
        expected_vibration_range=(0.01, 0.08),
        expected_ambient_light_range=(300.0, 3000.0),
    ),
    ScenarioType.CLOUDY: ScenarioInfo(
        id=ScenarioType.CLOUDY,
        name="Scenario C: Cloudy",
        description="Dense overcast cloud cover causing substantial optical scattering, high path extinction, and channel loss.",
        expected_cloud_range=(0.60, 0.98),
        expected_turbulence_range=(0.25, 0.65),
        expected_humidity_range=(65.0, 92.0),
        expected_vibration_range=(0.01, 0.10),
        expected_ambient_light_range=(1500.0, 12000.0),
    ),
    ScenarioType.HIGH_AMBIENT_LIGHT: ScenarioInfo(
        id=ScenarioType.HIGH_AMBIENT_LIGHT,
        name="Scenario D: High Ambient Light",
        description="Direct daytime solar illumination generating strong stray light, background photon counts, and thermal turbulence.",
        expected_cloud_range=(0.0, 0.15),
        expected_turbulence_range=(0.40, 0.82),
        expected_humidity_range=(20.0, 50.0),
        expected_vibration_range=(0.01, 0.08),
        expected_ambient_light_range=(55000.0, 100000.0),
    ),
    ScenarioType.VIBRATION: ScenarioInfo(
        id=ScenarioType.VIBRATION,
        name="Scenario E: Vibration",
        description="Severe telescope mount jitter and platform instability inducing beam deflection and pointing error.",
        expected_cloud_range=(0.0, 0.15),
        expected_turbulence_range=(0.05, 0.30),
        expected_humidity_range=(35.0, 65.0),
        expected_vibration_range=(0.50, 1.85),
        expected_ambient_light_range=(500.0, 3500.0),
    ),
    ScenarioType.COMBINED_DEGRADATION: ScenarioInfo(
        id=ScenarioType.COMBINED_DEGRADATION,
        name="Scenario F: Combined Degradation",
        description="Simultaneous adverse factors: high humidity, strong turbulence, heavy cloud obscuration, and platform vibration.",
        expected_cloud_range=(0.55, 0.96),
        expected_turbulence_range=(0.55, 0.98),
        expected_humidity_range=(75.0, 98.0),
        expected_vibration_range=(0.45, 1.70),
        expected_ambient_light_range=(8000.0, 50000.0),
    ),
}
