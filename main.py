#!/usr/bin/env python3
import time
import sys
from datetime import datetime
import os
import yaml
from db import init_schema, get_db
from collector import run_collector
from normalizer import normalize_raw_data, store_normalized, test_normalizer
from scorer import compute_score
from alerter import check_and_alert

DB_PATH = 'hardware_alerts.db'
LOG_FILE = 'logs/main.log'

import signal
import fcntl

PID_FILE = 'hardware_alerts.pid'

class Daemon:
    def __init__(self, pid_file):
        self.pid_file = pid_file

    def daemonize(self):
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError as e:
            sys.stderr.write(f"Fork #1 failed: {e}")
            sys.exit(1)

        os.chdir('/')
        os.setsid()
        os.umask(0)

        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError as e:
            sys.stderr.write(f"Fork #2 failed: {e}")
            sys.exit(1)

        sys.stdout.flush()
        sys.stderr.flush()

        si = open(os.devnull, 'r')
        so = open(LOG_FILE, 'a+')
        se = open(os.devnull, 'a+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        with open(self.pid_file, 'w') as f:
            f.write(str(os.getpid()))

    def already_running(self):
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return True
        except:
            return False

def log(msg):
    timestamp = datetime.now().isoformat()
    timestamp = datetime.now().isoformat()
    print(f"[{timestamp}] {msg}")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {msg}\\n")

def run_cycle(cycle_num):
    log(f"🌐 Cycle #{cycle_num}")
    errors = 0
    
    try:
        # 1. Collect raw data
        log("1. Collector...")
        collector_ok = run_collector()
        if not collector_ok:
            errors += 1
    except Exception as e:
        log(f"❌ Collector failed: {str(e)}")
        errors += 1
    
    try:
        # 2. Normalize new raw → products
        log("2. Normalizer...")
        test_normalizer(hours_back=1)  # only recent
    except Exception as e:
        log(f"❌ Normalizer failed: {str(e)}")
        errors += 1
    
    try:
        # 3. Score products (implicit in alerter)
        log("3. Scoring...")
    except Exception as e:
        log(f"❌ Scoring failed: {str(e)}")
        errors += 1
    
    try:
        # 4. Alerts
        log("4. Alerter...")
        alerted = check_and_alert()
        if alerted:
            log("🚨 Alerts sent!")
    except Exception as e:
        log(f"❌ Alerter failed: {str(e)}")
        errors += 1
    
    log(f"✅ Cycle #{cycle_num} complete ({errors} errors)")

def signal_handler(signum, frame):
    log('🛑 Received signal, shutting down gracefully')
    os.unlink(PID_FILE)
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def main():
    os.makedirs('logs', exist_ok=True)
    init_schema()
    
    log("🚀 AI Hardware Alert System starting...")
    
    # Test run
    log("🧪 Initial test cycle...")
    run_cycle(0)
    
        consecutive_fails = 0
    cycle_num = 1
    while True:
        try:
            run_cycle(cycle_num)
            consecutive_fails = 0
            cycle_num += 1
            time.sleep(60)
        except KeyboardInterrupt:
            log("🛑 Interrupted")
            break
        except Exception as e:
            consecutive_fails += 1
            log(f"❌ Cycle fail #{consecutive_fails}: {str(e)}")
            if consecutive_fails >= 3:
                log("🔴 WATCHDOG: 3 fails - pausing 1h")
                time.sleep(3600)
                consecutive_fails = 0
            else:
                time.sleep(10)

    log("Shutdown")

if __name__ == '__main__':
    daemon = Daemon(PID_FILE)
    if daemon.already_running():
        log('Already running, exiting')
        sys.exit(1)
    daemon.daemonize()

    main()
