from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import (Boolean, Column, DateTime, Float, ForeignKey, Integer, MetaData,
                        String, Table, Text, create_engine, func, insert, select, update)

BASE_DIR = Path(__file__).resolve().parent
metadata = MetaData()
_engine = None
_engine_url = None

devices = Table(
    "iot_devices", metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(80), nullable=False),
    Column("device_type", String(50), nullable=False, default="sensor"),
    Column("location", String(120)),
    Column("host", String(253)),
    Column("port", Integer),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

telemetry = Table(
    "iot_telemetry", metadata,
    Column("id", Integer, primary_key=True),
    Column("device_id", Integer, ForeignKey("iot_devices.id"), nullable=False, index=True),
    Column("timestamp", DateTime(timezone=True), nullable=False, index=True),
    Column("temperature", Float),
    Column("vibration", Float),
    Column("engine_rpm", Float),
    Column("battery_voltage", Float),
    Column("signal_strength", Float),
    Column("latency_ms", Float),
    Column("packet_loss", Float),
    Column("status", String(40)),
    Column("source", String(40), nullable=False, default="rest"),
)

alerts = Table(
    "iot_alerts", metadata,
    Column("id", Integer, primary_key=True),
    Column("device_id", Integer, ForeignKey("iot_devices.id"), nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("severity", String(20), nullable=False),
    Column("code", String(50), nullable=False),
    Column("message", Text, nullable=False),
    Column("acknowledged", Boolean, nullable=False, default=False),
)


def database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip() or f"sqlite:///{BASE_DIR / 'iot_operations.db'}"


def engine():
    global _engine, _engine_url
    url = database_url()
    if _engine is None or _engine_url != url:
        kwargs = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(url, future=True, **kwargs)
        _engine_url = url
    return _engine


def _dt(value=None):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _dict(row):
    result = dict(row)
    for key, value in result.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
    return result


def init_db() -> None:
    metadata.create_all(engine())


def add_device(name, device_type="sensor", location=None, host=None, port=None) -> int:
    with engine().begin() as connection:
        result = connection.execute(insert(devices).values(
            name=name[:80], device_type=(device_type or "sensor")[:50],
            location=location[:120] if location else None,
            host=host[:253] if host else None, port=port))
        return int(result.inserted_primary_key[0])


def list_devices() -> list[dict]:
    with engine().connect() as connection:
        rows = connection.execute(select(devices).order_by(devices.c.id)).mappings().all()
    return [_dict(row) for row in rows]


def get_device(device_id: int):
    with engine().connect() as connection:
        row = connection.execute(select(devices).where(devices.c.id == device_id)).mappings().first()
    return _dict(row) if row else None


def save_telemetry(payload: dict, source="rest") -> int:
    device_id = int(payload["device_id"])
    if not get_device(device_id):
        raise ValueError(f"Unknown device_id {device_id}")
    values = {
        "device_id": device_id,
        "timestamp": _dt(payload.get("timestamp")),
        "temperature": payload.get("temperature"),
        "vibration": payload.get("vibration"),
        "engine_rpm": payload.get("engine_rpm"),
        "battery_voltage": payload.get("battery_voltage"),
        "signal_strength": payload.get("signal_strength"),
        "latency_ms": payload.get("latency_ms"),
        "packet_loss": payload.get("packet_loss"),
        "status": payload.get("status"),
        "source": (payload.get("source") or source)[:40],
    }
    with engine().begin() as connection:
        result = connection.execute(insert(telemetry).values(**values))
        return int(result.inserted_primary_key[0])


def recent_telemetry(device_id: int, limit=100) -> list[dict]:
    statement = select(telemetry).where(telemetry.c.device_id == device_id).order_by(telemetry.c.id.desc()).limit(limit)
    with engine().connect() as connection:
        rows = connection.execute(statement).mappings().all()
    return [_dict(row) for row in reversed(rows)]


def add_alert(device_id: int, severity: str, code: str, message: str) -> int:
    with engine().begin() as connection:
        result = connection.execute(insert(alerts).values(
            device_id=device_id, severity=severity[:20], code=code[:50],
            message=message, acknowledged=False))
        return int(result.inserted_primary_key[0])


def list_alerts(limit=100, open_only=False) -> list[dict]:
    statement = select(
        alerts.c.id, alerts.c.device_id, devices.c.name.label("device_name"),
        alerts.c.created_at, alerts.c.severity, alerts.c.code,
        alerts.c.message, alerts.c.acknowledged,
    ).select_from(alerts.join(devices)).order_by(alerts.c.id.desc()).limit(limit)
    if open_only:
        statement = statement.where(alerts.c.acknowledged.is_(False))
    with engine().connect() as connection:
        rows = connection.execute(statement).mappings().all()
    return [_dict(row) for row in rows]


def get_alert(alert_id: int):
    statement = select(
        alerts.c.id, alerts.c.device_id, devices.c.name.label("device_name"),
        devices.c.device_type, alerts.c.severity, alerts.c.code, alerts.c.message,
    ).select_from(alerts.join(devices)).where(alerts.c.id == alert_id)
    with engine().connect() as connection:
        row = connection.execute(statement).mappings().first()
    return _dict(row) if row else None


def acknowledge_alert(alert_id: int) -> bool:
    with engine().begin() as connection:
        result = connection.execute(update(alerts).where(alerts.c.id == alert_id).values(acknowledged=True))
        return bool(result.rowcount)


def fleet_metrics() -> dict:
    minute_ago = datetime.now(timezone.utc) - timedelta(minutes=1)
    with engine().connect() as connection:
        device_count = connection.execute(select(func.count()).select_from(devices)).scalar_one()
        event_count = connection.execute(select(func.count()).select_from(telemetry)).scalar_one()
        open_alerts = connection.execute(select(func.count()).select_from(alerts).where(alerts.c.acknowledged.is_(False))).scalar_one()
        recent = connection.execute(select(func.count()).select_from(telemetry).where(telemetry.c.timestamp >= minute_ago)).scalar_one()
        signal = connection.execute(select(func.avg(telemetry.c.signal_strength))).scalar_one()
        latency = connection.execute(select(func.avg(telemetry.c.latency_ms))).scalar_one()
    return {
        "devices": int(device_count),
        "telemetry_events": int(event_count),
        "telemetry_last_minute": int(recent),
        "open_alerts": int(open_alerts),
        "average_signal_strength": round(float(signal), 1) if signal is not None else None,
        "average_latency_ms": round(float(latency), 1) if latency is not None else None,
    }
