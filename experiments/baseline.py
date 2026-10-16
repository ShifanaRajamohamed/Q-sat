"""Benchmark script for Experiment 1: Static Configuration Controller."""

from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.models.control import ControlAction
from backend.app.models.environment import ScenarioType
from ai.training.evaluate import evaluate_controller


class StaticController:
    """Fixed-parameter baseline controller."""
    def decide(self, satellite, environment, channel, qkd) -> ControlAction:
        return ControlAction(
            transmission_power_pct=70.0,
            photon_rate_norm=0.80,
            beam_divergence_norm=0.25,
            controller_type="STATIC",
            reason="Static preset"
        )


def run_static_experiment(scenario: ScenarioType = ScenarioType.CLEAR_SKY, steps: int = 300, seed: int = 42):
    ctrl = StaticController()
    return evaluate_controller(ctrl, scenario=scenario, steps=steps, seed=seed)


if __name__ == "__main__":
    res = run_static_experiment()
    print("Static Controller Results:", res)
