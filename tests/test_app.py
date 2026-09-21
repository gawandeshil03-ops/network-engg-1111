from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as app_module
import db
from monitor import CheckResult


def test_home_page(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE", tmp_path / "test.db")
    db.init_db()
    client = app_module.app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"Small Business Network Monitor" in response.data
    assert b"Latency over time" in response.data
    assert b"Packet loss over time" in response.data


def test_add_target(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE", tmp_path / "test.db")
    db.init_db()
    client = app_module.app.test_client()
    response = client.post(
        "/targets",
        data={"name": "NAS", "host": "192.168.1.10", "port": "445"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert any(t["name"] == "NAS" for t in db.list_targets())


def test_status_api(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE", tmp_path / "test.db")
    db.init_db()

    def fake_check(host, port):
        return CheckResult(
            online=True,
            latency_ms=12.5,
            packet_loss=0.0,
            dns_ip="127.0.0.1",
            port_open=True if port else None,
            checked_at="2026-01-01T00:00:00+00:00",
            error=None,
        )

    monkeypatch.setattr(app_module, "check_target", fake_check)
    client = app_module.app.test_client()
    response = client.get("/api/status")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["targets"]
    assert all(item["online"] is True for item in payload["targets"])


def test_history_api_returns_measurements(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE", tmp_path / "test.db")
    db.init_db()
    target_id = db.list_targets()[0]["id"]
    db.save_measurement(
        target_id,
        {
            "online": True,
            "latency_ms": 8.4,
            "packet_loss": 0.0,
            "dns_ip": "192.168.1.1",
            "port_open": None,
            "checked_at": "2026-01-01T00:00:00+00:00",
            "error": None,
        },
    )

    client = app_module.app.test_client()
    response = client.get(f"/api/history/{target_id}?limit=60")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["target_id"] == target_id
    assert len(payload["history"]) == 1
    assert payload["history"][0]["latency_ms"] == 8.4
    assert payload["history"][0]["packet_loss"] == 0.0
