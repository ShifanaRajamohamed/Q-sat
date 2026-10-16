"""Benchmark script for Experiment 4: Hierarchical Multi-Agent Controller."""

from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.agents.coordinator import CoordinatorAgent
from ai.training.evaluate import evaluate_controller
from backend.app.models.control import ControlAction
from backend.app.models.environment import ScenarioType


class MultiAgentControllerWrapper:
    """Wraps CoordinatorAgent to conform to evaluate_controller interface."""
    def __init__(self):
        self.coordinator = CoordinatorAgent()

    def decide(self, satellite, environment, channel, qkd) -> ControlAction:
        decision = self.coordinator.step(satellite, environment, channel, qkd)
        return decision.final_action


def run_multi_agent_experiment(scenario: ScenarioType = ScenarioType.CLEAR_SKY, steps: int = 300, seed: int = 42):
    ctrl = MultiAgentControllerWrapper()
    return evaluate_controller(ctrl, scenario=scenario, steps=steps, seed=seed)


if __name__ == "__main__":
    res = run_multi_agent_experiment()
    print("Multi-Agent Controller Results:", res)
