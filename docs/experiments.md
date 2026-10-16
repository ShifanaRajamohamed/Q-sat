# Experimental Benchmarking & Scientific Validation Suite

This document presents the complete specification, methodology, mathematical formulations, and empirical findings for the **20 Experimental Benchmarks** developed for the **Q-SAT Adaptive Ground Station** project.

> **DATA PROVENANCE NOTICE**: All datasets, tables, and graphs originate strictly from the **SIMULATED ENVIRONMENT** digital twin engine. No physical hardware was connected during these benchmark runs. Every metric is computed dynamically from empirical runs without fabrication.

---

## 1. Experimental Suite Overview

The experimental suite is organized under `experiments/` with outputs stored under `results/experiments/<experiment_name>/` and consolidated in `results/final_results.csv` and `results/final_summary.md`.

```
results/
├── final_results.csv                         # Consolidated comparison table
├── final_summary.md                          # Comprehensive publication report
└── experiments/
    ├── baseline/                             # Exp 1: Baseline pass profile
    ├── turbulence/                           # Exp 2: Cn2 turbulence sweep
    ├── elevation/                            # Exp 3: Orbital elevation geometry
    ├── distance/                             # Exp 4: Slant range path loss
    ├── qber/                                 # Exp 5: Security threshold cutoff
    ├── power/                                # Exp 6: Laser power vs energy
    ├── weather/                              # Exp 7: Standardized weather regimes
    ├── dynamic_weather/                      # Exp 8: Dynamic weather transition
    ├── static_vs_ppo/                        # Exp 9: Static vs PPO head-to-head
    ├── final_comparison/                     # Exp 10: Multi-controller comparison
    ├── ppo_training/                         # Exp 11: PPO training & convergence
    ├── ai_adaptation/                        # Exp 12: Real-time actuator adaptation
    ├── agent_analysis/                       # Exp 13: Hierarchical agent decisions
    ├── digital_twin/                         # Exp 14: Digital twin state tracking
    ├── security/                             # Exp 15: Security anomaly attribution
    ├── ablation/                             # Exp 16: Multi-agent ablation study
    ├── statistics/                           # Exp 17: Multi-seed statistical runs
    └── final_table/                          # Exp 18: Consolidated master radar
```

---

## 2. Catalog of All 20 Experiments

### Exp 1: Baseline QKD Performance Profile (`exp01_baseline.py`)
- **Objective**: Establish nominal single-pass performance for a LEO satellite pass (500 km, 97.4° inclination) over the Trichy Optical Ground Station.
- **Metrics**: Time-series of Secret Key Rate (SKR), Quantum Bit Error Rate (QBER), Channel Path Loss, and Detection Rates.
- **Key Result**: Mean SKR $0.397\text{ kbps}$, Peak $0.643\text{ kbps}$, Mean QBER $3.85\%$, Uptime $100\%$.

### Exp 2: Atmospheric Turbulence ($C_n^2$) Sweep (`exp02_turbulence.py`)
- **Objective**: Parametric sweep of refractive index structure parameter $C_n^2$ from weak ($10^{-16}\ \text{m}^{-2/3}$) to severe ($2\times 10^{-13}\ \text{m}^{-2/3}$) scintillation.
- **Model**: Rytov approximation variance $\sigma_R^2 = 1.23 C_n^2 k^{7/6} L^{11/6}$.
- **Key Result**: Total channel loss degrades from $32.96\text{ dB}$ to $34.60\text{ dB}$, decreasing SKR from $0.373\text{ kbps}$ to $0.183\text{ kbps}$.

### Exp 3: Orbital Elevation Geometry Sweep (`exp03_elevation.py`)
- **Objective**: Topocentric elevation angle sweep from $10^\circ$ (horizon threshold) to $90^\circ$ (zenith).
- **Model**: Airmass $X(\theta) \approx 1/\sin(\theta)$, free-space path loss (FSPL).
- **Key Result**: At $10^\circ$, range is $1695\text{ km}$ and QBER is $33.4\%$ (link aborted). At zenith ($90^\circ$, range $500\text{ km}$), loss drops to $30.22\text{ dB}$, yielding SKR of $0.839\text{ kbps}$ and QBER of $2.54\%$.

### Exp 4: Slant Range Path Loss Sweep (`exp04_distance.py`)
- **Objective**: Controlled geometric distance sweep from $500\text{ km}$ to $1800\text{ km}$.
- **Model**: Free-space geometric spreading $\text{FSPL} = 20\log_{10}(4\pi d / \lambda)$.
- **Key Result**: Single-photon link remains distillable up to $\approx 1050\text{ km}$; beyond $1100\text{ km}$, detector dark count noise dominates, causing QBER to exceed the $11.0\%$ threshold.

### Exp 5: QBER Threshold & Security Cutoff (`exp05_qber.py`)
- **Objective**: Empirical validation of the asymptotic BB84 security boundary:
  $$R_{\text{secret}} = R_{\text{sifted}} \left[ 1 - f(e) h_2(e) - h_2(e) \right]$$
  where $f(e) = 1.16$ is the error correction inefficiency and $h_2(e)$ is binary Shannon entropy.
- **Key Result**: Sharp cutoff observed precisely at $e = 11.0\%$, where information leakage to an eavesdropper matches mutual information between Alice and Bob.

### Exp 6: Transmission Power & Wall-Plug Tradeoff (`exp06_power.py`)
- **Objective**: Sweeps laser transmitter power from $10\%$ ($5\text{ mW}$) to $100\%$ ($50\text{ mW}$) with electrical consumption model $P_{\text{elec}} = P_{\text{opt}} / 0.15$.
- **Key Result**: Demonstrates diminishing returns; doubling power increases SKR modestly while doubling electrical and thermal dissipation.

### Exp 7: Standardized Weather Regimes (`exp07_weather.py`)
- **Objective**: Benchmarks link viability across CLEAR SKY, MODERATE HAZE, and SEVERE CLOUD regimes.
- **Key Result**: CLEAR delivers $0.438\text{ kbps}$ (100% uptime); MODERATE delivers $0.016\text{ kbps}$ (55% uptime); SEVERE undergoes total extinction ($53.6\text{ dB}$ loss, 0% uptime).

### Exp 8: Dynamic Weather Transition Across Pass (`exp08_dynamic_weather.py`)
- **Objective**: Continuous pass simulation undergoing atmospheric regime transitions:
  `CLEAR (0-60s) -> HAZE (60-110s) -> SEVERE STORM (110-190s) -> RECOVERY (190-250s) -> CLEAR (250-300s)`.
- **Key Result**: Demonstrates channel loss spikes from $32\text{ dB}$ to $48\text{ dB}$ during storm intrusion, with QBER temporarily exceeding threshold before recovering.

### Exp 9: Static Baseline vs PPO Controller (`exp09_static_vs_ppo.py`)
- **Objective**: Direct head-to-head evaluation under identical atmospheric seeds.
- **Key Result**: Static delivers $10.05\text{ kbits}$ using $50.17\text{ J}$ ($0.200\text{ kb/J}$); PPO prioritizes energy conservation ($11.65\text{ J}$) but shuts down transmission during marginal elevation angles.

### Exp 10: Multi-Controller Comparative Analysis (`exp10_final_comparison.py`)
- **Objective**: Side-by-side benchmark of STATIC, RULE_BASED, PPO, and MULTI_AGENT under identical realistic disturbance profiles.
- **Key Result**: MULTI_AGENT delivers $85.47\text{ kbits}$ (vs Static's $18.32\text{ kbits}$, $+366\%$), suppresses mean QBER to $4.76\%$, and expands uptime to $84.1\%$.

### Exp 11: PPO Training Convergence Curve (`exp11_ppo_training.py`)
- **Objective**: Evaluates 12,000-timestep CPU training run of continuous PPO with custom metric logging callbacks.
- **Key Result**: Tracks episodic return, moving average reward, and multi-objective breakdown (SKR reward vs QBER penalty vs energy penalty).

### Exp 12: Real-Time AI Actuator Adaptation (`exp12_ai_adaptation.py`)
- **Objective**: Traces continuous adjustments of Laser Power (%), Repetition Rate (norm), and Beam Divergence (norm) in response to localized cloud plumes and platform vibration spikes.
- **Key Result**: Divergence automatically broadens during vibration spikes ($0.20 \to 0.42$) to prevent beam wander clipping.

### Exp 13: Hierarchical Agent Decision Analysis (`exp13_agent_analysis.py`)
- **Objective**: Audits individual recommendations from Weather, Comm, and Security agents and logs Coordinator arbitration events.
- **Key Result**: Categorizes conflict frequencies: Comm vs Weather (power throttling during extinction), Security Alerts (rate reduction during anomaly), and Mount Vibration compensation.

### Exp 14: Digital Twin State Tracking & Physics (`exp14_digital_twin.py`)
- **Objective**: End-to-end digital twin orchestration synchronizing orbital mechanics, Ornstein-Uhlenbeck stochastic environmental telemetry, and optical link budgets.
- **Key Result**: Produces stacked optical loss decomposition (FSPL, Atmospheric, Pointing, Scintillation).

### Exp 15: Security Anomaly Detection & QBER Attribution (`exp15_security.py`)
- **Objective**: Evaluates multi-factor attribution discriminating between benign atmospheric storms and malicious eavesdropping attacks.
- **Key Result**: Anomaly probability remains low ($<15\%$) during severe storms because error is physically explained, but spikes to $85\%+$ during unexplained intercept-resend attacks.

### Exp 16: Multi-Agent Architecture Ablation Study (`exp16_ablation.py`)
- **Objective**: Systematically disables individual agents (`w/o Weather`, `w/o Security`, `w/o Comm`, `Static Baseline`).
- **Key Result**: Full Multi-Agent delivers $96.05\text{ kbits}$ ($1.166\text{ kb/J}$); removing the Security agent causes blind over-transmission of compromised keys during attacks; removing the Comm agent cuts yield to $41.74\text{ kbits}$.

### Exp 17: Statistical Validation Across Multi-Seed Runs (`exp17_statistics.py`)
- **Objective**: 10 independent Monte Carlo seeds per controller to establish variance and 95% confidence intervals.
- **Key Result**: MULTI_AGENT delivers $54.2 \pm 1.5\text{ kbits}$ ($0.797\text{ kb/J}$, $74.5\%$ uptime) vs Static's $10.7 \pm 0.6\text{ kbits}$ ($0.266\text{ kb/J}$, $46.6\%$ uptime), proving statistical significance.

### Exp 18: Consolidated Master Results Table & Radar (`exp18_final_table.py`)
- **Objective**: Synthesizes all empirical outputs into `results/final_results.csv` and multi-dimensional radar/spider benchmark figures.
- **Key Result**: Generates `master_comparison_spider.png` and `master_leaderboard_bar.png`.

### Exp 19: Master Experiment Runner (`run_all.py`)
- **Objective**: Automated CLI pipeline executing all 18 experiments sequentially, validating exit codes, tracking elapsed times, and triggering report generation.

### Exp 20: Comprehensive Automated Report Generator (`generate_report.py`)
- **Objective**: Synthesizes all CSV outputs into a publication-ready Markdown research report at `results/final_summary.md` with zero fabrication.

---

## 3. How to Execute Experiments

### Running the Entire Suite
```powershell
.\.venv\Scripts\python.exe experiments/run_all.py
```

### Running with Training Skipped (Fast Execution)
```powershell
.\.venv\Scripts\python.exe experiments/run_all.py --skip-training
```

### Running Specific Experiments
```powershell
.\.venv\Scripts\python.exe experiments/exp01_baseline.py
.\.venv\Scripts\python.exe experiments/exp10_final_comparison.py
.\.venv\Scripts\python.exe experiments/exp17_statistics.py
```

### Regenerating the Summary Report
```powershell
.\.venv\Scripts\python.exe experiments/generate_report.py
```

---

## 4. Interactive Demonstration via Web Dashboard

1. Navigate to `http://127.0.0.1:8000/dashboard/`.
2. Click the **"⚡ RUN FULL DEMO"** button in the top navigation bar.
3. The platform executes a dynamic 120-second multi-controller benchmark run across all four paradigms in real time.
4. Click **"📊 Results (20 Exp)"** to open the research results modal and inspect the master leaderboard, Monte Carlo statistics, and high-resolution publication figures.
