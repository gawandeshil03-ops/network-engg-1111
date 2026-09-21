# Small Business Network Monitor

A lightweight Python network-monitoring dashboard built with **Flask + SQLite + HTML/CSS/JavaScript**.

It is designed as a practical portfolio project that shows **networking, Python, dashboard development and troubleshooting** in one place.

## What it checks

For every device or host you add, the app can show:

- **Availability** — whether the host replies to ping
- **Latency** — average ping response time in milliseconds
- **Packet loss** — percentage of ping packets that do not return
- **DNS resolution** — the IP address returned for a hostname such as `google.com`
- **TCP port status** — whether one configured service port accepts a connection
- **Recent uptime** — percentage of successful checks from the latest stored measurements
- **History** — measurements saved in SQLite for later analysis
- **Latency over time chart** — a time-series view of response-time changes
- **Packet loss over time chart** — a time-series view of reliability changes

The dashboard automatically rechecks targets every 30 seconds while the page is open. Each completed check is saved to SQLite, then the selected target's latest measurements are redrawn in the two history charts.

## Performance history charts

The **Performance history** section lets you select any configured target and review up to the latest 60 stored checks.

The latency chart shows:

- latest latency
- average latency across the displayed history
- peak latency
- response-time trend over time

The packet-loss chart shows:

- latest packet loss
- average packet loss
- peak packet loss
- reliability trend on a fixed 0–100% scale

The charts are drawn with browser-native SVG and JavaScript, so no external charting library is required.

## Example use

A small office could add:

| Device | Host | Optional port | What it tells you |
|---|---|---:|---|
| Router | `192.168.1.1` | — | Is the gateway reachable? |
| NAS | `192.168.1.10` | `445` | Is the NAS online and is SMB reachable? |
| Printer | `192.168.1.20` | `9100` | Is the printer online and is its print service reachable? |
| Website | `google.com` | `443` | Do DNS, internet access and HTTPS connectivity work? |

> Local addresses such as `192.168.x.x` can only be checked when this app is running on a computer connected to that same network.

## How it works

```text
Browser Dashboard
       |
       v
Flask Web App
       |
       +--> DNS lookup (Python socket)
       +--> Ping test (system ping command)
       +--> TCP port check (Python socket)
       |
       v
SQLite Database
       |
       +--> targets
       +--> measurement history
       |
       v
History API
       |
       v
SVG time-series charts
```

## Run it on Windows / macOS / Linux

```bash
python -m venv .venv
```

Activate the environment:

**Windows PowerShell**

```powershell
.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
source .venv/bin/activate
```

Install packages and start the dashboard:

```bash
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

The SQLite database is created automatically on first run.

## Test it

```bash
pytest -q
```

## Project structure

```text
Network-Monitor-Dashboard/
├── app.py              # Flask routes, live-status API and history API
├── monitor.py          # ping, DNS and TCP checks
├── db.py               # SQLite operations
├── schema.sql          # database schema
├── templates/
│   └── index.html      # dashboard page and chart containers
├── static/
│   ├── app.js          # live refresh + SVG chart rendering
│   └── style.css       # responsive UI and chart styling
├── tests/
│   └── test_app.py
├── requirements.txt
└── README.md
```

## What I learned / demonstrated

- Python networking with `socket`
- ICMP-style reachability testing through the operating system `ping` utility
- TCP connectivity checks
- DNS troubleshooting
- Flask backend and JSON API development
- SQLite data storage and time-series history retrieval
- Frontend JavaScript for live dashboard updates
- SVG time-series data visualisation without an external chart dependency
- Turning raw network measurements into an interface useful for troubleshooting

## Good next upgrades

- Alert rules after repeated failures or high packet loss
- Email/Slack notifications
- SNMP monitoring for switches and routers
- Cisco device metrics and interface status
- Windows Server monitoring
- Export measurements to CSV
- Authentication for business use
- Docker deployment
