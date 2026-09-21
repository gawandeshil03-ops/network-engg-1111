from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
import requests


def register_devices(api_base: str, count: int) -> list[dict]:
    existing = requests.get(f"{api_base}/api/v1/devices", timeout=10).json()["devices"]
    by_name = {item["name"]: item for item in existing}
    registered = []
    for index in range(1, count + 1):
        name = f"Excavator-{index:03d}"
        if name in by_name:
            registered.append(by_name[name])
            continue
        response = requests.post(
            f"{api_base}/api/v1/devices",
            json={"name": name, "device_type": "excavator", "location": "Simulated Mine Site"},
            timeout=10,
        )
        response.raise_for_status()
        registered.append(response.json()["device"])
    return registered


def telemetry_for(device_id: int) -> dict:
    temperature = random.gauss(72, 7)
    vibration = max(0, random.gauss(2.5, 1.2))
    packet_loss = max(0, random.gauss(1.0, 1.5))
    signal = random.gauss(-76, 8)

    if random.random() < 0.015:
        temperature += random.uniform(20, 35)
    if random.random() < 0.015:
        vibration += random.uniform(5, 9)
    if random.random() < 0.01:
        packet_loss += random.uniform(10, 35)
    if random.random() < 0.01:
        signal -= random.uniform(15, 30)

    return {
        "device_id": device_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature": round(temperature, 2),
        "vibration": round(vibration, 2),
        "engine_rpm": round(random.gauss(2100, 220), 1),
        "battery_voltage": round(random.gauss(24.5, 1.1), 2),
        "signal_strength": round(signal, 1),
        "latency_ms": round(max(2, random.gauss(45, 18)), 1),
        "packet_loss": round(min(100, packet_loss), 2),
        "status": "running",
    }


def main():
    parser = argparse.ArgumentParser(description="Publish simulated industrial IoT telemetry over MQTT.")
    parser.add_argument("--count", type=int, default=25, help="number of devices")
    parser.add_argument("--interval", type=float, default=10.0, help="seconds between fleet cycles")
    parser.add_argument("--cycles", type=int, default=0, help="0 means run continuously")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--broker", default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    args = parser.parse_args()

    devices = register_devices(args.api.rstrip("/"), args.count)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(args.broker, args.port, keepalive=60)
    client.loop_start()

    cycle = 0
    try:
        while args.cycles == 0 or cycle < args.cycles:
            started = time.perf_counter()
            for device in devices:
                payload = telemetry_for(device["id"])
                client.publish(f"devices/{device['id']}/telemetry", json.dumps(payload), qos=1)
            cycle += 1
            elapsed = time.perf_counter() - started
            print(f"Published cycle {cycle}: {len(devices)} events in {elapsed:.3f}s")
            time.sleep(max(0, args.interval - elapsed))
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
