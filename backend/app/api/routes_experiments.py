"""Experiments and Benchmark Metrics API routes."""

import csv
import json
import os
from pathlib import Path
from typing import Any, Dict, List
from fastapi import APIRouter

router = APIRouter(prefix="/api/experiments", tags=["Experiments"])
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"


@router.get("", summary="List all benchmark experiment runs and result files")
async def list_experiments() -> List[Dict[str, Any]]:
    """Retrieve catalog of saved benchmark experiment runs."""
    legacy_dir = PROJECT_ROOT / "experiments" / "results"
    experiments = []
    if legacy_dir.exists():
        for f in sorted(legacy_dir.glob("*.json")):
            try:
                with open(f, "r") as fp:
                    data = json.load(fp)
                experiments.append({"filename": f.name, "data": data})
            except Exception:
                continue
    return experiments


@router.get("/metrics", summary="Get aggregate benchmark comparison metrics")
async def get_benchmark_metrics() -> Dict[str, Any]:
    """Return summary performance comparisons across controllers."""
    csv_file = RESULTS_DIR / "final_results.csv"
    if csv_file.exists():
        records = []
        with open(csv_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(row)
        return {
            "status": "completed",
            "provenance": "SIMULATED ENVIRONMENT",
            "benchmark_scenarios": [f"EXP-{i:02d}" for i in range(1, 19)],
            "controllers": records,
            "total_experiments": 18
        }

    return {
        "status": "pending",
        "benchmark_scenarios": [f"EXP-{i:02d}" for i in range(1, 19)],
        "evaluated_controllers": ["STATIC", "RULE_BASED", "PPO", "MULTI_AGENT"],
        "primary_metrics": ["total_secret_key", "average_skr", "average_qber", "energy_consumption", "uptime"]
    }


@router.get("/summary", summary="Get full scientific results and leaderboard")
async def get_full_summary() -> Dict[str, Any]:
    """Retrieve structured benchmark summary with multi-seed and master leaderboard metrics."""
    csv_file = RESULTS_DIR / "final_results.csv"
    records = []
    if csv_file.exists():
        with open(csv_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(row)

    stats_file = RESULTS_DIR / "experiments" / "statistics" / "statistical_summary_table.csv"
    stats_records = []
    if stats_file.exists():
        with open(stats_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                stats_records.append(row)

    return {
        "provenance": "SIMULATED ENVIRONMENT",
        "leaderboard": records,
        "statistical_runs": stats_records,
        "report_available": (RESULTS_DIR / "final_summary.md").exists()
    }


@router.post("/run-demo", summary="Trigger dynamic benchmark demonstration")
async def run_demo() -> Dict[str, Any]:
    """Execute a rapid demonstration evaluation of all 4 controllers on a turbulent pass."""
    from experiments.exp10_final_comparison import run_comparative_study
    combined_df, summary_df = run_comparative_study(duration_s=120, seed=42)
    return {
        "status": "SUCCESS",
        "provenance": "SIMULATED ENVIRONMENT",
        "summary": summary_df.to_dict(orient="records"),
        "duration_seconds": 120
    }
