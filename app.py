from __future__ import annotations

import ipaddress
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

from flask import Flask, jsonify, redirect, render_template, request, url_for

import db
from monitor import check_target

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

HOST_PATTERN = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$|^localhost$")


def valid_host(value: str) -> bool:
    value = value.strip()
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return bool(HOST_PATTERN.fullmatch(value))


def parse_port(value: str) -> Optional[int]:
    value = value.strip()
    if not value:
        return None
    port = int(value)
    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535.")
    return port


@app.before_request
def ensure_database() -> None:
    db.init_db()


@app.get("/")
def index():
    return render_template("index.html", targets=db.list_targets())


@app.post("/targets")
def create_target():
    name = request.form.get("name", "").strip()
    host = request.form.get("host", "").strip()
    port_text = request.form.get("port", "").strip()

    if not name or not host or not valid_host(host):
        return "Please provide a name and a valid hostname/IP address.", 400

    try:
        port = parse_port(port_text)
    except ValueError as exc:
        return str(exc), 400

    db.add_target(name=name[:80], host=host[:253], port=port)
    return redirect(url_for("index"))


@app.post("/targets/<int:target_id>/delete")
def remove_target(target_id: int):
    db.delete_target(target_id)
    return redirect(url_for("index"))


@app.get("/api/status")
def api_status():
    targets = db.list_targets()
    if not targets:
        return jsonify({"targets": []})

    results: list[dict] = []
    workers = min(8, len(targets))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(check_target, target["host"], target["port"]): target
            for target in targets
        }
        for future in as_completed(future_map):
            target = future_map[future]
            try:
                check = future.result().to_dict()
            except Exception as exc:
                check = {
                    "online": False,
                    "latency_ms": None,
                    "packet_loss": None,
                    "dns_ip": None,
                    "port_open": None,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                    "error": f"Unexpected check error: {exc}",
                }

            db.save_measurement(target["id"], check)
            results.append(
                {
                    **target,
                    **check,
                    "uptime_percent": db.uptime_percent(target["id"]),
                }
            )

    results.sort(key=lambda item: item["id"])
    return jsonify({"targets": results})


@app.get("/api/history/<int:target_id>")
def api_history(target_id: int):
    requested_limit = request.args.get("limit", default=60, type=int)
    limit = min(max(requested_limit or 60, 10), 200)
    return jsonify({"target_id": target_id, "history": db.history(target_id, limit=limit)})


if __name__ == "__main__":
    db.init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
