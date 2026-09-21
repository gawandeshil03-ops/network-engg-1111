from __future__ import annotations


def _number(payload: dict, key: str):
    value = payload.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def evaluate_telemetry(payload: dict) -> list[dict]:
    findings = []
    temperature = _number(payload, "temperature")
    vibration = _number(payload, "vibration")
    packet_loss = _number(payload, "packet_loss")
    signal_strength = _number(payload, "signal_strength")

    if temperature is not None and temperature >= 95:
        findings.append({"severity": "critical", "code": "HIGH_TEMPERATURE", "message": f"Temperature reached {temperature:.1f} C."})
    elif temperature is not None and temperature >= 85:
        findings.append({"severity": "warning", "code": "ELEVATED_TEMPERATURE", "message": f"Temperature reached {temperature:.1f} C."})

    if vibration is not None and vibration >= 8:
        findings.append({"severity": "critical", "code": "HIGH_VIBRATION", "message": f"Vibration reached {vibration:.2f} mm/s."})
    elif vibration is not None and vibration >= 5:
        findings.append({"severity": "warning", "code": "ELEVATED_VIBRATION", "message": f"Vibration reached {vibration:.2f} mm/s."})

    if packet_loss is not None and packet_loss >= 20:
        findings.append({"severity": "critical", "code": "HIGH_PACKET_LOSS", "message": f"Packet loss reached {packet_loss:.1f}%."})
    elif packet_loss is not None and packet_loss >= 5:
        findings.append({"severity": "warning", "code": "PACKET_LOSS", "message": f"Packet loss reached {packet_loss:.1f}%."})

    if signal_strength is not None and signal_strength <= -100:
        findings.append({"severity": "critical", "code": "WEAK_SIGNAL", "message": f"Signal strength dropped to {signal_strength:.0f} dBm."})
    elif signal_strength is not None and signal_strength <= -90:
        findings.append({"severity": "warning", "code": "DEGRADED_SIGNAL", "message": f"Signal strength dropped to {signal_strength:.0f} dBm."})

    return findings
