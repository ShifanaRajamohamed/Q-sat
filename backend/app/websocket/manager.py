"""WebSocket Connection Manager and real-time telemetry streaming broadcaster."""

import asyncio
import json
import logging
from typing import Dict, List, Optional
from fastapi import WebSocket, WebSocketDisconnect

from backend.app.services.alert_service import alert_service
from backend.app.services.control_service import control_service
from backend.app.services.environment_service import environment_service
from backend.app.services.qkd_service import qkd_service
from backend.app.services.satellite_service import satellite_service

logger = logging.getLogger("qsat.websocket")


class ConnectionManager:
    """Manages active WebSocket client connections and broadcasts live telemetry packets."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._broadcast_task: Optional[asyncio.Task] = None
        self.is_running = True
        self.stream_interval_s = 0.80  # Push updates every ~800 ms

    async def connect(self, websocket: WebSocket):
        """Accept new client WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket client connected. Total active: %d", len(self.active_connections))

        # Send immediate initial telemetry snapshot
        snapshot = self.build_telemetry_packet()
        await websocket.send_text(json.dumps(snapshot))

    def disconnect(self, websocket: WebSocket):
        """Handle client disconnection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("WebSocket client disconnected. Total active: %d", len(self.active_connections))

    def build_telemetry_packet(self) -> dict:
        """Assemble cohesive real-time telemetry payload covering all subsystems."""
        sat_state = satellite_service.get_state()
        env_state = environment_service.get_current_environment()
        qkd_metrics = qkd_service.get_metrics()
        channel_state = qkd_service.latest_channel_state
        ctrl_action = control_service.get_current_action()
        ctrl_delta = control_service.get_current_delta()
        multi_agent = control_service.get_multi_agent_decision()
        active_alerts = alert_service.get_active_alerts()

        packet = {
            "timestamp": sat_state.timestamp,
            "satellite": sat_state.model_dump(),
            "environment": env_state.model_dump(),
            "channel": channel_state.model_dump() if channel_state else None,
            "qkd": qkd_metrics.model_dump(),
            "control": {
                "current": ctrl_action.model_dump(),
                "delta": ctrl_delta.model_dump(),
                "mode": control_service.active_mode
            },
            "ai_agents": multi_agent.model_dump() if multi_agent else None,
            "alerts": [a.model_dump() for a in active_alerts]
        }
        return packet

    async def broadcast_telemetry(self):
        """Continuous background task stepping simulation and broadcasting live frames."""
        while self.is_running:
            try:
                if self.active_connections:
                    # Step simulation & control
                    control_service.step_control()
                    satellite_service.step(dt=1.0)
                    environment_service.step(dt=1.0)

                    packet = self.build_telemetry_packet()
                    payload_text = json.dumps(packet)

                    # Send to all connected clients
                    stale_sockets = []
                    for connection in self.active_connections:
                        try:
                            await connection.send_text(payload_text)
                        except Exception:
                            stale_sockets.append(connection)

                    for stale in stale_sockets:
                        self.disconnect(stale)

                await asyncio.sleep(self.stream_interval_s)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Error in WebSocket broadcast loop: %s", exc)
                await asyncio.sleep(1.0)


# Global singleton instance
ws_manager = ConnectionManager()
