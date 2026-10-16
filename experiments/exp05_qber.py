"""
exp05_qber.py — Experiment 5: Effect of Quantum Bit Error Rate (QBER) & Security Threshold

Evaluates the theoretical asymptotic Secret Key Rate as a function of QBER (0% to 15%)
using the Devetak-Winter / Shor-Preskill asymptotic bound with bidirectional error
correction inefficiency factor f(e) = 1.16 and binary Shannon entropy h2(e).
Demonstrates the strict 11.0% BB84 theoretical cutoff limit.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from qkd.secret_key_rate import calculate_secret_key_rate, binary_entropy
from experiments.plot_utils import create_figure, save_figure, PALETTE

OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "qber"


def run_experiment_5(sifted_key_rate_bps: float = 1000.0) -> pd.DataFrame:
    """Execute Experiment 5: QBER vs Secret Key Rate."""
    print("=" * 70)
    print("  EXPERIMENT 5: QBER EFFECT & SECURITY CUTOFF THRESHOLD")
    print(f"  Reference Sifted Rate: {sifted_key_rate_bps} bps | Error Correction Inefficiency f(e)=1.16")
    print("=" * 70)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Fine-grained QBER sweep from 0.0% to 15.0%
    qber_values = np.linspace(0.001, 0.150, 150)
    records = []

    for qber in qber_values:
        skr, sec_fraction, is_secure = calculate_secret_key_rate(
            sifted_key_rate=sifted_key_rate_bps,
            qber=float(qber),
            error_correction_efficiency=1.16,
            qber_threshold=0.110
        )
        h2 = binary_entropy(float(qber))
        leakage = 1.16 * h2

        records.append({
            "qber_fraction": float(qber),
            "qber_pct": round(float(qber) * 100.0, 3),
            "shannon_entropy_h2": round(h2, 4),
            "error_correction_leakage": round(leakage, 4),
            "secret_fraction": round(sec_fraction, 4),
            "secret_key_rate_bps": round(skr, 2),
            "secret_key_rate_kbps": round(skr / 1000.0, 4),
            "is_secure": 1.0 if is_secure else 0.0
        })

    df = pd.DataFrame(records)

    # 1. Save CSV
    csv_path = OUTPUT_DIR / "qber_sweep_metrics.csv"
    df.to_csv(csv_path, index=False)
    print(f"  [SAVED CSV] {csv_path}")

    # 2. Graph 1: QBER vs SKR with 11.0% Cutoff Threshold Demonstration
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.8))
    ax.plot(df["qber_pct"], df["secret_key_rate_bps"], color=PALETTE["secondary"], linewidth=2.4, label="Secret Key Rate $R_{SKR}$ (bps)")
    ax.axvline(x=11.0, color=PALETTE["danger"], linestyle="--", linewidth=2.0, label="BB84 Theoretical Cutoff (11.0%)")
    ax.axvspan(11.0, 15.0, color=PALETTE["danger"], alpha=0.10, label="Aborted / Insecure Zone")
    ax.scatter([11.0], [0.0], color=PALETTE["danger"], s=70, zorder=5)

    ax.annotate("Cutoff Limit: 11.0%\n$R_{SKR} = 0$ bps", xy=(11.0, 0), xytext=(11.8, 180),
                arrowprops=dict(arrowstyle="->", color=PALETTE["danger"], lw=1.5),
                fontweight="bold", color=PALETTE["danger"])

    ax.set_title("Experiment 5: QBER vs Secret Key Rate (Asymptotic BB84)", fontweight="bold")
    ax.set_xlabel("Quantum Bit Error Rate (%)")
    ax.set_ylabel("Secret Key Rate (bps) [Base Sifted: 1000 bps]")
    ax.set_xlim(0, 15.0)
    ax.set_ylim(-20, 1050)
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(loc="upper right")
    save_figure(fig, OUTPUT_DIR, "qber_vs_skr.png")

    # 3. Graph 2: Information Reconciliation Leakage & Secret Fraction
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.8))
    ax.plot(df["qber_pct"], df["secret_fraction"], color=PALETTE["primary"], linewidth=2.2, label=r"Secret Key Fraction $[1 - f(e)h_2(e) - h_2(e)]$")
    ax.plot(df["qber_pct"], df["shannon_entropy_h2"], color=PALETTE["accent"], linestyle=":", linewidth=2.0, label=r"Binary Shannon Entropy $h_2(e)$")
    ax.plot(df["qber_pct"], df["error_correction_leakage"], color=PALETTE["purple"], linestyle="--", linewidth=2.0, label=r"EC Leakage $f(e) \cdot h_2(e)$")
    ax.axvline(x=11.0, color=PALETTE["danger"], linestyle="--", linewidth=1.5, label="11.0% Cutoff")
    ax.set_title("Experiment 5: Information Leakage & Secret Fraction Breakdown", fontweight="bold")
    ax.set_xlabel("Quantum Bit Error Rate (%)")
    ax.set_ylabel("Fraction / Bit Yield")
    ax.set_xlim(0, 15.0)
    ax.set_ylim(0, 1.2)
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(loc="upper right")
    save_figure(fig, OUTPUT_DIR, "qber_information_leakage.png")

    print("  [SUCCESS] Experiment 5 complete. Demonstrated 11.0% security cutoff.")
    return df


if __name__ == "__main__":
    run_experiment_5()
