from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import time
from datetime import datetime, timezone

import httpx


async def ensure_device(client: httpx.AsyncClient, api: str) -> int:
    response = await client.get(f"{api}/api/v1/devices")
    response.raise_for_status()
    for device in response.json()["devices"]:
        if device["name"] == "API-Load-Test-Sensor":
            return int(device["id"])
    response = await client.post(
        f"{api}/api/v1/devices",
        json={"name": "API-Load-Test-Sensor", "device_type": "load-test"},
    )
    response.raise_for_status()
    return int(response.json()["device"]["id"])


async def run_request(client, semaphore, api, device_id):
    payload = {
        "device_id": device_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature": random.uniform(60, 82),
        "vibration": random.uniform(1, 4),
        "signal_strength": random.uniform(-88, -65),
        "latency_ms": random.uniform(15, 90),
        "packet_loss": random.uniform(0, 3),
        "status": "running",
        "source": "load-test",
    }
    async with semaphore:
        started = time.perf_counter()
        try:
            response = await client.post(f"{api}/api/v1/telemetry", json=payload)
            ok = response.status_code == 202
        except httpx.HTTPError:
            ok = False
        return ok, (time.perf_counter() - started) * 1000


async def run(api: str, request_count: int, concurrency: int):
    timeout = httpx.Timeout(20.0)
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        device_id = await ensure_device(client, api)
        semaphore = asyncio.Semaphore(concurrency)
        started = time.perf_counter()
        results = await asyncio.gather(*(
            run_request(client, semaphore, api, device_id) for _ in range(request_count)
        ))
        elapsed = time.perf_counter() - started

    latencies = sorted(latency for _, latency in results)
    successful = sum(1 for ok, _ in results if ok)
    p95_index = max(0, int(len(latencies) * 0.95) - 1)
    print(f"Requests: {request_count}")
    print(f"Successful: {successful}")
    print(f"Elapsed: {elapsed:.2f}s")
    print(f"Throughput: {request_count / elapsed:.1f} req/s")
    print(f"Average latency: {statistics.mean(latencies):.1f} ms")
    print(f"P95 latency: {latencies[p95_index]:.1f} ms")


def main():
    parser = argparse.ArgumentParser(description="Concurrent REST API telemetry load test.")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=50)
    args = parser.parse_args()
    asyncio.run(run(args.api.rstrip("/"), args.requests, args.concurrency))


if __name__ == "__main__":
    main()
