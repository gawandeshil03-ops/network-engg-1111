from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "network_monitor.db"
SCHEMA = BASE_DIR / "schema.sql"


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with connect() as connection:
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        count = connection.execute("SELECT COUNT(*) FROM targets").fetchone()[0]
        if count == 0:
            connection.executemany(
                "INSERT INTO targets (name, host, port) VALUES (?, ?, ?)",
                [
                    ("Router", "192.168.1.1", None),
                    ("Google", "google.com", 443),
                    ("Cloudflare DNS", "1.1.1.1", 53),
                ],
            )


def list_targets() -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT id, name, host, port, created_at FROM targets ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


def add_target(name: str, host: str, port: Optional[int]) -> int:
    with connect() as connection:
        cursor = connection.execute(
            "INSERT INTO targets (name, host, port) VALUES (?, ?, ?)",
            (name, host, port),
        )
        return int(cursor.lastrowid)


def delete_target(target_id: int) -> None:
    with connect() as connection:
        connection.execute("DELETE FROM targets WHERE id = ?", (target_id,))


def save_measurement(target_id: int, result: dict) -> None:
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO measurements
                (target_id, online, latency_ms, packet_loss, dns_ip, port_open, checked_at, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                target_id,
                int(bool(result["online"])),
                result["latency_ms"],
                result["packet_loss"],
                result["dns_ip"],
                None if result["port_open"] is None else int(bool(result["port_open"])),
                result["checked_at"],
                result["error"],
            ),
        )


def history(target_id: int, limit: int = 30) -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT online, latency_ms, packet_loss, dns_ip, port_open, checked_at, error
            FROM measurements
            WHERE target_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (target_id, limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def uptime_percent(target_id: int, limit: int = 100) -> Optional[float]:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total, COALESCE(SUM(online), 0) AS online_count
            FROM (
                SELECT online FROM measurements
                WHERE target_id = ?
                ORDER BY id DESC
                LIMIT ?
            )
            """,
            (target_id, limit),
        ).fetchone()
    if not row or row["total"] == 0:
        return None
    return round((row["online_count"] / row["total"]) * 100, 1)
