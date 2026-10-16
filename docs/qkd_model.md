# BB84-Inspired Quantum Key Distribution (QKD) Model

This document specifies the mathematical formulations, physical mechanisms, and architectural implementation of the satellite-to-ground optical quantum key distribution model used in **Q-SAT**.

---

## 1. Protocol Architecture: BB84 Overview

The Q-SAT platform models a downlink optical Quantum Key Distribution link operating between a Low Earth Orbit (LEO) satellite transmitter (Alice) and an optical ground station receiver (Bob) based on the Bennett-Brassard 1984 (BB84) protocol.

### 1.1 Polarization Bases & States

Alice modulates single-photon pulses (or phase-randomized weak coherent pulses) across two mutually unbiased measurement bases:

1. **Rectilinear Basis ($\mathcal{Z}$)**:
   - State $|0\rangle \equiv |H\rangle$ (Horizontal polarization, $0^\circ$)
   - State $|1\rangle \equiv |V\rangle$ (Vertical polarization, $90^\circ$)

2. **Diagonal Basis ($\mathcal{X}$)**:
   - State $|+\rangle \equiv |D\rangle = \frac{1}{\sqrt{2}}(|H\rangle + |V\rangle)$ (Diagonal polarization, $+45^\circ$)
   - State $|-\rangle \equiv |A\rangle = \frac{1}{\sqrt{2}}(|H\rangle - |V\rangle)$ (Anti-diagonal polarization, $-45^\circ$)

Because $\langle H | D \rangle^2 = \langle H | A \rangle^2 = \langle V | D \rangle^2 = \langle V | A \rangle^2 = \frac{1}{2}$, any measurement in the incompatible basis yields an uncorrelated random outcome with $50\%$ error probability, establishing information-theoretic security bounds under the Heisenberg uncertainty principle and the quantum no-cloning theorem.

---

## 2. Channel Physics & Photon Detection

### 2.1 Photon Transmission Rate & Link Efficiency

Given Alice's pulse repetition rate $R_{\text{rep}}$ (typically $10 - 100\text{ MHz}$) and mean photon number per pulse $\mu \approx 0.5 - 0.8$ (to suppress multi-photon emissions while maintaining signal flux):

$$\Phi_{\text{tx}} = R_{\text{rep}} \cdot \mu \quad [\text{photons/second}]$$

The channel transmittance $\eta_{\text{channel}}$ accounts for:
- Free-space geometric path attenuation $\eta_{\text{geom}} = \left(\frac{D_{\text{rx}}}{\theta_{\text{div}} \cdot d}\right)^2$
- Atmospheric Beer-Lambert extinction $\eta_{\text{atm}} = \exp(-\beta_{\text{ext}} \cdot m(\theta))$
- Cloud droplet scattering attenuation $\eta_{\text{cloud}} = 10^{-\text{COD} / 10}$
- Receiver optical efficiency $\eta_{\text{opt}} \approx 0.60$
- Single-Photon Avalanche Diode (SPAD) detection efficiency $\eta_{\text{det}} \approx 0.45$

The total received signal count rate $R_{\text{sig}}$ at Bob's detector plane is:

$$R_{\text{sig}} = \Phi_{\text{tx}} \cdot \eta_{\text{channel}} \cdot \eta_{\text{det}} \quad [\text{counts/s}]$$

### 2.2 Sifted Key Rate

During the public reconciliation phase, Alice and Bob announce the basis used for each pulse over an authenticated classical channel. Pulses measured in mismatched bases are discarded:

$$R_{\text{sift}} = \frac{1}{2} R_{\text{raw}} = \frac{1}{2} R_{\text{sig}} \quad [\text{bits/s}]$$

---

## 3. Quantum Bit Error Rate (QBER) Decomposition

In practical free-space optical channels, errors originate from distinct physical and mechanical processes. Rather than treating QBER as an opaque scalar, Q-SAT implements a **rigorous root-cause additive decomposition**:

$$e_{\text{total}} = e_{\text{base}} + e_{\text{atm}} + e_{\text{stray}} + e_{\text{vibe}} + e_{\text{dark}} + \Delta e_{\text{anomaly}}$$

### 3.1 Optical Base Error ($e_{\text{base}}$)
Originates from non-ideal polarization extinction ratios (PER) in Alice's electro-optic modulators and Bob's polarizing beam splitters:
$$e_{\text{base}} \approx 0.010 \quad (1.0\%)$$

### 3.2 Atmospheric Turbulence Error ($e_{\text{atm}}$)
Atmospheric refractive index variations (Kolmogorov turbulence) introduce wavefront distortion and beam wander, modelled via the Rytov scintillation variance $\sigma_R^2$:
$$e_{\text{atm}} = 0.015 \cdot \min(1.0, \sigma_R^2)$$

### 3.3 Stray Light Background Error ($e_{\text{stray}}$)
Ambient background photons (sunlight scatter, lunar flux, city light dome) leak through Bob's sub-nanometer optical bandpass filter ($0.15\text{ counts/s/lux}$):
$$e_{\text{stray}} = \frac{R_{\text{stray}}}{2(R_{\text{sig}} + R_{\text{stray}} + 2 R_{\text{dark}})}$$
Because background photons are completely unpolarized, they cause a bit-flip with $50\%$ probability.

### 3.4 Mount Vibration Error ($e_{\text{vibe}}$)
Mechanical buffeting and motor servo jitter cause sub-microradian pointing offsets, coupling into polarization misalignment:
$$e_{\text{vibe}} = 0.05 \cdot \text{vibration\_severity}$$

### 3.5 Detector Dark Count Error ($e_{\text{dark}}$)
Thermally generated electron-hole pairs in Bob's SPADs trigger false detection events ($R_{\text{dark}} \approx 100\text{ counts/s}$):
$$e_{\text{dark}} = \frac{R_{\text{dark}}}{R_{\text{sig}} + R_{\text{stray}} + 2 R_{\text{dark}}}$$

### 3.6 Security Anomaly Offset ($\Delta e_{\text{anomaly}}$)
Unexplained residual errors injected during eavesdropping simulations (e.g., intercept-resend attack induces $25\%$ base error increase):
$$\Delta e_{\text{anomaly}} = \begin{cases} 0.0, & \text{nominal operations} \\ \Delta_{\text{eavesdrop}}, & \text{active attack / tampering} \end{cases}$$

---

## 4. Asymptotic Secret Key Rate (SKR)

The asymptotic secret key generation rate $R_{\text{SKR}}$ after error correction (Cascade / LDPC) and privacy amplification (Toeplitz matrix hashing) is governed by the Devetak-Winter and Shor-Preskill bounds:

$$R_{\text{SKR}} = \max\left(0,\, R_{\text{sift}} \cdot \left[ 1 - f(e) \cdot h_2(e) - h_2(e) \right]\right)$$

Where:
- $h_2(e)$ is the **Binary Shannon Entropy function**:
  $$h_2(e) = -e \log_2(e) - (1-e) \log_2(1-e)$$
- $f(e) \ge 1.0$ is the **bidirectional error correction inefficiency factor** (empirically $f(e) = 1.16$ for modern LDPC codes).
- The term $f(e) \cdot h_2(e)$ represents information leaked to an eavesdropper during classical error reconciliation.
- The second $h_2(e)$ term represents information discarded during privacy amplification to eliminate phase errors.

### 4.1 Security Threshold Cutoff

When $e_{\text{total}} \ge 11.0\%$:
$$1 - f(e) h_2(e) - h_2(e) \le 0 \implies R_{\text{SKR}} = 0\text{ bps}$$
At this point, Alice and Bob **abort key generation**, as Eve could theoretically possess sufficient mutual information to reconstruct the full secret key.

---

## 5. Architectural Implementation

The QKD pipeline in Q-SAT is organized into modular Python classes located in `qkd/`:

| Module | Class | Role |
|---|---|---|
| `qkd/qber.py` | `QBERCalculator` | Computes isolated error components and aggregate QBER |
| `qkd/key_rate.py` | `KeyRateCalculator` | Computes transmitter flux, attenuation, and sifted key rates |
| `qkd/secret_key_rate.py` | `SecretKeyRateCalculator` | Evaluates Shannon entropy and asymptotic SKR |
| `qkd/bb84_model.py` | `BB84Model` | High-level orchestrator connecting optical channel state to QKD metrics |
| `qkd/qkd_simulator.py` | `QKDSimulator` | Episode stepper with configurable anomaly injection |

---

## 6. Scientific Data Labeling

To ensure research integrity, all QKD metrics generated in Q-SAT include source tags:
- `SIMULATION`: Computed via physical simulation models.
- `HARDWARE`: Acquired directly from physical ESP32 sensor node.
- `ASSUMPTION`: Theoretical baseline parameters (e.g., $e_{\text{base}} = 0.01$).
- `AI_OUTPUT`: Actuator setpoints determined by PPO or Multi-Agent Coordinator.
