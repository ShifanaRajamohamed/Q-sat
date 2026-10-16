"""Scenario Runner: CLI and batch tool for generating deterministic environmental datasets.

Runs scenarios A through F, computes summary statistics, and exports time-series
datasets to CSV/JSON in simulation/generated_data/.
"""

import argparse
import os
from pathlib import Path
import sys
import pandas as pd

# Add project root to sys.path for direct script execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.models.environment import ScenarioType
from digital_twin.simulation_environment_provider import SimulationEnvironmentProvider
from simulation.scenarios.scenario_definitions import SCENARIO_METADATA


def run_scenario(
    scenario: ScenarioType,
    duration_seconds: float = 300.0,
    dt: float = 1.0,
    seed: int = 42,
    output_dir: str = "simulation/generated_data"
) -> pd.DataFrame:
    """Execute a simulation scenario and export the generated time-series."""
    provider = SimulationEnvironmentProvider(scenario=scenario, seed=seed)
    df = provider.generate_time_series(duration_seconds=duration_seconds, dt=dt)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    filename = f"{scenario.value.lower()}_seed{seed}.csv"
    csv_file = out_path / filename
    df.to_csv(csv_file, index=False)

    print(f"\n--- Scenario: {scenario.value} ({SCENARIO_METADATA[scenario].name}) ---")
    print(f"Exported {len(df)} samples to {csv_file}")
    print("\nSummary Statistics:")
    summary_cols = ["temperature", "humidity", "ambient_light", "vibration", "cloud_factor", "turbulence"]
    stats = df[summary_cols].describe().T[["mean", "std", "min", "max"]]
    print(stats.to_string())

    return df


def run_all_scenarios(
    duration_seconds: float = 300.0,
    dt: float = 1.0,
    seed: int = 42,
    output_dir: str = "simulation/generated_data"
) -> dict[str, pd.DataFrame]:
    """Generate benchmark datasets for all 6 scenarios (A through F)."""
    results = {}
    for scenario in ScenarioType:
        results[scenario.value] = run_scenario(
            scenario=scenario,
            duration_seconds=duration_seconds,
            dt=dt,
            seed=seed,
            output_dir=output_dir
        )
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Q-SAT Environmental Scenario Runner")
    parser.add_argument(
        "--scenario",
        type=str,
        default="ALL",
        choices=["ALL"] + [s.value for s in ScenarioType],
        help="Scenario to run (or 'ALL' for complete suite)"
    )
    parser.add_argument("--duration", type=float, default=300.0, help="Duration in seconds")
    parser.add_argument("--dt", type=float, default=1.0, help="Time step in seconds")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    parser.add_argument("--output-dir", type=str, default="simulation/generated_data", help="Output directory")

    args = parser.parse_args()

    if args.scenario == "ALL":
        run_all_scenarios(duration_seconds=args.duration, dt=args.dt, seed=args.seed, output_dir=args.output_dir)
    else:
        run_scenario(
            scenario=ScenarioType(args.scenario),
            duration_seconds=args.duration,
            dt=args.dt,
            seed=args.seed,
            output_dir=args.output_dir
        )
