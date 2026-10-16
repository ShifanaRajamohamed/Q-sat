"""Tests for Q-SAT System Status and Health Endpoints."""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.config import settings

client = TestClient(app)


def test_system_status_endpoint():
    """Verify GET /api/system/status returns expected operational status and schema."""
    response = client.get("/api/system/status")
    assert response.status_code == 200
    data = response.json()

    assert data["system"] == "Q-SAT Adaptive Ground Station"
    assert data["status"] == "online"
    assert data["environment_mode"] in ["simulation", "mqtt"]
    assert data["version"] == "0.1.0"


def test_system_health_endpoint():
    """Verify GET /api/system/health returns detailed health, coordinates, and uptime."""
    response = client.get("/api/system/health")
    assert response.status_code == 200
    data = response.json()

    assert data["system"] == "Q-SAT Adaptive Ground Station"
    assert data["status"] == "online"
    assert "timestamp" in data
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] >= 0.0

    # Verify ground station telemetry configuration
    gs = data["ground_station"]
    assert gs["latitude"] == pytest.approx(settings.GROUND_STATION_LAT)
    assert gs["longitude"] == pytest.approx(settings.GROUND_STATION_LON)
    assert gs["altitude_m"] == pytest.approx(settings.GROUND_STATION_ALT)
    assert gs["min_elevation_deg"] == pytest.approx(settings.MIN_ELEVATION)


def test_root_endpoint():
    """Verify root navigation endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Welcome to Q-SAT Adaptive Ground Station" in data["message"]
    assert data["version"] == "0.1.0"
    assert data["docs"] == "/docs"
