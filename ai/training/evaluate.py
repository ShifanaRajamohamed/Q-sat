"""evaluate.py: Evaluation harness for benchmarking controllers on standardized scenarios."""

import argparse
import json
from pathlib import Path
import sys
from typing import Dict

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from ai.environment import QSATEnvironment
from ai.ppo_controller import PPOController
from ai.rule_based_controller import RuleBasedController
from backend.app.models.environment import ScenarioType


def evaluate_controller(
    controller,
    scenario: ScenarioType,
    steps: int = 300,
    seed: int = 42
) -> Dict[str, float]:
    """Execute a single evaluation pass and extract key research performance metrics."""
    env = QSATEnvironment(scenario=scenario, max_steps=steps, seed=seed)
    obs, info = env.reset(seed=seed)

    skr_history = []
    qber_history = []
    power_history = []
    reward_history = []
    control_changes = 0
    prev_power = env.power_pct

    for _ in range(steps):
        # Choose action
        action = controller.decide(
            satellite=env.latest_sat,
            environment=env.latest_env,
            channel=env.latest_channel,
            qkd=env.latest_qkd
        )
        if abs(action.transmission_power_pct - prev_power) > 1.0:
            control_changes += 1
        prev_power = action.transmission_power_pct

        # Map action to normalized [-1, 1] delta
        rate_limit = 0.20
        delta_p_norm = (action.transmission_power_pct - env.power_pct) / (rate_limit * 100.0)
        delta_r_norm = (action.photon_rate_norm - env.photon_rate_norm) / rate_limit
        delta_d_norm = (action.beam_divergence_norm - env.beam_divergence_norm) / rate_limit

        act_array = np.array([delta_p_norm, delta_r_norm, delta_d_norm], dtype=np.float32)
        obs, reward, terminated, truncated, step_info = env.step(act_array)

        skr_history.append(step_info["skr"])
        qber_history.append(step_info["qber"])
        power_history.append(step_info["power_pct"])
        reward_history.append(reward)

        if terminated:
            break

    skr_arr = np.array(skr_history)
    qber_arr = np.array(qber_history)
    power_arr = np.array(power_history)

    # Calculate metrics
    active_mask = skr_arr > 0.0
    availability = float(np.mean(active_mask) * 100.0)

    results = {
        "scenario": scenario.value,
        "mean_skr_bps": float(np.mean(skr_arr)),
        "peak_skr_bps": float(np.max(skr_arr)),
        "mean_qber": float(np.mean(qber_arr)),
        "max_qber": float(np.max(qber_arr)),
        "channel_availability_pct": availability,
        "energy_consumption_index": float(np.sum(power_arr) * env.dt),
        "control_changes_count": control_changes,
        "mean_step_reward": float(np.mean(reward_history))
    }
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Q-SAT Controllers")
    parser.add_argument("--scenario", type=str, default="CLEAR_SKY", choices=[s.value for s in ScenarioType])
    parser.add_argument("--controller", type=str, default="RULE_BASED", choices=["RULE_BASED", "PPO"])
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    ctrl = PPOController() if args.controller == "PPO" else RuleBasedController()
    res = evaluate_controller(ctrl, ScenarioType(args.scenario), steps=args.steps, seed=args.seed)

    print("\n--- Evaluation Results ---")
    for k, v in res.items():
        print(f"  {k}: {v}")
