from __future__ import annotations

import platform
import re
import socket
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class CheckResult:
    online: bool
    latency_ms: Optional[float]
    packet_loss: Optional[float]
    dns_ip: Optional[str]
    port_open: Optional[bool]
    checked_at: str
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def resolve_dns(host: str) -> tuple[Optional[str], Optional[str]]:
    """Resolve a host to an IP address."""
    try:
        return socket.gethostbyname(host), None
    except socket.gaierror as exc:
        return None, f"DNS resolution failed: {exc}"


def _ping_command(host: str, count: int, timeout_seconds: int) -> list[str]:
    system = platform.system().lower()
    if system == "windows":
        return ["ping", "-n", str(count), "-w", str(timeout_seconds * 1000), host]
    if system == "darwin":
        return ["ping", "-c", str(count), "-W", str(timeout_seconds * 1000), host]
    return ["ping", "-c", str(count), "-W", str(timeout_seconds), host]


def ping_host(host: str, count: int = 3, timeout_seconds: int = 1) -> tuple[bool, Optional[float], Optional[float], Optional[str]]:
    """Ping a host and return (online, avg_latency_ms, packet_loss_percent, error)."""
    try:
        completed = subprocess.run(
            _ping_command(host, count, timeout_seconds),
            capture_output=True,
            text=True,
            timeout=max(4, count * timeout_seconds + 2),
            check=False,
        )
    except FileNotFoundError:
        return False, None, None, "The system ping command was not found."
    except subprocess.TimeoutExpired:
        return False, None, 100.0, "Ping timed out."
    except OSError as exc:
        return False, None, None, f"Ping failed: {exc}"

    output = f"{completed.stdout}\n{completed.stderr}"
    system = platform.system().lower()
    packet_loss: Optional[float] = None
    latency_ms: Optional[float] = None

    if system == "windows":
        loss_match = re.search(r"\((\d+)%\s*loss\)", output, re.IGNORECASE)
        if loss_match:
            packet_loss = float(loss_match.group(1))
        avg_match = re.search(r"Average\s*=\s*(\d+)ms", output, re.IGNORECASE)
        if avg_match:
            latency_ms = float(avg_match.group(1))
    else:
        loss_match = re.search(r"([\d.]+)%\s*packet loss", output, re.IGNORECASE)
        if loss_match:
            packet_loss = float(loss_match.group(1))
        avg_match = re.search(r"(?:round-trip|rtt).*?=\s*[\d.]+/([\d.]+)/", output, re.IGNORECASE)
        if avg_match:
            latency_ms = float(avg_match.group(1))

    online = completed.returncode == 0 or (packet_loss is not None and packet_loss < 100.0)
    if online and packet_loss is None:
        packet_loss = 0.0

    error = None if online else "No ping response."
    return online, latency_ms, packet_loss, error


def check_tcp_port(host: str, port: Optional[int], timeout_seconds: float = 1.0) -> Optional[bool]:
    """Check one user-configured TCP port. Returns None when no port is configured."""
    if port is None:
        return None
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except (OSError, socket.timeout):
        return False


def check_target(host: str, port: Optional[int] = None) -> CheckResult:
    """Run DNS, ping and an optional single-port TCP check for one configured target."""
    checked_at = datetime.now(timezone.utc).isoformat()
    dns_ip, dns_error = resolve_dns(host)
    online, latency_ms, packet_loss, ping_error = ping_host(host)
    port_open = check_tcp_port(host, port)

    errors = [message for message in (dns_error, ping_error) if message]
    return CheckResult(
        online=online,
        latency_ms=latency_ms,
        packet_loss=packet_loss,
        dns_ip=dns_ip,
        port_open=port_open,
        checked_at=checked_at,
        error=" | ".join(errors) if errors else None,
    )
