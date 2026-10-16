# Digital Twin & Physical Channel Modeling

This document details the mathematical architecture and physical formulations governing the **Digital Twin** in the Q-SAT platform, including orbital kinematics, topocentric geometry, atmospheric optical propagation, and stochastic microclimate dynamics.

---

## 1. Topocentric Satellite Geometry & Orbit Mechanics

### 1.1 Reference Frame & Ground Station Parameters

The ground station receiver (Bob) is geolocated at:
- **Latitude ($\phi_0$)**: $10.7905^\circ\text{ N}$ (Tiruchirappalli, Tamil Nadu, India)
- **Longitude ($\lambda_0$)**: $78.7047^\circ\text{ E}$
- **Elevation ($h_0$)**: $80.0\text{ m}$ above WGS-84 reference ellipsoid ($R_E \approx 6371.0\text{ km}$)

The satellite transmitter (Alice) traverses a circular Low Earth Orbit (LEO) at nominal altitude $h_{\text{sat}} = 500\text{ km}$.

### 1.2 Keplerian Dynamics & Pass Duration

The satellite orbital velocity $v_{\text{sat}}$ and orbital period $T_{\text{orb}}$ are given by standard two-body gravitational dynamics:

$$v_{\text{sat}} = \sqrt{\frac{G M_E}{R_E + h_{\text{sat}}}} \approx 7.613\text{ km/s}$$

$$T_{\text{orb}} = 2\pi \sqrt{\frac{(R_E + h_{\text{sat}})^3}{G M_E}} \approx 5677\text{ s} \quad (\approx 94.6\text{ minutes})$$

For an overhead pass with minimum elevation angle threshold $\theta_{\text{min}} = 10^\circ$, the maximum visible ground station pass duration is approximately:

$$t_{\text{pass}} \approx \frac{2 R_E}{v_{\text{sat}}} \arccos\left(\frac{R_E \cos\theta_{\text{min}}}{R_E + h_{\text{sat}}}\right) \approx 450 - 550\text{ seconds}$$

### 1.3 Topocentric Slant Range & Elevation Progression

As the satellite traverses the local celestial dome, its elevation angle $\theta(t)$ above Bob's horizon follows the cosine pass trajectory:

$$\theta(t) = \theta_{\text{peak}} \cos\left( \frac{\pi (t - t_{\text{mid}})}{t_{\text{pass}}} \right)$$

The geometric slant range $d(t)$ from ground station telescope aperture to satellite is derived from the law of cosines:

$$d(\theta) = \sqrt{R_E^2 \sin^2\theta + 2 R_E h_{\text{sat}} + h_{\text{sat}}^2} - R_E \sin\theta$$

- At zenith ($\theta = 90^\circ$): $d = h_{\text{sat}} = 500\text{ km}$
- At horizon threshold ($\theta = 10^\circ$): $d \approx 1450\text{ km}$

---

## 2. Atmospheric & Optical Channel Physics

Optical quantum signals transmitted from space to Earth experience three primary degradation mechanisms: geometric diffraction, atmospheric extinction, and optical turbulence.

### 2.1 Rozenberg Relative Airmass Model

At low elevation angles, a planar plane-parallel atmosphere approximation fails due to Earth's planetary curvature. Q-SAT utilizes the Rozenberg formulation for accurate optical airmass $m(\theta)$:

$$m(\theta) = \frac{1}{\sin\theta + 0.025 \cdot \exp(-11 \cdot \sin\theta)}$$

- At $\theta = 90^\circ$ (zenith): $m = 1.000$
- At $\theta = 30^\circ$: $m = 1.995$
- At $\theta = 10^\circ$: $m = 5.602$

### 2.2 Atmospheric Beer-Lambert Extinction

Signal attenuation due to Rayleigh molecular scattering and Mie aerosol absorption is modeled via Beer-Lambert law:

$$\tau_{\text{atm}}(\theta) = \exp\left( -\beta_{\text{ext}} \cdot m(\theta) \right)$$

Where $\beta_{\text{ext}} \approx 0.08 - 0.25$ is the zenith extinction optical depth at $\lambda = 850\text{ nm}$. Under cloudy conditions with Cloud Optical Depth ($\text{COD}$), an additional cloud transmittance penalty is applied:

$$\tau_{\text{cloud}} = 10^{-\text{COD} / 10}$$

### 2.3 Optical Turbulence & Scintillation (Rytov Variance)

Temperature and pressure fluctuations in the boundary layer generate refractive index structure constant $C_n^2(h)$ gradients (Hufnagel-Valley model). The intensity scintillation index $\sigma_I^2$ along the slant propagation path is parameterized via the Rytov variance:

$$\sigma_R^2 = 1.23 \, C_n^2 \, k^{7/6} \, d^{11/6} \cdot m(\theta)^{11/6}$$

Where $k = \frac{2\pi}{\lambda}$ is the optical wave number. Strong scintillation ($\sigma_R^2 > 0.5$) induces instantaneous fading and increases polarization noise $e_{\text{atm}}$.

### 2.4 Beam Divergence & Geometric Collection Efficiency

Alice's transmitter collimates the laser beam to a diffraction-limited Gaussian waist with full-angle divergence $\theta_{\text{div}}$ ($10 - 50\ \mu\text{rad}$). Upon reaching the ground, the beam foot-print diameter $w(d)$ is:

$$w(d) = d \cdot \theta_{\text{div}} \quad [\text{meters}]$$

For an optical ground station telescope with primary collector aperture diameter $D_{\text{rx}} = 0.30\text{ m}$ ($300\text{ mm}$), the geometric collection fraction $\eta_{\text{geom}}$ is:

$$\eta_{\text{geom}} = \left(\frac{D_{\text{rx}}}{w(d)}\right)^2 = \left(\frac{D_{\text{rx}}}{d \cdot \theta_{\text{div}}}\right)^2$$

### 2.5 Telescope Mount Pointing Jitter

Wind buffeting and servo tracking errors introduce pointing angular jitter $\theta_{\text{jitter}}$. The pointing efficiency $\eta_{\text{jitter}}$ follows the Rayleigh-Rice pointing loss distribution:

$$\eta_{\text{jitter}} = \exp\left( -\frac{\theta_{\text{jitter}}^2}{2 \, \theta_{\text{div}}^2} \right)$$

---

## 3. Stochastic Microclimate Dynamics

To capture realistic physical volatility without synthetic discontinuities, environmental variables in Q-SAT follow **Ornstein-Uhlenbeck mean-reverting stochastic processes**:

$$dX_t = \theta (\mu - X_t) dt + \sigma dW_t$$

Where:
- $\mu$ is the long-term equilibrium mean (e.g., $25^\circ\text{C}$, $60\%\text{ RH}$, $350\text{ lux}$).
- $\theta > 0$ is the mean-reversion rate driving recovery toward nominal conditions.
- $\sigma > 0$ is the diffusion volatility coefficient.
- $W_t$ is a continuous Wiener process with Gaussian increments $dW_t \sim \mathcal{N}(0, dt)$.

### Parameter Table by Variable

| Variable | Unit | Nominal $\mu$ | Reversion $\theta$ | Volatility $\sigma$ | Minimum Bound | Maximum Bound |
|---|---|---|---|---|---|---|
| Temperature | $^\circ\text{C}$ | $25.0$ | $0.05$ | $0.20$ | $-10.0$ | $55.0$ |
| Humidity | $\%$ | $55.0$ | $0.05$ | $0.50$ | $5.0$ | $100.0$ |
| Ambient Light | $\text{lux}$ | $350.0$ | $0.10$ | $25.0$ | $0.0$ | $120,000.0$ |
| Vibration | metric | $0.010$ | $0.20$ | $0.005$ | $0.001$ | $1.000$ |

---

## 4. Software Abstraction & Provider Pattern

The environmental data ingestion pipeline implements the **Provider Pattern**:

```
           ┌────────────────────────────┐
           │ <<abstract>>               │
           │ EnvironmentProvider        │
           ├────────────────────────────┤
           │ + get_readings()           │
           │ + get_source_label()       │
           └──────────────┬─────────────┘
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
┌─────────────────────────┐ ┌─────────────────────────┐
│ SimulationProvider      │ │ MQTTEnvironmentProvider │
│ (Ornstein-Uhlenbeck SDE)│ │ (ESP32 Live Telemetry)  │
└─────────────────────────┘ └─────────────────────────┘
```

When an ESP32 hardware node is active on the local network, `MQTTEnvironmentProvider` streams live hardware telemetry with zero changes required in the higher-level digital twin, RL controller, or QKD security layers.
