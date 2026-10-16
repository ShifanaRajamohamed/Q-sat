"""Abstract base class for Environment Providers in the Q-SAT architecture.

Provides a unified interface decoupling environmental telemetry sources (whether
generated via physical simulation models or streamed from ESP32 hardware via MQTT).
The Digital Twin and AI layers consume EnvironmentProvider without needing to know
the telemetry origin.
"""

from abc import ABC, abstractmethod
from typing import Optional
from backend.app.models.environment import EnvironmentData


class EnvironmentProvider(ABC):
    """Abstract interface defining required methods for environmental data providers."""

    @abstractmethod
    def get_current_environment(self) -> EnvironmentData:
        """Return the latest environmental telemetry state."""
        pass

    @abstractmethod
    def step(self, dt: float = 1.0) -> EnvironmentData:
        """Advance the environmental state by dt seconds and return the updated state."""
        pass

    @abstractmethod
    def reset(self, seed: Optional[int] = None) -> EnvironmentData:
        """Reset the environment to initial conditions with an optional deterministic seed."""
        pass

    @abstractmethod
    def get_mode(self) -> str:
        """Return the operating mode identifier ('simulation' or 'mqtt')."""
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        """Return True if the provider is actively producing valid environmental data."""
        pass
