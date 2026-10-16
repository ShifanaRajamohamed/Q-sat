"""Unit and integration tests for WebSocket telemetry streaming and Alert management."""

import json
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_websocket_telemetry_stream():
    """Verify WebSocket /ws/live connects and streams structured telemetry frames."""
    with client.websocket_connect("/ws/live") as websocket:
        # Receive initial telemetry snapshot
        data_text = websocket.receive_text()
        data = json.loads(data_text)

        assert "satellite" in data
        assert "environment" in data
        assert "qkd" in data
        assert "control" in data
        assert "ai_agents" in data
        assert "alerts" in data

        # Check subfields
        assert "elevation_deg" in data["satellite"]
        assert "qber" in data["qkd"]
        assert "secret_key_rate" in data["qkd"]
        assert "transmission_power_pct" in data["control"]["current"]


def test_api_alerts():
    """Verify GET /api/alerts returns active list of system alerts."""
    response = client.get("/api/alerts")
    assert response.status_code == 200
    alerts = response.json()
    assert isinstance(alerts, list)
    for alert in alerts:
        assert "id" in alert
        assert "severity" in alert
        assert "category" in alert
        assert "title" in alert


def test_api_experiments_catalog():
    """Verify GET /api/experiments and /api/experiments/metrics."""
    res_exp = client.get("/api/experiments")
    assert res_exp.status_code == 200
    assert isinstance(res_exp.json(), list)

    res_met = client.get("/api/experiments/metrics")
    assert res_met.status_code == 200
    assert "benchmark_scenarios" in res_met.json()


def test_api_simulation_clock_controls():
    """Verify GET /api/simulation/status, POST /start, POST /stop."""
    res_status = client.get("/api/simulation/status")
    assert res_status.status_code == 200
    assert "is_running" in res_status.json()

    res_stop = client.post("/api/simulation/stop")
    assert res_stop.status_code == 200
    assert res_stop.json()["is_running"] is False

    res_start = client.post("/api/simulation/start")
    assert res_start.status_code == 200
    assert res_start.json()["is_running"] is True
