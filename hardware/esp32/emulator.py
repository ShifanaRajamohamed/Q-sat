"""
Q-SAT Adaptive Ground Station - ESP32 Hardware Emulator
Hardware-in-the-Loop Simulation Testbench

This script emulates the physical ESP32 sensor node transmitting telemetry
over MQTT to topic 'qsat/environment'. It allows testing the Hardware-in-the-Loop
pipeline without physical microcontroller hardware.
"""

import argparse
import json
import math
import sys
import time
from typing import Dict, Any

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("[ERROR] 'paho-mqtt' is required. Install with: pip install paho-mqtt")
    sys.exit(1)


def generate_emulated_readings(step: int, profile: str = "nominal") -> Dict[str, Any]:
    """
    Generate realistic sensor readings corresponding to DHT22, LDR, and MPU6050.
    """
    t = step * 1.0  # seconds elapsed

    if profile == "nominal":
        temp = 24.5 + 1.2 * math.sin(t / 60.0)
        humidity = 58.0 + 4.0 * math.cos(t / 45.0)
        lux = 350.0 + 50.0 * math.sin(t / 30.0)
        vibration = 0.008 + 0.003 * abs(math.sin(t / 5.0))
    elif profile == "vibration_storm":
        temp = 26.0 + 0.5 * math.sin(t / 10.0)
        humidity = 62.0
        lux = 420.0
        # High mechanical vibration from wind buffeting
        vibration = 0.085 + 0.035 * abs(math.sin(t / 2.0))
    elif profile == "high_ambient_light":
        temp = 32.0 + 2.0 * math.sin(t / 100.0)
        humidity = 35.0
        # Direct sunlight / dawn scatter
        lux = 75000.0 + 5000.0 * math.sin(t / 20.0)
        vibration = 0.005
    elif profile == "humid_night":
        temp = 18.0 + 0.5 * math.sin(t / 120.0)
        humidity = 92.0 + 3.0 * math.sin(t / 50.0)
        lux = 5.0 + 2.0 * math.sin(t / 30.0)
        vibration = 0.004
    else:
        temp = 25.0
        humidity = 50.0
        lux = 300.0
        vibration = 0.010

    return {
        "temperature": round(temp, 1),
        "relative_humidity": round(humidity, 1),
        "ambient_light_lux": round(lux, 1),
        "vibration_level": round(vibration, 4),
        "optical_background_noise": round(lux, 1),
        "source": "HARDWARE",
        "device_id": "ESP32_EMULATOR_01",
        "uptime_ms": int(t * 1000),
        "timestamp": time.time()
    }


def main():
    parser = argparse.ArgumentParser(description="Q-SAT ESP32 Sensor Node Emulator")
    parser.add_argument("--broker", default="localhost", help="MQTT Broker host (default: localhost)")
    parser.add_argument("--port", type=int, default=1883, help="MQTT Broker port (default: 1883)")
    parser.add_argument("--topic", default="qsat/environment", help="MQTT publish topic (default: qsat/environment)")
    parser.add_argument("--rate", type=float, default=1.0, help="Publish frequency in Hz (default: 1.0)")
    parser.add_argument("--profile", default="nominal", choices=["nominal", "vibration_storm", "high_ambient_light", "humid_night"],
                        help="Telemetry profile (default: nominal)")
    parser.add_argument("--steps", type=int, default=0, help="Number of steps (0 = infinite)")
    args = parser.parse_args()

    client = mqtt.Client(client_id="ESP32_EMULATOR_01", protocol=mqtt.MQTTv311)

    print("=" * 60)
    print("  Q-SAT ADAPTIVE GROUND STATION - ESP32 SENSOR EMULATOR")
    print(f"  Target Broker: {args.broker}:{args.port}")
    print(f"  Topic:         {args.topic}")
    print(f"  Profile:       {args.profile}")
    print(f"  Rate:          {args.rate} Hz")
    print("=" * 60)

    try:
        client.connect(args.broker, args.port, keepalive=60)
        client.loop_start()
        print("[CONNECTED] Successfully connected to MQTT broker.")
    except Exception as e:
        print(f"[WARN] Connection failed to {args.broker}:{args.port}: {e}")
        print("[INFO] Running in dry-run local print mode (no active broker).")
        client = None

    step = 0
    interval = 1.0 / max(0.1, args.rate)

    try:
        while True:
            step += 1
            payload = generate_emulated_readings(step, args.profile)
            json_str = json.dumps(payload)

            if client:
                client.publish(args.topic, json_str)
                print(f"[STEP {step:04d} PUB] {json_str}")
            else:
                print(f"[STEP {step:04d} EMUL] {json_str}")

            if args.steps > 0 and step >= args.steps:
                print(f"[COMPLETE] Reached target {args.steps} steps.")
                break

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[STOP] Emulator terminated by user.")
    finally:
        if client:
            client.loop_stop()
            client.disconnect()


if __name__ == "__main__":
    main()
