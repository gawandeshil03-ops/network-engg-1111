# Industrial IoT Operations Intelligence — V2

This V2 extends the original Network Monitor Dashboard into an industrial IoT systems-engineering project. The original Flask + SQLite network dashboard remains intact; V2 runs as a separate service so the migration can be reviewed safely before replacing the legacy entry point.

## What V2 adds

- REST API for connected-device registration and telemetry ingestion
- Single-event and batch telemetry endpoints
- MQTT ingestion through Eclipse Mosquitto
- PostgreSQL persistence in Docker, with SQLite fallback for simple local development
- Industrial telemetry fields: temperature, vibration, RPM, battery voltage, signal strength, latency and packet loss
- Rule-based anomaly detection and alert generation
- Optional LLM-assisted incident summaries only after an anomaly becomes an alert
- Preserved network probing using the original DNS / ping / TCP checker
- Fleet analytics dashboard
- Configurable IoT device simulator
- Concurrent API load-testing utility
- Docker Compose stack and automated tests

## Architecture

```text
Simulated / real IoT devices
        |
        | MQTT telemetry
        v
    Mosquitto
        |
        v
  MQTT ingestion worker -----> REST API <----- other clients / integrations
                                  |
                                  v
                              PostgreSQL
                                  |
                    +-------------+-------------+
                    |                           |
              Fleet analytics             Rule engine
                                                |
                                                v
                                              Alerts
                                                |
                                   optional AI incident summary
```

The system deliberately does **not** send every telemetry event to an LLM. High-volume telemetry is stored and filtered first; AI is used only for meaningful incident-level analysis.

## Quick start with Docker

Requirements: Docker Desktop with Docker Compose.

Start PostgreSQL, Mosquitto, the V2 API and MQTT ingestion worker:

```bash
docker compose -f docker-compose.iot.yml up --build
```

Open the V2 dashboard:

```text
http://localhost:8000
```

Start the same stack plus 50 simulated excavators publishing every 10 seconds:

```bash
docker compose -f docker-compose.iot.yml --profile demo up --build
```

Stop the stack:

```bash
docker compose -f docker-compose.iot.yml down
```

To remove the PostgreSQL demo data as well:

```bash
docker compose -f docker-compose.iot.yml down -v
```

## REST API

Health check:

```bash
curl http://localhost:8000/api/v1/health
```

Create a device:

```bash
curl -X POST http://localhost:8000/api/v1/devices \
  -H "Content-Type: application/json" \
  -d '{"name":"Excavator-001","device_type":"excavator","location":"Mine Site A"}'
```

Send telemetry:

```bash
curl -X POST http://localhost:8000/api/v1/telemetry \
  -H "Content-Type: application/json" \
  -d '{"device_id":1,"temperature":74.2,"vibration":2.8,"engine_rpm":2100,"battery_voltage":24.6,"signal_strength":-76,"latency_ms":41,"packet_loss":0.4,"status":"running"}'
```

Create an abnormal event to verify alert generation:

```bash
curl -X POST http://localhost:8000/api/v1/telemetry \
  -H "Content-Type: application/json" \
  -d '{"device_id":1,"temperature":99,"vibration":9,"signal_strength":-103,"packet_loss":25,"status":"running"}'
```

View open alerts:

```bash
curl "http://localhost:8000/api/v1/alerts?open_only=true"
```

View fleet analytics:

```bash
curl http://localhost:8000/api/v1/analytics/fleet
```

## Network monitoring retained in V2

A V2 device can also contain a host and optional TCP port:

```bash
curl -X POST http://localhost:8000/api/v1/devices \
  -H "Content-Type: application/json" \
  -d '{"name":"Public Web Endpoint","device_type":"gateway","host":"google.com","port":443}'
```

Run the original DNS, ping, latency, packet-loss and TCP-port probe through V2:

```bash
curl -X POST http://localhost:8000/api/v1/devices/1/probe
```

The resulting latency and packet-loss values are stored as telemetry, so network health becomes part of the same operational data model as IoT sensor data.

## MQTT

The ingestion worker subscribes to:

```text
devices/+/telemetry
```

A typical MQTT payload is:

```json
{
  "device_id": 1,
  "temperature": 73.4,
  "vibration": 2.1,
  "engine_rpm": 2180,
  "battery_voltage": 24.5,
  "signal_strength": -78,
  "latency_ms": 46,
  "packet_loss": 0.6,
  "status": "running"
}
```

## Device simulator

Outside Docker, after installing `requirements-v2.txt` and starting an MQTT broker:

```bash
python simulator.py --count 100 --interval 10
```

For 500 devices publishing every 10 seconds, the simulated fleet produces an average of about 50 telemetry messages per second.

```bash
python simulator.py --count 500 --interval 10
```

## REST API load test

The included asynchronous load test sends many telemetry requests concurrently and reports throughput, average response latency and P95 latency.

```bash
python load_test.py --requests 1000 --concurrency 50
```

Increase the request count only after confirming the local Docker stack is stable.

## Optional AI incident summaries

The platform works without an AI key. Without one, the endpoint returns a deterministic local incident summary.

To enable the optional LLM path, set `OPENAI_API_KEY` in your shell before starting Docker. The model can be changed with `OPENAI_MODEL`.

Generate a summary for an existing alert:

```bash
curl -X POST http://localhost:8000/api/v1/alerts/1/ai-summary
```

Only alert data is sent for AI summarisation; the continuous telemetry stream is not sent to the model.

## Tests

Install V2 dependencies and run both the legacy and V2 test suites:

```bash
pip install -r requirements-v2.txt
pytest -q
```

GitHub Actions also runs the test suite for the V2 branch and pull requests.

## Main V2 endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/health` | service/database status |
| GET | `/api/v1/devices` | list devices |
| POST | `/api/v1/devices` | register a connected device |
| POST | `/api/v1/telemetry` | ingest one telemetry event |
| POST | `/api/v1/telemetry/batch` | ingest up to 5,000 events |
| GET | `/api/v1/devices/{id}/telemetry` | device history |
| POST | `/api/v1/devices/{id}/probe` | DNS/ping/TCP network probe |
| GET | `/api/v1/analytics/fleet` | fleet-level operational metrics |
| GET | `/api/v1/alerts` | operational alerts |
| POST | `/api/v1/alerts/{id}/acknowledge` | acknowledge an alert |
| POST | `/api/v1/alerts/{id}/ai-summary` | optional AI incident analysis |

## V2 files

- `iot_app.py` — V2 REST API and dashboard service
- `iot_db.py` — PostgreSQL/SQLAlchemy data layer
- `anomaly.py` — telemetry anomaly rules
- `ai_incident.py` — optional AI incident summarisation
- `mqtt_ingest.py` — MQTT-to-REST ingestion worker
- `simulator.py` — configurable IoT fleet simulator
- `load_test.py` — concurrent REST API performance test
- `Dockerfile.iot` — V2 application image
- `docker-compose.iot.yml` — PostgreSQL + Mosquitto + API + worker + optional simulator
- `templates/iot_dashboard.html` — V2 operations dashboard
- `tests/test_iot_app.py` — V2 functional tests
