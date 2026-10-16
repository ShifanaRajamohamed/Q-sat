# Hardware-in-the-Loop (HIL) Integration & ESP32 Firmware

This document describes the physical architecture, sensor hardware schematics, firmware operation, MQTT communication protocol, and digital-twin abstraction layer for the **Q-SAT Hardware-in-the-Loop** environment.

---

## 1. Hardware Architecture Overview

To transition from pure software simulation to empirical validation without altering the core simulation engine or AI controllers, Q-SAT features a modular **Hardware-in-the-Loop (HIL)** pipeline based on the **ESP32 microcontroller**:

```
 ┌────────────────────────────────────────────────────────┐
 │ PHYSICAL SENSORS (Optical Ground Station Mount)       │
 │                                                        │
 │ ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
 │ │    DHT22     │   │     LDR      │   │   MPU6050    │ │
 │ │  Temp & Hum  │   │ Ambient Lux  │   │ Mount Jitter │ │
 │ └──────┬───────┘   └──────┬───────┘   └──────┬───────┘ │
 └────────┼──────────────────┼──────────────────┼─────────┘
          │ GPIO 4           │ GPIO 34 (ADC)    │ I2C (21/22)
          ▼                  ▼                  ▼
 ┌────────────────────────────────────────────────────────┐
 │ ESP32 DEVKIT V1 (Xtensa 32-bit Dual-Core 240 MHz)      │
 │ - 12-bit ADC Sampling & Calibration                    │
 │ - MPU6050 Dynamic RMS Filtering                        │
 │ - FreeRTOS Telemetry Task (1 Hz)                       │
 │ - WiFi Station + PubSubClient MQTT 3.1.1               │
 └───────────────────────────┬────────────────────────────┘
                             │
                             │ WiFi IEEE 802.11 b/g/n
                             │ MQTT JSON over TCP port 1883
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ MQTT BROKER (Mosquitto / Local Bridge)                 │
 │ Topic: "qsat/environment"                              │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ Q-SAT BACKEND (Python FastAPI)                         │
 │ MQTTEnvironmentProvider -> Dynamic Fallback Engine    │
 └────────────────────────────────────────────────────────┘
```

---

## 2. Sensor Interfacing & Signal Conditioning

### 2.1 DHT22: Temperature & Relative Humidity
- **Pin**: GPIO 4 (Digital bidirectional single-wire bus with $4.7\text{ k}\Omega$ pull-up).
- **Range**: $-40^\circ\text{C}$ to $+80^\circ\text{C}$ ($\pm 0.5^\circ\text{C}$ accuracy); $0 - 100\%\text{ RH}$ ($\pm 2\%$ accuracy).
- **Physical Role**: Informs the Weather Agent of atmospheric dew point, vapor pressure, and potential thermal condensation on telescope mirrors.

### 2.2 GL5528 Photoresistor (LDR): Ambient Optical Background
- **Pin**: GPIO 34 (ADC1 Channel 6, input-only pin isolated from WiFi radio RF noise).
- **Circuit**: Voltage divider with $V_{\text{in}} = 3.3\text{V}$, $R_{\text{ref}} = 10.0\text{ k}\Omega$ to Ground.
- **Conversion Equation**:
  $$V_{\text{out}} = \frac{\text{ADC}}{4095} \times 3.3\text{V}, \quad R_{\text{ldr}} = R_{\text{ref}} \left(\frac{V_{\text{in}}}{V_{\text{out}}} - 1\right)$$
  $$\text{Lux} = \frac{500}{(R_{\text{ldr}} / 1000)^{1.4}}$$
- **Physical Role**: Quantifies stray sunlight, moonlight, and urban light pollution leaking into the single-photon detector plane ($e_{\text{stray}}$).

### 2.3 MPU6050: Ground Station Mount Pointing Jitter
- **Bus**: $\text{I}^2\text{C}$ (SDA: GPIO 21, SCL: GPIO 22; clock frequency: $400\text{ kHz}$).
- **Configuration**: Accelerometer $\pm 2g$ range, onboard digital low-pass filter (DLPF) set to $21\text{ Hz}$.
- **Dynamic RMS Vibration Metric**:
  To decouple static gravitational acceleration ($1g \approx 9.80665\text{ m/s}^2$) from dynamic mount vibration, the firmware samples 20 high-frequency readings per cycle:
  $$\sigma_{\text{RMS}} = \sqrt{\frac{1}{N} \sum_{i=1}^N \left( \sqrt{a_{x,i}^2 + a_{y,i}^2 + a_{z,i}^2} - 9.80665 \right)^2}$$
- **Physical Role**: Directly feeds into the pointing jitter error budget $e_{\text{vibe}}$ and telescope pointing loss $\eta_{\text{jitter}}$.

---

## 3. Telemetry Protocol Specification

### 3.1 MQTT Topic & Message Format

The sensor node publishes JSON packets to `qsat/environment` every $1000\text{ ms}$:

```json
{
  "temperature": 24.8,
  "relative_humidity": 62.1,
  "ambient_light_lux": 450.2,
  "vibration_level": 0.0125,
  "optical_background_noise": 450.2,
  "source": "HARDWARE",
  "device_id": "ESP32_QGS_NODE_01",
  "uptime_ms": 145200,
  "timestamp": 1726834000.123
}
```

---

## 4. Software Abstraction & Failover Architecture

The backend implements `MQTTEnvironmentProvider` inheriting from `EnvironmentProvider`:

1. **Non-Blocking Background Ingestion**: An isolated Paho MQTT client thread subscribes to `qsat/environment` and pushes decoded packets into a thread-safe circular buffer.
2. **Heartbeat & Graceful Fallback**:
   - Every sampling interval, `get_readings()` checks the timestamp of the latest hardware packet.
   - If no packet is received for $> 3.0\text{ seconds}$ (e.g. WiFi outage, sensor unplugged, hardware offline), the system **automatically and seamlessly transitions to `SimulationEnvironmentProvider` (Ornstein-Uhlenbeck SDE)**.
   - The data packet's `source` field is dynamically toggled between `"HARDWARE"` and `"SIMULATION"`, ensuring the operator is continuously aware of data provenance.

---

## 5. Standalone Software Emulator (`emulator.py`)

For automated CI/CD pipelines and testing when physical hardware is not present, `hardware/esp32/emulator.py` emulates the exact electrical and network behavior of the ESP32 node, supporting multiple atmospheric profiles:
- `nominal`: Clear sky conditions with gentle diurnal thermal drift.
- `vibration_storm`: Strong wind buffeting causing large mount jitter spikes.
- `high_ambient_light`: Direct daytime sunlight scatter test.
- `humid_night`: Dense maritime fog with saturated relative humidity.
