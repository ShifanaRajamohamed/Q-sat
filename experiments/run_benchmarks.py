"""run_benchmarks.py: Comprehensive benchmark suite evaluating all 4 controllers across EXP-01 to EXP-08."""

import json
from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from backend.app.models.environment import ScenarioType
from experiments.baseline import StaticController
from experiments.multi_agent import MultiAgentControllerWrapper
from experiments.ppo import PPOController
from experiments.rule_based import RuleBasedController
from ai.training.evaluate import evaluate_controller

EXPERIMENT_SCENARIOS = {
    "EXP-01": (ScenarioType.CLEAR_SKY, "Clear Sky Baseline"),
    "EXP-02": (ScenarioType.HUMID, "High Atmospheric Humidity"),
    "EXP-03": (ScenarioType.CLOUDY, "Overcast Cloud Extinction"),
    "EXP-04": (ScenarioType.HIGH_AMBIENT_LIGHT, "Intense Solar Stray Noise"),
    "EXP-05": (ScenarioType.VIBRATION, "Severe Mount Jitter & Pointing Error"),
    "EXP-06": (ScenarioType.COMBINED_DEGRADATION, "Sudden/Severe Atmospheric Shift"),
    "EXP-07": (ScenarioType.COMBINED_DEGRADATION, "Combined Multi-factor Stress Test"),
    "EXP-08": (ScenarioType.CLEAR_SKY, "Potential Anomalous QBER Pattern")
}


def run_full_benchmark_suite(steps_per_run: int = 150, seed: int = 42, output_dir: str = "experiments/results") -> pd.DataFrame:
    """Execute all benchmark scenarios against Static, Rule-Based, PPO, and Multi-Agent controllers."""
    print("=" * 80)
    print("     Q-SAT RESEARCH EXPERIMENT BENCHMARK SUITE")
    print(f"     Steps: {steps_per_run} | Base Seed: {seed}")
    print("=" * 80)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    controllers = {
        "STATIC": StaticController(),
        "RULE_BASED": RuleBasedController(),
        "PPO": PPOController(),
        "MULTI_AGENT": MultiAgentControllerWrapper()
    }

    all_results = []

    for exp_id, (scenario, desc) in EXPERIMENT_SCENARIOS.items():
        print(f"\n>>> Running {exp_id}: {desc} ({scenario.value})...")
        for ctrl_name, ctrl in controllers.items():
            t0 = time.time()
            metrics = evaluate_controller(ctrl, scenario=scenario, steps=steps_per_run, seed=seed)
            duration = round(time.time() - t0, 3)

            record = {
                "experiment_id": exp_id,
                "description": desc,
                "scenario": scenario.value,
                "controller": ctrl_name,
                "mean_skr_kbps": round(metrics["mean_skr_bps"] / 1000.0, 3),
                "peak_skr_kbps": round(metrics["peak_skr_bps"] / 1000.0, 3),
                "mean_qber_pct": round(metrics["mean_qber"] * 100.0, 2),
                "max_qber_pct": round(metrics["max_qber"] * 100.0, 2),
                "availability_pct": round(metrics["channel_availability_pct"], 1),
                "energy_index": round(metrics["energy_consumption_index"], 1),
                "control_changes": metrics["control_changes_count"],
                "mean_step_reward": round(metrics["mean_step_reward"], 3),
                "seed": seed,
                "duration_s": duration
            }
            all_results.append(record)
            print(f"  [{ctrl_name:12s}] SKR: {record['mean_skr_kbps']:6.2f} kbps | QBER: {record['mean_qber_pct']:5.2f}% | Avail: {record['availability_pct']:5.1f}% | Energy: {record['energy_index']:7.1f}")

    df = pd.DataFrame(all_results)
    csv_file = out_path / "benchmark_comparison_results.csv"
    json_file = out_path / "benchmark_comparison_results.json"

    df.to_csv(csv_file, index=False)
    with open(json_file, "w") as fp:
        json.dump(all_results, fp, indent=4)

    print("\n" + "=" * 80)
    print("                     BENCHMARK SUMMARY TABLE")
    print("=" * 80)
    summary = df.groupby("controller")[["mean_skr_kbps", "mean_qber_pct", "availability_pct", "energy_index"]].mean()
    print(summary.to_string())
    print(f"\nFull results exported to: {csv_file}")
    return df


if __name__ == "__main__":
    run_full_benchmark_suite(steps_per_run=100, seed=42)
