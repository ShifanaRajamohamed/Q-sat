# Q-SAT Adaptive Ground Station — Installation & Research Guide

> **Software-Only Satellite-to-Ground QKD Digital Twin and Controller Evaluation Platform**  
> Ground Station: **Tiruchirappalli reference ground station** [10.7905° N, 78.7047° E, 88.0 m MSL]  
> Target: LEO Satellite (500 km altitude, 850 nm optical downlink, BB84 protocol)

---

## 1. System Overview

Q-SAT is an open research and simulation platform for evaluating adaptive quantum optical link controllers:
- **FastAPI Backend (Port 8000)**: Serves REST API, WebSocket live telemetry stream (`/ws/live`), and hosts the digital twin physics, QKD distillation engine, and AI controllers.
- **Angular 22 Dashboard**: High-tech aerospace operations console with real-time polar sky-dome radar, 2D ground track, live link budget, error decomposition, historical weather replay controls, and CSV/JSON telemetry export.
- **Controllers Supported**:
  1. `STATIC`: Fixed transmitter baseline (50% power, 70 MHz repetition rate, 25 µrad divergence).
  2. `RULE_BASED`: Closed-loop threshold heuristic controller.
  3. `PPO`: Stable-Baselines3 continuous Proximal Policy Optimization neural network with validated archive loading and strict evaluation mode.
  4. `MULTI_AGENT`: Hierarchical domain-expert rule-arbitrated controller (Weather, Comm, Security agents with coordinator arbitration; explicitly NOT MARL).

---

## 2. Prerequisites & Installation

### Requirements
- **Python**: 3.12 (with PyTorch, Stable-Baselines3, Skyfield, SGP4, FastAPI, Uvicorn, Pandas, Gymnasium).
- **Node.js**: v20+ or v22 LTS with npm.
- **Physical Hardware**: None required (all features run software-only).

### Step 1: Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Build Angular Dashboard
```bash
cd frontend/qsat-dashboard
npm install --ignore-engines
npm run build
cd ../..
```
The compiled production bundle is generated at `frontend/qsat-dashboard/dist/qsat-dashboard` and served directly by the FastAPI backend at `http://localhost:8000/dashboard/`.

---

## 3. How to Run the Application

### Starting the Backend Server
Run the FastAPI application from the project root:
```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
- **Mission Control Dashboard**: `http://localhost:8000/dashboard/`
- **Interactive Swagger API Docs**: `http://localhost:8000/docs`
- **WebSocket Telemetry Stream**: `ws://localhost:8000/ws/live`

### Running Angular in Live Dev Mode (Optional)
If modifying dashboard UI components:
```bash
cd frontend/qsat-dashboard
npm start
```
Accessible at `http://localhost:4200/`.

---

## 4. PPO Model Validation & Loading

### Audit and Repair
The pre-trained model `models/ppo_qsat.zip` was audited. The original nested archive was backed up to:
`models/ppo_qsat_original_nested.zip`

To validate or repair the model archive at any time:
```bash
python -m ai.model_validator
```
This utility inspects the archive structure, validates root-level files (`data`, `policy.pth`, `_stable_baselines3_version`), tests TensorFlow/Keras environment sanitization on Windows, and runs a dummy 15-dim observation inference test.

### Model Loading & Strict Evaluation Mode
- **Contract**: `PPOController(evaluation_mode=True)` fails explicitly if the neural weights cannot load or predict. It will **never** silently fall back to Rule-Based and report it as a PPO benchmark.
- **Non-Evaluation Mode**: On fallback, it explicitly populates:
  - `requested_controller`: `"PPO"`
  - `actual_controller`: `"RULE_BASED"`
  - `model_loaded`: `False`
  - `fallback_reason`: Exact exception reason.

---

## 5. Historical Weather Integration & Replay

### Meteorological Data Architecture
The platform features a `HistoricalWeatherProvider` adhering to the `EnvironmentProvider` interface:
- **Station**: Tiruchirappalli reference ground station (`10.7905° N, 78.7047° E`).
- **Separation of Cloud Cover & Cloud Factor**:
  - Meteorological cloud cover ($0-100\%$) is preserved as a physical observation/reanalysis quantity.
  - Optical `cloud_factor` ($[0, 1]$) is separately calculated via non-linear optical extinction modeling ($f(\text{cloud\_cover}^{1.25})$).
- **Configured Assumptions**:
  - Atmospheric turbulence ($0.12$) and mount vibration ($0.015\text{ g}$) are explicitly flagged as configured research assumptions, not measured telemetry.
- **Interpolation**: Supports both `"LINEAR"` and `"HOLD"` modes with explicit labeling.

### Included Synthetic Fixture
Located at: `simulation/historical_weather/tiruchirappalli_2024_03_synthetic_fixture.csv`
- Contains 744 hourly timestamped records for March 2024 (2024-03-01 to 2024-03-31).
- Accompanied by metadata file `tiruchirappalli_2024_03_synthetic_fixture.meta.json`.
- Clearly documented: **Synthetic test fixture for research validation; not fabricated real measurements.**

### Importing Real ERA5 Weather via Open-Meteo API
To fetch real reanalysis weather data from the documented Open-Meteo Archive API (free, open-access, ERA5 reanalysis):
```bash
python simulation/historical_weather/fetch_open_meteo.py --start 2024-03-01 --end 2024-03-07 --output simulation/historical_weather/tiruchirappalli_era5_march2024.csv
```
If network access is unavailable, the script reports the limitation gracefully and exits without corrupting existing files.

### Running a Deterministic Multi-Controller Benchmark
To evaluate all 4 controllers against identical historical weather and satellite pass geometry:
```bash
python experiments/historical_replay_benchmark.py --csv simulation/historical_weather/tiruchirappalli_2024_03_synthetic_fixture.csv --start 2024-03-01T15:00:00Z --duration 120
```
Outputs:
- `results/experiments/historical_replay/historical_benchmark_timeseries.csv`: Per-step timeseries with decision latency, action variation, and integrated metrics.
- `results/experiments/historical_replay/historical_benchmark_summary.csv`: Summary leaderboard with Secret Key (kbits), Mean QBER (%), Energy (Joules), and Uptime.
- `results/experiments/historical_replay/historical_benchmark_metadata.json`: Exact seed, code revision, and configuration metadata.

---

## 6. SGP4 & Skyfield Orbital Tracking

### Providers
1. **Reference Pass Mode (`reference_pass`)**: Analytical topocentric pass model for controlled repeatable benchmarks.
2. **SGP4 TLE Mode (`tle_prediction`)**: High-fidelity SGP4 orbital propagator powered by Skyfield.

### Documented Reference Satellites
- **MICIUS (QUESS, NORAD 41738)**: Quantum Experiments at Space Scale (~500 km Sun-synchronous orbit, 97.4° inclination).
- **ISS (ZARYA, NORAD 25544)**: International Space Station (~420 km LEO, 51.6° inclination).

### Scientific Guardrails
- Propagated positions are strictly flagged as **`[ORBITAL PREDICTION]`**, not direct satellite telemetry.
- An **epoch age warning** is automatically triggered if propagation time is $>14\text{ days}$ from the TLE epoch:
  > *"SGP4 propagation is X days from TLE epoch. SGP4 propagation accuracy degrades significantly outside ±14 days. Do not treat as accurate historical tracking without contemporaneous orbital elements."*
- Optical and QKD transmitter payload parameters are explicitly marked as configured research assumptions (`is_payload_verified = False`).

---

## 7. Multi-Agent Controller & Ablation Suite

### System Architecture
The Multi-Agent Controller is a **hierarchical domain-expert rule-arbitrated system** (explicitly NOT Multi-Agent Reinforcement Learning):
- **Weather Agent**: Analyzes atmospheric severity and solar background.
- **Communication Agent**: Optimizes SNR link margin, repetition rate, and transmitter power.
- **Security Agent**: Evaluates QBER decomposition against the physical noise budget.
  - Outputs are strictly labeled as **modeled anomaly assessments**, not confirmed physical eavesdropping.
- **Coordinator Agent**: Arbitrates inter-agent conflicts and enforces physical rate-of-change limits.

### Running the Ablation Study
To evaluate the contribution of individual agents against ablated baselines:
```bash
python experiments/exp16_ablation.py
```
Outputs standardized comparison metrics to:
`results/experiments/ablation/ablation_study_summary.csv`

---

## 8. Running the Complete Automated Test Suite

To run all 33 unit and integration tests:
```bash
python -m pytest tests/test_bb84_qkd.py tests/test_optical_channel.py tests/test_rule_based_controller.py tests/test_gym_environment.py tests/test_historical_weather.py tests/test_ppo_validation.py tests/test_orbital_tracking.py tests/test_multi_agent.py -v
```
**Results: 33 passed in ~13 seconds.**

---

## 9. Feature Implementation Status Matrix

| Subsystem / Feature | Implementation Status | Test Status | Data Provenance / Assumptions | Known Limitations / Notes |
|---|---|---|---|---|
| **PPO Model Loading** | **Implemented** | **Tested** (`test_ppo_validation.py`) | Restructured root archive `models/ppo_qsat.zip`; original preserved in `models/ppo_qsat_original_nested.zip` | Evaluates in strict mode; fails explicitly without silent fallback. |
| **Shared Spaces & Delta Actions** | **Implemented** | **Tested** (`ai/spaces.py`) | 15-dim normalized observation vector $[0, 1]$; continuous action deltas $[-0.20, +0.20]$ | Shared between training environment and inference controller. |
| **Physical Units & Energy Conversion** | **Implemented** | **Tested** (`test_optical_channel.py`) | Receiver aperture $1.0\text{ m}$, Wavelength $850\text{ nm}$, Max power $50\text{ mW}$, Wall-plug efficiency $15\%$ | Energy reported in Joules ($P_{\text{elec}} \times dt$); proxy explicitly separated. |
| **Ground Station Designation** | **Implemented** | **Verified** | Tiruchirappalli reference ground station (`10.7905° N, 78.7047° E`, $88.0\text{ m}$ MSL) | Neutral naming; no institutional affiliation implied. |
| **Historical Weather Provider** | **Implemented** | **Tested** (`test_historical_weather.py`) | CSV provider supporting LINEAR and HOLD interpolation; March 2024 synthetic fixture included | Real weather fetch script `fetch_open_meteo.py` documented; network required for live fetching. |
| **Cloud Factor vs Cloud Cover** | **Implemented** | **Tested** (`test_historical_weather.py`) | Meteorological cloud cover ($0-100\%$) strictly decoupled from optical `cloud_factor` ($0-1$) | Optical factor derived via non-linear empirical extinction model. |
| **Turbulence & Vibration Inputs** | **Implemented** | **Tested** (`test_historical_weather.py`) | Clearly labeled as `[CONFIGURED_ASSUMPTION]` ($0.12$ index, $0.015\text{ g}$) | Not claimed as physical field measurements. |
| **SGP4 & Skyfield Orbital Tracking** | **Implemented** | **Tested** (`test_orbital_tracking.py`) | Offline Skyfield timescale; documented MICIUS and ISS reference TLEs | Flagged as `[ORBITAL PREDICTION]`; epoch warning when $|age| > 14\text{ days}$. |
| **Deterministic Multi-Controller Benchmarks** | **Implemented** | **Tested** (`historical_replay_benchmark.py`) | Identical pass and weather sequence across STATIC, RULE_BASED, PPO, and MULTI_AGENT | Verifies integrated timeseries matches aggregate totals. |
| **Multi-Agent Explainability & Ablation** | **Implemented** | **Tested** (`test_multi_agent.py`, `exp16_ablation.py`) | Rule-arbitrated domain agents; security outputs labeled as modeled anomaly assessments | Explicitly labeled as heuristic multi-agent, not MARL. |
| **Angular Mission Dashboard** | **Implemented** | **Tested** (`npm run build` passing) | Angular 22 standalone components; high-tech dark/light theme; ECharts telemetry graphs | Includes Historical Replay controls, PPO status badge, CSV/JSON export. |
