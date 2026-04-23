# AI Hardware Availability Intelligence System

Minimal viable system to monitor AI hardware (SBCs/GPUs) availability/pricing and alert on high-value opportunities via Telegram.

## Setup
1. `cd hardware-alerts`
2. `python3 -m venv venv`
3. `source venv/bin/activate`
4. `pip install -r requirements.txt`
5. Edit `config/sources.yaml` and `config/products.yaml`
6. Add Telegram bot token to config
7. Run daemon: `./run_daemon.sh` (or `nohup ./venv/bin/python main.py &`)

## Components
- Collector: Fetches raw data
- Normalizer: Structures data
- Scorer: 0-20 opportunity score
- Alerter: Telegram notifications

Runs on Raspberry Pi 5, SQLite only, no Docker/frameworks.\n\n## Daemon Mode\n- Uses PID file to prevent duplicates\n- Daemonizes (forks to background)\n- Graceful SIGTERM/SIGINT shutdown\n- Logs to `logs/main.log`\n\nStop: `kill $(cat hardware_alerts.pid)` or `pkill -f hardware_alerts`\n\n## Stability\n- Per-module error isolation\n- WAL DB mode for concurrency\n- Throttled fetches (2-3s/domain)\n- 6h alert cooldown per SKU\n- Resource light: <50MB RAM expected
