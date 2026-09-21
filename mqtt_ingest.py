from __future__ import annotations

import json
import os
import time

import paho.mqtt.client as mqtt
import requests

BROKER = os.getenv("MQTT_BROKER", "localhost")
PORT = int(os.getenv("MQTT_PORT", "1883"))
TOPIC = os.getenv("MQTT_TOPIC", "devices/+/telemetry")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"Connected to MQTT broker {BROKER}:{PORT}; subscribing to {TOPIC}")
        client.subscribe(TOPIC, qos=1)
    else:
        print(f"MQTT connection failed: {reason_code}")


def on_message(client, userdata, message):
    try:
        payload = json.loads(message.payload.decode("utf-8"))
        payload["source"] = "mqtt"
        response = requests.post(f"{API_BASE_URL}/api/v1/telemetry", json=payload, timeout=5)
        response.raise_for_status()
        print(f"Ingested {message.topic}: {response.json()}")
    except Exception as exc:
        print(f"Failed to ingest {message.topic}: {exc}")


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"iot-ingestor-{int(time.time())}")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT, keepalive=60)
    client.loop_forever()


if __name__ == "__main__":
    main()
