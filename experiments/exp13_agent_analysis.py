"""
exp13_agent_analysis.py — Experiment 13: Hierarchical Multi-Agent Decision Analysis

Traces the inter-agent communications, individual assessments, conflict detection,
and arbitration outcomes among:
1. Weather Agent (meteorological risk assessment)
2. Communication Agent (link budget & throughput maximization)
3. Security Agent (QBER root-cause attribution & anomaly detection)
4. Coordinator Agent (hierarchical policy synthesis & conflict resolution)

Explicitly labeled: SIMULATED ENVIRONMENT.
Produces granular decision audit logs and multi-agent coordination figures.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from digital_twin.orbital_model import OrbitalModel
from digital_twin.optical_channel import OpticalChannelModel
from qkd.bb84_model import BB84Model
from backend.app.models.satellite import GroundStationConfig
from backend.app.models.environment import EnvironmentData
from ai.agents.coordinator import CoordinatorAgent
from experiments.plot_utils import create_figure, save_figure, PALETTE

OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "agent_analysis"


def run_agent_analysis_experiment(duration_s: int = 300, seed: int = 42) -> pd.DataFrame:
    print("=" * 70)
    print("  EXPERIMENT 13: HIERARCHICAL MULTI-AGENT DECISION ANALYSIS")
    print("  Data Provenance: SIMULATED ENVIRONMENT")
    print(f"  Duration: {duration_s}s | Seed: {seed} | Inter-Agent Conflict Audit")
    print("=" * 70)

    np.random.seed(seed)
    gs = GroundStationConfig(station_id="GS-RESEARCH-01", latitude=10.7905, longitude=78.7047, altitude_m=80.0)
    orbit = OrbitalModel(ground_station=gs)
    channel_model = OpticalChannelModel()
    bb84 = BB84Model()
    coordinator = CoordinatorAgent()

    records = []
    dt = 1.0

    # Initial states
    sat_prev = orbit.propagate(0.0)
    env_prev = EnvironmentData(
        timestamp=0.0,
        temperature=25.0,
        humidity=50.0,
        ambient_light=300.0,
        vibration=0.010,
        cloud_factor=0.05,
        turbulence=0.08,
        data_source="SIMULATION"
    )
    chan_prev = channel_model.calculate_link_state(sat_prev, env_prev, 50.0, 0.70, 0.25)
    qkd_prev = bb84.evaluate(chan_prev, env_prev, 0.0, 0.0)

    for t in np.arange(0.0, duration_s + dt, dt):
        sat = orbit.propagate(t)

        # Baseline weather
        cloud = 0.05 + 0.10 * np.sin(0.02 * t) ** 2
        turb = 0.08 + 0.12 * np.sin(0.015 * t) ** 2
        vib = 0.010

        # Inject severe weather event between t=80s and t=130s
        if 80 <= t <= 130:
            cloud += 0.55 * np.sin(np.pi * (t - 80) / 50)
            turb += 0.40 * np.sin(np.pi * (t - 80) / 50)

        # Inject high mount vibration between t=160s and t=190s
        if 160 <= t <= 190:
            vib += 0.45

        # Inject simulated security anomaly (eavesdropping disturbance) between t=210s and t=240s
        anomaly_component = 0.0
        if 210 <= t <= 240:
            anomaly_component = 0.045  # 4.5% excess unexplained error

        env = EnvironmentData(
            timestamp=t,
            temperature=25.0,
            humidity=60.0,
            ambient_light=400.0,
            vibration=float(vib),
            cloud_factor=float(np.clip(cloud, 0.0, 0.95)),
            turbulence=float(np.clip(turb, 0.0, 0.90)),
            data_source="SIMULATION"
        )

        # Execute coordinator decision cycle
        coord_dec = coordinator.step(sat, env, chan_prev, qkd_prev)
        w_dec = coord_dec.weather_agent
        c_dec = coord_dec.communication_agent
        s_dec = coord_dec.security_agent
        act = coord_dec.final_action

        # Update environment & QKD
        chan = channel_model.calculate_link_state(
            sat, env,
            act.transmission_power_pct,
            act.photon_rate_norm,
            act.beam_divergence_norm
        )
        qkd = bb84.evaluate(chan, env, t, anomaly_component=anomaly_component)

        chan_prev = chan
        qkd_prev = qkd

        records.append({
            "timestamp_s": t,
            "elevation_deg": sat.elevation_deg,
            # Weather Agent
            "weather_severity": w_dec.severity,
            "weather_cloud_impact": w_dec.cloud_impact,
            "weather_turb_impact": w_dec.turbulence_impact,
            # Comm Agent
            "comm_link_viability": c_dec.link_viability,
            "comm_link_margin_db": c_dec.link_margin_db,
            "comm_target_power_pct": c_dec.target_power_pct,
            "comm_target_rate_norm": c_dec.target_photon_rate_norm,
            # Security Agent
            "security_classification": s_dec.classification,
            "security_anomaly_prob": s_dec.anomaly_probability,
            "security_primary_driver": s_dec.primary_error_driver,
            # Coordinator
            "conflict_detected": coord_dec.conflict_detected,
            "conflict_resolution": coord_dec.conflict_resolution_notes,
            "arbitrated_power_pct": act.transmission_power_pct,
            "arbitrated_rate_norm": act.photon_rate_norm,
            "arbitrated_divergence_norm": act.beam_divergence_norm,
            # Physical Link Performance
            "qber_pct": qkd.qber * 100.0,
            "skr_kbps": qkd.secret_key_rate / 1e3
        })

    df = pd.DataFrame(records)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_DIR / "agent_decisions_log.csv", index=False)
    print(f"  [SAVED CSV] {OUTPUT_DIR / 'agent_decisions_log.csv'}")

    summary = pd.DataFrame([{
        "Total Steps": len(df),
        "Total Conflicts Detected": int(df["conflict_detected"].sum()),
        "Conflict Rate (%)": round((df["conflict_detected"].sum() / len(df)) * 100.0, 1),
        "Weather Severe Steps": int((df["weather_severity"] == "SEVERE").sum()),
        "Security Anomalies Flagged": int((df["security_classification"] == "ANOMALY").sum()),
        "Comm Viability Optimal Steps": int((df["comm_link_viability"] == "OPTIMAL").sum()),
        "Mean Power Arbitrated (%)": round(df["arbitrated_power_pct"].mean(), 1),
    }])
    summary.to_csv(OUTPUT_DIR / "agent_coordination_summary.csv", index=False)
    print(f"  [SAVED CSV] {OUTPUT_DIR / 'agent_coordination_summary.csv'}")

    return df


def plot_agent_analysis_figures(df: pd.DataFrame):
    t = df["timestamp_s"]

    # 1. Multi-Agent Coordination Timeline
    fig1, axes = plt.subplots(4, 1, figsize=(12, 11), sharex=True)

    # Subplot 1: Weather Severity & Comm Margin
    ax1 = axes[0]
    severity_map = {"LOW": 1, "MODERATE": 2, "HIGH": 3, "SEVERE": 4}
    sev_values = df["weather_severity"].map(severity_map)
    ax1.plot(t, sev_values, color="#f59e0b", lw=2.2, label="Weather Severity Tier (1=Low, 4=Severe)")
    ax1.set_ylabel("Weather Severity", color="#f59e0b")
    ax1.set_yticks([1, 2, 3, 4])
    ax1.set_yticklabels(["LOW", "MOD", "HIGH", "SEVERE"])
    ax1.tick_params(axis="y", labelcolor="#f59e0b")
    ax1.set_title("SIMULATED ENVIRONMENT: Domain Agent Evaluations Across Time", fontsize=12, weight="bold")

    ax1_m = ax1.twinx()
    ax1_m.plot(t, df["comm_link_margin_db"], color="#0284c7", lw=1.8, linestyle="--", label="Comm Link Margin (dB)")
    ax1_m.set_ylabel("Link Margin (dB)", color="#0284c7")
    ax1_m.tick_params(axis="y", labelcolor="#0284c7")
    ax1.grid(True, alpha=0.3)

    # Subplot 2: Comm Agent Recommended Power vs Coordinator Arbitrated Power
    ax2 = axes[1]
    ax2.plot(t, df["comm_target_power_pct"], color="#64748b", lw=1.8, linestyle=":", label="Comm Agent Proposed Power (%)")
    ax2.plot(t, df["arbitrated_power_pct"], color="#059669", lw=2.4, label="Coordinator Arbitrated Power (%)")
    ax2.fill_between(t, df["comm_target_power_pct"], df["arbitrated_power_pct"], color="#f59e0b", alpha=0.2, label="Arbitration Delta")
    ax2.set_ylabel("Laser Power (%)")
    ax2.legend(loc="upper right", framealpha=0.9)
    ax2.grid(True, alpha=0.3)

    # Subplot 3: Security Anomaly Probability & Classification
    ax3 = axes[2]
    ax3.plot(t, df["security_anomaly_prob"] * 100.0, color="#dc2626", lw=2.2, label="Security Anomaly Confidence (%)")
    ax3.axhline(50.0, color="#991b1b", linestyle="--", lw=1.5, label="Detection Threshold (50%)")
    ax3.set_ylabel("Anomaly Prob (%)", color="#dc2626")
    ax3.set_ylim(-5, 105)
    ax3.legend(loc="upper right", framealpha=0.9)
    ax3.grid(True, alpha=0.3)

    # Subplot 4: Inter-Agent Conflicts & Resulting Key Rate
    ax4 = axes[3]
    conflict_steps = df[df["conflict_detected"]]
    ax4.scatter(conflict_steps["timestamp_s"], [1] * len(conflict_steps), color="#ef4444", marker="v", s=60, label="Agent Conflict Event", zorder=5)
    ax4.set_ylabel("Conflict Flag")
    ax4.set_yticks([0, 1])
    ax4.set_yticklabels(["Harmonious", "Conflict"])
    ax4.set_xlabel("Elapsed Time (seconds)")

    ax4_s = ax4.twinx()
    ax4_s.plot(t, df["skr_kbps"], color="#059669", lw=2.0, label="Net Secret Key Rate (kbps)")
    ax4_s.set_ylabel("SKR (kbps)", color="#059669")
    ax4.legend(loc="upper left", framealpha=0.9)
    ax4_s.legend(loc="upper right", framealpha=0.9)
    ax4.grid(True, alpha=0.3)

    save_figure(fig1, OUTPUT_DIR / "agent_recommendation_timeline.png")

    # 2. Conflict Classification & Frequency Breakdown
    fig2, (ax_bar, ax_noise) = create_figure(nrows=1, ncols=2, figsize=(13, 5))

    # Types of conflicts parsed from text
    resolutions = df["conflict_resolution"]
    c_comm_weather = sum("Comm vs Weather" in r for r in resolutions)
    c_security = sum("Security Alert" in r for r in resolutions)
    c_vibration = sum("vibration" in r.lower() for r in resolutions)
    c_nominal = sum("aligned" in r.lower() or "standby" in r.lower() for r in resolutions)

    conflict_labels = ["Comm vs Weather", "Security Alert", "Platform Vibration", "Harmonious"]
    conflict_counts = [c_comm_weather, c_security, c_vibration, c_nominal]
    conflict_colors = ["#f59e0b", "#ef4444", "#8b5cf6", "#10b981"]

    bars = ax_bar.bar(conflict_labels, conflict_counts, color=conflict_colors, edgecolor="black", lw=1.2, width=0.55)
    ax_bar.set_title("Distribution of Inter-Agent Decision Events", fontsize=11, weight="bold")
    ax_bar.set_ylabel("Duration / Timesteps")
    ax_bar.tick_params(axis="x", rotation=15)
    for b in bars:
        h = b.get_height()
        ax_bar.annotate(f"{h}", xy=(b.get_x() + b.get_width() / 2, h), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", weight="bold")
    ax_bar.grid(axis="y", alpha=0.3)

    # Primary noise attribution by security agent
    driver_counts = df["security_primary_driver"].value_counts()
    wedges, texts, autotexts = ax_noise.pie(
        driver_counts.values,
        labels=driver_counts.index,
        autopct="%1.1f%%",
        startangle=140,
        colors=["#0284c7", "#f59e0b", "#10b981", "#8b5cf6", "#ef4444"],
        wedgeprops={"edgecolor": "black", "linewidth": 1.0}
    )
    for at in autotexts:
        at.set_fontweight("bold")
    ax_noise.set_title("Security Agent: Primary Physical Noise Attribution", fontsize=11, weight="bold")

    fig2.suptitle("SIMULATED ENVIRONMENT: Hierarchical Multi-Agent Arbitration Profile", fontsize=13, weight="bold", y=1.02)
    save_figure(fig2, OUTPUT_DIR / "conflict_frequency_distribution.png")


if __name__ == "__main__":
    df = run_agent_analysis_experiment(duration_s=300, seed=42)
    plot_agent_analysis_figures(df)
    print("  [SUCCESS] Experiment 13 execution completed.")
