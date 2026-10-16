"""Configuration module for Q-SAT Adaptive Ground Station.

Loads configuration parameters from environment variables and .env files,
providing strongly typed settings with default values aligned with the
research and simulation specifications.
"""

from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # System Identification
    SYSTEM_NAME: str = "Q-SAT Adaptive Ground Station"
    VERSION: str = "0.1.0"
    ENVIRONMENT_MODE: Literal["simulation", "mqtt"] = "simulation"

    # API Server Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = False

    # Ground Station Coordinates (Default: NIT Trichy / Regional reference)
    GROUND_STATION_LAT: float = Field(default=10.7905, description="Latitude in degrees North")
    GROUND_STATION_LON: float = Field(default=78.7047, description="Longitude in degrees East")
    GROUND_STATION_ALT: float = Field(default=80.0, description="Altitude in meters above sea level")
    MIN_ELEVATION: float = Field(default=10.0, description="Minimum elevation angle in degrees for link establishment")

    # Simulation Dynamics
    SIMULATION_SPEED: float = Field(default=1.0, ge=0.1, le=100.0, description="Simulation speed multiplier")
    SIMULATION_TIME_STEP: float = Field(default=1.0, description="Base time step in seconds")
    RANDOM_SEED: int = Field(default=42, description="Seed for deterministic reproducibility")

    # MQTT Broker Configuration
    MQTT_BROKER: str = "localhost"
    MQTT_PORT: int = 1883
    MQTT_KEEPALIVE: int = 60
    MQTT_TOPIC_ENVIRONMENT: str = "qsat/environment"
    MQTT_TOPIC_SATELLITE: str = "qsat/satellite"
    MQTT_TOPIC_QKD: str = "qsat/qkd"
    MQTT_TOPIC_CONTROL: str = "qsat/control"
    MQTT_TOPIC_ALERTS: str = "qsat/alerts"

    # Optical & Quantum Channel Parameters (BB84 Model Defaults)
    QKD_DETECTOR_EFFICIENCY: float = Field(default=0.10, description="Single photon detector quantum efficiency (eta_det)")
    DARK_COUNT_RATE: float = Field(default=1e-5, description="Detector dark count probability per pulse")
    BASE_QBER: float = Field(default=0.01, description="Intrinsic optical baseline error rate (1%)")
    BASIS_MATCHING_PROBABILITY: float = Field(default=0.50, description="BB84 basis reconciliation probability")
    ERROR_CORRECTION_EFFICIENCY: float = Field(default=1.16, description="f(e) bidirectional error correction efficiency")
    OPTICAL_WAVELENGTH_NM: float = Field(default=850.0, description="Communication wavelength in nm")

    # Actuator & Control Constraints
    MAX_TRANSMISSION_POWER: float = Field(default=100.0, description="Max laser power (mW or % scale)")
    MIN_TRANSMISSION_POWER: float = Field(default=5.0, description="Min laser power")
    MAX_PHOTON_RATE: float = Field(default=1.0, description="Normalized photon rate ceiling [0.0, 1.0]")
    MIN_PHOTON_RATE: float = Field(default=0.05, description="Normalized photon rate floor [0.0, 1.0]")
    MAX_BEAM_DIVERGENCE: float = Field(default=1.0, description="Normalized beam divergence ceiling [0.0, 1.0]")
    MIN_BEAM_DIVERGENCE: float = Field(default=0.1, description="Normalized beam divergence floor [0.0, 1.0]")
    MAX_RATE_OF_CHANGE: float = Field(default=0.20, description="Maximum control adjustment allowed per step")

    # Database
    DATABASE_URL: str = "sqlite:///./qsat.db"


settings = Settings()
