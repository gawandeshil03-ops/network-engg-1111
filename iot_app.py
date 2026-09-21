from __future__ import annotations

from flask import Flask, jsonify, render_template, request

import iot_db
from ai_incident import summarize_incident
from anomaly import evaluate_telemetry
from monitor import check_target

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


def error(message: str, status=400):
    return jsonify({"error": message}), status


def ingest(payload: dict, source="rest") -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Telemetry payload must be a JSON object.")
    if "device_id" not in payload:
        raise ValueError("device_id is required.")
    telemetry_id = iot_db.save_telemetry(payload, source=source)
    alert_ids = []
    for finding in evaluate_telemetry(payload):
        alert_ids.append(iot_db.add_alert(
            int(payload["device_id"]), finding["severity"], finding["code"], finding["message"]))
    return {"telemetry_id": telemetry_id, "alert_ids": alert_ids}


@app.before_request
def ensure_database():
    iot_db.init_db()


@app.get("/")
def dashboard():
    return render_template("iot_dashboard.html")


@app.get("/api/v1/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "industrial-iot-operations-intelligence",
        "database": "postgresql" if iot_db.database_url().startswith("postgresql") else "sqlite-fallback",
    })


@app.get("/api/v1/devices")
def list_devices():
    return jsonify({"devices": iot_db.list_devices()})


@app.post("/api/v1/devices")
def create_device():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    if not name:
        return error("name is required.")
    port = payload.get("port")
    if port is not None:
        try:
            port = int(port)
            if not 1 <= port <= 65535:
                raise ValueError
        except (TypeError, ValueError):
            return error("port must be between 1 and 65535.")
    device_id = iot_db.add_device(
        name=name,
        device_type=str(payload.get("device_type") or "sensor"),
        location=str(payload["location"]) if payload.get("location") else None,
        host=str(payload["host"]) if payload.get("host") else None,
        port=port,
    )
    return jsonify({"device": iot_db.get_device(device_id)}), 201


@app.get("/api/v1/devices/<int:device_id>")
def get_device(device_id: int):
    device = iot_db.get_device(device_id)
    return jsonify({"device": device}) if device else error("device not found.", 404)


@app.post("/api/v1/telemetry")
def telemetry():
    payload = request.get_json(silent=True)
    if payload is None:
        return error("JSON body is required.")
    try:
        result = ingest(payload)
    except (TypeError, ValueError) as exc:
        return error(str(exc))
    return jsonify(result), 202


@app.post("/api/v1/telemetry/batch")
def telemetry_batch():
    payload = request.get_json(silent=True)
    events = payload.get("events") if isinstance(payload, dict) else payload
    if not isinstance(events, list) or not events:
        return error("Provide a non-empty list of telemetry events.")
    if len(events) > 5000:
        return error("A batch can contain at most 5000 events.")
    accepted, rejected = [], []
    for index, event in enumerate(events):
        try:
            accepted.append(ingest(event, source="rest-batch"))
        except (TypeError, ValueError) as exc:
            rejected.append({"index": index, "error": str(exc)})
    return jsonify({
        "accepted": len(accepted),
        "rejected": len(rejected),
        "results": accepted,
        "errors": rejected,
    }), 202


@app.get("/api/v1/devices/<int:device_id>/telemetry")
def device_telemetry(device_id: int):
    if not iot_db.get_device(device_id):
        return error("device not found.", 404)
    limit = min(max(request.args.get("limit", 100, type=int) or 100, 1), 1000)
    return jsonify({"device_id": device_id, "telemetry": iot_db.recent_telemetry(device_id, limit)})


@app.post("/api/v1/devices/<int:device_id>/probe")
def probe_device(device_id: int):
    device = iot_db.get_device(device_id)
    if not device:
        return error("device not found.", 404)
    if not device.get("host"):
        return error("device has no host configured for network probing.")
    result = check_target(device["host"], device.get("port")).to_dict()
    payload = {
        "device_id": device_id,
        "timestamp": result["checked_at"],
        "latency_ms": result["latency_ms"],
        "packet_loss": result["packet_loss"],
        "status": "online" if result["online"] else "offline",
        "source": "network_probe",
    }
    stored = ingest(payload, source="network_probe")
    return jsonify({"probe": result, **stored})


@app.get("/api/v1/analytics/fleet")
def fleet_analytics():
    return jsonify(iot_db.fleet_metrics())


@app.get("/api/v1/alerts")
def alerts():
    limit = min(max(request.args.get("limit", 100, type=int) or 100, 1), 500)
    open_only = request.args.get("open_only", "false").lower() in {"1", "true", "yes"}
    return jsonify({"alerts": iot_db.list_alerts(limit, open_only)})


@app.post("/api/v1/alerts/<int:alert_id>/acknowledge")
def acknowledge(alert_id: int):
    if not iot_db.acknowledge_alert(alert_id):
        return error("alert not found.", 404)
    return jsonify({"alert_id": alert_id, "acknowledged": True})


@app.post("/api/v1/alerts/<int:alert_id>/ai-summary")
def ai_summary(alert_id: int):
    alert = iot_db.get_alert(alert_id)
    if not alert:
        return error("alert not found.", 404)
    return jsonify({"alert_id": alert_id, "analysis": summarize_incident(alert)})


if __name__ == "__main__":
    iot_db.init_db()
    app.run(host="0.0.0.0", port=8000, debug=True)
