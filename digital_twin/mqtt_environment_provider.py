"""MQTTEnvironmentProvider: Ingests real-time telemetry from physical ESP32 sensors via MQTT.

Subscribes to topic 'qsat/environment'. If MQTT broker is unavailable or
telemetry times out, provides graceful fallback to synthetic simulation
without crashing the application.
"""

import json
import logging
import time
from typing import Optional
import paho.mqtt.client as mqtt

from backend.app.config import settings
from backend.app.models.environment import EnvironmentData
from digital_twin.environment_provider import EnvironmentProvider
from digital_twin.simulation_environment_provider import SimulationEnvironmentProvider

logger = logging.getLogger("qsat.mqtt_provider")


class MQTTEnvironmentProvider(EnvironmentProvider):
    """Ingests real-time hardware telemetry from ESP32 via MQTT with automatic simulation fallback."""

    def __init__(
        self,
        broker_host: Optional[str] = None,
        broker_port: Optional[int] = None,
        topic: Optional[str] = None,
        fallback_timeout: float = 5.0,
        auto_fallback: bool = True
    ):
        self.broker_host = broker_host or settings.MQTT_BROKER
        self.broker_port = broker_port or settings.MQTT_PORT
        self.topic = topic or settings.MQTT_TOPIC_ENVIRONMENT
        self.fallback_timeout = fallback_timeout
        self.auto_fallback = auto_fallback

        # Internal simulation fallback provider
        self.fallback_provider = SimulationEnvironmentProvider()

        # Telemetry cache
        self.latest_data: Optional[EnvironmentData] = None
        self.last_packet_time: float = 0.0
        self.is_connected = False

        # MQTT Client setup
        self.client: Optional[mqtt.Client] = None
        self._init_mqtt()

    def _init_mqtt(self) -> None:
        """Configure MQTT client callbacks and initiate non-blocking background connection."""
        try:
            # Compatible with paho-mqtt v2.x
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="qsat_backend_ingest")
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message

            logger.info("Attempting non-blocking MQTT connection to %s:%s...", self.broker_host, self.broker_port)
            self.client.connect_async(self.broker_host, self.broker_port, keepalive=settings.MQTT_KEEPALIVE)
            self.client.loop_start()
        except Exception as exc:
            logger.warning("Failed to initialize MQTT client (%s). Fallback to simulation active.", exc)
            self.is_connected = False

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback when connection to broker is established."""
        if rc == 0:
            self.is_connected = True
            logger.info("Connected to MQTT broker. Subscribing to '%s'", self.topic)
            client.subscribe(self.topic, qos=1)
        else:
            self.is_connected = False
            logger.warning("MQTT connection failed with code %d. Using simulation fallback.", rc)

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        """Callback when disconnected from broker."""
        self.is_connected = False
        logger.warning("Disconnected from MQTT broker (code %d). Fallback to simulation active.", rc)

    def _on_message(self, client, userdata, msg):
        """Callback when telemetry message is received from ESP32."""
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            # Example payload from ESP32:
            # {"device_id": "qsat-esp32-01", "timestamp": "...", "temperature": 29.4, "humidity": 68.2, "ambient_light": 730, "vibration": 0.12}

            # Map hardware inputs, and estimate cloud/turbulence or retain fallback estimates
            now = time.time()
            self.latest_data = EnvironmentData(
                timestamp=round(now, 3),
                temperature=float(payload.get("temperature", 25.0)),
                humidity=float(payload.get("humidity", 50.0)),
                ambient_light=float(payload.get("ambient_light", 500.0)),
                vibration=float(payload.get("vibration", 0.02)),
                cloud_factor=float(payload.get("cloud_factor", 0.05)),
                turbulence=float(payload.get("turbulence", 0.10)),
                data_source="HARDWARE",
                scenario_name="PHYSICAL_ESP32"
            )
            self.last_packet_time = now
            logger.debug("Received ESP32 hardware telemetry: %s", self.latest_data)
        except Exception as exc:
            logger.error("Failed to parse ESP32 MQTT telemetry payload: %s", exc)

    def get_current_environment(self) -> EnvironmentData:
        """Return latest hardware telemetry or fallback to simulation if hardware disconnected."""
        now = time.time()
        hardware_stale = (now - self.last_packet_time) > self.fallback_timeout

        if self.is_connected and self.latest_data is not None and not hardware_stale:
            return self.latest_data

        if self.auto_fallback:
            # Fallback to simulation provider
            sim_data = self.fallback_provider.get_current_environment()
            return sim_data

        if self.latest_data is not None:
            return self.latest_data

        return self.fallback_provider.get_current_environment()

    def step(self, dt: float = 1.0) -> EnvironmentData:
        """Step method advances internal fallback timer and returns latest environment."""
        self.fallback_provider.step(dt=dt)
        return self.get_current_environment()

    def reset(self, seed: Optional[int] = None) -> EnvironmentData:
        """Reset internal fallback provider."""
        self.fallback_provider.reset(seed=seed)
        return self.get_current_environment()

    def get_mode(self) -> str:
        return "mqtt"

    def is_healthy(self) -> bool:
        now = time.time()
        return self.is_connected and (now - self.last_packet_time <= self.fallback_timeout)

    def close(self) -> None:
        """Cleanly terminate MQTT background loop and network connection."""
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass
