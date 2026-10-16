# Hierarchical Multi-Agent System Architecture

This document describes the design, operational logic, arbitration protocol, and security diagnostics of the **Hierarchical Multi-Agent Architecture** in Q-SAT.

---

## 1. Architectural Overview

While end-to-end Reinforcement Learning (PPO) excels at high-dimensional continuous optimization, deep policies often suffer from black-box opacity and cannot provide explainable root-cause attribution during security anomalies. To solve this, Q-SAT introduces a **Hierarchical Multi-Agent Framework** with two distinct functional tiers:

```
               ┌─────────────────────────────────────────┐
               │         COORDINATOR AGENT               │
               │   Arbitration, Conflict Resolution,     │
               │      Safety Enforcement & Smoothing     │
               └───────────▲─────────▲─────────▲─────────┘
                           │         │         │
           ┌───────────────┘         │         └───────────────┐
           │                         │                         │
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│    WEATHER AGENT     │  │ COMMUNICATION AGENT  │  │    SECURITY AGENT    │
│  Atmospheric Loss,   │  │   Link Margin, SNR,  │  │ Physical Attribution │
│ Humidity, Turbulence │  │ Repetition & Collim. │  │  vs Anomaly / Attack │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘
```

---

## 2. Domain Agents (Tier 1)

### 2.1 Weather Agent (`ai/agents/weather_agent.py`)

The Weather Agent monitors atmospheric microclimate variables (temperature, relative humidity, cloud optical depth, and scintillation index):
- **Severity Classification**:
  - `CLEAR`: Nominal extinction ($\tau_{\text{atm}} > 0.80$), minimal clouding.
  - `MILD_HAZE`: Increased humidity ($>75\%$) or light aerosol scatter.
  - `HEAVY_CLOUD`: Cloud Optical Depth $\text{COD} > 5.0$, high attenuation.
  - `TURBULENT`: High temperature gradient or ground-layer mechanical wind shear.
- **Output Setpoints**:
  - Recommends power boost factor ($1.0 - 2.0\times$) to punch through cloud and haze.
  - Recommends divergence widening ($+5 - 15\ \mu\text{rad}$) during strong turbulence to avoid scintillation-induced deep fades.

### 2.2 Communication Agent (`ai/agents/communication_agent.py`)

The Communication Agent tracks topocentric link dynamics:
- **Link Metrics**: Slant range ($500 - 1500\text{ km}$), elevation angle, telescope aperture collection fraction, and geometric path loss.
- **Dynamic Optimization**:
  - At low elevation ($10^\circ - 30^\circ$): High slant range and long airmass require high laser power and wider divergence to ensure link acquisition.
  - At zenith peak ($60^\circ - 90^\circ$): Shortest slant range ($500\text{ km}$) and lowest airmass allow narrow beam collimation ($10 - 15\ \mu\text{rad}$) and maximum repetition rate ($80 - 100\text{ MHz}$) for key rate burst.

### 2.3 Security & Anomaly Agent (`ai/agents/security_agent.py`)

A fundamental requirement in quantum communication is distinguishing benign physical degradation from active eavesdropping attacks (e.g., intercept-resend, beam-splitter attacks).

#### Diagnostic Attribution Algorithm:
1. Bob observes aggregate measured error $e_{\text{measured}}$.
2. The Security Agent computes the predicted physical error budget $e_{\text{phys}}$ based on real-time sensors:
   $$e_{\text{phys}} = e_{\text{base}} + e_{\text{atm}} + e_{\text{stray}} + e_{\text{vibe}} + e_{\text{dark}}$$
3. It evaluates the unexplained residual error $\Delta e$:
   $$\Delta e = e_{\text{measured}} - e_{\text{phys}}$$
4. **Classification Logic**:
   - If $e_{\text{measured}} < 0.08$ and $\Delta e \le 0.02$: Status = `SECURE`.
   - If $e_{\text{measured}} \ge 0.08$ but $\Delta e \le 0.03$: Status = `DEGRADED_PHYSICAL` (elevated noise is accounted for by ambient light, turbulence, or mount vibration; **no false alarm raised**).
   - If $\Delta e > 0.03$ or an anomaly injection is confirmed: Status = `ANOMALY_DETECTED` (unexplained error implies eavesdropping).
   - If $e_{\text{measured}} \ge 0.11$: Status = `ABORT_INSECURE` (exceeds theoretical BB84 security cutoff; key generation immediately halted).

---

## 3. Coordinator Agent (Tier 2)

The Coordinator Agent (`ai/agents/coordinator.py`) receives decisions from all three domain agents and synthesizes a unified, hazard-free control command.

### 3.1 Arbitration Hierarchy & Priority Rules:

```
[Level 1: SECURITY HARD OVERRIDE]
  IF Status == 'ABORT_INSECURE':
     -> Cut transmitter power to minimum (5.0 mW)
     -> Suppress key accumulation
     -> Assert MISSION_ABORT alert

[Level 2: ANOMALY MITIGATION]
  IF Status == 'ANOMALY_DETECTED':
     -> Increase privacy amplification compression
     -> Request basis check protocol

[Level 3: NOMINAL MULTI-OBJECTIVE COMPROMISE]
  Laser Power:     Weighted average of Comm and Weather recommendations
  Repetition Rate: Capped by Link Margin & Detector Saturation bounds
  Beam Divergence: MAX(Comm Target, Weather Widening Target)
```

### 3.2 Dynamic Smoothing

To guarantee physical actuator safety, the Coordinator applies exponential moving average (EMA) filtering:

$$\mathbf{u}_t = \alpha \cdot \mathbf{u}_{\text{target}} + (1 - \alpha) \cdot \mathbf{u}_{t-1}, \quad \alpha = 0.40$$

Followed by rate-of-change clamping ($|\Delta u| \le 20\%$ per step).
