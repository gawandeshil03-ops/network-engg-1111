from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import iot_app
import iot_db
from monitor import CheckResult


def make_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'iot-test.db'}")
    iot_db._engine = None
    iot_db._engine_url = None
    return iot_app.app.test_client()


def test_health_and_dashboard(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    assert client.get("/").status_code == 200
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_device_telemetry_and_alert_flow(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    created = client.post("/api/v1/devices", json={
        "name": "Excavator-001", "device_type": "excavator", "location": "Test Site"
    })
    assert created.status_code == 201
    device_id = created.get_json()["device"]["id"]

    ingested = client.post("/api/v1/telemetry", json={
        "device_id": device_id,
        "temperature": 99.0,
        "vibration": 2.0,
        "signal_strength": -75,
        "latency_ms": 32,
        "packet_loss": 0.2,
        "status": "running",
    })
    assert ingested.status_code == 202
    assert ingested.get_json()["alert_ids"]

    history = client.get(f"/api/v1/devices/{device_id}/telemetry")
    assert len(history.get_json()["telemetry"]) == 1

    alerts = client.get("/api/v1/alerts?open_only=true").get_json()["alerts"]
    assert alerts[0]["code"] == "HIGH_TEMPERATURE"

    summary = client.post(f"/api/v1/alerts/{alerts[0]['id']}/ai-summary")
    assert summary.status_code == 200
    assert summary.get_json()["analysis"]["summary"]

    acknowledged = client.post(f"/api/v1/alerts/{alerts[0]['id']}/acknowledge")
    assert acknowledged.status_code == 200


def test_batch_and_fleet_analytics(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    device_id = client.post("/api/v1/devices", json={"name": "Sensor-001"}).get_json()["device"]["id"]
    response = client.post("/api/v1/telemetry/batch", json={"events": [
        {"device_id": device_id, "temperature": 70, "signal_strength": -70},
        {"device_id": device_id, "temperature": 71, "signal_strength": -72},
    ]})
    assert response.status_code == 202
    assert response.get_json()["accepted"] == 2
    metrics = client.get("/api/v1/analytics/fleet").get_json()
    assert metrics["devices"] == 1
    assert metrics["telemetry_events"] == 2


def test_network_probe_is_preserved(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    device_id = client.post("/api/v1/devices", json={
        "name": "Gateway", "device_type": "gateway", "host": "example.com", "port": 443
    }).get_json()["device"]["id"]

    monkeypatch.setattr(iot_app, "check_target", lambda host, port: CheckResult(
        online=True, latency_ms=18.5, packet_loss=0.0, dns_ip="127.0.0.1",
        port_open=True, checked_at="2026-09-09T00:00:00+00:00", error=None))
    response = client.post(f"/api/v1/devices/{device_id}/probe")
    assert response.status_code == 200
    assert response.get_json()["probe"]["latency_ms"] == 18.5
