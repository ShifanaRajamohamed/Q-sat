"""Benchmark script for Experiment 2: Rule-Based Controller."""

from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.rule_based_controller import RuleBasedController
from ai.training.evaluate import evaluate_controller
from backend.app.models.environment import ScenarioType


def run_rule_based_experiment(scenario: ScenarioType = ScenarioType.CLEAR_SKY, steps: int = 300, seed: int = 42):
    ctrl = RuleBasedController()
    return evaluate_controller(ctrl, scenario=scenario, steps=steps, seed=seed)


if __name__ == "__main__":
    res = run_rule_based_experiment()
    print("Rule-Based Controller Results:", res)
