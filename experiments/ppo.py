"""Benchmark script for Experiment 3: Single-Agent PPO Controller."""

from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.ppo_controller import PPOController
from ai.training.evaluate import evaluate_controller
from backend.app.models.environment import ScenarioType


def run_ppo_experiment(scenario: ScenarioType = ScenarioType.CLEAR_SKY, steps: int = 300, seed: int = 42):
    ctrl = PPOController()
    return evaluate_controller(ctrl, scenario=scenario, steps=steps, seed=seed)


if __name__ == "__main__":
    res = run_ppo_experiment()
    print("PPO Controller Results:", res)
