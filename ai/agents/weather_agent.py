"""Weather Agent: Evaluates environmental severity and recommends operating conditions."""

from backend.app.models.agents import WeatherAgentDecision
from backend.app.models.environment import EnvironmentData


class WeatherAgent:
    """Specialized agent analyzing meteorological and atmospheric parameters."""

    def analyze(self, env: EnvironmentData) -> WeatherAgentDecision:
        """Evaluate ambient light, turbulence, cloud factor, and humidity."""
        cloud = env.cloud_factor
        turb = env.turbulence
        light = env.ambient_light
        hum = env.humidity

        # Ambient noise tier
        if light < 2000.0:
            noise_tier = "NEGLIGIBLE"
        elif light < 45000.0:
            noise_tier = "MODERATE"
        else:
            noise_tier = "SATURATED"

        # Severity heuristic score [0, 100]
        severity_score = (cloud * 50.0) + (turb * 30.0) + (min(1.0, light / 80000.0) * 15.0) + ((hum / 100.0) * 5.0)

        if severity_score < 20.0:
            severity = "LOW"
            recommendation = "Optimal seeing; nominal beam divergence and standard transmission power recommended"
            conf = 0.95
        elif severity_score < 45.0:
            severity = "MODERATE"
            recommendation = "Moderate atmospheric attenuation; boost transmission power modestly"
            conf = 0.88
        elif severity_score < 75.0:
            severity = "HIGH"
            recommendation = "Substantial optical degradation; prioritize beam penetration and noise filtering"
            conf = 0.85
        else:
            severity = "SEVERE"
            recommendation = "Severe cloud cover or scintillation; conserve laser power or operate cautiously"
            conf = 0.92

        return WeatherAgentDecision(
            severity=severity,
            cloud_impact=round(float(cloud), 3),
            turbulence_impact=round(float(turb), 3),
            ambient_noise_level=noise_tier,
            recommendation=recommendation,
            confidence=conf
        )
