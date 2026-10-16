"""
run_all.py — Master Experiment Execution Pipeline (Experiment 19)

Sequentially orchestrates and validates the entire suite of 18 empirical experiments
for the Q-SAT Adaptive Ground Station project.

Features:
- CLI flags for running all or specific experiment subsets
- Timing, success validation, and artifact tracking
- Automatically invokes report generator upon pipeline completion
"""

import argparse
from pathlib import Path
import subprocess
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYTHON_EXE = sys.executable

EXPERIMENTS = [
    ("exp01_baseline.py", "Exp 1: Baseline QKD Performance Profile"),
    ("exp02_turbulence.py", "Exp 2: Atmospheric Turbulence Sweep"),
    ("exp03_elevation.py", "Exp 3: Orbital Elevation Geometry Sweep"),
    ("exp04_distance.py", "Exp 4: Slant Range Path Loss Sweep"),
    ("exp05_qber.py", "Exp 5: QBER Threshold & Information Leakage"),
    ("exp06_power.py", "Exp 6: Transmission Power & Energy Tradeoff"),
    ("exp07_weather.py", "Exp 7: Distinct Weather Regimes Benchmark"),
    ("exp08_dynamic_weather.py", "Exp 8: Dynamic Weather Transition Across Pass"),
    ("exp09_static_vs_ppo.py", "Exp 9: Static Baseline vs PPO Controller"),
    ("exp10_final_comparison.py", "Exp 10: Multi-Controller Comparative Analysis"),
    ("exp11_ppo_training.py", "Exp 11: PPO Training Convergence Curve"),
    ("exp12_ai_adaptation.py", "Exp 12: Real-Time AI Actuator Adaptation"),
    ("exp13_agent_analysis.py", "Exp 13: Hierarchical Agent Decision Analysis"),
    ("exp14_digital_twin.py", "Exp 14: Digital Twin State Tracking & Physics"),
    ("exp15_security.py", "Exp 15: Security Anomaly Detection & QBER Attribution"),
    ("exp16_ablation.py", "Exp 16: Multi-Agent Architecture Ablation Study"),
    ("exp17_statistics.py", "Exp 17: Statistical Validation Across Multi-Seed Runs"),
    ("exp18_final_table.py", "Exp 18: Consolidated Master Results Table & Radar"),
]


def run_pipeline(selected_indices=None, skip_training=False):
    print("=" * 80)
    print("       Q-SAT ADAPTIVE GROUND STATION — MASTER EXPERIMENT SUITE")
    print("       Data Provenance: SIMULATED ENVIRONMENT (All Experiments)")
    print("=" * 80)

    start_all = time.time()
    results = []

    for idx, (script_name, title) in enumerate(EXPERIMENTS, start=1):
        if selected_indices and idx not in selected_indices:
            continue
        if skip_training and "exp11" in script_name:
            print(f"\n[SKIPPING] {title} (--skip-training active)")
            continue

        script_path = PROJECT_ROOT / "experiments" / script_name
        print(f"\n>>> [{idx}/18] RUNNING: {title}")
        print(f"    Script: {script_path.name}")

        t0 = time.time()
        res = subprocess.run([PYTHON_EXE, str(script_path)], cwd=str(PROJECT_ROOT))
        dur = time.time() - t0

        status = "PASSED" if res.returncode == 0 else "FAILED"
        print(f"    Status: {status} | Duration: {dur:.1f}s")
        results.append({
            "index": idx,
            "title": title,
            "script": script_name,
            "status": status,
            "duration_s": round(dur, 2)
        })

    total_time = time.time() - start_all
    print("\n" + "=" * 80)
    print("                       EXPERIMENT SUITE SUMMARY")
    print("=" * 80)
    passed_count = sum(1 for r in results if r["status"] == "PASSED")
    for r in results:
        print(f"  [{r['index']:02d}] {r['title']:<50} | {r['status']:<8} | {r['duration_s']:>6.1f}s")
    print("-" * 80)
    print(f"  Total Passed: {passed_count}/{len(results)} | Total Elapsed Time: {total_time:.1f}s")
    print("=" * 80 + "\n")

    # Run automated report generation
    report_gen = PROJECT_ROOT / "experiments" / "generate_report.py"
    if report_gen.exists():
        print(">>> Generating comprehensive final summary report...")
        subprocess.run([PYTHON_EXE, str(report_gen)], cwd=str(PROJECT_ROOT))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Master Experiment Runner for Q-SAT")
    parser.add_argument("--exp", type=int, nargs="+", help="Specific experiment numbers to execute (e.g. --exp 1 2 10)")
    parser.add_argument("--skip-training", action="store_true", help="Skip PPO training experiment to save time")
    args = parser.parse_args()

    run_pipeline(selected_indices=args.exp, skip_training=args.skip_training)
