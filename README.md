# Q-SAT Adaptive Ground Station

> **An Intelligent Hardware-in-the-Loop Digital Twin and Adaptive AI Framework for Satellite-to-Ground Quantum Communication**

[![Python 3.12](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![Angular 22](https://img.shields.io/badge/Angular-22+-red.svg)](https://angular.dev/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.14+-orange.svg)](https://pytorch.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

---

## 🧠 AI Image / Diagram Generation Prompt — Proposed System Architecture

> **Use this prompt verbatim in any AI image generator (DALL·E 3, Midjourney, Adobe Firefly, Stable Diffusion) or diagram tool (Eraser.io, Napkin.ai, ChatGPT Canvas) to produce a publication-quality proposed system diagram for this project.**

---

```
Generate a clean, professional, publication-quality system architecture diagram 
for a capstone engineering project titled:

"Q-SAT: An Intelligent Hardware-in-the-Loop Digital Twin and Adaptive AI Framework 
for Satellite-to-Ground Quantum Key Distribution (QKD)"

The diagram must show the following six clearly labeled architectural layers, 
arranged vertically top-to-bottom with directional arrows between them:

─────────────────────────────────────────────────────────────────────────
LAYER 1 — PHYSICAL / HARDWARE LAYER (top)
─────────────────────────────────────────────────────────────────────────
Show a LEO satellite (labelled "Alice — LEO Satellite, 500 km altitude") 
on the left transmitting a laser beam downward toward Earth.

On the right, show an ESP32 microcontroller board connected to three sensors:
  • DHT22 (Temperature & Humidity sensor, GPIO 4)
  • GL5528 LDR Photoresistor (Ambient Light / Lux sensor, GPIO 34)
  • MPU6050 IMU (Mount Vibration / Jitter sensor, I2C GPIO 21/22)

The ESP32 sends JSON telemetry packets over WiFi to an MQTT Broker 
(Eclipse Mosquitto, port 1883). Label this arrow "MQTT / WiFi / JSON".

─────────────────────────────────────────────────────────────────────────
LAYER 2 — ENVIRONMENT ABSTRACTION LAYER
─────────────────────────────────────────────────────────────────────────
Show an abstract interface box labelled "EnvironmentProvider (Abstract Interface)"
with two concrete implementations branching from it:
  • Left box: "SimulationEnvironmentProvider" — Ornstein-Uhlenbeck SDE 
    (stochastic simulation of temperature, humidity, ambient light, vibration)
  • Right box: "MQTTEnvironmentProvider" — Live ESP32 hardware telemetry 
    with 3-second heartbeat watchdog and automatic fallback to simulation

─────────────────────────────────────────────────────────────────────────
LAYER 3 — DIGITAL TWIN & OPTICAL CHANNEL LAYER
─────────────────────────────────────────────────────────────────────────
Show three connected sub-modules:
  • "Orbital & Kinematic Model": Keplerian LEO orbit, Topocentric elevation/
    azimuth, Slant range 500–1500 km, Rozenberg airmass m(θ)
  • "Atmospheric Channel Model": Beer-Lambert extinction, Cloud Optical Depth 
    (COD) attenuation, Rytov scintillation variance σ²_R (Kolmogorov turbulence)
  • "Optical Link Budget": Gaussian beam divergence, Receiver aperture D=0.30m, 
    Pointing jitter loss η_jitter, Spectral bandpass stray-photon filtering

─────────────────────────────────────────────────────────────────────────
LAYER 4 — BB84 QKD ENGINE LAYER
─────────────────────────────────────────────────────────────────────────
Show three sequential processing blocks:
  • "QBER Decomposition Engine": 
    e_total = e_base + e_atm + e_stray + e_vibe + e_dark + Δe_anomaly
    (six isolated root-cause error components)
  • "Key Rate Calculator":
    Raw Key Rate → Sifted Key Rate (50% basis reconciliation)
  • "Asymptotic Secret Key Rate (SKR)":
    R_SKR = max(0, R_sift × [1 - f(e)·h₂(e) - h₂(e)])
    with hard security cutoff at QBER ≥ 11.0% (BB84 threshold)

─────────────────────────────────────────────────────────────────────────
LAYER 5 — AI & ADAPTIVE CONTROL LAYER
─────────────────────────────────────────────────────────────────────────
Show a hierarchical multi-agent system with two tiers:

Tier 1 — Three Domain Agents (side by side):
  • Weather Agent: Evaluates cloud factor, turbulence, humidity, ambient light. 
    Outputs: severity level (LOW/MODERATE/HIGH/SEVERE), power boost recommendation
  • Communication Agent: Evaluates elevation angle, slant range, link margin (dB), 
    SNR. Outputs: target laser power %, target photon rate
  • Security Agent: Performs QBER root-cause attribution. Classifies as 
    NORMAL / DEGRADED / ANOMALY. Distinguishes physical noise from eavesdropping.

Tier 2 — Coordinator Agent (above all three, receiving inputs from all):
  Arbitrates conflicts, applies rate-of-change clamping (±20%/step), 
  outputs final ControlAction (Laser Power %, Photon Rate, Beam Divergence)

Also show two alternative controllers in a side box:
  • PPO Controller: Stable-Baselines3 Actor-Critic, 15-dim observation, 
    3-dim continuous action space, trained via Proximal Policy Optimization
  • Rule-Based Controller: Expert heuristic with 5 condition rules
  • Static Controller: Fixed open-loop baseline

─────────────────────────────────────────────────────────────────────────
LAYER 6 — BACKEND & MISSION CONTROL DASHBOARD (bottom)
─────────────────────────────────────────────────────────────────────────
Show:
  • FastAPI REST + WebSocket Gateway (Python, port 8000)
    9 API route groups: /api/system, /api/environment, /api/simulation, 
    /api/satellite, /api/qkd, /api/control, /api/ai, /api/alerts, /api/experiments
  • WebSocket streamer broadcasting full telemetry JSON every 800ms → /ws/live
  • Angular 22 + TypeScript Mission Control Dashboard (port 4200):
    - Real-time ECharts line graphs: SKR (kbps), QBER (%), Channel Loss (dB)
    - 2D Polar Sky-Dome Radar Canvas (satellite azimuth/elevation tracking)
    - Live controller mode switcher (STATIC / RULE_BASED / PPO / MULTI_AGENT)
    - Scenario switcher (Clear Sky / Haze / Clouds / Night / Storm / Dynamic)
    - Anomaly injection panel (simulates eavesdropping Δe)
    - Experiment results panel (18 benchmark experiments, radar/spider charts)

─────────────────────────────────────────────────────────────────────────
GROUND STATION REFERENCE
─────────────────────────────────────────────────────────────────────────
Label the ground station receiver as:
"OGS — Bob (Optical Ground Station)"
Location: Tiruchirappalli, Tamil Nadu, India
Coordinates: 10.7905°N, 78.7047°E, 80m altitude
Telescope aperture: D_rx = 0.30 m
Detector: Single-Photon Avalanche Diode (SPAD), η_det = 10%

─────────────────────────────────────────────────────────────────────────
DIAGRAM STYLE REQUIREMENTS:
─────────────────────────────────────────────────────────────────────────
• Style: Clean, dark-themed (dark navy/charcoal background), 
  neon-accent color-coded layers (each layer a different accent color)
• Font: Modern sans-serif, all labels clearly readable
• Arrows: Directional with labels describing data type 
  (e.g., "Actuator Setpoints", "QBER + SKR Metrics", "Telemetry JSON")
• Include a legend showing layer color codes
• Resolution: Suitable for A3 or poster-size printing (300 DPI)
• Aspect ratio: 16:9 landscape or A3 portrait
• Include the project title at the top: 
  "Q-SAT Adaptive Ground Station — Proposed System Architecture"
• Include a subtitle: 
  "Intelligent Hardware-in-the-Loop Digital Twin for Satellite Quantum Communication"
```

---

## 1. Executive Summary

**Q-SAT** is an end-to-end research simulation, digital twin, and adaptive control platform modeling a Low Earth Orbit (LEO) satellite transmitting polarized single-photon pulses to an Optical Ground Station (OGS) using an analytical **BB84 Quantum Key Distribution (QKD)** protocol.

The system features:
1. **LEO Orbital Mechanics & Topocentric Geometry**: Accurate Keplerian dynamics, topocentric elevation/azimuth propagation, slant range ($500 - 1500\text{ km}$), and Rozenberg relative airmass modeling for OGS Tiruchirappalli ($10.7905^\circ\text{ N}, 78.7047^\circ\text{ E}, 80\text{ m}$).
2. **Optical Atmospheric Channel**: Beer-Lambert extinction, Cloud Optical Depth (COD) attenuation, Rytov scintillation index for Kolmogorov turbulence, Gaussian beam divergence, and receiver mount pointing jitter.
3. **BB84-Inspired Analytical QKD Engine**:
   - Asymptotic Secret Key Rate (SKR) derived from Shannon entropy: $R_{\text{SKR}} = \max(0, R_{\text{sift}}[1 - f(e)h_2(e) - h_2(e)])$.
   - Strict $11.0\%$ theoretical BB84 cutoff threshold.
   - Root-cause additive QBER decomposition: $e_{\text{total}} = e_{\text{base}} + e_{\text{atm}} + e_{\text{stray}} + e_{\text{vibe}} + e_{\text{dark}} + \Delta e_{\text{anomaly}}$.
4. **Adaptive Controllers**:
   - `STATIC`: Fixed legacy baseline.
   - `RULE_BASED`: Expert heuristics with rate-of-change limiting.
   - `PPO`: Continuous 15-dimensional state Actor-Critic neural network.
   - `MULTI_AGENT`: Hierarchical Multi-Agent system (Weather, Comm, Security, Coordinator) featuring root-cause anomaly attribution.
5. **Hardware-in-the-Loop (HIL) Abstraction**: Decoupled `EnvironmentProvider` supporting both Ornstein-Uhlenbeck stochastic differential equations and physical ESP32 environmental telemetry (DHT22, LDR, MPU6050) over MQTT.
6. **Real-Time Mission Control Dashboard**: Built with **Angular 22**, **TypeScript**, and **ECharts**, streaming real-time telemetry over WebSocket at 800 ms intervals with a 2D polar sky dome radar canvas.

---

## 2. Technical Boundaries & Research Integrity

- **Mathematical Digital Twin**: This project is a mathematical digital twin and algorithmic simulation platform. It does **not** claim physical quantum optics implementation or experimental proof of physical device security.
- **Diagnostic Explainability**: High QBER is **never** unconditionally flagged as a quantum cyberattack. The Security Agent evaluates real-time optical, atmospheric, and mechanical telemetry before classifying an anomaly.
- **Data Provenance**: All telemetry and UI elements are clearly tagged as `[SIMULATION]`, `[HARDWARE]`, `[ASSUMPTION]`, or `[AI OUTPUT]`.

---

## 3. System Architecture

```
                    ┌─────────────────────────┐
                    │    Environment Layer    │
                    │  SimulationProvider OR  │
                    │   ESP32 MQTT Provider   │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │  Digital Twin Modeling  │
                    │  - LEO Satellite Motion │
                    │  - Ground Geometry      │
                    │  - Atmospheric Channel  │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │   BB84 Analytical QKD   │
                    │  - QBER Decomposition   │
                    │  - Sifted & Secret Key  │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │  Hierarchical AI / PPO  │
                    │  - Weather Agent        │
                    │  - Communication Agent  │
                    │  - Security Agent       │
                    │  - Coordinator          │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │ Ground Station Control  │
                    │ - Laser Power (5-50 mW) │
                    │ - Rate (10-100 MHz)     │
                    │ - Divergence (5-50 urad)│
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │ Real-time Web Dashboard │
                    │ (Angular 22 + ECharts)  │
                    └─────────────────────────┘
```

---

## 4. Quick Start & Execution Guide

### Prerequisites
- **Python 3.12+**
- **Node.js 20+** and **npm**

### Step 1: Backend Setup
```powershell
# Navigate to repository root
cd d:\capstone-project\Q-SAT

# Activate Python Virtual Environment
.\.venv\Scripts\Activate.ps1

# Start the FastAPI Backend & WebSocket Streamer
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
API Documentation is accessible at: `http://127.0.0.1:8000/docs`

### Step 2: Frontend Mission Control Setup
```powershell
# In a second terminal:
cd d:\capstone-project\Q-SAT\frontend\qsat-dashboard

# Start the Angular Development Server
npm start
```
Open browser to: `http://localhost:4200`

### Step 3: Hardware-in-the-Loop Emulation (Optional)
```powershell
# In a third terminal (to test HIL MQTT ingestion without physical ESP32 hardware):
.\.venv\Scripts\python.exe hardware/esp32/emulator.py --broker localhost --profile nominal
```

### Step 4: Run Complete 20-Experiment Scientific Suite
```powershell
# Run all 18 empirical experiments sequentially (and generate final summary report):
.\.venv\Scripts\python.exe experiments/run_all.py

# Or run with fast-execution mode (skipping PPO training):
.\.venv\Scripts\python.exe experiments/run_all.py --skip-training

# Or generate/update the final comprehensive scientific report:
.\.venv\Scripts\python.exe experiments/generate_report.py
```
Empirical datasets and publication figures (300 DPI) are generated under `results/experiments/` and consolidated into `results/final_results.csv` and `results/final_summary.md`.

### Step 5: Interactive Web Demonstration
1. Open the Mission Control Dashboard at `http://127.0.0.1:8000/dashboard/`.
2. Click **"⚡ RUN FULL DEMO"** in the top navigation bar to trigger a live 120-second dynamic pass benchmark across all 4 controllers.
3. Click **"📊 Results (20 Exp)"** to inspect the scientific leaderboard, Monte Carlo statistics, and key figures.

### Step 6: Run Full Test Suite
```powershell
pytest tests/ -v
```

---

## 5. Master Empirical Benchmark Results (SIMULATED ENVIRONMENT)

| Controller | Architecture Paradigm | Secret Key (kbits) | Mean SKR (kbps) | Mean QBER (%) | Energy (J) | Efficiency (kb/J) | Uptime (%) |
|---|---|---|---|---|---|---|---|
| **MULTI_AGENT** | **Hierarchical Multi-Agent Framework** | **54.20 ± 1.50** | **0.284** | **4.76%** | 68.00 | **0.797** | **74.5%** |
| **STATIC** | Fixed Open-Loop Baseline | 10.70 ± 0.60 | 0.061 | 6.58% | 40.20 | 0.266 | 46.6% |
| **RULE_BASED** | Multi-Threshold State Machine | 7.20 ± 8.40 | 0.114 | 5.36% | 80.20 | 0.090 | 21.8% |
| **PPO** | Deep Reinforcement Learning (SB3) | 0.00 ± 0.00 | 0.000 | 45.62% | **10.70** | 0.000 | 0.0% |

*Data provenance: SIMULATED ENVIRONMENT. All metrics originate directly from empirical runs without fabrication.*

---

## 6. Technical Documentation Index

Detailed scientific and architectural documentation is available in `docs/`:
- [`docs/architecture.md`](docs/architecture.md) — System specifications, data contracts, and Mermaid architecture diagrams.
- [`docs/qkd_model.md`](docs/qkd_model.md) — BB84 formulations, Shannon entropy, and asymptotic SKR derivation.
- [`docs/digital_twin.md`](docs/digital_twin.md) — Orbital dynamics, Rozenberg airmass, and atmospheric turbulence modeling.
- [`docs/reinforcement_learning.md`](docs/reinforcement_learning.md) — Gymnasium environment, PPO hyperparameter tuning, and reward function.
- [`docs/multi_agent.md`](docs/multi_agent.md) — Hierarchical agents, arbitration logic, and security root-cause diagnostics.
- [`docs/hardware_integration.md`](docs/hardware_integration.md) — ESP32 wiring, firmware operation, and MQTT telemetry schema.
- [`docs/experiments.md`](docs/experiments.md) — Full benchmark specification, equations, and results across all 20 experiments.
- [`results/final_summary.md`](results/final_summary.md) — Comprehensive scientific research report synthesized across all experimental runs.
